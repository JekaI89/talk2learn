from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import asyncio
import time
import traceback
import shutil
import uuid
import random
import string
import hashlib
import hmac
from pathlib import Path
from contextlib import asynccontextmanager

from database.db import (
    init_db,
    close_pool,
    register_or_get_user,
    get_all_lessons,
    get_lesson_by_id,
    update_lesson,
    get_admin_statistics,
    add_lesson,
    delete_lesson,
    add_question,
    save_user_progress,
    update_user_streak,
    update_user_status,
    check_is_admin,
    get_user_level,
    add_word_to_user_dict,
    get_user_words,
    get_random_practice_question,
    get_next_uncompleted_lesson,
    get_lesson_progress,
    get_vocab_topics,
    get_vocab_cards,
    add_vocab_card,
    update_vocab_card,
    delete_vocab_card,
    get_all_vocab_cards_admin,
    complete_onboarding,
    get_onboarding_status,
    update_word_status,
    get_user_category_stats,
    get_user_languages,
    update_user_languages,
    LANG_NAMES_EN,
)

from utils.ai_service import transcribe_voice, get_ai_response, generate_voice, translate_word

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
AUDIO_DIR = os.path.join(STATIC_DIR, "audio")

ADMIN_IDS = [377424247, 696767499]


# ====================== BOT (фоновая задача) ======================
async def start_telegram_bot():
    """Запускает Telegram-бота как фоновую asyncio-задачу внутри webapp."""
    bot_token = os.environ.get("BOT_TOKEN", "")
    if not bot_token:
        print("⚠️ BOT_TOKEN не задан — Telegram-бот не запущен")
        return
    try:
        from aiogram import Bot, Dispatcher
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from handlers import menu, speaking_club

        bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()
        dp.include_router(menu.router)
        dp.include_router(speaking_club.router)
        print("🤖 Telegram-бот запущен (polling)...")
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    except asyncio.CancelledError:
        print("🤖 Telegram-бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка Telegram-бота: {e}")


# ====================== AUDIO CLEANUP ======================
async def audio_cleanup_loop():
    """Удаляет аудиофайлы старше 1 часа каждые 30 минут."""
    while True:
        try:
            await asyncio.sleep(1800)  # 30 минут
            now = time.time()
            cleaned = 0
            for f in Path(AUDIO_DIR).glob("*.mp3"):
                if now - f.stat().st_mtime > 3600:  # старше 1 часа
                    f.unlink()
                    cleaned += 1
            if cleaned:
                print(f"🧹 Аудиоочистка: удалено {cleaned} файлов")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ Ошибка очистки аудио: {e}")


# ====================== LIFESPAN ======================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Запуск Talk2Learn...")
    os.makedirs(AUDIO_DIR, exist_ok=True)
    await init_db()

    # Запускаем бота и очистку аудио как фоновые задачи
    bot_task = asyncio.create_task(start_telegram_bot())
    cleanup_task = asyncio.create_task(audio_cleanup_loop())

    yield

    bot_task.cancel()
    cleanup_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        pass
    await close_pool()
    print("🛑 Остановка Talk2Learn...")


app = FastAPI(lifespan=lifespan)


# ====================== МОДЕЛИ ======================
class AnswerCheckRequest(BaseModel):
    user_id: int
    queue_item_id: int
    is_correct: bool


class AddLessonRequest(BaseModel):
    level: str
    title: str
    lesson_text: str = ""
    content_type: str = "lesson"
    order_num: int = 0
    language: str = "en"


class UpdateLessonRequest(BaseModel):
    id: int
    level: str
    title: str
    lesson_text: str = ""
    content_type: str = "lesson"
    order_num: int = 0
    language: str = "en"


class RegisterUserRequest(BaseModel):
    user_id: int
    name: str = ""
    username: str = ""


class ProgressRequest(BaseModel):
    user_id: int
    content_type: str
    content_id: int


class ManageUserRequest(BaseModel):
    tg_id: str
    action: str


class AddQuestionRequest(BaseModel):
    lesson_id: int
    level: str
    task_type: str
    question_text: str
    option_1: str = ""
    option_2: str = ""
    option_3: str = ""
    correct_option: int = 1

class AddWordRequest(BaseModel):
    user_id: int
    word: str
    translation: str
    transcription: str = ""
    context_example: str = ""


