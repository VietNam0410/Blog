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

# CSS tùy chỉnh để tối ưu hiển thị, Reaction và Album
st.markdown("""
    <style>
    .post-content {
        white-space: pre-wrap;
        word-wrap: break-word;
        font-family: 'Source Sans Pro', sans-serif;
        line-height: 1.7;
        margin-bottom: 15px;
        color: #1a1a1a;
        font-size: 1.05rem;
    }
    
    /* Tối ưu ảnh trong Album để đều nhau */
    .album-card img {
        object-fit: cover;
        height: 200px !important;
        width: 100%;
        border-radius: 10px;
    }

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

    .post-title {
        font-weight: 700;
        font-size: 1.6rem;
        margin-bottom: 5px;
        color: #0e1117;
    }
    
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

# ================= XỬ LÝ DATABASE =================
@st.cache_resource
def get_connection_pool():
    try:
        return psycopg2.pool.ThreadedConnectionPool(
            1, 20,
            host=st.secrets["DB_HOST"],
            dbname=st.secrets["DB_NAME"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            port=int(st.secrets["DB_PORT"]),
            sslmode="require",
            connect_timeout=10,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5
        )
    except Exception as e:
        st.error(f"❌ Lỗi kết nối Database: {e}")
        return None

@contextlib.contextmanager
def get_db_connection():
    pool_obj = get_connection_pool()
    conn = None
    if pool_obj:
        try:
            conn = pool_obj.getconn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            yield conn
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            if conn: pool_obj.putconn(conn, close=True)
            st.warning("⚠️ Đang thiết lập lại kết nối bảo mật...")
            yield None
        except Exception as e:
            if conn: pool_obj.putconn(conn)
            raise e
        finally:
            if conn: pool_obj.putconn(conn)
    else:
        yield None

@st.cache_data(ttl=5, show_spinner=False)
def fetch_posts(category_filter, search_term):
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
    with get_db_connection() as conn:
        if not conn: return
        cur = conn.cursor()
        cur.execute("SELECT emoji, count FROM reactions WHERE post_id=%s AND count > 0", (post_id,))
        active_reacts = dict(cur.fetchall())
        
        col_widths = [0.18] * len(active_reacts) + [0.3]
        cols = st.columns(col_widths, gap="small")
        
        for i, (emoji, count) in enumerate(active_reacts.items()):
            if cols[i].button(f"{emoji} {count}", key=f"react_{post_id}_{emoji}"):
                cur.execute("UPDATE reactions SET count = count + 1 WHERE post_id=%s AND emoji=%s", (post_id, emoji))
                conn.commit()
                st.rerun()
            
        with cols[-1]:
            with st.popover("➕"):
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
    st.markdown(f'<p class="post-title">{post[1]}</p>', unsafe_allow_html=True)
    st.caption(f"📂 {post[6]} | ✍️ {post[4]} | 🕒 {post[5].strftime('%d/%m/%Y %H:%M')}")
    if post[3]:
        img_path = os.path.join("images", post[3])
        if os.path.exists(img_path):
            st.image(Image.open(img_path), use_container_width=True)
    formatted_content = post[2].replace("\n", "  \n")
    st.markdown(f'<div class="post-content">{formatted_content}</div>', unsafe_allow_html=True)

# ================= ỨNG DỤNG CHÍNH =================
st.sidebar.title("🎮 Blog Menu")
app_mode = st.sidebar.radio("Chọn chức năng:", ["📖 Bản tin", "🖼️ Album ảnh", "✍️ Viết bài mới", "⚙️ Quản trị"])

# ----------------- 📖 BẢN TIN -----------------
if app_mode == "📖 Bản tin":
    st.header("📖 Bản tin cộng đồng")
    c1, c2 = st.columns([1, 1])
    with c1: filter_cat = st.selectbox("🗂️ Chủ đề", CATEGORIES)
    with c2: search_txt = st.text_input("🔍 Tìm kiếm bài viết...")

    posts = fetch_posts(filter_cat, search_txt)
    if posts:
        for p in posts:
            with st.container(border=True):
                display_post_item(p)
                reaction_area(p[0])
                with st.expander("💬 Xem bình luận"):
                    with get_db_connection() as conn:
                        if conn:
                            c_cur = conn.cursor()
                            c_cur.execute("SELECT author, content, created_at FROM comments WHERE post_id=%s ORDER BY created_at ASC", (p[0],))
                            for c in c_cur.fetchall():
                                st.markdown(f"**{c[0]}**: {c[1]} <small style='color:gray'>({c[2].strftime('%H:%M')})</small>", unsafe_allow_html=True)
                            c_cur.close()

                    with st.form(key=f"comment_f_{p[0]}", clear_on_submit=True):
                        u_name = st.text_input("Tên", "Ẩn danh", key=f"name_{p[0]}")
                        u_comm = st.text_area("Nội dung", key=f"comm_{p[0]}")
                        if st.form_submit_button("Gửi"):
                            if u_comm.strip():
                                with get_db_connection() as conn:
                                    if conn:
                                        c_cur = conn.cursor()
                                        c_cur.execute("INSERT INTO comments (post_id, author, content) VALUES (%s, %s, %s)", (p[0], u_name, u_comm))
                                        conn.commit()
                                        st.rerun()
    else:
        st.info("Chưa có bài viết nào.")

# ----------------- 🖼️ ALBUM ẢNH (TÍNH NĂNG MỚI) -----------------
elif app_mode == "🖼️ Album ảnh":
    st.header("🖼️ Album ảnh cộng đồng")
    with get_db_connection() as conn:
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT image, title, author, created_at FROM posts WHERE image IS NOT NULL ORDER BY created_at DESC")
            photos = cur.fetchall()
            cur.close()

            if photos:
                # Tạo lưới 3 cột cho album
                cols = st.columns(3)
                for idx, (img_name, title, author, dt) in enumerate(photos):
                    img_path = os.path.join("images", img_name)
                    if os.path.exists(img_path):
                        with cols[idx % 3]:
                            st.markdown('<div class="album-card">', unsafe_allow_html=True)
                            st.image(Image.open(img_path), use_container_width=True)
                            with st.expander("ℹ️"):
                                st.write(f"**{title}**")
                                st.caption(f"✍️ {author}")
                                st.caption(f"📅 {dt.strftime('%d/%m/%Y')}")
                            st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("Hiện album chưa có ảnh nào.")

# ----------------- ✍️ VIẾT BÀI MỚI -----------------
elif app_mode == "✍️ Viết bài mới":
    st.header("✍️ Tạo bài viết mới")
    with st.form("new_post_f"):
        t_title = st.text_input("Tiêu đề bài viết (*)")
        t_cat = st.selectbox("Chủ đề", VALID_CATEGORIES)
        t_author = st.text_input("Tên tác giả", "Ẩn danh")
        t_content = st.text_area("Nội dung bài viết", height=300)
        t_image = st.file_uploader("Đính kèm hình ảnh", type=['jpg', 'png', 'jpeg'])
        
        if st.form_submit_button("🚀 Xuất bản ngay"):
            if t_title and t_content:
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
                        fetch_posts.clear()
                        st.success("🎉 Bài viết đã được đăng!")
            else:
                st.error("Thiếu tiêu đề hoặc nội dung!")

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
                    cur.execute("SELECT title, content, category, author FROM posts WHERE id=%s", (st.session_state.edit_target_id,))
                    e_row = cur.fetchone()
                    if e_row:
                        with st.form("edit_admin"):
                            new_t = st.text_input("Tiêu đề", value=e_row[0])
                            new_a = st.text_input("Tác giả", value=e_row[3])
                            new_c = st.selectbox("Chủ đề", VALID_CATEGORIES, index=VALID_CATEGORIES.index(e_row[2]) if e_row[2] in VALID_CATEGORIES else 0)
                            new_n = st.text_area("Nội dung", value=e_row[1])
                            if st.form_submit_button("Lưu"):
                                cur.execute("UPDATE posts SET title=%s, content=%s, category=%s, author=%s WHERE id=%s", (new_t, new_n, new_c, new_a, st.session_state.edit_target_id))
                                conn.commit()
                                st.session_state.edit_target_id = None
                                fetch_posts.clear()
                                st.rerun()

                cur.execute("SELECT id, title FROM posts ORDER BY id DESC")
                for row in cur.fetchall():
                    with st.expander(f"ID: {row[0]} - {row[1]}"):
                        if st.button("📝 Sửa", key=f"e_{row[0]}"):
                            st.session_state.edit_target_id = row[0]
                            st.rerun()
                        if st.button("🗑️ Xóa", key=f"d_{row[0]}"):
                            cur.execute("DELETE FROM posts WHERE id=%s", (row[0],))
                            conn.commit()
                            fetch_posts.clear()
                            st.rerun()
                cur.close()
    else:
        st.info("Nhập mã để truy cập quản trị.")