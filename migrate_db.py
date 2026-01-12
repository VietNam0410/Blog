import sqlite3

conn = sqlite3.connect("blog.db")
cursor = conn.cursor()

# Thêm cột category nếu chưa có
try:
    cursor.execute("ALTER TABLE posts ADD COLUMN category TEXT")
except sqlite3.OperationalError:
    pass  # cột đã tồn tại

# Thêm cột author
try:
    cursor.execute("ALTER TABLE posts ADD COLUMN author TEXT")
except sqlite3.OperationalError:
    pass

# Thêm cột created_at
try:
    cursor.execute("ALTER TABLE posts ADD COLUMN created_at TEXT")
except sqlite3.OperationalError:
    pass

# Set giá trị mặc định
cursor.execute("""
UPDATE posts
SET 
    category = 'Khác'
WHERE category IS NULL
""")

cursor.execute("""
UPDATE posts
SET 
    author = 'Ẩn danh'
WHERE author IS NULL
""")

conn.commit()
conn.close()

print("✅ Migration database hoàn tất")
cursor.execute("""
UPDATE posts
SET category = 'Khác'
WHERE category IS NULL OR TRIM(category) = ''
""")
conn.commit()
