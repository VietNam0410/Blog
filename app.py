import streamlit as st
import sqlite3
import os
from PIL import Image
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(
    page_title="Blog Streamlit",
    layout="centered"
)

# ================= CONSTANT =================
CATEGORIES = [
    "Tất cả",
    "Truyền kỳ Thuỷ Dương",
    "Triết lý nhân sinh",
    "Meme",
    "Thơ ca",
    "Khác"
]

VALID_CATEGORIES = CATEGORIES[1:]  # dùng chung cho DB

# ================= DB =================
def get_db():
    return sqlite3.connect("blog.db", check_same_thread=False)

conn = get_db()
cursor = conn.cursor()

# ================= INIT / MIGRATE =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT,
    image TEXT
)
""")

def add_column(name, ctype):
    try:
        cursor.execute(f"ALTER TABLE posts ADD COLUMN {name} {ctype}")
    except sqlite3.OperationalError:
        pass

add_column("author", "TEXT")
add_column("created_at", "TEXT")
add_column("category", "TEXT")

# ===== Chuẩn hóa dữ liệu cũ =====
cursor.execute("""
UPDATE posts
SET author='Ẩn danh'
WHERE author IS NULL OR TRIM(author)=''
""")

cursor.execute("""
UPDATE posts
SET category='Khác'
WHERE category IS NULL OR TRIM(category)=''
   OR category NOT IN ('Truyền kỳ Thuỷ Dương','Triết lý nhân sinh','Meme','Thơ ca','Khác')
""")

conn.commit()

# ================= UI =================
st.markdown("<h2 style='text-align:center'>📝 Blog cộng đồng</h2>", unsafe_allow_html=True)

menu = st.sidebar.selectbox(
    "📌 Menu",
    ["📖 Xem bài", "✍️ Đăng bài", "⚙️ Quản lý bài viết"]
)

# =================================================
# ================= ĐĂNG BÀI ======================
# =================================================
if menu == "✍️ Đăng bài":
    st.subheader("✍️ Viết bài mới")

    title = st.text_input("Tiêu đề")
    author = st.text_input("Tác giả", value="Ẩn danh")

    category = st.selectbox(
        "📂 Chủ đề",
        VALID_CATEGORIES
    )

    content = st.text_area("Nội dung", height=300)
    image = st.file_uploader("Ảnh (không bắt buộc)", type=["png", "jpg", "jpeg"])

    if st.button("🚀 Đăng bài"):
        if not title.strip() or not content.strip():
            st.warning("⚠️ Vui lòng nhập tiêu đề và nội dung")
            st.stop()

        img_name = None
        if image:
            os.makedirs("images", exist_ok=True)
            img_name = f"{datetime.now().timestamp()}_{image.name}"
            with open(os.path.join("images", img_name), "wb") as f:
                f.write(image.getbuffer())

        cursor.execute("""
            INSERT INTO posts (title, content, image, author, created_at, category)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            title.strip(),
            content.strip(),
            img_name,
            author.strip() or "Ẩn danh",
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            category
        ))

        conn.commit()
        st.success("✅ Đăng bài thành công!")

# =================================================
# ================= XEM BÀI =======================
# =================================================
if menu == "📖 Xem bài":
    st.subheader("📚 Bài viết")

    selected_category = st.radio(
        "🗂️ Chủ đề",
        CATEGORIES,
        horizontal=True
    )

    search = st.text_input("🔍 Tìm kiếm")

    cursor.execute("""
        SELECT id, title, content, image, author, created_at, category
        FROM posts
        ORDER BY id DESC
    """)
    posts = cursor.fetchall()

    def match(post):
        title, content, author, category = (
            post[1] or "",
            post[2] or "",
            post[4] or "",
            post[6] or "Khác"
        )

        if selected_category != "Tất cả" and category != selected_category:
            return False

        if search:
            s = search.lower().strip()
            return s in title.lower() or s in content.lower() or s in author.lower()

        return True

    posts = [p for p in posts if match(p)]

    if not posts:
        st.info("📭 Chưa có bài viết phù hợp")
        st.stop()

    for post in posts:
        st.markdown(f"### {post[1]}")
        st.caption(f"🏷️ {post[6]} | ✍️ {post[4]} | 🕒 {post[5]}")

        if post[3]:
            st.image(
                Image.open(f"images/{post[3]}"),
                use_container_width=True
            )

        st.write(post[2])
        st.markdown("---")

# =================================================
# ================= QUẢN LÝ =======================
# =================================================
if menu == "⚙️ Quản lý bài viết":
    st.subheader("⚙️ Quản lý bài viết")

    cursor.execute("""
        SELECT id, title, content, image, author, created_at, category
        FROM posts
        ORDER BY id DESC
    """)
    posts = cursor.fetchall()

    for post in posts:
        with st.expander(f"📝 {post[1]}"):
            new_title = st.text_input(
                "Tiêu đề",
                post[1],
                key=f"title_{post[0]}"
            )

            new_content = st.text_area(
                "Nội dung",
                post[2],
                key=f"content_{post[0]}"
            )

            current_category = post[6] if post[6] in VALID_CATEGORIES else "Khác"

            new_category = st.selectbox(
                "Chủ đề",
                VALID_CATEGORIES,
                index=VALID_CATEGORIES.index(current_category),
                key=f"category_{post[0]}"
            )

            col1, col2 = st.columns(2)

            with col1:
                if st.button("💾 Lưu", key=f"save_{post[0]}"):
                    cursor.execute("""
                        UPDATE posts
                        SET title=?, content=?, category=?
                        WHERE id=?
                    """, (
                        new_title.strip(),
                        new_content.strip(),
                        new_category,
                        post[0]
                    ))
                    conn.commit()
                    st.success("✅ Đã cập nhật")

            with col2:
                if st.button("🗑️ Xóa", key=f"delete_{post[0]}"):
                    cursor.execute("DELETE FROM posts WHERE id=?", (post[0],))
                    conn.commit()
                    st.warning("🗑️ Đã xóa bài")
