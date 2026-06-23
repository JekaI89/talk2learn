import asyncpg
import os
from datetime import date, timedelta

# Получаем строку подключения из переменных окружения Render
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Render иногда отдаёт postgres:// вместо postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_pool: asyncpg.Pool = None


async def get_pool() -> asyncpg.Pool:
    """Получаем пул соединений (создаётся один раз)"""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60
        )
    return _pool


async def close_pool():
    """Закрываем пул при остановке приложения"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ==================== ИНИЦИАЛИЗАЦИЯ БАЗЫ ====================

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as db:
        # USERS
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
                onboarding_done BOOLEAN DEFAULT FALSE,
                native_language TEXT DEFAULT 'ru',
                target_language TEXT DEFAULT 'en',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Миграции для существующих БД
        await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_done BOOLEAN DEFAULT FALSE")
        await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS native_language TEXT DEFAULT 'ru'")
        await db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS target_language TEXT DEFAULT 'en'")

        # LESSONS
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id SERIAL PRIMARY KEY,
                level TEXT NOT NULL,
                title TEXT NOT NULL,
                lesson_text TEXT,
                content_type TEXT DEFAULT 'lesson',
                language TEXT DEFAULT 'en',
                order_num INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("ALTER TABLE lessons ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en'")

        # QUESTIONS
        await db.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                lesson_id INTEGER REFERENCES lessons(id) ON DELETE SET NULL,
                level TEXT NOT NULL,
                task_type TEXT DEFAULT 'multiple_choice',
                question_text TEXT NOT NULL,
                option_1 TEXT DEFAULT '',
                option_2 TEXT DEFAULT '',
                option_3 TEXT DEFAULT '',
                correct_option INTEGER DEFAULT 1,
                language TEXT DEFAULT 'en',
                order_num INTEGER DEFAULT 0
            )
        """)

        await db.execute("ALTER TABLE questions ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en'")
        await db.execute("ALTER TABLE questions ADD COLUMN IF NOT EXISTS commentary TEXT")

        # USER_QUEUE (очередь заданий пользователя; использовалась в
        # check_and_fill_queue/get_next_queue_item/handle_answer_result,
        # но таблица нигде не создавалась — добавлена для согласованности схемы)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_queue (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                content_type TEXT NOT NULL,
                content_id INTEGER NOT NULL,
                queue_order INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # USER_PROGRESS
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
        # ==================== DICTIONARY ====================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dictionary (
                id SERIAL PRIMARY KEY,
                word TEXT UNIQUE NOT NULL,
                translation TEXT NOT NULL,
                transcription TEXT,
                context_example TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ==================== USER_DICTIONARY ====================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_dictionary (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                word_id INTEGER REFERENCES dictionary(id) ON DELETE CASCADE,
                status TEXT DEFAULT 'learning',
                correct_answers_streak INTEGER DEFAULT 0,
                next_review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, word_id)
            )
        """)
        # ==================== VOCABULARY_CARDS ====================
        await db.execute("""
            CREATE TABLE IF NOT EXISTS vocabulary_cards (
                id SERIAL PRIMARY KEY,
                topic TEXT NOT NULL,
                level TEXT NOT NULL DEFAULT 'A1',
                word TEXT NOT NULL,
                translation TEXT NOT NULL,
                definition TEXT DEFAULT '',
                emoji_code TEXT NOT NULL,
                card_language TEXT DEFAULT 'en',
                native_language TEXT DEFAULT 'ru',
                order_num INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("ALTER TABLE vocabulary_cards ADD COLUMN IF NOT EXISTS card_language TEXT DEFAULT 'en'")
        await db.execute("ALTER TABLE vocabulary_cards ADD COLUMN IF NOT EXISTS native_language TEXT DEFAULT 'ru'")
        print("✅ PostgreSQL: База данных инициализирована")


# ==================== ЯЗЫКИ ПОЛЬЗОВАТЕЛЯ ====================

SUPPORTED_LANGUAGES = {
    'ru': 'Русский',   'en': 'English',    'de': 'Deutsch',
    'fr': 'Français',  'es': 'Español',    'it': 'Italiano',
    'pt': 'Português', 'zh': '中文',        'ja': '日本語',
}

LANG_NAMES_EN = {
    'ru': 'Russian',   'en': 'English',    'de': 'German',
    'fr': 'French',    'es': 'Spanish',    'it': 'Italian',
    'pt': 'Portuguese','zh': 'Chinese',    'ja': 'Japanese',
}


async def get_user_languages(user_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow(
            "SELECT native_language, target_language FROM users WHERE user_id = $1", user_id
        )
        if row:
            return {
                "native": row["native_language"] or "ru",
                "target": row["target_language"] or "en"
            }
        return {"native": "ru", "target": "en"}


async def update_user_languages(user_id: int, native_language: str, target_language: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            UPDATE users SET native_language = $1, target_language = $2 WHERE user_id = $3
        """, native_language, target_language, user_id)


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
                     content_type: str = "lesson", order_num: int = 0,
                     language: str = "en") -> int:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("""
            INSERT INTO lessons (level, title, lesson_text, content_type, order_num, language)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """, level, title, lesson_text, content_type, order_num, language)
        return row["id"]


async def get_all_lessons(language: str = None):
    pool = await get_pool()
    async with pool.acquire() as db:
        if language:
            rows = await db.fetch("""
                SELECT id, level, title, content_type, order_num, language, lesson_text
                FROM lessons WHERE is_active = TRUE AND language = $1
                ORDER BY language, level, content_type, order_num, id
            """, language)
        else:
            rows = await db.fetch("""
                SELECT id, level, title, content_type, order_num, language, lesson_text
                FROM lessons WHERE is_active = TRUE
                ORDER BY language, level, content_type, order_num, id
            """)
        return rows


async def get_lesson_by_id(lesson_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetchrow("""
            SELECT id, level, title, lesson_text, content_type, order_num, language
            FROM lessons WHERE id = $1
        """, lesson_id)


async def update_lesson(lesson_id: int, title: str, lesson_text: str,
                        level: str, content_type: str, order_num: int, language: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            UPDATE lessons
            SET title = $1, lesson_text = $2, level = $3,
                content_type = $4, order_num = $5, language = $6
            WHERE id = $7
        """, title, lesson_text, level, content_type, order_num, language, lesson_id)


async def delete_lesson(lesson_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE lessons SET is_active = FALSE WHERE id = $1", lesson_id)
    print(f"🗑️ Урок ID {lesson_id} скрыт")


async def get_next_uncompleted_lesson(user_id: int, level: str, content_type: str = None,
                                      language: str = 'en'):
    """
    Первый непройденный урок уровня, с фильтром по языку (target_language пользователя).
    """
    pool = await get_pool()
    async with pool.acquire() as db:
        if content_type:
            return await db.fetchrow("""
                SELECT l.id, l.title, l.lesson_text, l.content_type
                FROM lessons l
                WHERE l.level = $1 AND l.is_active = TRUE
                  AND l.content_type = $2 AND l.language = $3
                  AND NOT EXISTS (
                      SELECT 1 FROM user_progress up
                      WHERE up.user_id = $4
                        AND up.content_type = l.content_type
                        AND up.content_id = l.id
                  )
                ORDER BY l.order_num, l.id
                LIMIT 1
            """, level, content_type, language, user_id)

        return await db.fetchrow("""
            SELECT l.id, l.title, l.lesson_text, l.content_type
            FROM lessons l
            WHERE l.level = $1 AND l.is_active = TRUE AND l.language = $2
              AND NOT EXISTS (
                  SELECT 1 FROM user_progress up
                  WHERE up.user_id = $3
                    AND up.content_type = l.content_type
                    AND up.content_id = l.id
              )
            ORDER BY l.order_num, l.id
            LIMIT 1
        """, level, language, user_id)


# ==================== ВОПРОСЫ ====================

async def add_question(lesson_id: int, level: str, task_type: str, question_text: str,
                       option_1: str = "", option_2: str = "", option_3: str = "",
                       correct_option: int = 0, order_num: int = 0):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            INSERT INTO questions 
            (lesson_id, level, task_type, question_text, option_1, option_2, option_3, correct_option, order_num)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, lesson_id, level, task_type, question_text, option_1, option_2, option_3, correct_option, order_num)


async def get_questions_by_level_and_type(level: str, task_type: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetch("""
            SELECT id, question_text, option_1, option_2, option_3, correct_option
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


# ==================== ПРАКТИКА (СЛУЧАЙНЫЙ ВОПРОС) ====================
# Прежняя реализация опиралась на таблицу user_queue, которая нигде не
# создавалась (init_db её не содержал), и на колонку questions.commentary,
# которой тоже не существует в схеме — обращение к ним гарантированно
# падало с ошибкой "relation/column does not exist". Эти функции нигде
# не вызывались из webapp.py, поэтому ошибка не проявлялась раньше.
# Вместо отдельной таблицы-очереди используем ту же логику, что и для
# уроков: прогресс пользователя по вопросам трекаем в user_progress
# с content_type='practice', content_id=questions.id.

async def get_random_practice_question(user_id: int, level: str, task_type: str, language: str = 'en'):
    """Случайный непройденный вопрос по уровню, типу и языку изучения."""
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetchrow("""
            SELECT q.id, q.question_text, q.option_1, q.option_2, q.option_3, q.correct_option
            FROM questions q
            WHERE q.level = $1 AND q.task_type = $2 AND q.language = $3
              AND NOT EXISTS (
                  SELECT 1 FROM user_progress up
                  WHERE up.user_id = $4
                    AND up.content_type = 'practice'
                    AND up.content_id = q.id
              )
            ORDER BY random()
            LIMIT 1
        """, level, task_type, language, user_id)




async def add_word_to_user_dict(
    user_id: int, 
    word: str, 
    translation: str, 
    transcription: str = "", 
    context: str = ""
) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        try:
            # Добавляем слово в глобальный словарь (или обновляем, если уже есть)
            word_row = await db.fetchrow("""
                INSERT INTO dictionary (word, translation, transcription, context_example)
                VALUES (LOWER($1), $2, $3, $4)
                ON CONFLICT (word) DO UPDATE 
                    SET translation = EXCLUDED.translation,
                        transcription = EXCLUDED.transcription,
                        context_example = EXCLUDED.context_example
                RETURNING id
            """, word.strip(), translation.strip(), transcription.strip(), context.strip())

            word_id = word_row["id"]

            # Привязываем слово к пользователю
            await db.execute("""
                INSERT INTO user_dictionary (user_id, word_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id, word_id) DO NOTHING
            """, user_id, word_id)

            return True
        except Exception as e:
            print(f"Ошибка добавления слова: {e}")
            return False


async def get_user_words(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("""
            SELECT d.word, d.translation, d.transcription, d.context_example, ud.status
            FROM user_dictionary ud
            JOIN dictionary d ON ud.word_id = d.id
            WHERE ud.user_id = $1
            ORDER BY ud.created_at DESC
        """, user_id)
        return rows


# ==================== VOCABULARY CARDS ====================

async def get_vocab_topics(level: str = None):
    """Список тем с количеством карточек (для главного экрана словаря)."""
    pool = await get_pool()
    async with pool.acquire() as db:
        if level:
            rows = await db.fetch("""
                SELECT topic, level, COUNT(*) as card_count
                FROM vocabulary_cards
                WHERE is_active = TRUE AND level = $1
                GROUP BY topic, level
                ORDER BY MIN(order_num), topic
            """, level)
        else:
            rows = await db.fetch("""
                SELECT topic, level, COUNT(*) as card_count
                FROM vocabulary_cards
                WHERE is_active = TRUE
                GROUP BY topic, level
                ORDER BY level, MIN(order_num), topic
            """)
        return rows


async def get_vocab_cards(topic: str, level: str = None):
    """Все карточки темы (опционально фильтр по уровню)."""
    pool = await get_pool()
    async with pool.acquire() as db:
        if level:
            rows = await db.fetch("""
                SELECT id, topic, level, word, translation, definition, emoji_code
                FROM vocabulary_cards
                WHERE topic = $1 AND level = $2 AND is_active = TRUE
                ORDER BY order_num, id
            """, topic, level)
        else:
            rows = await db.fetch("""
                SELECT id, topic, level, word, translation, definition, emoji_code
                FROM vocabulary_cards
                WHERE topic = $1 AND is_active = TRUE
                ORDER BY order_num, id
            """, topic)
        return rows


async def add_vocab_card(topic: str, level: str, word: str, translation: str,
                          emoji_code: str, definition: str = "", order_num: int = 0) -> int:
    """Добавить карточку. Возвращает id новой записи."""
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("""
            INSERT INTO vocabulary_cards (topic, level, word, translation, definition, emoji_code, order_num)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """, topic, level, word, translation, definition, emoji_code, order_num)
        return row["id"]


async def update_vocab_card(card_id: int, topic: str, level: str, word: str,
                             translation: str, emoji_code: str, definition: str = ""):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            UPDATE vocabulary_cards
            SET topic=$1, level=$2, word=$3, translation=$4, emoji_code=$5, definition=$6
            WHERE id=$7
        """, topic, level, word, translation, emoji_code, definition, card_id)


async def delete_vocab_card(card_id: int):
    """Мягкое удаление — is_active = FALSE."""
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE vocabulary_cards SET is_active=FALSE WHERE id=$1", card_id)


async def get_all_vocab_cards_admin():
    """Все активные карточки для просмотра в админке."""
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("""
            SELECT id, topic, level, word, translation, definition, emoji_code, order_num
            FROM vocabulary_cards
            WHERE is_active = TRUE
            ORDER BY level, topic, order_num, id
        """)
        return rows


# ==================== ОНБОРДИНГ ====================

async def complete_onboarding(user_id: int, level: str, goal: str = "",
                              native_language: str = "ru", target_language: str = "en"):
    """Отмечаем онбординг пройденным и сохраняем выбранный уровень и языки."""
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            UPDATE users
            SET onboarding_done = TRUE, level = $1,
                native_language = $2, target_language = $3
            WHERE user_id = $4
        """, level, native_language, target_language, user_id)


async def get_onboarding_status(user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT onboarding_done FROM users WHERE user_id = $1", user_id)
        return bool(row["onboarding_done"]) if row else False


# ==================== ПРОГРЕСС ПО УРОВНЮ ====================

async def get_lesson_progress(user_id: int, level: str, content_type: str = None) -> dict:
    """
    Возвращает {total, completed, next_num} для экрана «Урок X из Y».
    """
    pool = await get_pool()
    async with pool.acquire() as db:
        if content_type:
            total_row = await db.fetchrow("""
                SELECT COUNT(*) as cnt FROM lessons
                WHERE level = $1 AND content_type = $2 AND is_active = TRUE
            """, level, content_type)
            done_row = await db.fetchrow("""
                SELECT COUNT(*) as cnt FROM user_progress up
                JOIN lessons l ON up.content_id = l.id AND up.content_type = l.content_type
                WHERE up.user_id = $1 AND l.level = $2 AND l.content_type = $3 AND l.is_active = TRUE
            """, user_id, level, content_type)
        else:
            total_row = await db.fetchrow("""
                SELECT COUNT(*) as cnt FROM lessons WHERE level = $1 AND is_active = TRUE
            """, level)
            done_row = await db.fetchrow("""
                SELECT COUNT(*) as cnt FROM user_progress up
                JOIN lessons l ON up.content_id = l.id AND up.content_type = l.content_type
                WHERE up.user_id = $1 AND l.level = $2 AND l.is_active = TRUE
            """, user_id, level)

        total = int(total_row["cnt"]) if total_row else 0
        completed = int(done_row["cnt"]) if done_row else 0
        return {"total": total, "completed": completed, "next_num": completed + 1}


# ==================== СТАТУС СЛОВА В СЛОВАРЕ ====================

async def update_word_status(user_id: int, word: str, status: str):
    """Меняет статус слова: 'learning' → 'known' или обратно."""
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            UPDATE user_dictionary ud
            SET status = $1
            FROM dictionary d
            WHERE ud.word_id = d.id AND ud.user_id = $2 AND d.word = $3
        """, status, user_id, word)


# ==================== СТАТИСТИКА ПО КАТЕГОРИЯМ ====================

async def get_user_category_stats(user_id: int) -> dict:
    """Прогресс пользователя по каждой категории контента."""
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("""
            SELECT
                l.content_type,
                COUNT(DISTINCT l.id) as total,
                COUNT(DISTINCT up.content_id) as completed
            FROM lessons l
            LEFT JOIN user_progress up
                ON up.content_id = l.id
                AND up.content_type = l.content_type
                AND up.user_id = $1
            WHERE l.is_active = TRUE
            GROUP BY l.content_type
        """, user_id)

        practice_total = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM questions WHERE lesson_id IS NOT NULL OR lesson_id IS NULL"
        )
        practice_done = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM user_progress WHERE user_id = $1 AND content_type = 'practice'",
            user_id
        )
        words_total = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM user_dictionary WHERE user_id = $1", user_id
        )
        words_known = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM user_dictionary WHERE user_id = $1 AND status = 'known'",
            user_id
        )
        vocab_cards_total = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM vocabulary_cards WHERE is_active = TRUE"
        )
        vocab_cards_done = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM user_progress WHERE user_id = $1 AND content_type = 'vocab_card'",
            user_id
        )

        stats = {r["content_type"]: {"total": int(r["total"]), "completed": int(r["completed"])} for r in rows}
        stats["practice"] = {"total": int(practice_total["cnt"]), "completed": int(practice_done["cnt"])}
        stats["words"] = {
            "total":     int(words_total["cnt"]),
            "completed": int(words_known["cnt"])
        }
        stats["vocab_cards"] = {
            "total":     int(vocab_cards_total["cnt"]),
            "completed": int(vocab_cards_done["cnt"])
        }
        return stats