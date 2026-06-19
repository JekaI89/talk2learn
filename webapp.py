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
import aiosqlite

# Импорты для правильного Middleware (обход заглушки ngrok)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi import Request

from database.db import (
    init_db, register_or_get_user, get_all_lessons,
    get_next_queue_item, handle_answer_result, get_admin_statistics,
    add_lesson, update_user_streak, save_user_progress, update_user_status
)

from utils.ai_service import transcribe_voice, get_ai_response, generate_voice

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
AUDIO_DIR = os.path.join(STATIC_DIR, "audio")
DB_PATH = "bot_database.db"

# ====================== LIFESPAN (Инициализация) ======================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Запуск Talk2Learn... Проверка папок и БД")
    if not os.path.exists(AUDIO_DIR):
        os.makedirs(AUDIO_DIR)
    await init_db()
    yield
    print("🛑 Остановка Talk2Learn...")

# Инициализируем приложение ОДИН раз и передаем lifespan
app = FastAPI(lifespan=lifespan)

# ====================== MIDDLEWARE (Ngrok Bypass) ======================
class BypassNgrokMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        # Принудительно добавляем заголовок во ВСЕ ответы (включая статические HTML/JS файлы)
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

# Регистрируем миддлваре до подключения роутов и статики
app.add_middleware(BypassNgrokMiddleware)

# ====================== МОДЕЛИ ДАННЫХ ======================
class AnswerCheckRequest(BaseModel):
    user_id: int
    queue_item_id: int
    is_correct: bool

class AddLessonRequest(BaseModel):
    level: str
    title: str
    lesson_text: str = ""
    content_type: str = "theory"

class RegisterUserRequest(BaseModel):
    user_id: int
    name: str = ""
    username: str = ""

class ProgressRequest(BaseModel):  # <-- Новая модель для фиксации оценок
    user_id: int
    content_type: str  # 'lesson', 'grammar', 'practice'
    content_id: int

# ====================== ДАШБОРД ======================
ADMIN_IDS = [377424247, 696767499]

