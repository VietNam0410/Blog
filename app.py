import streamlit as st
import psycopg2
from psycopg2 import pool
import os
from PIL import Image
from datetime import datetime
import contextlib
import time

# ================= CẤU HÌNH & GIAO DIỆN =================
st.set_page_config(page_title="Blog Cộng Đồng", layout="centered", page_icon="📝")

# CSS tùy chỉnh để tối ưu hiển thị trên Mobile và xử lý xuống dòng
st.markdown("""
    <style>
    /* Nội dung bài viết: Giữ nguyên định dạng xuống dòng và ngắt từ thông minh */
    .post-content {
        white-space: pre-wrap;
        word-wrap: break-word;
        font-family: 'Source Sans Pro', sans-serif;
        line-height: 1.7;
        margin-bottom: 15px;
        color: #1a1a1a;
        font-size: 1.05rem;
    }
    
    /* Tối ưu hóa các nút reaction nhỏ gọn thông qua CSS thay vì tham số size */
    div[data-testid="stButton"] button {
        border-radius: 20px !important;
        padding: 2px 12px !important;
        min-height: 30px !important;
        height: 30px !important;
        border: 1px solid #f0f0f0 !important;
        background-color: #f8f9fa !important;
        transition: 0.2s;
        font-size: 0.85rem !important;
    }
    
    div[data-testid="stButton"] button:hover {
        border-color: #ff4b4b !important;
        color: #ff4b4b !important;
    }

    /* Tiêu đề bài viết */
    .post-title {
        font-weight: 700;
        font-size: 1.6rem;
        margin-bottom: 5px;
        color: #0e1117;
    }
    
    /* Bo góc khung bài viết */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 15px !important;
    }
    </style>
""", unsafe_allow_html=True)

if not os.path.exists("images"):
    os.makedirs("images")

# ================= HẰNG SỐ =================
CATEGORIES = ["Tất cả", "Truyền kỳ Thuỷ Dương", "Triết lý nhân sinh", "Meme", "Thơ ca", "Khác"]
VALID_CATEGORIES = CATEGORIES[1:]
EMOJIS = ["👍", "❤️", "😂", "😮", "😢"]

