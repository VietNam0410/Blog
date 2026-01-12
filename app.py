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

# CSS tối ưu hiển thị mượt mà và đồng bộ xuống dòng
st.markdown("""
    <style>
    .stApp { animation: fadeIn 0.4s; }
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    
    .post-content-container { 
        white-space: pre-wrap; 
        word-wrap: break-word;
        line-height: 1.7; 
        margin-bottom: 15px; 
    }
    
    .album-card img {
        object-fit: cover;
        height: 200px !important;
        width: 100%;
        border-radius: 12px;
        transition: 0.3s;
    }
    .album-card img:hover { transform: scale(1.02); }

    div[data-testid="stButton"] button {
        border-radius: 20px !important;
    }
    </style>
""", unsafe_allow_html=True)

if not os.path.exists("images"):
    os.makedirs("images")

# ================= HẰNG SỐ =================
CATEGORIES = ["Tất cả", "Truyền kỳ Thuỷ Dương", "Triết lý nhân sinh", "Meme", "Thơ ca", "Khác"]
VALID_CATEGORIES = CATEGORIES[1:]
EMOJIS = ["👍", "❤️", "😂", "😮", "😢"]
FONTS = {
    "Mặc định": "sans-serif",
    "Chân phương (Serif)": "serif",
    "Hiện đại (Mono)": "monospace",
    "Nghệ thuật": "cursive"
}

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
            connect_timeout=10
        )
    except Exception as e:
        print(f"Lỗi khởi tạo Pool: {e}")
        return None

@contextlib.contextmanager
def get_db_connection():
    pool_obj = get_connection_pool()
    conn = None
    if pool_obj:
        try:
            conn = pool_obj.getconn()
            yield conn
        except Exception as e:
            print(f"Lỗi lấy kết nối: {e}")
            if conn: pool_obj.putconn(conn, close=True)
            yield None
        finally:
            if conn: pool_obj.putconn(conn)
    else:
        yield None

# ================= HÀM HỖ TRỢ PHÂN TRANG =================
def fetch_posts_paginated(cat, search, page, limit=5):
    offset = (page - 1) * limit
    params = []
    conds = []
    if cat != "Tất cả":
        conds.append("category = %s")
        params.append(cat)
    if search:
        conds.append("(title ILIKE %s OR content ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    
    where_sql = " WHERE " + " AND ".join(conds) if conds else ""
    
    with get_db_connection() as conn:
        if conn:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM posts {where_sql}", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(f"SELECT id, title, content, image, author, created_at, category FROM posts {where_sql} ORDER BY created_at DESC LIMIT %s OFFSET %s", 
                        tuple(params + [limit, offset]))
            data = cur.fetchall()
            cur.close()
            return data, (total + limit - 1) // limit
    return [], 0

# ================= ỨNG DỤNG CHÍNH =================
st.sidebar.title("🎮 Blog Menu")
app_mode = st.sidebar.radio("Chọn chức năng:", ["📖 Bản tin", "🖼️ Album ảnh", "✍️ Viết bài mới", "⚙️ Quản trị"])