@app.get("/api/dashboard/{user_id}")
async def get_dashboard(user_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT level, xp, streak, is_admin FROM users WHERE user_id = ?", (user_id,)) as c:
                user = await c.fetchone()

            lessons = await get_all_lessons()

            is_admin = user_id in ADMIN_IDS or bool(user and user[3])

            return {
                "user": {
                    "level": user[0] if user else "A1",
                    "xp": user[1] if user else 0,
                    "streak": user[2] if user else 0,
                    "is_admin": is_admin
                },
                "total_lessons": len(lessons),
                "available_levels": ["A1", "A2", "B1", "B2", "C1", "C2"]
            }
    except Exception as e:
        raise HTTPException(500, str(e))

# ====================== ПРОФИЛЬ ======================
@app.get("/api/profile/{user_id}")
async def get_profile(user_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT level, xp, streak, is_premium, is_admin, name, username
                FROM users WHERE user_id = ?
            """, (user_id,)) as c:
                user = await c.fetchone()

            if not user:
                return {"level": "A1", "xp": 0, "streak": 0, "is_premium": False, "is_admin": False,
                        "name": "", "username": "", "lessons_done": 0, "tasks_done": 0}

            async with db.execute("""
                SELECT COUNT(*) FROM user_progress
                WHERE user_id = ? AND content_type IN ('lesson', 'grammar')
            """, (user_id,)) as c:
                lessons_done = (await c.fetchone())[0]

            async with db.execute("""
                SELECT COUNT(*) FROM user_progress
                WHERE user_id = ? AND content_type IN ('practice', 'speaking', 'question')
            """, (user_id,)) as c:
                tasks_done = (await c.fetchone())[0]

            is_admin = user_id in ADMIN_IDS or bool(user[4])

            return {
                "name": user[5] or "",
                "username": user[6] or "",
                "level": user[0],
                "xp": user[1],
                "streak": user[2],
                "is_premium": bool(user[3]),
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
    """Возвращает список уроков. При наличии user_id — добавляет флаг completed."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            if user_id:
                sql = """
                    SELECT l.id, l.title, l.content_type,
                           CASE WHEN up.id IS NOT NULL THEN 1 ELSE 0 END as completed
                    FROM lessons l
                    LEFT JOIN user_progress up 
                        ON up.content_id = l.id 
                       AND up.user_id = :user_id 
                       AND up.content_type = l.content_type
                    WHERE l.level = :level AND l.is_active = 1
                    ORDER BY l.order_num
                """
                params = {"user_id": user_id, "level": level}
            else:
                sql = """
                    SELECT id, title, content_type, 0 as completed
                    FROM lessons 
                    WHERE level = :level AND is_active = 1 
                    ORDER BY order_num
                """
                params = {"level": level}

            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()

            return [
                {
                    "id": r[0],
                    "title": r[1],
                    "type": r[2],
                    "completed": bool(r[3])
                } for r in rows
            ]
    except Exception as e:
        print("Ошибка в get_lessons_by_level:", e)
        return []

@app.get("/api/lesson/{lesson_id}")
async def get_lesson(lesson_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT id, title, lesson_text, content_type
                FROM lessons WHERE id = ?
            """, (lesson_id,)) as cursor:
                row = await cursor.fetchone()
                
            if not row:
                raise HTTPException(404, "Урок не найден")
                
            return {
                "id": row[0],
                "title": row[1],
                "lesson_text": row[2] or "",
                "type": row[3]
            }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, "Ошибка загрузки урока")

# ====================== ОЦЕНКИ И ПРОГРЕСС ======================
@app.post("/api/progress/complete")
async def complete_content(data: ProgressRequest):
    """Эндпоинт для начисления 5 баллов за уроки и 10 за тесты/практику"""
    try:
        # Сохраняем прогресс и высчитываем баллы внутри db.py
        result = await save_user_progress(data.user_id, data.content_type, data.content_id)
        
        # Обновляем ежедневный стрик активности пользователя
        await update_user_streak(data.user_id)
        
        return {
            "status": "success",
            "xp_earned": result["xp_earned"],
            "message": "Баллы зачислены" if result["status"] == "success" else "Уже пройдено ранее"
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Ошибка при сохранении оценок: {str(e)}")

# ====================== АДМИНКА ======================
@app.get("/api/admin/stats")
async def admin_stats():
    try:
        return await get_admin_statistics()
    except Exception as e:
        raise HTTPException(500, str(e))
@app.get("/api/admin/lessons_for_questions")
async def admin_lessons_for_questions():
    try:
        rows = await get_all_lessons()
        # Возвращаем упрощенный список для селекта вопросов
        return [{"id": r[0], "level": r[1], "title": r[2]} for r in rows]
    except:
        return []
    
@app.get("/api/admin/lessons")
async def admin_lessons():
    try:
        rows = await get_all_lessons()
        return [{"id": r[0], "level": r[1], "title": r[2], "type": r[3], "active": True} for r in rows]
    except:
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
        raise HTTPException(500, f"Ошибка: {str(e)}")

@app.delete("/api/admin/delete_lesson/{lesson_id}")
async def admin_delete_lesson(lesson_id: int):
    try:
        from database.db import delete_lesson
        await delete_lesson(lesson_id)
        return {"status": "success", "message": f"Урок {lesson_id} успешно удален"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Ошибка при удалении урока: {str(e)}")
      
# ====================== ЗАДАНИЯ И ВОПРОСЫ ======================
@app.get("/api/random_task")
async def get_random_task(user_id: int, type: str, level: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT id, title FROM lessons 
                WHERE level = ? 
                AND content_type = ?
                AND id NOT IN (
                    SELECT content_id FROM user_queue 
                    WHERE user_id = ? AND status = 'completed'
                )
                ORDER BY RANDOM() LIMIT 1
            """, (level, type, user_id)) as cursor:
                row = await cursor.fetchone()

            if not row:
                async with db.execute("""
                    SELECT id, title FROM lessons 
                    WHERE level = ? AND content_type = ?
                    ORDER BY RANDOM() LIMIT 1
                """, (level, type)) as cursor:
                    row = await cursor.fetchone()

            if not row:
                return {"error": "Нет доступных заданий"}

            return {
                "task_id": row[0],
                "title": row[1]
            }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))

