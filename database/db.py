import asyncpg
import os
from datetime import date, timedelta

# Render.com передаёт строку подключения через переменную окружения DATABASE_URL
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# asyncpg не понимает префикс postgres://, только postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Глобальный пул соединений — создаётся один раз при старте
_pool: asyncpg.Pool = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ==================== ИНИЦИАЛИЗАЦИЯ ====================

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                name TEXT,
                username TEXT,
                level TEXT DEFAULT 'A1',
                xp INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 0,
                last_activity_date TEXT,
                is_admin BOOLEAN DEFAULT FALSE,
                is_premium BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id SERIAL PRIMARY KEY,
                level TEXT NOT NULL,
                title TEXT NOT NULL,
                lesson_text TEXT,
                content_type TEXT DEFAULT 'lesson',
                order_num INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                lesson_id INTEGER REFERENCES lessons(id),
                level TEXT NOT NULL,
                task_type TEXT NOT NULL,
                question_text TEXT NOT NULL,
                option_1 TEXT,
                option_2 TEXT,
                option_3 TEXT,
                correct_option INTEGER,
                correct_answer TEXT,
                media_url TEXT,
                commentary TEXT,
                order_num INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                content_type TEXT,
                content_id INTEGER,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                xp_earned INTEGER DEFAULT 10
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_queue (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                content_type TEXT,
                content_id INTEGER,
                queue_order INTEGER,
                status TEXT DEFAULT 'pending'
            )
        """)

        # Индексы
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_progress_user
            ON user_progress(user_id, content_type)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_lessons_level
            ON lessons(level, is_active)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_level
            ON questions(level, task_type)
        """)

    print("✅ PostgreSQL: база данных инициализирована")


# ==================== ПОЛЬЗОВАТЕЛИ ====================

async def register_or_get_user(user_id: int, name: str = "", username: str = "") -> str:
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            INSERT INTO users (user_id, name, username, level)
            VALUES ($1, $2, $3, 'A1')
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, name, username)

        row = await db.fetchrow("SELECT level FROM users WHERE user_id = $1", user_id)
        return row["level"] if row else "A1"


