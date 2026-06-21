from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import traceback
import shutil
import uuid
from contextlib import asynccontextmanager

from database.db import (
    init_db,
    close_pool,
    register_or_get_user,
    get_all_lessons,
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
    get_random_practice_question
)

from utils.ai_service import transcribe_voice, get_ai_response, generate_voice

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
AUDIO_DIR = os.path.join(STATIC_DIR, "audio")

ADMIN_IDS = [377424247, 696767499]


# ====================== LIFESPAN ======================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Запуск Talk2Learn...")
    os.makedirs(AUDIO_DIR, exist_ok=True)
    await init_db()
    yield
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
        row = await get_random_practice_question(user_id, level, task_type)
        if not row:
            return {"error": "no_more_questions"}

        return {
            "question_id": row["id"],
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
async def admin_lessons():
    try:
        rows = await get_all_lessons()
        return [
            {
                "id": r["id"],
                "level": r["level"],
                "title": r["title"],
                "type": r["content_type"]
            } for r in rows
        ]
    except Exception as e:
        traceback.print_exc()
        return []


@app.get("/api/admin/lessons_for_questions")
async def admin_lessons_for_questions():
    try:
        rows = await get_all_lessons()
        return [
            {
                "id": r["id"],
                "level": r["level"],
                "title": r["title"]
            } for r in rows
        ]
    except Exception as e:
        traceback.print_exc()
        return []


@app.post("/api/admin/add_lesson")
async def admin_add_lesson(data: AddLessonRequest):
    try:
        await add_lesson(
            level=data.level,
            title=data.title,
            lesson_text=data.lesson_text,
            content_type=data.content_type
        )
        return {"status": "success", "message": "Урок добавлен"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.delete("/api/admin/delete_lesson/{lesson_id}")
async def admin_delete_lesson(lesson_id: int):
    try:
        await delete_lesson(lesson_id)
        return {"status": "success", "message": f"Урок {lesson_id} скрыт"}
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
async def web_club_text(user_id: int = Form(...), text: str = Form(...), level: str = Form("A1")):
    try:
        ai_response = await get_ai_response(text, user_level=level)
        session_id = f"ai_{user_id}_{uuid.uuid4().hex[:6]}"
        output_path = os.path.join(AUDIO_DIR, f"{session_id}.mp3")
        await generate_voice(ai_response, output_path)

        return {
            "user_text": text,
            "ai_text": ai_response,
            "audio_url": f"/static/audio/{session_id}.mp3"
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/web-club/voice")
async def web_club_voice(user_id: int = Form(...), file: UploadFile = File(...), level: str = Form("A1")):
    try:
        temp_path = os.path.join(AUDIO_DIR, f"user_{user_id}_{uuid.uuid4().hex[:6]}.wav")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        user_text = await transcribe_voice(temp_path)
        if os.path.exists(temp_path):
            os.remove(temp_path)

        if not user_text.strip():
            return {"user_text": "", "ai_text": "I couldn't hear you. Please try again!", "audio_url": ""}

        ai_response = await get_ai_response(user_text, user_level=level)
        session_id = f"ai_{user_id}_{uuid.uuid4().hex[:6]}"
        output_path = os.path.join(AUDIO_DIR, f"{session_id}.mp3")
        await generate_voice(ai_response, output_path)

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

# ====================== СТАТИКА ======================
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
@app.get("/index.html")
async def serve_home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/admin")
async def serve_admin():
    return FileResponse(os.path.join(STATIC_DIR, "admin.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)