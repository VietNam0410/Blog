import streamlit as st
import psycopg2
import os
from PIL import Image
from datetime import datetime

# ================= CONFIG & STYLE =================
st.set_page_config(page_title="Blog Cộng Đồng", layout="centered", page_icon="📝")

# CSS tối ưu giao diện
st.markdown("""
    <style>
    .post-card {
        border-radius: 10px;
        padding: 20px;
        background-color: #ffffff;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 25px;
        border: 1px solid #eee;
    }
    div[data-testid="stHorizontalBlock"] button {
        border: 1px solid #eee;
        background: #f9f9f9;
        border-radius: 20px;
        padding: 2px 12px;
        transition: 0.3s;
    }
    div[data-testid="stHorizontalBlock"] button:hover {
        border-color: #ff4b4b;
        color: #ff4b4b;
        background: #fff5f5;
    }
    .stButton>button { width: 100%; }
    </style>
""", unsafe_allow_html=True)

if not os.path.exists("images"):
    os.makedirs("images")

# ================= CONSTANTS =================
CATEGORIES = ["Tất cả", "Truyền kỳ Thuỷ Dương", "Triết lý nhân sinh", "Meme", "Thơ ca", "Khác"]
VALID_CATEGORIES = CATEGORIES[1:]
EMOJIS = ["👍", "❤️", "😂", "😮", "😢"]