# ----------------- 📖 BẢN TIN (BAO GỒM REACTION & COMMENT) -----------------
if app_mode == "📖 Bản tin":
    st.header("📖 Bản tin cộng đồng")
    c1, c2 = st.columns(2)
    with c1: f_cat = st.selectbox("🗂️ Chủ đề", CATEGORIES)
    with c2: f_search = st.text_input("🔍 Tìm kiếm bài viết...")

    if 'page' not in st.session_state: st.session_state.page = 1
    posts, total_pages = fetch_posts_paginated(f_cat, f_search, st.session_state.page)

    if posts:
        for p in posts:
            with st.container(border=True):
                st.markdown(f"### {p[1]}")
                st.caption(f"📂 {p[6]} | ✍️ {p[4]} | 🕒 {p[5].strftime('%d/%m/%Y %H:%M')}")
                if p[3] and os.path.exists(os.path.join("images", p[3])):
                    st.image(os.path.join("images", p[3]), use_container_width=True)
                
                # Hiển thị nội dung
                st.markdown(f'<div class="post-content-container">{p[2]}</div>', unsafe_allow_html=True)
                
                # --- Reaction ---
                with get_db_connection() as conn:
                    if conn:
                        cur = conn.cursor()
                        cur.execute("SELECT emoji, count FROM reactions WHERE post_id=%s AND count > 0", (p[0],))
                        reacts = dict(cur.fetchall())
                        r_cols = st.columns([0.15]*len(reacts) + [0.3])
                        for i, (em, count) in enumerate(reacts.items()):
                            if r_cols[i].button(f"{em} {count}", key=f"re_{p[0]}_{em}"):
                                cur.execute("UPDATE reactions SET count = count + 1 WHERE post_id=%s AND emoji=%s", (p[0], em))
                                conn.commit(); st.rerun()
                        with r_cols[-1]:
                            with st.popover("➕"):
                                p_cols = st.columns(5)
                                for idx, em in enumerate(EMOJIS):
                                    if p_cols[idx].button(em, key=f"pop_{p[0]}_{em}"):
                                        cur.execute("INSERT INTO reactions (post_id, emoji, count) VALUES (%s, %s, 1) ON CONFLICT (post_id, emoji) DO UPDATE SET count = reactions.count + 1", (p[0], em))
                                        conn.commit(); st.rerun()

                # --- Bình luận ---
                with st.expander("💬 Bình luận"):
                    with get_db_connection() as conn:
                        if conn:
                            c_cur = conn.cursor()
                            c_cur.execute("SELECT author, content, created_at FROM comments WHERE post_id=%s ORDER BY created_at ASC", (p[0],))
                            for c in c_cur.fetchall():
                                st.markdown(f"**{c[0]}**: {c[1]} <small style='color:gray'>({c[2].strftime('%H:%M')})</small>", unsafe_allow_html=True)
                    
                    with st.form(key=f"f_comm_{p[0]}", clear_on_submit=True):
                        u_n = st.text_input("Tên", "Ẩn danh", key=f"un_{p[0]}")
                        u_c = st.text_area("Nội dung", key=f"uc_{p[0]}")
                        if st.form_submit_button("Gửi"):
                            if u_c.strip():
                                with get_db_connection() as conn:
                                    cur = conn.cursor()
                                    cur.execute("INSERT INTO comments (post_id, author, content) VALUES (%s, %s, %s)", (p[0], u_n, u_c))
                                    conn.commit(); st.rerun()

        # Phân trang
        if total_pages > 1:
            st.divider()
            pg1, pg2, pg3 = st.columns([1, 2, 1])
            if st.session_state.page > 1:
                if pg1.button("⬅️ Trước"): st.session_state.page -= 1; st.rerun()
            pg2.markdown(f"<center>Trang {st.session_state.page} / {total_pages}</center>", unsafe_allow_html=True)
            if st.session_state.page < total_pages:
                if pg3.button("Sau ➡️"): st.session_state.page += 1; st.rerun()
    else:
        st.info("Chưa có bài viết nào.")

# ----------------- 🖼️ ALBUM ẢNH -----------------
elif app_mode == "🖼️ Album ảnh":
    st.header("🖼️ Album ảnh cộng đồng")
    with get_db_connection() as conn:
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT image, title, author, created_at FROM posts WHERE image IS NOT NULL ORDER BY created_at DESC")
            photos = cur.fetchall()
            if photos:
                cols = st.columns(3)
                for idx, (img_n, title, author, dt) in enumerate(photos):
                    img_p = os.path.join("images", img_n)
                    if os.path.exists(img_p):
                        with cols[idx % 3]:
                            st.markdown('<div class="album-card">', unsafe_allow_html=True)
                            st.image(img_p, use_container_width=True)
                            with st.expander("ℹ️"):
                                st.write(f"**{title}**\n\n✍️ {author}\n\n📅 {dt.strftime('%d/%m/%Y')}")
                            st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("Album chưa có ảnh.")

