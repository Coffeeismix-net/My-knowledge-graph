import streamlit as st
from datetime import datetime
import time

# [MODULE IMPORTS]
from utils.db_api import load_nodes, load_trash, restore_node, permanent_delete, get_workbook, load_stock_trash, restore_stock, permanent_delete_stock
from modules.stock_ui import render_stock_page
from modules.node_ui import render_node_page, render_sidebar

# ==========================================
# CONFIG
# ==========================================
st.set_page_config(layout="wide", page_title="나만의 지식 센터", page_icon="🔗")

st.markdown("""
<style>
    .stApp { background-color: #000000 !important; color: #ffffff !important; }
    header { visibility: hidden; }
    .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
    iframe { background-color: #000000 !important; border: 1px solid #444 !important; border-radius: 12px; }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { background-color: #1a1a1a !important; color: white !important; border: 1px solid #333 !important; }
    .stMultiSelect div[data-baseweb="select"] > div { background-color: #111 !important; border-color: #333 !important; color: white !important; }
    .stMultiSelect div[data-baseweb="tag"] { background-color: #00ADB5 !important; color: black !important; }
    div.stButton > button { background-color: transparent !important; border: 1px solid transparent !important; color: #fff !important; width: 100%; height: auto; min-height: 38px; min-width: 0px !important; padding: 0px !important; margin: 0px !important; display: flex !important; justify-content: center !important; align-items: center !important; line-height: 1 !important; }
    div.stButton > button p { width: 100% !important; text-align: center !important; margin: 0 !important; color: #ffffff !important; }
    div.stButton > button:hover { background-color: #222 !important; border: 1px solid #444 !important; color: #00ADB5 !important; border-radius: 8px; }
    div.stButton > button:hover p { color: #00ADB5 !important; }
    div.stButton > button[kind="primary"] { background-color: #E03131 !important; border: none !important; color: white !important; }
    div.stButton > button[kind="primary"]:hover { background-color: #c92a2a !important; }
    .list-header-row { display: flex; align-items: center; height: 35px; font-weight: bold; color: #888; font-size: 0.85rem; }
    .list-content-row { display: flex; align-items: center; height: 46px; }
    .col-center { justify-content: center; width: 100%; display: flex; }
    .tight-header { font-size: 1.5rem; font-weight: 600; margin-bottom: 0px !important; padding-bottom: 0px !important; }
    .tight-hr { margin-top: 5px !important; margin-bottom: 15px !important; border: 0; border-top: 1px solid #333; }
    div[data-testid="stPopover"] > button { background-color: transparent !important; border: 1px solid transparent !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# SESSION STATE
# ==========================================
def init_session_state():
    defaults = {
        'logged_in': False, 'menu_mode': "Knowledge Graph", 'nodes_db': [], 'workspace_nodes': [],
        'selected_keyword': None, 'temp_analysis': None, 'search_history': [], 'last_selection': None, 'card_stack': [],
        'phy_active': True, 'phy_damping': 0.9, 'phy_repulsion': -1000, 'phy_len': 200, 'phy_overlap': True,
        'settings_loaded': False, 'stock_view_mode': 'list'
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

init_session_state()

# Settings Load
if not st.session_state['settings_loaded']:
    wb = get_workbook()
    if wb:
        try:
            ws = wb.worksheet("settings")
            records = ws.get_all_records()
            settings_map = {str(r['key']): str(r['value']) for r in records}
            if 'phy_active' in settings_map: st.session_state['phy_active'] = settings_map['phy_active'].strip().lower() == 'true'
            if 'phy_damping' in settings_map: st.session_state['phy_damping'] = float(settings_map['phy_damping'])
            if 'phy_repulsion' in settings_map: st.session_state['phy_repulsion'] = int(settings_map['phy_repulsion'])
            if 'phy_len' in settings_map: st.session_state['phy_len'] = int(settings_map['phy_len'])
            if 'phy_overlap' in settings_map: st.session_state['phy_overlap'] = settings_map['phy_overlap'].strip().lower() == 'true'
            st.session_state['settings_loaded'] = True
        except: pass

if not st.session_state['nodes_db']: st.session_state['nodes_db'] = load_nodes()

# ==========================================
# MAIN
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<br><br><h1 style='text-align: center;'>🔗 나만의 지식 센터</h1><br>", unsafe_allow_html=True)
    _, c, _ = st.columns([1,1,1])
    with c:
        with st.form("login"):
            st.markdown("### User Login")
            uid = st.text_input("ID"); upw = st.text_input("PW", type="password")
            if st.form_submit_button("Login", type="primary", use_container_width=True):
                if "login" in st.secrets and uid == st.secrets["login"]["id"] and upw == st.secrets["login"]["pw"]:
                    st.session_state['logged_in'] = True; st.rerun()
                else: st.error("Check ID/PW")
else:
    left, main = st.columns([0.8, 5.2])
    render_sidebar(left)
    
    with main:
        menu_cols = st.columns([6, 1, 1, 1, 1]) 
        with menu_cols[1]:
            with st.popover("Node", use_container_width=True):
                if st.button("Graph", key="nav_n_g", use_container_width=True): st.session_state['menu_mode'] = "Knowledge Graph"; st.rerun()
                if st.button("List", key="nav_n_l", use_container_width=True): st.session_state['menu_mode'] = "List View"; st.rerun()
                if st.button("Add", key="nav_n_a", use_container_width=True): st.session_state['menu_mode'] = "Add Data"; st.rerun()
        with menu_cols[2]:
            with st.popover("Stock", use_container_width=True):
                if st.button("List", key="nav_s_l", use_container_width=True): st.session_state['menu_mode'] = "Stock Analysis"; st.session_state['stock_view_mode'] = "list"; st.rerun()
                if st.button("Add", key="nav_s_a", use_container_width=True): st.session_state['menu_mode'] = "Stock Analysis"; st.session_state['stock_view_mode'] = "add"; st.session_state['edit_target_id'] = None; st.rerun()
        if menu_cols[3].button("Trash", key="nav_trash", use_container_width=True): st.session_state['menu_mode'] = "Trash Can"; st.rerun()
        if menu_cols[4].button("Out", key="nav_out", use_container_width=True): st.session_state['logged_in'] = False; st.rerun()

        st.markdown(f"<div class='tight-header' style='text-align: right;'>📂 {st.session_state['menu_mode']}</div>", unsafe_allow_html=True)
        st.markdown("<hr class='tight-hr'>", unsafe_allow_html=True)

        current_mode = st.session_state['menu_mode']

        if current_mode in ["Knowledge Graph", "List View", "Add Data"]:
            render_node_page(main)
            
        elif current_mode == "Stock Analysis":
            if render_stock_page: render_stock_page()
            else: st.warning("Stock Module Error")
            
        elif current_mode == "Trash Can":
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
                            st.session_state['nodes_db'].append({"id": str(row['id']), "label": row['label'], "group": row['group'], "summary": row['summary'], "keywords": str(row['keywords']).split(','), "timestamp": row['created_at']})
                            st.success("복구됨"); time.sleep(0.5); st.rerun()
                        if c3.button("🔥 삭제", key=f"del_n_{row['id']}", type="primary", use_container_width=True):
                            permanent_delete(row['id']); st.warning("영구 삭제됨"); time.sleep(0.5); st.rerun()
            else: st.caption("비어있음")
            
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
                            # 세션도 갱신 (리스트에 바로 뜨게)
                            if 'stock_db' in st.session_state:
                                st.session_state['stock_db'].append(row)
                            st.success("복구됨"); time.sleep(0.5); st.rerun()
                        if c3.button("🔥 삭제", key=f"del_s_{row['id']}", type="primary", use_container_width=True):
                            permanent_delete_stock(row['id']); st.warning("영구 삭제됨"); time.sleep(0.5); st.rerun()
            else: st.caption("비어있음")