@app.get("/api/random_question")
async def get_random_question(user_id: int, type: str, level: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT q.id, q.question_text, q.option_1, q.option_2, q.option_3, q.correct_option
                FROM questions q
                WHERE q.level = ? 
                  AND q.task_type = ?
                  AND q.id NOT IN (
                      SELECT content_id FROM user_progress 
                      WHERE user_id = ? AND content_type = 'question'
                  )
                ORDER BY RANDOM() 
                LIMIT 1
            """, (level, type, user_id)) as cursor:
                row = await cursor.fetchone()

            if not row:
                async with db.execute("""
                    SELECT id, question_text, option_1, option_2, option_3, correct_option
                    FROM questions 
                    WHERE level = ? AND task_type = ?
                    ORDER BY RANDOM() 
                    LIMIT 1
                """, (level, type)) as cursor:
                    row = await cursor.fetchone()

            if not row:
                return {"error": "Нет доступных вопросов для этого уровня и типа"}

            return {
                "question_id": row[0],
                "question": row[1],
                "options": [row[2], row[3], row[4]],
                "correct_option": row[5]
            }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))

# ====================== РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ ======================
@app.post("/api/register_user")
async def register_user(data: RegisterUserRequest):
    try:
        level = await register_or_get_user(data.user_id, data.name, data.username)
        return {"status": "success", "level": level}
    except Exception as e:
        raise HTTPException(500, str(e))

# ====================== SPEAKING CLUB В MINI APP ======================
@app.post("/api/web-club/text")
async def web_club_text(user_id: int = Form(...), text: str = Form(...), level: str = Form("A1")):
    try:
        ai_response = await get_ai_response(text, user_level=level)
        session_id = f"ai_{user_id}_{uuid.uuid4().hex[:6]}"
        output_audio_path = os.path.join(AUDIO_DIR, f"{session_id}.mp3")
        await generate_voice(ai_response, output_audio_path)
        
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
        temp_blob_path = os.path.join(AUDIO_DIR, f"user_{user_id}_{uuid.uuid4().hex[:6]}.wav")
        with open(temp_blob_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        user_text = await transcribe_voice(temp_blob_path)
        
        if os.path.exists(temp_blob_path):
            os.remove(temp_blob_path)
            
        if not user_text.strip():
            return {"user_text": "", "ai_text": "I couldn't hear you clearly. Please try again!", "audio_url": ""}

        ai_response = await get_ai_response(user_text, user_level=level)
        
        session_id = f"ai_{user_id}_{uuid.uuid4().hex[:6]}"
        output_audio_path = os.path.join(AUDIO_DIR, f"{session_id}.mp3")
        await generate_voice(ai_response, output_audio_path)
        
        return {
            "user_text": user_text,
            "ai_text": ai_response,
            "audio_url": f"/static/audio/{session_id}.mp3"
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))

# ====================== СТАТИЧЕСКИЕ ФАЙЛЫ И РОУТЫ СТРАНИЦ ======================
# Монтируем статику ОДИН раз в самом конце файла, чтобы она не перехватывала API-эндпоинты
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
@app.get("/index.html")
async def serve_home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/admin")
async def serve_admin():
    return FileResponse(os.path.join(STATIC_DIR, "admin.html"))

# ====================== ПРОВЕРКА ОТВЕТА (ОЧЕРЕДЬ) ======================
@app.post("/api/check_answer")
async def check_answer(data: AnswerCheckRequest):
    try:
        await handle_answer_result(data.user_id, data.queue_item_id, data.is_correct)
        return {"status": "success"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ====================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (АДМИНКА) ======================
class ManageUserRequest(BaseModel):
    tg_id: str
    action: str  # grant_premium | revoke_premium | grant_admin | revoke_admin

@app.post("/api/admin/manage_user")
async def admin_manage_user(data: ManageUserRequest):
    try:
        user_id = int(data.tg_id.lstrip("@"))
    except ValueError:
        raise HTTPException(400, "Некорректный ID пользователя")

    action_map = {
        "grant_premium":  ("is_premium", True),
        "revoke_premium": ("is_premium", False),
        "grant_admin":    ("is_admin",   True),
        "revoke_admin":   ("is_admin",   False),
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


# ====================== ДОБАВЛЕНИЕ ВОПРОСА (АДМИНКА) ======================
class AddQuestionRequest(BaseModel):
    lesson_id: int
    level: str
    task_type: str
    question_text: str
    option_1: str = ""
    option_2: str = ""
    option_3: str = ""
    correct_option: int = 1

@app.post("/api/admin/add_question")
async def admin_add_question(data: AddQuestionRequest):
    try:
        from database.db import add_question
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


if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Запуск FastAPI сервера на порту {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)