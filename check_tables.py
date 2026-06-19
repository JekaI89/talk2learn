import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

print("DATABASE_URL:", DATABASE_URL)

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found!")
    exit()

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    ORDER BY table_name
""")

tables = [row[0] for row in cur.fetchall()]

print("\nTables in database:")
for table in tables:
    print("  -", table)

cur.close()
conn.close()