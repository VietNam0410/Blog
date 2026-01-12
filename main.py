import sqlite3

conn = sqlite3.connect("blog.db")
cursor = conn.cursor()

cursor.execute("ALTER TABLE posts ADD COLUMN author TEXT")
cursor.execute("ALTER TABLE posts ADD COLUMN created_at TEXT")
cursor.execute("ALTER TABLE posts ADD COLUMN status TEXT")

conn.commit()
conn.close()
