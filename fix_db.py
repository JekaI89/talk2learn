import sqlite3

conn = sqlite3.connect("bot_database.db")
cur = conn.cursor()

try:
    cur.execute(
        "ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0"
    )
    print("Добавлено поле is_premium")
except:
    print("Поле is_premium уже существует")

try:
    cur.execute(
        "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0"
    )
    print("Добавлено поле is_admin")
except:
    print("Поле is_admin уже существует")

conn.commit()
conn.close()

print("Готово")