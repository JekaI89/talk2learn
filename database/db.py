import aiosqlite
from datetime import date, timedelta

DB_PATH = "bot_database.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        # ==================== USERS ====================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                username TEXT,
                level TEXT DEFAULT 'A1',
                xp INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 0,
                last_activity_date TEXT,
                is_admin BOOLEAN DEFAULT 0,
                is_premium BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ==================== LESSONS ====================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                title TEXT NOT NULL,
                lesson_text TEXT,
                content_type TEXT DEFAULT 'theory',
                order_num INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ==================== QUESTIONS ====================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id INTEGER,
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
                order_num INTEGER DEFAULT 0,
                FOREIGN KEY(lesson_id) REFERENCES lessons(id)
            )
        """)

        # ==================== USER_PROGRESS ====================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content_type TEXT,
                content_id INTEGER,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                xp_earned INTEGER DEFAULT 10,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

        # ==================== USER_QUEUE ====================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content_type TEXT,
                content_id INTEGER,
                queue_order INTEGER,
                status TEXT DEFAULT 'pending'
            )
        """)

        # ==================== ИНДЕКСЫ ====================
        await db.execute("CREATE INDEX IF NOT EXISTS idx_user_progress_user ON user_progress(user_id, content_type)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_lessons_level ON lessons(level, is_active)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_questions_level ON questions(level, task_type)")

        await db.commit()
        print("✅ База данных успешно инициализирована")


# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================

async def register_or_get_user(user_id: int, name: str = "", username: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, name, username, level)
            VALUES (?, ?, ?, 'A1')
        """, (user_id, name, username))
        await db.commit()

        async with db.execute("SELECT level FROM users WHERE user_id = ?", (user_id,)) as c:
            row = await c.fetchone()
            return row[0] if row else "A1"


async def get_user_level(user_id: int) -> str:
    """Возвращает текущий уровень пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT level FROM users WHERE user_id = ?", (user_id,)) as c:
            row = await c.fetchone()
            return row[0] if row else "A1"


async def update_user_streak(user_id: int):
    """Обновляет streak пользователя"""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT last_activity_date, streak FROM users WHERE user_id = ?", (user_id,)) as c:
            row = await c.fetchone()

        if not row:
            return

        last_date = row[0]
        current_streak = row[1] or 0

        if last_date == today:
            return  # Уже обновляли сегодня

        new_streak = current_streak + 1 if last_date == yesterday else 1

        await db.execute("""
            UPDATE users 
            SET streak = ?, last_activity_date = ? 
            WHERE user_id = ?
        """, (new_streak, today, user_id))
        await db.commit()


async def get_user_category_stats(user_id: int):
    """Возвращает статистику по категориям"""
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {}
        for content_type in ["lesson", "grammar", "practice", "speaking"]:
            async with db.execute("""
                SELECT COUNT(*) FROM user_progress 
                WHERE user_id = ? AND content_type = ?
            """, (user_id, content_type)) as c:
                stats[content_type] = (await c.fetchone())[0]
        return stats


# ==================== LESSONS ====================

async def add_lesson(level: str, title: str, lesson_text: str = "", content_type: str = "theory", order_num: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO lessons (level, title, lesson_text, content_type, order_num)
            VALUES (?, ?, ?, ?, ?)
        """, (level, title, lesson_text, content_type, order_num))
        await db.commit()


async def get_all_lessons():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id, level, title, content_type, order_num 
            FROM lessons 
            WHERE is_active = 1 
            ORDER BY level, order_num, id
        """) as cursor:
            return await cursor.fetchall()


async def delete_lesson(lesson_id: int):
    """Мягкое удаление урока — скрываем из доступа, не ломая статистику и очереди"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE lessons SET is_active = 0 WHERE id = ?", (lesson_id,))
        await db.commit()
        print(f"🗑️ Урок ID {lesson_id} переведён в статус неактивных")


# ==================== QUESTIONS ====================

async def add_question(lesson_id: int, level: str, task_type: str, question_text: str,
                       option_1: str = "", option_2: str = "", option_3: str = "",
                       correct_option: int = 0, correct_answer: str = "",
                       media_url: str = "", commentary: str = "", order_num: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO questions 
            (lesson_id, level, task_type, question_text, option_1, option_2, option_3, 
             correct_option, correct_answer, media_url, commentary, order_num)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (lesson_id, level, task_type, question_text, option_1, option_2, option_3,
              correct_option, correct_answer, media_url, commentary, order_num))
        await db.commit()


async def get_questions_by_level_and_type(level: str, task_type: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id, question_text, option_1, option_2, option_3, correct_option, correct_answer, media_url
            FROM questions 
            WHERE level = ? AND task_type = ?
            ORDER BY order_num, id
        """, (level, task_type)) as cursor:
            return await cursor.fetchall()