class QuickAddWordRequest(BaseModel):
    user_id: int
    word: str
    context_sentence: str = ""
    native_language: str = "ru"
    target_language: str = "en"


class OnboardingRequest(BaseModel):
    user_id: int
    level: str
    goal: str = ""
    native_language: str = "ru"
    target_language: str = "en"


class UserLanguagesRequest(BaseModel):
    user_id: int
    native_language: str
    target_language: str


class WordStatusRequest(BaseModel):
    user_id: int
    word: str
    status: str  # 'learning' | 'known'

# ====================== ДАШБОРД ======================
@app.get("/api/dashboard/{user_id}")
async def get_dashboard(user_id: int):
    try:
        from database.db import get_pool
        pool = await get_pool()
        async with pool.acquire() as db:
            user = await db.fetchrow(
                "SELECT level, xp, streak, is_admin FROM users WHERE user_id = $1", user_id
            )
        lessons = await get_all_lessons()
        is_admin = user_id in ADMIN_IDS or bool(user and user["is_admin"])
        return {
            "user": {
                "level": user["level"] if user else "A1",
                "xp": user["xp"] if user else 0,
                "streak": user["streak"] if user else 0,
                "is_admin": is_admin
            },
            "total_lessons": len(lessons),
            "available_levels": ["A1", "A2", "B1", "B2", "C1", "C2"]
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ====================== ПРОФИЛЬ ======================
@app.get("/api/profile/{user_id}")
async def get_profile(user_id: int):
    try:
        from database.db import get_pool
        pool = await get_pool()
        async with pool.acquire() as db:
            user = await db.fetchrow("""
                SELECT level, xp, streak, is_premium, is_admin, name, username
                FROM users WHERE user_id = $1
            """, user_id)
            if not user:
                return {"level": "A1", "xp": 0, "streak": 0, "is_premium": False,
                        "is_admin": False, "name": "", "username": "",
                        "lessons_done": 0, "tasks_done": 0}

            row = await db.fetchrow("""
                SELECT COUNT(*) as cnt FROM user_progress
                WHERE user_id = $1 AND content_type IN ('lesson', 'grammar')
            """, user_id)
            lessons_done = row["cnt"]

            row = await db.fetchrow("""
                SELECT COUNT(*) as cnt FROM user_progress
                WHERE user_id = $1 AND content_type IN ('practice', 'speaking', 'question')
            """, user_id)
            tasks_done = row["cnt"]

        is_admin = user_id in ADMIN_IDS or bool(user["is_admin"])
        cat_stats = await get_user_category_stats(user_id)
        return {
            "name": user["name"] or "",
            "username": user["username"] or "",
            "level": user["level"],
            "xp": user["xp"],
            "streak": user["streak"],
            "is_premium": bool(user["is_premium"]),
            "is_admin": is_admin,
            "lessons_done": lessons_done,
            "tasks_done": tasks_done,
            "category_stats": cat_stats,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ====================== УРОКИ ======================
@app.get("/api/lessons/{level}")
async def get_lessons_by_level(level: str, user_id: Optional[int] = Query(None)):
    try:
        lessons = await get_all_lessons()
        filtered = [l for l in lessons if l["level"] == level]

        return [
            {
                "id": l["id"],
                "title": l["title"],
                "type": l["content_type"],
                "completed": False
            } for l in filtered
        ]
    except Exception as e:
        traceback.print_exc()
        return []


@app.get("/api/lessons/next/{level}")
async def get_next_lesson(level: str, user_id: int = Query(...),
                          content_type: Optional[str] = Query(None)):
    try:
        langs = await get_user_languages(user_id)
        row = await get_next_uncompleted_lesson(
            user_id, level, content_type, language=langs["target"]
        )
        progress = await get_lesson_progress(user_id, level, content_type)

        if not row:
            return {"completed": True, "progress": progress}

        return {
            "completed": False,
            "id": row["id"],
            "title": row["title"],
            "lesson_text": row["lesson_text"] or "",
            "type": row["content_type"],
            "progress": progress
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, "Ошибка загрузки урока")


@app.get("/api/lesson/{lesson_id}")
async def get_lesson(lesson_id: int):
    try:
        from database.db import get_pool
        pool = await get_pool()
        async with pool.acquire() as db:
            row = await db.fetchrow("""
                SELECT id, title, lesson_text, content_type
                FROM lessons WHERE id = $1 AND is_active = TRUE
            """, lesson_id)

        if not row:
            raise HTTPException(404, "Урок не найден")

        return {
            "id": row["id"],
            "title": row["title"],
            "lesson_text": row["lesson_text"] or "",
            "type": row["content_type"]
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, "Ошибка загрузки урока")


# ====================== ПРОГРЕСС ======================
@app.post("/api/progress/complete")
async def complete_content(data: ProgressRequest):
    try:
        result = await save_user_progress(data.user_id, data.content_type, data.content_id)
        await update_user_streak(data.user_id)
        return {
            "status": "success",
            "xp_earned": result["xp_earned"],
            "message": "Баллы зачислены" if result["status"] == "success" else "Уже пройдено ранее"
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ====================== ПРАКТИКА ======================
@app.get("/api/random_question")
async def random_question(
    user_id: int = Query(...),
    level: str = Query("A1"),
    task_type: str = Query("multiple_choice", alias="type")
):
    try:
        langs = await get_user_languages(user_id)
        row = await get_random_practice_question(user_id, level, task_type, language=langs["target"])
        if not row:
            return {"error": "no_more_questions"}

        if task_type == "sentence_builder":
            import random as _random
            correct_sentence = row["option_1"] or ""
            distractors = [w.strip() for w in (row["option_2"] or "").split(",") if w.strip()]
            word_bank = correct_sentence.split() + distractors
            _random.shuffle(word_bank)
            return {
                "question_id": row["id"],
                "task_type": "sentence_builder",
                "question": row["question_text"],
                "correct_sentence": correct_sentence,
                "word_bank": word_bank,
            }

        return {
            "question_id": row["id"],
            "task_type": "multiple_choice",
            "question": row["question_text"],
            "options": [row["option_1"], row["option_2"], row["option_3"]],
            "correct_option": row["correct_option"]
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": "server_error"}


@app.post("/api/check_answer")
async def check_answer(data: AnswerCheckRequest):
    try:
        # XP и прогресс по верному ответу уже сохраняются через /api/progress/complete
        # (фронтенд вызывает submitProgress('practice', ...) до этого запроса).
        # Этот эндпоинт просто подтверждает приём результата для фронтенда.
        return {"status": "success", "is_correct": data.is_correct}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ====================== РЕГИСТРАЦИЯ ======================
@app.post("/api/register_user")
async def register_user(data: RegisterUserRequest):
    try:
        level = await register_or_get_user(data.user_id, data.name, data.username)
        return {"status": "success", "level": level}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ====================== АДМИНКА ======================
@app.get("/api/admin/stats")
async def admin_stats():
    try:
        return await get_admin_statistics()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/admin/lessons")
async def admin_lessons(language: Optional[str] = Query(None)):
    try:
        rows = await get_all_lessons(language=language)
        return [
            {
                "id": r["id"],
                "level": r["level"],
                "title": r["title"],
                "type": r["content_type"],
                "language": r.get("language", "en"),
                "order_num": r.get("order_num", 0),
                "lesson_text": r.get("lesson_text", "")
            } for r in rows
        ]
    except Exception as e:
        traceback.print_exc()
        return []


@app.get("/api/admin/lessons_for_questions")
async def admin_lessons_for_questions():
    try:
        rows = await get_all_lessons()
        return [{"id": r["id"], "level": r["level"], "title": r["title"]} for r in rows]
    except Exception as e:
        traceback.print_exc()
        return []


@app.get("/api/admin/lesson/{lesson_id}")
async def admin_get_lesson(lesson_id: int):
    try:
        row = await get_lesson_by_id(lesson_id)
        if not row:
            raise HTTPException(404, "Урок не найден")
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/admin/add_lesson")
async def admin_add_lesson(data: AddLessonRequest):
    try:
        lesson_id = await add_lesson(
            level=data.level, title=data.title, lesson_text=data.lesson_text,
            content_type=data.content_type, order_num=data.order_num, language=data.language
        )
        return {"status": "success", "id": lesson_id, "message": "Урок добавлен"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.put("/api/admin/update_lesson")
async def admin_update_lesson(data: UpdateLessonRequest):
    try:
        await update_lesson(
            lesson_id=data.id, title=data.title, lesson_text=data.lesson_text,
            level=data.level, content_type=data.content_type,
            order_num=data.order_num, language=data.language
        )
        return {"status": "success", "message": "Урок обновлён"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.delete("/api/admin/delete_lesson/{lesson_id}")
async def admin_delete_lesson(lesson_id: int):
    try:
        await delete_lesson(lesson_id)
        return {"status": "success", "message": f"Урок {lesson_id} удалён"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/admin/add_question")
async def admin_add_question(data: AddQuestionRequest):
    try:
        await add_question(
            lesson_id=data.lesson_id,
            level=data.level,
            task_type=data.task_type,
            question_text=data.question_text,
            option_1=data.option_1,
            option_2=data.option_2,
            option_3=data.option_3,
            correct_option=data.correct_option,
        )
        return {"status": "success", "message": "Вопрос добавлен"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/admin/manage_user")
async def admin_manage_user(data: ManageUserRequest):
    try:
        user_id = int(data.tg_id.lstrip("@"))
    except ValueError:
        raise HTTPException(400, "Некорректный ID пользователя")

    action_map = {
        "grant_premium": ("is_premium", True),
        "revoke_premium": ("is_premium", False),
        "grant_admin": ("is_admin", True),
        "revoke_admin": ("is_admin", False),
    }

    if data.action not in action_map:
        raise HTTPException(400, "Неизвестное действие")

    field, value = action_map[data.action]
    try:
        await update_user_status(user_id, field, value)
        return {"status": "success"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ====================== SPEAKING CLUB ======================
@app.post("/api/web-club/text")
async def web_club_text(
    user_id: int = Form(...),
    text: str = Form(...),
    level: str = Form("A1"),
    situation: str = Form(""),
    native_language: str = Form("ru"),
    target_language: str = Form("en")
):
    try:
        ai_response = await get_ai_response(
            text, user_level=level, situation=situation,
            target_lang=target_language, native_lang=native_language
        )
        session_id = f"ai_{user_id}_{uuid.uuid4().hex[:6]}"
        output_path = os.path.join(AUDIO_DIR, f"{session_id}.mp3")
        await generate_voice(ai_response, output_path, target_lang=target_language)
        return {
            "user_text": text,
            "ai_text": ai_response,
            "audio_url": f"/static/audio/{session_id}.mp3"
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/web-club/voice")
async def web_club_voice(
    user_id: int = Form(...),
    file: UploadFile = File(...),
    level: str = Form("A1"),
    situation: str = Form(""),
    native_language: str = Form("ru"),
    target_language: str = Form("en")
):
    try:
        temp_path = os.path.join(AUDIO_DIR, f"user_{user_id}_{uuid.uuid4().hex[:6]}.wav")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        user_text = await transcribe_voice(temp_path, target_lang=target_language)
        if os.path.exists(temp_path):
            os.remove(temp_path)

        if not user_text.strip():
            return {"user_text": "", "ai_text": "I couldn't hear you. Please try again!", "audio_url": ""}

        ai_response = await get_ai_response(
            user_text, user_level=level, situation=situation,
            target_lang=target_language, native_lang=native_language
        )
        session_id = f"ai_{user_id}_{uuid.uuid4().hex[:6]}"
        output_path = os.path.join(AUDIO_DIR, f"{session_id}.mp3")
        await generate_voice(ai_response, output_path, target_lang=target_language)

        return {
            "user_text": user_text,
            "ai_text": ai_response,
            "audio_url": f"/static/audio/{session_id}.mp3"
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))

# ====================== СЛОВАРЬ ======================

@app.get("/api/dictionary/{user_id}")
async def get_dictionary(user_id: int):
    try:
        words = await get_user_words(user_id)
        return [
            {
                "word": w["word"],
                "translation": w["translation"],
                "transcription": w["transcription"] or "",
                "context_example": w["context_example"] or "",
                "status": w["status"]
            }
            for w in words
        ]
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, "Ошибка получения словаря")


@app.post("/api/dictionary/add")
async def add_word(data: AddWordRequest):
    try:
        success = await add_word_to_user_dict(
            user_id=data.user_id,
            word=data.word,
            translation=data.translation,
            transcription=data.transcription,
            context=data.context_example
        )
        if success:
            return {"status": "success", "message": "Слово добавлено в словарь"}
        return {"status": "error", "message": "Не удалось добавить слово"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/dictionary/quick_add")
async def quick_add_word(data: QuickAddWordRequest):
    """Перевод слова через AI + сохранение в личный словарь пользователя."""
    try:
        word_clean = data.word.strip()
        if not word_clean:
            raise HTTPException(400, "Пустое слово")

        translated = await translate_word(word_clean, context=data.context_sentence)

        if not translated["translation"]:
            return {"status": "error", "message": "Не удалось получить перевод, попробуйте ещё раз"}

        success = await add_word_to_user_dict(
            user_id=data.user_id,
            word=word_clean,
            translation=translated["translation"],
            transcription=translated["transcription"],
            context=translated["example"] or data.context_sentence
        )

        if not success:
            return {"status": "error", "message": "Не удалось добавить слово"}

        return {
            "status": "success",
            "word": word_clean,
            "translation": translated["translation"],
            "transcription": translated["transcription"],
            "context_example": translated["example"]
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/dictionary/translate")
async def translate_word_only(data: QuickAddWordRequest):
    try:
        word_clean = data.word.strip()
        if not word_clean:
            raise HTTPException(400, "Пустое слово")
        # Если языки не переданы — берём из БД
        if data.user_id > 0 and (data.native_language == "ru" and data.target_language == "en"):
            try:
                langs = await get_user_languages(data.user_id)
                native = langs["native"]
                target = langs["target"]
            except Exception:
                native, target = data.native_language, data.target_language
        else:
            native, target = data.native_language, data.target_language

        translated = await translate_word(
            word_clean, context=data.context_sentence,
            native_lang=native, target_lang=target
        )
        if not translated["translation"]:
            return {"status": "error", "message": "Не удалось получить перевод"}
        return {
            "status": "success",
            "word": word_clean,
            "translation": translated["translation"],
            "transcription": translated["transcription"],
            "context_example": translated["example"]
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))

@app.get("/api/tts/word")
async def tts_word(word: str = Query(...)):
    """Синтез речи для одного слова через gTTS. Возвращает MP3."""
    try:
        session_id = f"word_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(AUDIO_DIR, f"{session_id}.mp3")
        await generate_voice(word, output_path)
        return FileResponse(
            output_path,
            media_type="audio/mpeg",
            headers={"Cache-Control": "public, max-age=3600"}
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ====================== VOCABULARY CARDS ======================

class VocabCardCreate(BaseModel):
    topic: str
    level: str = "A1"
    word: str
    translation: str
    emoji_code: str
    definition: str = ""
    order_num: int = 0

class VocabCardUpdate(VocabCardCreate):
    id: int


@app.get("/api/vocab/topics")
async def vocab_topics(level: Optional[str] = Query(None)):
    """Список тем с кол-вом карточек (для главного экрана раздела Словарь)."""
    try:
        rows = await get_vocab_topics(level)
        return [dict(r) for r in rows]
    except Exception as e:
        traceback.print_exc()
        return []


@app.get("/api/vocab/cards")
async def vocab_cards(topic: str = Query(...), level: Optional[str] = Query(None)):
    """Все карточки темы."""
    try:
        rows = await get_vocab_cards(topic, level)
        return [dict(r) for r in rows]
    except Exception as e:
        traceback.print_exc()
        return []


@app.get("/api/admin/vocab")
async def admin_vocab_all():
    """Все карточки для таблицы в админке."""
    try:
        rows = await get_all_vocab_cards_admin()
        return [dict(r) for r in rows]
    except Exception as e:
        traceback.print_exc()
        return []


@app.post("/api/admin/vocab/add")
async def admin_vocab_add(data: VocabCardCreate):
    try:
        card_id = await add_vocab_card(
            topic=data.topic, level=data.level, word=data.word,
            translation=data.translation, emoji_code=data.emoji_code,
            definition=data.definition, order_num=data.order_num
        )
        return {"status": "success", "id": card_id}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.put("/api/admin/vocab/update")
async def admin_vocab_update(data: VocabCardUpdate):
    try:
        await update_vocab_card(
            card_id=data.id, topic=data.topic, level=data.level,
            word=data.word, translation=data.translation,
            emoji_code=data.emoji_code, definition=data.definition
        )
        return {"status": "success"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.delete("/api/admin/vocab/delete/{card_id}")
async def admin_vocab_delete(card_id: int):
    try:
        await delete_vocab_card(card_id)
        return {"status": "success"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ====================== ОНБОРДИНГ ======================

@app.get("/api/onboarding/{user_id}")
async def check_onboarding(user_id: int):
    try:
        done = await get_onboarding_status(user_id)
        return {"onboarding_done": done}
    except Exception as e:
        traceback.print_exc()
        return {"onboarding_done": False}


@app.post("/api/onboarding/complete")
async def finish_onboarding(data: OnboardingRequest):
    try:
        await complete_onboarding(
            data.user_id, data.level, data.goal,
            data.native_language, data.target_language
        )
        return {"status": "success"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.get("/api/user/languages/{user_id}")
async def get_languages(user_id: int):
    try:
        return await get_user_languages(user_id)
    except Exception as e:
        traceback.print_exc()
        return {"native": "ru", "target": "en"}


@app.post("/api/user/languages")
async def set_languages(data: UserLanguagesRequest):
    try:
        await update_user_languages(data.user_id, data.native_language, data.target_language)
        return {"status": "success"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ====================== СТАТУС СЛОВА ======================

@app.post("/api/dictionary/status")
async def set_word_status(data: WordStatusRequest):
    try:
        if data.status not in ("learning", "known"):
            raise HTTPException(400, "status должен быть 'learning' или 'known'")
        await update_word_status(data.user_id, data.word, data.status)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ====================== СТАТИСТИКА ПО КАТЕГОРИЯМ ======================

@app.get("/api/stats/categories/{user_id}")
async def category_stats(user_id: int):
    try:
        return await get_user_category_stats(user_id)
    except Exception as e:
        traceback.print_exc()
        return {}


# ====================== АВТОРИЗАЦИЯ: EMAIL (тестовый режим) ======================
#
# Коды хранятся в памяти процесса — после рестарта сервера сбрасываются.
# В продакшене замените на Redis или таблицу в БД + реальную отправку писем.
#
# Структура: { "user@example.com": {"code": "123456", "expires_at": <unix_ts>} }

_email_codes: dict[str, dict] = {}

CODE_TTL_SECONDS = 600  # код живёт 10 минут


class EmailCodeRequest(BaseModel):
    email: str


class EmailVerifyRequest(BaseModel):
    email: str
    code: str


@app.post("/api/auth/email/request-code")
async def email_request_code(data: EmailCodeRequest):
    """
    Генерирует 6-значный одноразовый код и печатает его в логи сервера.
    В продакшене здесь нужно отправлять письмо через SMTP / SendGrid / etc.
    """
    email = data.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Некорректный адрес электронной почты")

    code = "".join(random.choices(string.digits, k=6))
    _email_codes[email] = {
        "code": code,
        "expires_at": time.time() + CODE_TTL_SECONDS,
    }

    # --- ТЕСТОВЫЙ РЕЖИМ: код выводится в консоль сервера ---
    print(f"[AUTH] Код подтверждения для {email}: {code}  (действителен {CODE_TTL_SECONDS // 60} мин)")

    return {
        "status": "ok",
        "message": "Код отправлен. В тестовом режиме смотрите логи сервера.",
        "debug_hint": "Проверьте stdout/логи Render → вкладка Logs",
    }


@app.post("/api/auth/email/verify")
async def email_verify(data: EmailVerifyRequest):
    """
    Проверяет код. При успехе регистрирует пользователя (или возвращает
    существующего) через register_or_get_user() и возвращает его данные.
    """
    email = data.email.strip().lower()
    entry = _email_codes.get(email)

    if not entry:
        raise HTTPException(400, "Код не найден. Запросите новый.")

    if time.time() > entry["expires_at"]:
        del _email_codes[email]
        raise HTTPException(400, "Код устарел. Запросите новый.")

    if entry["code"] != data.code.strip():
        raise HTTPException(400, "Неверный код.")

    # Код верный — удаляем, чтобы нельзя было использовать повторно
    del _email_codes[email]

    # Синтетический числовой user_id из хэша email (без коллизий не гарантируем,
    # но для тестов достаточно; в продакшене храните email в таблице users).
    synthetic_user_id = int(hashlib.sha256(email.encode()).hexdigest(), 16) % (10 ** 12)

    level = await register_or_get_user(
        user_id=synthetic_user_id,
        name=email.split("@")[0],
        username=email,
    )

    return {
        "status": "ok",
        "user_id": synthetic_user_id,
        "email": email,
        "level": level,
    }


# ====================== АВТОРИЗАЦИЯ: TELEGRAM LOGIN WIDGET ======================
#
# Как это работает:
# 1. Фронтенд подключает официальный виджет:
#      <script async src="https://telegram.org/js/telegram-widget.js?22"
#              data-telegram-login="ВАШ_БОТ_USERNAME"
#              data-size="large"
#              data-onauth="onTelegramAuth(user)"
#              data-request-access="write">
#      </script>
# 2. После клика Telegram вызывает onTelegramAuth(user) с объектом:
#      { id, first_name, last_name, username, photo_url, auth_date, hash }
# 3. Фронтенд отправляет этот объект POST-запросом на /api/auth/telegram/verify
# 4. Бэкенд проверяет подпись (hash) и авторизует пользователя.
#
# Переменная окружения: TELEGRAM_BOT_TOKEN  (получить у @BotFather → /newbot → /mytoken)


class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int  # Unix-timestamp момента авторизации
    hash: str       # HMAC-подпись от Telegram


def _verify_telegram_hash(data: TelegramAuthData) -> bool:
    """
    Официальный алгоритм проверки подписи Telegram Login Widget:

    1. Берём все поля объекта КРОМЕ hash, строим строки вида "key=value",
       сортируем по алфавиту и объединяем через '\n'.
    2. Секретный ключ = SHA-256 от токена бота (не сам токен!).
    3. HMAC-SHA256(секретный_ключ, data_check_string) должен совпадать с hash.
    4. Дополнительно проверяем, что auth_date не старше 24 часов.

    Источник: https://core.telegram.org/widgets/login#checking-authorization
    """
    bot_token = os.environ.get("BOT_TOKEN", "") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        raise HTTPException(500, "BOT_TOKEN не задан на сервере")

    # Шаг 1 — строим data-check-string из всех полей кроме hash
    fields = {
        "id": str(data.id),
        "first_name": data.first_name,
        "auth_date": str(data.auth_date),
    }
    if data.last_name:
        fields["last_name"] = data.last_name
    if data.username:
        fields["username"] = data.username
    if data.photo_url:
        fields["photo_url"] = data.photo_url

    # Сортируем по имени ключа и склеиваем через \n
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))

    # Шаг 2 — секретный ключ = SHA-256(bot_token)
    secret_key = hashlib.sha256(bot_token.encode()).digest()

    # Шаг 3 — вычисляем ожидаемый хэш
    expected_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Шаг 4 — сравниваем безопасно (против timing-атак) и проверяем свежесть
    hash_valid = hmac.compare_digest(expected_hash, data.hash)
    time_valid = (time.time() - data.auth_date) < 86400  # не старше 24 часов

    return hash_valid and time_valid


@app.post("/api/auth/telegram/verify")
async def telegram_verify(data: TelegramAuthData):
    """
    Принимает объект от Telegram Login Widget, проверяет подпись
    и регистрирует / авторизует пользователя по его Telegram ID.

    Возвращает: { status, user_id, level, name, username }
    """
    if not _verify_telegram_hash(data):
        raise HTTPException(403, "Неверная подпись Telegram. Авторизация отклонена.")

    full_name = data.first_name
    if data.last_name:
        full_name += f" {data.last_name}"

    level = await register_or_get_user(
        user_id=data.id,
        name=full_name,
        username=data.username or "",
    )

    return {
        "status": "ok",
        "user_id": data.id,
        "name": full_name,
        "username": data.username or "",
        "photo_url": data.photo_url or "",
        "level": level,
    }


# ====================== СТАТИКА ======================
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
@app.get("/index.html")
async def serve_home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/admin")
async def serve_admin():
    return FileResponse(os.path.join(STATIC_DIR, "admin.html"))


# ====================== САЙТ (не мини-апп) ======================
SITE_DIR = os.path.join(STATIC_DIR, "site")

@app.get("/site")
@app.get("/site/")
@app.get("/site/app")
@app.get("/site/lessons")
@app.get("/site/dictionary")
@app.get("/site/word")
@app.get("/site/profile")
async def serve_site():
    return FileResponse(os.path.join(SITE_DIR, "app.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)