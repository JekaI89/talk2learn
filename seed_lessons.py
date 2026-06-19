import os
import asyncio
from database.db import init_db, get_pool


# =====================================================
# БЛОК УРОКОВ
# =====================================================
LESSONS_TO_SEED = [
    # 4 обычных урока
    {"level": "A1", "title": "Приветствие и знакомство", "lesson_text": "Hello! My name is Anna. Nice to meet you!", "content_type": "lesson", "order_num": 1},
    {"level": "A1", "title": "Моя семья", "lesson_text": "This is my mother. This is my father.", "content_type": "lesson", "order_num": 2},
    {"level": "A2", "title": "Мой день", "lesson_text": "I wake up at 7 o'clock.", "content_type": "lesson", "order_num": 3},
    {"level": "A2", "title": "Хобби и свободное время", "lesson_text": "In my free time I like to read books.", "content_type": "lesson", "order_num": 4},

    # 3 грамматики
    {"level": "A1", "title": "Глагол to be (am / is / are)", "lesson_text": "I am, You are, He/She/It is...", "content_type": "grammar", "order_num": 1},
    {"level": "A1", "title": "Present Simple", "lesson_text": "I live in Moscow. You work in a bank.", "content_type": "grammar", "order_num": 2},
    {"level": "A2", "title": "There is / There are", "lesson_text": "There is a book on the table.", "content_type": "grammar", "order_num": 3},

    # 2 практики
    {
        "level": "A1", "title": "Practice: to be", "lesson_text": "", "content_type": "practice", "order_num": 1,
        "questions": [
            {"question_text": "I ___ a teacher.", "option_1": "am", "option_2": "is", "option_3": "are", "correct_option": 1},
            {"question_text": "She ___ my sister.", "option_1": "am", "option_2": "is", "option_3": "are", "correct_option": 2}
        ]
    },
    {
        "level": "A2", "title": "Practice: Present Simple", "lesson_text": "", "content_type": "practice", "order_num": 2,
        "questions": [
            {"question_text": "He ___ to school every day.", "option_1": "go", "option_2": "goes", "option_3": "going", "correct_option": 2}
        ]
    },

    # 1 ситуация
    {"level": "A2", "title": "В магазине (In the Shop)", "lesson_text": "Customer: Hello! How much is this T-shirt?", "content_type": "situation", "order_num": 1}
]


async def seed_data():
    print("Инициализация базы данных...")
    await init_db()

    pool = await get_pool()
    async with pool.acquire() as db:
        for lesson in LESSONS_TO_SEED:
            row = await db.fetchrow("""
                INSERT INTO lessons (level, title, lesson_text, content_type, order_num)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT DO NOTHING
                RETURNING id
            """, lesson["level"], lesson["title"], lesson.get("lesson_text", ""),
               lesson["content_type"], lesson.get("order_num", 0))

            if row:
                lesson_id = row["id"]
                print(f"Добавлен: [{lesson['content_type']}] {lesson['title']}")

                if lesson.get("content_type") == "practice" and lesson.get("questions"):
                    for q in lesson["questions"]:
                        await db.execute("""
                            INSERT INTO questions 
                            (lesson_id, level, task_type, question_text, option_1, option_2, option_3, correct_option)
                            VALUES ($1, $2, 'multiple_choice', $3, $4, $5, $6, $7)
                            ON CONFLICT DO NOTHING
                        """, lesson_id, lesson["level"], q["question_text"],
                           q["option_1"], q["option_2"], q["option_3"], q["correct_option"])
                        print(f"   Вопрос добавлен")

    print("\nГотово! База инициализирована и заполнена.")


if __name__ == "__main__":
    asyncio.run(seed_data())