# ==================== ADMIN ====================

async def get_admin_statistics():
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {}
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            stats["total_users"] = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1") as c:
            stats["premium_users"] = (await c.fetchone())[0]

        stats["levels"] = {}
        for level in ["A1", "A2", "B1", "B2", "C1", "C2"]:
            async with db.execute("SELECT COUNT(*) FROM lessons WHERE level = ? AND is_active = 1", (level,)) as c:
                stats["levels"][level] = (await c.fetchone())[0]
        return stats


async def update_user_status(user_id: int, field: str, value: bool):
    allowed = {"is_premium", "is_admin"}
    if field not in allowed:
        raise ValueError("Недопустимое поле")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
        await db.commit()


async def check_is_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0])


# ==================== ПРОГРЕСС ====================

async def save_user_progress(user_id: int, content_type: str, content_id: int):
    """
    Фиксирует прохождение контента и начисляет баллы:
    - lesson / grammar (теория) = 5 баллов
    - practice / speaking (тесты и практика) = 10 баллов
    """
    xp_to_add = 5 if content_type in ["lesson", "grammar"] else 10

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id FROM user_progress 
            WHERE user_id = ? AND content_type = ? AND content_id = ?
        """, (user_id, content_type, content_id)) as c:
            already_passed = await c.fetchone()

        if already_passed:
            return {"status": "already_passed", "xp_earned": 0}

        await db.execute("""
            INSERT INTO user_progress (user_id, content_type, content_id, xp_earned)
            VALUES (?, ?, ?, ?)
        """, (user_id, content_type, content_id, xp_to_add))

        await db.execute("""
            UPDATE users 
            SET xp = xp + ? 
            WHERE user_id = ?
        """, (xp_to_add, user_id))

        await db.commit()
        return {"status": "success", "xp_earned": xp_to_add}


# ==================== USER QUEUE ====================

async def check_and_fill_queue(user_id: int, level: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM user_queue WHERE user_id = ? AND status = 'pending'", (user_id,)) as c:
            if (await c.fetchone())[0] > 0:
                return
        await db.execute("""
            INSERT INTO user_queue (user_id, content_type, content_id, queue_order, status)
            SELECT ?, 'lesson', id, order_num, 'pending'
            FROM lessons WHERE level = ? AND is_active = 1 ORDER BY order_num
        """, (user_id, level))
        await db.commit()


async def get_next_queue_item(user_id: int, level: str):
    await check_and_fill_queue(user_id, level)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT uq.id, uq.content_type, uq.content_id, l.title, l.lesson_text,
                   q.question_text, q.option_1, q.option_2, q.option_3, q.correct_option, q.commentary
            FROM user_queue uq
            LEFT JOIN lessons l ON uq.content_id = l.id
            LEFT JOIN questions q ON l.id = q.lesson_id
            WHERE uq.user_id = ? AND uq.status = 'pending'
            ORDER BY uq.queue_order ASC LIMIT 1
        """, (user_id,)) as cursor:
            return await cursor.fetchone()


async def handle_answer_result(user_id: int, queue_item_id: int, is_correct: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        if is_correct:
            await db.execute("UPDATE user_queue SET status = 'completed' WHERE id = ?", (queue_item_id,))
            await db.execute("UPDATE users SET xp = xp + 10 WHERE user_id = ?", (user_id,))
        else:
            async with db.execute("SELECT MAX(queue_order) FROM user_queue WHERE user_id = ?", (user_id,)) as c:
                max_order = (await c.fetchone())[0] or 0
            await db.execute("UPDATE user_queue SET queue_order = ? WHERE id = ?", (max_order + 1, queue_item_id))
        await db.commit()