# ================= DB CONNECTION =================
def get_connection():
    try:
        return psycopg2.connect(
            host=st.secrets["DB_HOST"],
            dbname=st.secrets["DB_NAME"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            port=int(st.secrets["DB_PORT"]),
            sslmode="require",
            connect_timeout=10
        )
    except Exception as e:
        st.error(f"❌ Lỗi kết nối DB: {e}")
        return None

# ================= COMPONENTS (FRAGMENTS) =================
@st.fragment
def reaction_section(post_id):
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        react_cols = st.columns(len(EMOJIS))
        for i, emoji in enumerate(EMOJIS):
            cur.execute("SELECT count FROM reactions WHERE post_id=%s AND emoji=%s", (post_id, emoji))
            row = cur.fetchone()
            count = row[0] if row else 0
            if react_cols[i].button(f"{emoji} {count}", key=f"re_{post_id}_{emoji}"):
                cur.execute("""
                    INSERT INTO reactions (post_id, emoji, count) VALUES (%s, %s, 1)
                    ON CONFLICT (post_id, emoji) DO UPDATE SET count = reactions.count + 1
                """, (post_id, emoji))
                conn.commit()
                st.rerun()
        cur.close()
        conn.close()

# ================= UI HELPERS =================
def display_post(post):
    st.markdown(f"## {post[1]}")
    st.caption(f"📂 {post[6]} | ✍️ {post[4]} | 🕒 {post[5].strftime('%d/%m/%Y %H:%M')}")
    if post[3]:
        img_path = os.path.join("images", post[3])
        if os.path.exists(img_path):
            st.image(Image.open(img_path), use_container_width=True)
    st.write(post[2])

# ================= MAIN APP =================
st.sidebar.title("🎮 Điều Hướng")
menu = st.sidebar.radio("Chọn chức năng:", ["📖 Bản tin", "✍️ Viết bài mới", "⚙️ Quản trị"])

# ----------------- 📖 BẢN TIN -----------------
if menu == "📖 Bản tin":
    st.header("📖 Bản tin cộng đồng")
    col_cat, col_search = st.columns([1, 1])
    with col_cat:
        selected_category = st.selectbox("🗂️ Lọc theo chủ đề", CATEGORIES)
    with col_search:
        search_query = st.text_input("🔍 Tìm bài viết...", placeholder="Nhập từ khóa...")

    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT id, title, content, image, author, created_at, category FROM posts ORDER BY created_at DESC")
        posts = cur.fetchall()
        for post in posts:
            if selected_category != "Tất cả" and post[6] != selected_category: continue
            if search_query and not any(search_query.lower() in str(f).lower() for f in [post[1], post[2], post[4]]): continue

            with st.container():
                display_post(post)
                reaction_section(post[0])
                with st.expander(f"💬 Bình luận"):
                    cur.execute("SELECT author, content, created_at FROM comments WHERE post_id=%s ORDER BY created_at ASC", (post[0],))
                    for c in cur.fetchall():
                        st.markdown(f"**{c[0]}**: {c[1]} *({c[2].strftime('%H:%M')})*")
                    with st.form(key=f"comment_form_{post[0]}", clear_on_submit=True):
                        c_name = st.text_input("Tên bạn", "Ẩn danh")
                        c_msg = st.text_area("Nội dung bình luận")
                        if st.form_submit_button("Gửi bình luận"):
                            if c_msg.strip():
                                cur.execute("INSERT INTO comments (post_id, author, content) VALUES (%s, %s, %s)", (post[0], c_name, c_msg))
                                conn.commit()
                                st.rerun()
            st.divider()
        cur.close()
        conn.close()

# ----------------- ✍️ VIẾT BÀI MỚI -----------------
elif menu == "✍️ Viết bài mới":
    st.header("✍️ Tạo bài viết mới")
    with st.form("post_form"):
        t1 = st.text_input("Tiêu đề bài viết (*)")
        t2 = st.selectbox("Chủ đề", VALID_CATEGORIES)
        t3 = st.text_input("Tên tác giả", "Ẩn danh")
        t4 = st.text_area("Nội dung bài viết", height=250)
        t5 = st.file_uploader("Đính kèm hình ảnh", type=['jpg', 'png', 'jpeg'])
        if st.form_submit_button("🚀 Xuất bản ngay"):
            if not t1 or not t4:
                st.error("Vui lòng điền đủ tiêu đề và nội dung!")
            else:
                img_name = None
                if t5:
                    img_name = f"{datetime.now().timestamp()}_{t5.name}"
                    with open(os.path.join("images", img_name), "wb") as f:
                        f.write(t5.getbuffer())
                conn = get_connection()
                if conn:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO posts (title, content, image, author, category) VALUES (%s, %s, %s, %s, %s)", (t1, t4, img_name, t3, t2))
                    conn.commit()
                    st.success("🎉 Bài viết đã được đăng!")
                    conn.close()

# ----------------- ⚙️ QUẢN TRỊ (CÓ SỬA BÀI) -----------------
elif menu == "⚙️ Quản trị":
    st.header("⚙️ Quản lý hệ thống")
    pw = st.text_input("Nhập mã quản trị", type="password")
    
    if pw == st.secrets.get("ADMIN_PASSWORD", "123456"):
        conn = get_connection()
        if conn:
            cur = conn.cursor()
            
            # Khởi tạo trạng thái sửa bài nếu chưa có
            if "editing_post_id" not in st.session_state:
                st.session_state.editing_post_id = None

            # FORM CHỈNH SỬA (Chỉ hiện khi có ID đang được chọn để sửa)
            if st.session_state.editing_post_id:
                st.info(f"Đang chỉnh sửa bài viết ID: {st.session_state.editing_post_id}")
                cur.execute("SELECT title, content, category, author FROM posts WHERE id=%s", (st.session_state.editing_post_id,))
                edit_data = cur.fetchone()
                
                if edit_data:
                    with st.form("edit_form"):
                        new_title = st.text_input("Tiêu đề", value=edit_data[0])
                        new_author = st.text_input("Tác giả", value=edit_data[3])
                        new_cat = st.selectbox("Chủ đề", VALID_CATEGORIES, index=VALID_CATEGORIES.index(edit_data[2]) if edit_data[2] in VALID_CATEGORIES else 0)
                        new_content = st.text_area("Nội dung", value=edit_data[1], height=200)
                        
                        col_save, col_cancel = st.columns(2)
                        if col_save.form_submit_button("💾 Lưu thay đổi"):
                            cur.execute("UPDATE posts SET title=%s, content=%s, category=%s, author=%s WHERE id=%s", 
                                       (new_title, new_content, new_cat, new_author, st.session_state.editing_post_id))
                            conn.commit()
                            st.session_state.editing_post_id = None
                            st.success("Đã cập nhật thành công!")
                            st.rerun()
                        if col_cancel.form_submit_button("❌ Hủy"):
                            st.session_state.editing_post_id = None
                            st.rerun()
                st.divider()

            # DANH SÁCH BÀI VIẾT ĐỂ QUẢN LÝ
            cur.execute("SELECT id, title, author, category FROM posts ORDER BY id DESC")
            items = cur.fetchall()
            
            for item in items:
                with st.expander(f"ID: {item[0]} | {item[1]}"):
                    st.write(f"**Tác giả:** {item[2]} | **Chủ đề:** {item[3]}")
                    c1, c2 = st.columns(2)
                    if c1.button("📝 Sửa bài", key=f"edit_btn_{item[0]}"):
                        st.session_state.editing_post_id = item[0]
                        st.rerun()
                    if c2.button("🗑️ Xóa bài", key=f"del_btn_{item[0]}"):
                        cur.execute("DELETE FROM posts WHERE id=%s", (item[0],))
                        conn.commit()
                        st.warning(f"Đã xóa bài viết {item[0]}")
                        st.rerun()
            conn.close()
    else:
        st.info("Vui lòng nhập đúng mã quản trị.")