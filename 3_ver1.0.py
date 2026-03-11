"""
app.py — 나만의 지식 센터 (Optimized)
메인 엔트리포인트. CSS 주입, 세션 초기화, 라우팅을 담당.
"""
import streamlit as st
import time

# [MODULE IMPORTS]
from utils.db_node import load_nodes, load_trash, restore_node, permanent_delete
from utils.db_common import load_settings_from_db
from utils.db_stock import load_stock_trash, restore_stock, permanent_delete_stock
from utils.style import GLOBAL_CSS
from modules.stock_ui import render_stock_page
from modules.node_ui import render_node_page, render_sidebar
from modules.valuechain_ui import render_valuechain_page

# ==========================================
# CONFIG
# ==========================================
st.set_page_config(layout="wide", page_title="나만의 지식 센터", page_icon="🔗")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ==========================================
# SESSION STATE (전체 키를 여기서 일원 관리)
# ==========================================
_DEFAULTS = {
    # Auth
    'logged_in': False,
    # Navigation
    'menu_mode': "Knowledge Graph",
    # Node
    'nodes_db': [],
    'workspace_nodes': [],
    'selected_keyword': None,
    'temp_analysis': None,
    'search_history': [],
    'last_selection': None,
    'card_stack': [],
    'node_form_id': 0,
    'ai_result_summary': "",
    'ai_result_kw': "",
    # Physics
    'phy_active': True,
    'phy_damping': 0.9,
    'phy_repulsion': -1000,
    'phy_len': 200,
    'phy_overlap': True,
    'settings_loaded': False,
    # Stock
    'stock_view_mode': 'list',
    'selected_doc_ids': [],
    'edit_target_id': None,
    # Value Chain
    'vc_mode': 'list',
    'vc_list': None,  # None = not loaded yet
    'selected_vc_id': None,
    'show_original_img': False,
    'analyzed_json': "",
    'analyzed_img_b64': "",
}

for key, default in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

# 설정 로드 (한 번만)
load_settings_from_db()

# 노드 로드 (한 번만)
if not st.session_state['nodes_db']:
    st.session_state['nodes_db'] = load_nodes()

# ==========================================
# LOGIN
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<br><br><h1 style='text-align: center;'>🔗 나만의 지식 센터</h1><br>", unsafe_allow_html=True)
    _, center, _ = st.columns([1, 1, 1])
    with center:
        with st.form("login"):
            st.markdown("### User Login")
            uid = st.text_input("ID")
            upw = st.text_input("PW", type="password")
            if st.form_submit_button("Login", type="primary", use_container_width=True):
                if ("login" in st.secrets
                    and uid == st.secrets["login"]["id"]
                    and upw == st.secrets["login"]["pw"]):
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("Check ID/PW")

