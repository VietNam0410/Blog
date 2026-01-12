import streamlit as st
import sqlite3
import os
from datetime import datetime
from PIL import Image

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Blog Streamlit", layout="wide")

# ---------------- DB ----------------
def get_db():
    return sqlite3.connect("blog.db", check_same_thread=False)

conn = get_db()
cursor = conn.cursor()

# ---------------- INIT DB ----------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT,
    image TEXT,
    author TEXT,
    created_at TEXT,
    status TEXT
)
""")
conn.commit()

# ---------------- UI ----------------
st.title("📝 Blog cộng đồng")

menu = st.sidebar.selectbox(
    "Menu",
    ["📖 Xem bài", "✍️ Đăng bài", "⚙️ Quản lý"]
)

# ================== ĐĂNG BÀI ==================
if menu == "✍️ Đăng bài":
    st.subheader("✍️ Viết bài mới")

    title = st.text_input("Tiêu đề")
    content = st.text_area("Nội dung")
    author = st.text_input("Tên tác giả", value="Guest")
    image = st.file_uploader("Ảnh (không bắt buộc)", ["png", "jpg", "jpeg"])

    if st.button("Đăng bài"):
        if not title or not content:
            st.error("❌ Tiêu đề và nội dung không được trống")
        else:
            img_name = None
            if image:
                os.makedirs("images", exist_ok=True)
                img_name = f"{datetime.now().timestamp()}_{image.name}"
                with open(f"images/{img_name}", "wb") as f:
                    f.write(image.getbuffer())

            cursor.execute(
                """
                INSERT INTO posts 
                (title, content, image, author, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    content,
                    img_name,
                    author,
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "pending"
                )
            )
            conn.commit()
            st.success("✅ Bài viết đang chờ duyệt")

# ================== XEM BÀI ==================
if menu == "📖 Xem bài":
    st.subheader("📚 Bài đã đăng")

    cursor.execute(
        "SELECT * FROM posts WHERE status='published' ORDER BY id DESC"
    )
    posts = cursor.fetchall()

    for post in posts:
        st.markdown(f"## {post[1]}")
        st.caption(f"✍️ {post[4]} | 🕒 {post[5]}")
        st.write(post[2])

        if post[3]:
            st.image(Image.open(f"images/{post[3]}"), width=500)

        st.markdown("---")

# ================== QUẢN LÝ ==================
if menu == "⚙️ Quản lý":
    st.subheader("⚙️ Quản lý bài viết")

    cursor.execute("SELECT * FROM posts ORDER BY id DESC")
    posts = cursor.fetchall()

    for post in posts:
        with st.expander(f"{post[1]} ({post[6]})"):
            st.write(post[2])

            col1, col2, col3 = st.columns(3)

            if col1.button("✅ Duyệt", key=f"pub{post[0]}"):
                cursor.execute(
                    "UPDATE posts SET status='published' WHERE id=?",
                    (post[0],)
                )
                conn.commit()
                st.success("Đã duyệt")

            if col2.button("🗑️ Xóa", key=f"del{post[0]}"):
                cursor.execute("DELETE FROM posts WHERE id=?", (post[0],))
                conn.commit()
                st.warning("Đã xóa")

            if col3.button("✏️ Sửa", key=f"edit{post[0]}"):
                st.info("Chức năng sửa sẽ làm ở bước tiếp theo")
