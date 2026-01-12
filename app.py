import streamlit as st
import psycopg2
import os
from PIL import Image
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="Blog cộng đồng", layout="centered")

# ================= CONSTANT =================
CATEGORIES = [
    "Tất cả",
    "Truyền kỳ Thuỷ Dương",
    "Triết lý nhân sinh",
    "Meme",
    "Thơ ca",
    "Khác"
]
VALID_CATEGORIES = CATEGORIES[1:]
EMOJIS = ["👍", "❤️", "😂", "😮", "😢"]

# ================= DB CONNECT =================
@st.cache_resource
def get_db():
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        database=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        port=st.secrets["DB_PORT"],
    )

conn = get_db()
cursor = conn.cursor()

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
    category = st.selectbox("📂 Chủ đề", VALID_CATEGORIES)
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
            INSERT INTO posts (title, content, image, author, category)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            title.strip(),
            content.strip(),
            img_name,
            author.strip() or "Ẩn danh",
            category
        ))
        conn.commit()
        st.success("✅ Đăng bài thành công!")

# =================================================
# ================= XEM BÀI =======================
# =================================================
if menu == "📖 Xem bài":
    st.subheader("📚 Bài viết")

    selected_category = st.radio("🗂️ Chủ đề", CATEGORIES, horizontal=True)
    search = st.text_input("🔍 Tìm kiếm")

    cursor.execute("""
        SELECT id, title, content, image, author, created_at, category
        FROM posts
        ORDER BY id DESC
    """)
    posts = cursor.fetchall()

    def match(post):
        title, content, author, category = post[1], post[2], post[4], post[6]
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
        st.caption(
            f"🏷️ {post[6]} | ✍️ {post[4]} | 🕒 {post[5].strftime('%d/%m/%Y %H:%M')}"
        )

        if post[3]:
            st.image(Image.open(f"images/{post[3]}"), use_container_width=True)

        st.write(post[2])

        # ===== REACTIONS (GỌN) =====
        cols = st.columns(len(EMOJIS))
        for i, emoji in enumerate(EMOJIS):
            cursor.execute(
                "SELECT count FROM reactions WHERE post_id=%s AND emoji=%s",
                (post[0], emoji)
            )
            row = cursor.fetchone()
            count = row[0] if row else 0

            with cols[i]:
                if st.button(f"{emoji} {count}", key=f"react_{post[0]}_{emoji}"):
                    cursor.execute("""
                        INSERT INTO reactions (post_id, emoji, count)
                        VALUES (%s, %s, 1)
                        ON CONFLICT (post_id, emoji)
                        DO UPDATE SET count = reactions.count + 1
                    """, (post[0], emoji))
                    conn.commit()
                    st.rerun()

        # ===== COMMENTS (GỌN – CLICK MỚI MỞ) =====
        with st.expander("💬 Bình luận"):
            cursor.execute("""
                SELECT author, content, created_at
                FROM comments
                WHERE post_id=%s
                ORDER BY id DESC
            """, (post[0],))
            comments = cursor.fetchall()

            for c in comments:
                st.markdown(f"**{c[0]}** · {c[2].strftime('%d/%m/%Y %H:%M')}")
                st.write(c[1])
                st.markdown("---")

            c_author = st.text_input("Tên", key=f"ca_{post[0]}")
            c_text = st.text_area("Viết bình luận...", key=f"ct_{post[0]}")

            if st.button("💬 Gửi", key=f"cs_{post[0]}"):
                if c_text.strip():
                    cursor.execute("""
                        INSERT INTO comments (post_id, author, content)
                        VALUES (%s, %s, %s)
                    """, (
                        post[0],
                        c_author.strip() or "Ẩn danh",
                        c_text.strip()
                    ))
                    conn.commit()
                    st.rerun()

        st.markdown("---")

# =================================================
# ================= QUẢN LÝ =======================
# =================================================
if menu == "⚙️ Quản lý bài viết":
    st.subheader("⚙️ Quản lý bài viết")

    cursor.execute("""
        SELECT id, title, content, category
        FROM posts
        ORDER BY id DESC
    """)
    posts = cursor.fetchall()

    for post in posts:
        with st.expander(f"📝 {post[1]}"):
            new_title = st.text_input(
                "Tiêu đề", post[1], key=f"title_{post[0]}"
            )
            new_content = st.text_area(
                "Nội dung", post[2], key=f"content_{post[0]}"
            )
            new_category = st.selectbox(
                "Chủ đề",
                VALID_CATEGORIES,
                index=VALID_CATEGORIES.index(post[3]),
                key=f"cat_{post[0]}"
            )

            col1, col2 = st.columns(2)

            with col1:
                if st.button("💾 Lưu", key=f"save_{post[0]}"):
                    cursor.execute("""
                        UPDATE posts
                        SET title=%s, content=%s, category=%s
                        WHERE id=%s
                    """, (
                        new_title.strip(),
                        new_content.strip(),
                        new_category,
                        post[0]
                    ))
                    conn.commit()
                    st.success("✅ Đã cập nhật")

            with col2:
                if st.button("🗑️ Xóa", key=f"del_{post[0]}"):
                    cursor.execute("DELETE FROM posts WHERE id=%s", (post[0],))
                    conn.commit()
                    st.warning("🗑️ Đã xóa bài")