async def get_user_level(user_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT level FROM users WHERE user_id = $1", user_id)
        return row["level"] if row else "A1"


async def update_user_streak(user_id: int):
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow(
            "SELECT last_activity_date, streak FROM users WHERE user_id = $1", user_id
        )
        if not row:
            return

        last_date = row["last_activity_date"]
        current_streak = row["streak"] or 0

        if last_date == today:
            return

        new_streak = current_streak + 1 if last_date == yesterday else 1

        await db.execute("""
            UPDATE users SET streak = $1, last_activity_date = $2 WHERE user_id = $3
        """, new_streak, today, user_id)


async def get_user_category_stats(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        stats = {}
        for content_type in ["lesson", "grammar", "practice", "speaking"]:
            row = await db.fetchrow("""
                SELECT COUNT(*) as cnt FROM user_progress
                WHERE user_id = $1 AND content_type = $2
            """, user_id, content_type)
            stats[content_type] = row["cnt"]
        return stats


# ==================== УРОКИ ====================

async def add_lesson(level: str, title: str, lesson_text: str = "",
                     content_type: str = "lesson", order_num: int = 0):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            INSERT INTO lessons (level, title, lesson_text, content_type, order_num)
            VALUES ($1, $2, $3, $4, $5)
        """, level, title, lesson_text, content_type, order_num)


async def get_all_lessons():
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("""
            SELECT id, level, title, content_type, order_num
            FROM lessons
            WHERE is_active = TRUE
            ORDER BY level, order_num, id
        """)
        return rows


async def delete_lesson(lesson_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE lessons SET is_active = FALSE WHERE id = $1", lesson_id)
    print(f"🗑️ Урок ID {lesson_id} переведён в статус неактивных")


# ==================== ВОПРОСЫ ====================

async def add_question(lesson_id: int, level: str, task_type: str, question_text: str,
                       option_1: str = "", option_2: str = "", option_3: str = "",
                       correct_option: int = 0, correct_answer: str = "",
                       media_url: str = "", commentary: str = "", order_num: int = 0):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            INSERT INTO questions
            (lesson_id, level, task_type, question_text, option_1, option_2, option_3,
             correct_option, correct_answer, media_url, commentary, order_num)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """, lesson_id, level, task_type, question_text,
            option_1, option_2, option_3, correct_option,
            correct_answer, media_url, commentary, order_num)


async def get_questions_by_level_and_type(level: str, task_type: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetch("""
            SELECT id, question_text, option_1, option_2, option_3,
                   correct_option, correct_answer, media_url
            FROM questions
            WHERE level = $1 AND task_type = $2
            ORDER BY order_num, id
        """, level, task_type)


# ==================== АДМИН ====================

async def get_admin_statistics():
    pool = await get_pool()
    async with pool.acquire() as db:
        stats = {}

        row = await db.fetchrow("SELECT COUNT(*) as cnt FROM users")
        stats["total_users"] = row["cnt"]

        row = await db.fetchrow("SELECT COUNT(*) as cnt FROM users WHERE is_premium = TRUE")
        stats["premium_users"] = row["cnt"]
        stats["free_users"] = stats["total_users"] - stats["premium_users"]

        stats["levels"] = {}
        for level in ["A1", "A2", "B1", "B2", "C1", "C2"]:
            row = await db.fetchrow(
                "SELECT COUNT(*) as cnt FROM lessons WHERE level = $1 AND is_active = TRUE",
                level
            )
            stats["levels"][level] = row["cnt"]

        return stats


async def update_user_status(user_id: int, field: str, value: bool):
    allowed = {"is_premium", "is_admin"}
    if field not in allowed:
        raise ValueError("Недопустимое поле")
    pool = await get_pool()
    async with pool.acquire() as db:
        # Используем format т.к. asyncpg не поддерживает динамические имена полей через $
        await db.execute(
            f"UPDATE users SET {field} = $1 WHERE user_id = $2", value, user_id
        )


async def check_is_admin(user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT is_admin FROM users WHERE user_id = $1", user_id)
        return bool(row and row["is_admin"])


# ==================== ПРОГРЕСС ====================

async def save_user_progress(user_id: int, content_type: str, content_id: int):
    xp_to_add = 5 if content_type in ["lesson", "grammar"] else 10

    pool = await get_pool()
    async with pool.acquire() as db:
        already = await db.fetchrow("""
            SELECT id FROM user_progress
            WHERE user_id = $1 AND content_type = $2 AND content_id = $3
        """, user_id, content_type, content_id)

        if already:
            return {"status": "already_passed", "xp_earned": 0}

        await db.execute("""
            INSERT INTO user_progress (user_id, content_type, content_id, xp_earned)
            VALUES ($1, $2, $3, $4)
        """, user_id, content_type, content_id, xp_to_add)

        await db.execute("""
            UPDATE users SET xp = xp + $1 WHERE user_id = $2
        """, xp_to_add, user_id)

        return {"status": "success", "xp_earned": xp_to_add}


# ==================== USER QUEUE ====================

async def check_and_fill_queue(user_id: int, level: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("""
            SELECT COUNT(*) as cnt FROM user_queue
            WHERE user_id = $1 AND status = 'pending'
        """, user_id)
        if row["cnt"] > 0:
            return

        await db.execute("""
            INSERT INTO user_queue (user_id, content_type, content_id, queue_order, status)
            SELECT $1, 'lesson', id, order_num, 'pending'
            FROM lessons WHERE level = $2 AND is_active = TRUE ORDER BY order_num
        """, user_id, level)


async def get_next_queue_item(user_id: int, level: str):
    await check_and_fill_queue(user_id, level)
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetchrow("""
            SELECT uq.id, uq.content_type, uq.content_id, l.title, l.lesson_text,
                   q.question_text, q.option_1, q.option_2, q.option_3,
                   q.correct_option, q.commentary
            FROM user_queue uq
            LEFT JOIN lessons l ON uq.content_id = l.id
            LEFT JOIN questions q ON l.id = q.lesson_id
            WHERE uq.user_id = $1 AND uq.status = 'pending'
            ORDER BY uq.queue_order ASC
            LIMIT 1
        """, user_id)


async def handle_answer_result(user_id: int, queue_item_id: int, is_correct: bool):
    pool = await get_pool()
    async with pool.acquire() as db:
        if is_correct:
            await db.execute(
                "UPDATE user_queue SET status = 'completed' WHERE id = $1", queue_item_id
            )
            await db.execute(
                "UPDATE users SET xp = xp + 10 WHERE user_id = $1", user_id
            )
        else:
            row = await db.fetchrow(
                "SELECT MAX(queue_order) as max_order FROM user_queue WHERE user_id = $1", user_id
            )
            max_order = row["max_order"] or 0
            await db.execute(
                "UPDATE user_queue SET queue_order = $1 WHERE id = $2",
                max_order + 1, queue_item_id
            )
