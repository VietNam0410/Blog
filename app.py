import streamlit as st
import psycopg2
import os
from PIL import Image
from datetime import datetime

# ================= CONFIG & STYLE =================
st.set_page_config(page_title="Blog Cộng Đồng", layout="centered", page_icon="📝")

# CSS để giao diện trông hiện đại hơn
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
    .stButton>button { width: 100%; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

# Khởi tạo thư mục ảnh
if not os.path.exists("images"):
    os.makedirs("images")

# ================= CONSTANTS =================
CATEGORIES = ["Tất cả", "Truyền kỳ Thuỷ Dương", "Triết lý nhân sinh", "Meme", "Thơ ca", "Khác"]
VALID_CATEGORIES = CATEGORIES[1:]
EMOJIS = ["👍", "❤️", "😂", "😮", "😢"]

# ================= DB CONNECTION =================
def get_connection():
    try:
        # Tự động ép kiểu port và lấy thông tin từ secrets
        return psycopg2.connect(
            host=st.secrets["DB_HOST"],
            dbname=st.secrets["DB_NAME"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            port=int(st.secrets["DB_PORT"]),
            sslmode="require",
            connect_timeout=10 # Tránh treo trang nếu DB lỗi
        )
    except Exception as e:
        st.error(f"❌ Lỗi kết nối DB: {e}")
        return None

# ================= UI HELPERS =================
def display_post(post):
    """Hàm hiển thị bài viết theo dạng Card chuyên nghiệp"""
    with st.container():
        st.markdown(f"## {post[1]}")
        st.caption(f"📂 {post[6]} | ✍️ {post[4]} | 🕒 {post[5].strftime('%d/%m/%Y %H:%M')}")
        
        # Hiển thị ảnh
        if post[3]:
            img_path = os.path.join("images", post[3])
            if os.path.exists(img_path):
                st.image(Image.open(img_path), use_container_width=True)
        
        st.write(post[2])
        st.divider()

# ================= MAIN APP =================
st.sidebar.title("🎮 Menu Điều Hướng")
menu = st.sidebar.radio("Chọn chức năng:", ["📖 Bản tin", "✍️ Viết bài mới", "⚙️ Quản trị"])

# ----------------- XEM BÀI -----------------
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
        # Query tối ưu: Chỉ lấy bài viết cần thiết
        cur.execute("SELECT id, title, content, image, author, created_at, category FROM posts ORDER BY created_at DESC")
        posts = cur.fetchall()

        for post in posts:
            # Logic lọc
            if selected_category != "Tất cả" and post[6] != selected_category: continue
            if search_query and not any(search_query.lower() in str(f).lower() for f in [post[1], post[2], post[4]]): continue

            # Hiển thị bài viết
            with st.container():
                display_post(post)
                
                # Reactions tầng 1
                react_cols = st.columns(len(EMOJIS) + 1)
                for i, emoji in enumerate(EMOJIS):
                    cur.execute("SELECT count FROM reactions WHERE post_id=%s AND emoji=%s", (post[0], emoji))
                    row = cur.fetchone()
                    count = row[0] if row else 0
                    if react_cols[i].button(f"{emoji} {count}", key=f"re_{post[0]}_{emoji}"):
                        cur.execute("""
                            INSERT INTO reactions (post_id, emoji, count) VALUES (%s, %s, 1)
                            ON CONFLICT (post_id, emoji) DO UPDATE SET count = reactions.count + 1
                        """, (post[0], emoji))
                        conn.commit()
                        st.rerun()

                # Comments tầng 2
                with st.expander(f"💬 Bình luận"):
                    cur.execute("SELECT author, content, created_at FROM comments WHERE post_id=%s ORDER BY created_at ASC", (post[0],))
                    for c in cur.fetchall():
                        st.markdown(f"**{c[0]}**: {c[1]} *({c[2].strftime('%H:%M')})*")
                    
                    with st.form(key=f"comment_form_{post[0]}", clear_on_submit=True):
                        c_name = st.text_input("Tên bạn", "Ẩn danh")
                        c_msg = st.text_area("Nội dung bình luận")
                        if st.form_submit_button("Gửi bình luận"):
                            if c_msg.strip():
                                cur.execute("INSERT INTO comments (post_id, author, content) VALUES (%s, %s, %s)",
                                           (post[0], c_name, c_msg))
                                conn.commit()
                                st.rerun()
        cur.close()
        conn.close()

# ----------------- ĐĂNG BÀI -----------------
elif menu == "✍️ Viết bài mới":
    st.header("✍️ Tạo bài viết mới")
    with st.form("post_form"):
        t1 = st.text_input("Tiêu đề bài viết (*)")
        t2 = st.selectbox("Chủ đề", VALID_CATEGORIES)
        t3 = st.text_input("Tên tác giả", "Ẩn danh")
        t4 = st.text_area("Nội dung bài viết", height=250)
        t5 = st.file_uploader("Đính kèm hình ảnh", type=['jpg', 'png', 'jpeg'])
        
        submit = st.form_submit_button("🚀 Xuất bản ngay")
        
        if submit:
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
                    cur.execute("INSERT INTO posts (title, content, image, author, category) VALUES (%s, %s, %s, %s, %s)",
                               (t1, t4, img_name, t3, t2))
                    conn.commit()
                    st.success("🎉 Bài viết của bạn đã được đăng!")
                    conn.close()

# ----------------- QUẢN TRỊ -----------------
elif menu == "⚙️ Quản trị":
    st.header("⚙️ Hệ thống quản lý")
    # Thêm mật khẩu đơn giản để bảo vệ mục quản lý
    pw = st.text_input("Nhập mã quản trị", type="password")
    if pw == st.secrets.get("ADMIN_PASSWORD", "123456"):
        conn = get_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT id, title FROM posts ORDER BY id DESC")
            items = cur.fetchall()
            for item in items:
                col1, col2 = st.columns([4, 1])
                col1.write(f"ID: {item[0]} | **{item[1]}**")
                if col2.button("🗑️ Xóa", key=f"del_{item[0]}"):
                    cur.execute("DELETE FROM posts WHERE id=%s", (item[0],))
                    conn.commit()
                    st.rerun()
            conn.close()
    else:
        st.info("Vui lòng nhập đúng mã quản trị để truy cập.")