# ================= XỬ LÝ DATABASE (FIX LỖI SSL) =================
@st.cache_resource
def get_connection_pool():
    """
    Sử dụng ThreadedConnectionPool và Keepalives để duy trì kết nối SSL tới Supabase.
    """
    try:
        return psycopg2.pool.ThreadedConnectionPool(
            1, 20, # Tối thiểu 1, tối đa 20 kết nối
            host=st.secrets["DB_HOST"],
            dbname=st.secrets["DB_NAME"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            port=int(st.secrets["DB_PORT"]),
            sslmode="require",
            connect_timeout=10,
            # Cấu hình Keepalives: Giải pháp đặc trị lỗi "SSL connection closed unexpectedly"
            keepalives=1,
            keepalives_idle=30,      # Kiểm tra sau 30 giây nhàn rỗi
            keepalives_interval=10,  # Khoảng cách giữa các lần thử
            keepalives_count=5       # Đóng kết nối sau 5 lần thất bại
        )
    except Exception as e:
        st.error(f"❌ Lỗi kết nối Database: {e}")
        return None

@contextlib.contextmanager
def get_db_connection():
    """
    Hàm kiểm tra sức khỏe kết nối (Health Check) trước khi thực thi lệnh.
    """
    pool_obj = get_connection_pool()
    conn = None
    if pool_obj:
        try:
            conn = pool_obj.getconn()
            # Thực hiện kiểm tra nhanh (Ping) để đảm bảo SSL không bị ngắt ngầm
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            yield conn
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            # Nếu phát hiện kết nối đã chết, xóa bỏ kết nối này khỏi pool và báo lỗi nhẹ
            if conn:
                pool_obj.putconn(conn, close=True)
            conn = None
            st.warning("⚠️ Đang thiết lập lại kết nối bảo mật...")
            yield None
        except Exception as e:
            if conn: pool_obj.putconn(conn)
            conn = None
            raise e
        finally:
            if conn:
                pool_obj.putconn(conn)
    else:
        yield None

@st.cache_data(ttl=5, show_spinner=False)
def fetch_posts(category_filter, search_term):
    """
    Tải danh sách bài viết với cơ chế Cache 5 giây để giảm tải.
    """
    query = "SELECT id, title, content, image, author, created_at, category FROM posts ORDER BY created_at DESC"
    with get_db_connection() as conn:
        if conn:
            cur = conn.cursor()
            cur.execute(query)
            all_posts = cur.fetchall()
            cur.close()
            
            filtered = []
            for p in all_posts:
                if category_filter != "Tất cả" and p[6] != category_filter: continue
                if search_term and not any(search_term.lower() in str(f).lower() for f in [p[1], p[2], p[4]]): continue
                filtered.append(p)
            return filtered
    return []

# ================= THÀNH PHẦN GIAO DIỆN =================
@st.fragment
def reaction_area(post_id):
    """
    Khu vực cảm xúc: Chỉ hiện các icon đã có người bấm + Nút Popover để thêm.
    """
    with get_db_connection() as conn:
        if not conn: return
        cur = conn.cursor()
        
        # Lấy các cảm xúc hiện tại
        cur.execute("SELECT emoji, count FROM reactions WHERE post_id=%s AND count > 0", (post_id,))
        active_reacts = dict(cur.fetchall())
        
        # Sắp xếp hiển thị: Icon hiện có + Nút cộng
        col_widths = [0.18] * len(active_reacts) + [0.3]
        cols = st.columns(col_widths, gap="small")
        
        for i, (emoji, count) in enumerate(active_reacts.items()):
            # Loại bỏ tham số size="small" để tránh lỗi TypeError
            if cols[i].button(f"{emoji} {count}", key=f"react_{post_id}_{emoji}"):
                cur.execute("UPDATE reactions SET count = count + 1 WHERE post_id=%s AND emoji=%s", (post_id, emoji))
                conn.commit()
                st.rerun()
            
        with cols[-1]:
            with st.popover("➕", help="Chọn cảm xúc"):
                p_cols = st.columns(len(EMOJIS))
                for idx, emoji in enumerate(EMOJIS):
                    if p_cols[idx].button(emoji, key=f"popover_{post_id}_{emoji}"):
                        cur.execute("""
                            INSERT INTO reactions (post_id, emoji, count) VALUES (%s, %s, 1)
                            ON CONFLICT (post_id, emoji) DO UPDATE SET count = reactions.count + 1
                        """, (post_id, emoji))
                        conn.commit()
                        st.rerun()
        cur.close()

def display_post_item(post):
    """
    Hàm hiển thị chi tiết bài viết.
    """
    st.markdown(f'<p class="post-title">{post[1]}</p>', unsafe_allow_html=True)
    st.caption(f"📂 {post[6]} | ✍️ {post[4]} | 🕒 {post[5].strftime('%d/%m/%Y %H:%M')}")
    
    if post[3]: # Hiển thị ảnh nếu có
        img_path = os.path.join("images", post[3])
        if os.path.exists(img_path):
            st.image(Image.open(img_path), use_container_width=True)
    
    # Xử lý xuống dòng: Thay thế \n bằng space-space-newline trong Markdown
    formatted_content = post[2].replace("\n", "  \n")
    st.markdown(f'<div class="post-content">{formatted_content}</div>', unsafe_allow_html=True)

# ================= ỨNG DỤNG CHÍNH =================
st.sidebar.title("🎮 Blog Menu")
app_mode = st.sidebar.radio("Chọn chức năng:", ["📖 Bản tin", "✍️ Viết bài mới", "⚙️ Quản trị"])

# ----------------- 📖 BẢN TIN -----------------
if app_mode == "📖 Bản tin":
    st.header("📖 Bản tin cộng đồng")
    c1, c2 = st.columns([1, 1])
    with c1: filter_cat = st.selectbox("🗂️ Chủ đề", CATEGORIES)
    with c2: search_txt = st.text_input("🔍 Tìm kiếm bài viết...")

    with st.spinner('Đang tải bài viết...'):
        posts = fetch_posts(filter_cat, search_txt)

    if posts:
        for p in posts:
            with st.container(border=True):
                display_post_item(p)
                reaction_area(p[0])
                
                with st.expander(f"💬 Xem bình luận"):
                    with get_db_connection() as conn:
                        if conn:
                            c_cur = conn.cursor()
                            c_cur.execute("SELECT author, content, created_at FROM comments WHERE post_id=%s ORDER BY created_at ASC", (p[0],))
                            for c in c_cur.fetchall():
                                st.markdown(f"**{c[0]}**: {c[1]} <small style='color:gray'>({c[2].strftime('%H:%M')})</small>", unsafe_allow_html=True)
                            c_cur.close()

                    with st.form(key=f"comment_f_{p[0]}", clear_on_submit=True):
                        user_name = st.text_input("Tên của bạn", "Ẩn danh")
                        user_comment = st.text_area("Nội dung")
                        if st.form_submit_button("Gửi bình luận"):
                            if user_comment.strip():
                                with get_db_connection() as conn:
                                    if conn:
                                        c_cur = conn.cursor()
                                        c_cur.execute("INSERT INTO comments (post_id, author, content) VALUES (%s, %s, %s)", (p[0], user_name, user_comment))
                                        conn.commit()
                                        c_cur.close()
                                        st.rerun()
    else:
        st.info("Hiện chưa có bài viết nào phù hợp.")

# ----------------- ✍️ VIẾT BÀI MỚI -----------------
elif app_mode == "✍️ Viết bài mới":
    st.header("✍️ Tạo bài viết mới")
    with st.form("new_post_f"):
        t_title = st.text_input("Tiêu đề bài viết (*)")
        t_cat = st.selectbox("Chủ đề", VALID_CATEGORIES)
        t_author = st.text_input("Tên tác giả", "Ẩn danh")
        t_content = st.text_area("Nội dung bài viết", height=300, help="Dùng phím Enter để xuống dòng thoải mái.")
        t_image = st.file_uploader("Đính kèm hình ảnh", type=['jpg', 'png', 'jpeg'])
        
        if st.form_submit_button("🚀 Xuất bản ngay"):
            if t_title and t_content:
                with st.spinner('Đang lưu bài viết...'):
                    saved_img_name = None
                    if t_image:
                        saved_img_name = f"{int(time.time())}_{t_image.name}"
                        with open(os.path.join("images", saved_img_name), "wb") as f:
                            f.write(t_image.getbuffer())
                    
                    with get_db_connection() as conn:
                        if conn:
                            cur = conn.cursor()
                            cur.execute("INSERT INTO posts (title, content, image, author, category) VALUES (%s, %s, %s, %s, %s)", (t_title, t_content, saved_img_name, t_author, t_cat))
                            conn.commit()
                            cur.close()
                            fetch_posts.clear()
                            st.success("🎉 Chúc mừng! Bài viết của bạn đã được đăng.")
            else:
                st.error("Tiêu đề và Nội dung không được để trống!")

# ----------------- ⚙️ QUẢN TRỊ -----------------
elif app_mode == "⚙️ Quản trị":
    st.header("⚙️ Khu vực quản trị")
    access_code = st.text_input("Mã bảo mật", type="password")
    
    if access_code == st.secrets.get("ADMIN_PASSWORD", "123456"):
        with get_db_connection() as conn:
            if conn:
                cur = conn.cursor()
                if "edit_target_id" not in st.session_state: st.session_state.edit_target_id = None

                if st.session_state.edit_target_id:
                    st.divider()
                    cur.execute("SELECT title, content, category, author FROM posts WHERE id=%s", (st.session_state.edit_target_id,))
                    e_row = cur.fetchone()
                    if e_row:
                        with st.form("edit_post_admin"):
                            new_t = st.text_input("Tiêu đề", value=e_row[0])
                            new_a = st.text_input("Tác giả", value=e_row[3])
                            new_c = st.selectbox("Chủ đề", VALID_CATEGORIES, index=VALID_CATEGORIES.index(e_row[2]) if e_row[2] in VALID_CATEGORIES else 0)
                            new_n = st.text_area("Nội dung", value=e_row[1], height=200)
                            s_col, c_col = st.columns(2)
                            if s_col.form_submit_button("💾 Lưu thay đổi"):
                                cur.execute("UPDATE posts SET title=%s, content=%s, category=%s, author=%s WHERE id=%s", (new_t, new_n, new_c, new_a, st.session_state.edit_target_id))
                                conn.commit()
                                st.session_state.edit_target_id = None
                                fetch_posts.clear()
                                st.rerun()
                            if c_col.form_submit_button("❌ Hủy"):
                                st.session_state.edit_target_id = None
                                st.rerun()

                cur.execute("SELECT id, title, author FROM posts ORDER BY id DESC")
                for row in cur.fetchall():
                    with st.expander(f"ID: {row[0]} | {row[1]}"):
                        st.write(f"Tác giả: {row[2]}")
                        btn_col1, btn_col2 = st.columns(2)
                        if btn_col1.button("📝 Chỉnh sửa", key=f"edit_btn_{row[0]}"):
                            st.session_state.edit_target_id = row[0]
                            st.rerun()
                        if btn_col2.button("🗑️ Xóa bài", key=f"delete_btn_{row[0]}"):
                            cur.execute("DELETE FROM posts WHERE id=%s", (row[0],))
                            conn.commit()
                            fetch_posts.clear()
                            st.rerun()
                cur.close()
    else:
        st.info("Vui lòng nhập mã bảo mật quản trị.")