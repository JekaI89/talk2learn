import aiosqlite
import asyncio

async def main():
    async with aiosqlite.connect("bot_database.db") as db:
        # Количество вопросов
        async with db.execute("SELECT COUNT(*) FROM questions") as cursor:
            count = (await cursor.fetchone())[0]
            print(f"Всего вопросов в базе: {count}")

        # Показать первые 5 вопросов
        print("\n📋 Первые 5 вопросов:")
        async with db.execute("""
            SELECT id, level, task_type, question_text 
            FROM questions 
            LIMIT 5
        """) as cursor:
            rows = await cursor.fetchall()
            if rows:
                for row in rows:
                    print(f"ID: {row[0]}, Level: {row[1]}, Type: {row[2]}, Question: {row[3][:60]}...")
            else:
                print("Вопросов пока нет в базе.")

asyncio.run(main())