# ----------------- ✍️ VIẾT BÀI MỚI (CHỐNG LỖI TOKEN) -----------------
elif app_mode == "✍️ Viết bài mới":
    st.header("✍️ Tạo bài viết mới")
    with st.form("new_post_form", clear_on_submit=True):
        t_title = st.text_input("Tiêu đề bài viết (*)")
        t_cat = st.selectbox("Chủ đề", VALID_CATEGORIES)
        t_author = st.text_input("Tên tác giả", "Ẩn danh")
        
        with st.popover("🎨 Định dạng chữ & màu sắc"):
            col1, col2, col3 = st.columns(3)
            f_color = col1.color_picker("Màu chữ", "#1a1a1a")
            f_family = col2.selectbox("Kiểu chữ", list(FONTS.keys()))
            f_size = col3.selectbox("Cỡ chữ", ["16px", "18px", "22px", "26px"])
        
        t_content = st.text_area("Nội dung bài viết", height=300)
        t_image = st.file_uploader("Đính kèm hình ảnh", type=['jpg', 'png', 'jpeg'])
        
        if st.form_submit_button("🚀 Xuất bản ngay"):
            if t_title and t_content:
                font_css = FONTS[f_family]
                # Sử dụng f-string an toàn không chứa ký tự xuống dòng trực tiếp trong biểu thức
                styled_html = f'<div style="color:{f_color}; font-family:{font_css}; font-size:{f_size};">{t_content}</div>'
                
                img_name = None
                if t_image:
                    img_name = f"{int(time.time())}.jpg"
                    Image.open(t_image).convert("RGB").save(os.path.join("images", img_name), "JPEG", quality=85)
                
                with get_db_connection() as conn:
                    if conn:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO posts (title, content, image, author, category) VALUES (%s, %s, %s, %s, %s)", 
                                   (t_title, styled_html, img_name, t_author, t_cat))
                        conn.commit()
                        st.success("🎉 Đăng bài thành công!"); time.sleep(1); st.rerun()

# ----------------- ⚙️ QUẢN TRỊ -----------------
elif app_mode == "⚙️ Quản trị":
    st.header("⚙️ Khu vực quản trị")
    access_code = st.text_input("Mã bảo mật", type="password")
    if access_code == st.secrets.get("ADMIN_PASSWORD", "123456"):
        with get_db_connection() as conn:
            if conn:
                cur = conn.cursor()
                if "e_id" not in st.session_state: st.session_state.e_id = None
                
                if st.session_state.e_id:
                    cur.execute("SELECT title, content, category, author FROM posts WHERE id=%s", (st.session_state.e_id,))
                    e = cur.fetchone()
                    if e:
                        with st.form("edit_f"):
                            new_t = st.text_input("Tiêu đề", value=e[0])
                            new_a = st.text_input("Tác giả", value=e[3])
                            new_c = st.selectbox("Chủ đề", VALID_CATEGORIES, index=VALID_CATEGORIES.index(e[2]) if e[2] in VALID_CATEGORIES else 0)
                            new_n = st.text_area("Nội dung", value=e[1], height=200)
                            if st.form_submit_button("Cập nhật"):
                                cur.execute("UPDATE posts SET title=%s, content=%s, category=%s, author=%s WHERE id=%s", (new_t, new_n, new_c, new_a, st.session_state.e_id))
                                conn.commit(); st.session_state.e_id = None; st.rerun()

                cur.execute("SELECT id, title FROM posts ORDER BY id DESC")
                for row in cur.fetchall():
                    with st.expander(f"ID: {row[0]} - {row[1]}"):
                        c1, c2 = st.columns(2)
                        if c1.button("📝 Sửa", key=f"edit_{row[0]}"):
                            st.session_state.e_id = row[0]; st.rerun()
                        if c2.button("🗑️ Xóa", key=f"del_{row[0]}"):
                            cur.execute("DELETE FROM posts WHERE id=%s", (row[0],))
                            conn.commit(); st.rerun()