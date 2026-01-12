import streamlit as st
import psycopg2
import os
from PIL import Image
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="Blog cộng đồng", layout="centered")

# Tạo thư mục ảnh nếu chưa có
if not os.path.exists("images"):
    os.makedirs("images")

# ================= CONSTANT =================
CATEGORIES = ["Tất cả", "Truyền kỳ Thuỷ Dương", "Triết lý nhân sinh", "Meme", "Thơ ca", "Khác"]
VALID_CATEGORIES = CATEGORIES[1:]
EMOJIS = ["👍", "❤️", "😂", "😮", "😢"]

# ================= DB CONNECT =================
# Dùng hàm này để đảm bảo kết nối luôn sống
def get_connection():
    try:
        conn = psycopg2.connect(
            host=st.secrets["DB_HOST"],
            dbname=st.secrets["DB_NAME"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            port=st.secrets["DB_PORT"],
            sslmode="require"
        )
        return conn
    except Exception as e:
        st.error(f"Lỗi kết nối cơ sở dữ liệu: {e}")
        return None

# ================= UI =================
st.markdown("<h2 style='text-align:center'>📝 Blog cộng đồng</h2>", unsafe_allow_html=True)

menu = st.sidebar.selectbox(
    "📌 Menu",
    ["📖 Xem bài", "✍️ Đăng bài", "⚙️ Quản lý bài viết"]
)

# ================= ĐĂNG BÀI ======================
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
        else:
            img_name = None
            if image:
                img_name = f"{datetime.now().timestamp()}_{image.name}"
                with open(os.path.join("images", img_name), "wb") as f:
                    f.write(image.getbuffer())

            conn = get_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO posts (title, content, image, author, category)
                    VALUES (%s, %s, %s, %s, %s)
                """, (title.strip(), content.strip(), img_name, author.strip() or "Ẩn danh", category))
                conn.commit()
                cur.close()
                conn.close()
                st.success("✅ Đăng bài thành công!")

# ================= XEM BÀI =======================
if menu == "📖 Xem bài":
    st.subheader("📚 Bài viết")
    selected_category = st.radio("🗂️ Chủ đề", CATEGORIES, horizontal=True)
    search = st.text_input("🔍 Tìm kiếm")

    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT id, title, content, image, author, created_at, category FROM posts ORDER BY id DESC")
        posts = cur.fetchall()

        for post in posts:
            # Filter logic
            if selected_category != "Tất cả" and post[6] != selected_category:
                continue
            if search and not any(search.lower() in str(field).lower() for field in [post[1], post[2], post[4]]):
                continue

            st.markdown(f"### {post[1]}")
            st.caption(f"🏷️ {post[6]} | ✍️ {post[4]} | 🕒 {post[5].strftime('%d/%m/%Y %H:%M')}")

            # Xử lý ảnh an toàn
            if post[3]:
                img_path = os.path.join("images", post[3])
                if os.path.exists(img_path):
                    st.image(Image.open(img_path), use_container_width=True)

            st.write(post[2])

            # Reactions
            cols = st.columns(len(EMOJIS))
            for i, emoji in enumerate(EMOJIS):
                cur.execute("SELECT count FROM reactions WHERE post_id=%s AND emoji=%s", (post[0], emoji))
                row = cur.fetchone()
                count = row[0] if row else 0
                if cols[i].button(f"{emoji} {count}", key=f"react_{post[0]}_{emoji}"):
                    cur.execute("""
                        INSERT INTO reactions (post_id, emoji, count) VALUES (%s, %s, 1)
                        ON CONFLICT (post_id, emoji) DO UPDATE SET count = reactions.count + 1
                    """, (post[0], emoji))
                    conn.commit()
                    st.rerun()

            # Comments
            with st.expander("💬 Bình luận"):
                cur.execute("SELECT author, content, created_at FROM comments WHERE post_id=%s ORDER BY id DESC", (post[0],))
                comments = cur.fetchall()
                for c in comments:
                    st.markdown(f"**{c[0]}** · {c[2].strftime('%d/%m/%Y %H:%M')}")
                    st.write(c[1])
                    st.divider()

                with st.form(key=f"form_cm_{post[0]}"):
                    c_author = st.text_input("Tên", key=f"ca_{post[0]}")
                    c_text = st.text_area("Viết bình luận...", key=f"ct_{post[0]}")
                    if st.form_submit_button("💬 Gửi"):
                        if c_text.strip():
                            cur.execute("INSERT INTO comments (post_id, author, content) VALUES (%s, %s, %s)",
                                       (post[0], c_author.strip() or "Ẩn danh", c_text.strip()))
                            conn.commit()
                            st.rerun()
            st.divider()
        cur.close()
        conn.close()

# ================= QUẢN LÝ =======================
if menu == "⚙️ Quản lý bài viết":
    st.subheader("⚙️ Quản trị")
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT id, title, content, category FROM posts ORDER BY id DESC")
        posts = cur.fetchall()

        for post in posts:
            with st.expander(f"📝 {post[1]}"):
                new_title = st.text_input("Tiêu đề", post[1], key=f"edit_t_{post[0]}")
                new_category = st.selectbox("Chủ đề", VALID_CATEGORIES, 
                                           index=VALID_CATEGORIES.index(post[3]) if post[3] in VALID_CATEGORIES else 0,
                                           key=f"edit_c_{post[0]}")
                new_content = st.text_area("Nội dung", post[2], key=f"edit_con_{post[0]}")

                c1, c2 = st.columns(2)
                if c1.button("💾 Lưu", key=f"sv_{post[0]}"):
                    cur.execute("UPDATE posts SET title=%s, content=%s, category=%s WHERE id=%s",
                               (new_title, new_content, new_category, post[0]))
                    conn.commit()
                    st.success("Đã cập nhật!")
                    st.rerun()
                if c2.button("🗑️ Xóa", key=f"del_{post[0]}"):
                    cur.execute("DELETE FROM posts WHERE id=%s", (post[0],))
                    conn.commit()
                    st.rerun()
        cur.close()
        conn.close()