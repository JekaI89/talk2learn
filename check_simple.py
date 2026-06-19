import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print(" DATABASE_URL не найден в переменных окружения")
    exit()

print(" Подключаемся к базе...\n")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Получаем список всех таблиц
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    ORDER BY table_name
""")
tables = [row[0] for row in cur.fetchall()]

print(" Таблицы в базе данных:")
if not tables:
    print("   (таблиц нет)")
else:
    for table in tables:
        print(f"   • {table}")

print("\n" + "="*60)

# Показываем структуру каждой таблицы
for table in tables:
    print(f"\n Структура таблицы: {table}")
    cur.execute(f"""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = '{table}'
        ORDER BY ordinal_position
    """)
    columns = cur.fetchall()
    for col in columns:
        print(f"   - {col[0]:25} | {col[1]:15} | nullable: {col[2]}")

cur.close()
conn.close()

print("\n Проверка завершена.")