# ==========================================
# MAIN APP
# ==========================================
else:
    left, main = st.columns([0.8, 5.2])
    render_sidebar(left)

    with main:
        # [MENU BAR]
        menu_cols = st.columns([5, 1, 1, 1, 1, 1])

        # Node Menu
        with menu_cols[1]:
            with st.popover("Node", use_container_width=True):
                if st.button("Graph", key="nav_n_g", use_container_width=True):
                    st.session_state['menu_mode'] = "Knowledge Graph"
                    st.rerun()
                if st.button("List", key="nav_n_l", use_container_width=True):
                    st.session_state['menu_mode'] = "List View"
                    st.rerun()
                if st.button("Add", key="nav_n_a", use_container_width=True):
                    st.session_state['menu_mode'] = "Add Data"
                    st.rerun()

        # Stock Menu
        with menu_cols[2]:
            with st.popover("Stock", use_container_width=True):
                if st.button("List", key="nav_s_l", use_container_width=True):
                    st.session_state['menu_mode'] = "Stock Analysis"
                    st.session_state['stock_view_mode'] = "list"
                    st.rerun()
                if st.button("Add", key="nav_s_a", use_container_width=True):
                    st.session_state['menu_mode'] = "Stock Analysis"
                    st.session_state['stock_view_mode'] = "add"
                    st.session_state['edit_target_id'] = None
                    st.rerun()

        # Chain Menu
        with menu_cols[3]:
            with st.popover("Chain", use_container_width=True):
                if st.button("List", key="nav_vc_l", use_container_width=True):
                    st.session_state['menu_mode'] = "Value Chain"
                    st.session_state['vc_mode'] = 'list'
                    st.rerun()
                if st.button("Add", key="nav_vc_a", use_container_width=True):
                    st.session_state['menu_mode'] = "Value Chain"
                    st.session_state['vc_mode'] = 'add'
                    st.rerun()

        # Trash & Out
        if menu_cols[4].button("Trash", key="nav_trash", use_container_width=True):
            st.session_state['menu_mode'] = "Trash Can"
            st.rerun()
        if menu_cols[5].button("Out", key="nav_out", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

        # Page Header
        st.markdown(
            f"<div class='tight-header' style='text-align: right;'>📂 {st.session_state['menu_mode']}</div>",
            unsafe_allow_html=True
        )
        st.markdown("<hr class='tight-hr'>", unsafe_allow_html=True)

        # ==========================================
        # ROUTING
        # ==========================================
        current_mode = st.session_state['menu_mode']

        if current_mode in ("Knowledge Graph", "List View", "Add Data"):
            render_node_page(main)

        elif current_mode == "Stock Analysis":
            render_stock_page()

        elif current_mode == "Value Chain":
            render_valuechain_page(main)

        elif current_mode == "Trash Can":
            _render_trash_can()

# ==========================================
# TRASH CAN (인라인 정의 — 간단하므로 별도 모듈 불필요)
# ==========================================
def _render_trash_can():
    st.markdown("### 🗑️ 휴지통")

    # [1] Node 휴지통
    st.markdown("#### 1. 지식 그래프 (Nodes)")
    trash_nodes = load_trash()
    if trash_nodes:
        for row in trash_nodes:
            with st.container(border=True):
                c1, c2, c3 = st.columns([7, 1.5, 1.5])
                c1.markdown(f"**{row['label']}** :gray[| {row['keywords']}]")
                c1.caption(f"Deleted: {row['deleted_at']}")
                if c2.button("♻️ 복구", key=f"res_n_{row['id']}", use_container_width=True):
                    restore_node(row)
                    st.session_state['nodes_db'].append({
                        "id": str(row['id']), "label": row['label'],
                        "group": row['group'], "summary": row['summary'],
                        "keywords": str(row['keywords']).split(','),
                        "timestamp": row['created_at']
                    })
                    st.success("복구됨")
                    time.sleep(0.5)
                    st.rerun()
                if c3.button("🔥 삭제", key=f"del_n_{row['id']}", type="primary", use_container_width=True):
                    permanent_delete(row['id'])
                    st.warning("영구 삭제됨")
                    time.sleep(0.5)
                    st.rerun()
    else:
        st.caption("비어있음")

    st.divider()

    # [2] Stock 휴지통
    st.markdown("#### 2. 기업 분석 (Stocks)")
    trash_stocks = load_stock_trash()
    if trash_stocks:
        for row in trash_stocks:
            with st.container(border=True):
                c1, c2, c3 = st.columns([7, 1.5, 1.5])
                c1.markdown(f"**[{row['company']}] {row['title']}**")
                c1.caption(f"Deleted: {row['deleted_at']}")
                if c2.button("♻️ 복구", key=f"res_s_{row['id']}", use_container_width=True):
                    restore_stock(row)
                    if 'stock_db' in st.session_state:
                        st.session_state['stock_db'].append(row)
                    st.success("복구됨")
                    time.sleep(0.5)
                    st.rerun()
                if c3.button("🔥 삭제", key=f"del_s_{row['id']}", type="primary", use_container_width=True):
                    permanent_delete_stock(row['id'])
                    st.warning("영구 삭제됨")
                    time.sleep(0.5)
                    st.rerun()
    else:
        st.caption("비어있음")
