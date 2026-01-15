import streamlit as st
from datetime import datetime
import time

# [MODULE IMPORTS]
from utils.db_api import load_nodes, load_trash, restore_node, permanent_delete, load_trash, get_workbook
from modules.stock_ui import render_stock_page
# render_node_page와 render_sidebar를 모두 가져옵니다.
from modules.node_ui import render_node_page, render_sidebar

# ==========================================
# 1. PAGE & STYLE CONFIGURATION
# ==========================================
st.set_page_config(layout="wide", page_title="나만의 지식 센터", page_icon="🔗")

st.markdown("""
<style>
    /* [1] 기본 앱 스타일 */
    .stApp { background-color: #000000 !important; color: #ffffff !important; }
    header { visibility: hidden; }
    .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
    
    /* [2] Iframe (그래프) 스타일 */
    iframe { background-color: #000000 !important; border: 1px solid #444 !important; border-radius: 12px; }
    
    /* [3] 입력 폼 스타일 */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { 
        background-color: #1a1a1a !important; color: white !important; border: 1px solid #333 !important; 
    }
    
    /* [4] 멀티셀렉트 스타일 */
    .stMultiSelect div[data-baseweb="select"] > div { background-color: #111 !important; border-color: #333 !important; color: white !important; }
    .stMultiSelect div[data-baseweb="tag"] { background-color: #00ADB5 !important; color: black !important; }
    
    /* [5] 메뉴 및 버튼 스타일 */
    div.stButton > button { 
        background-color: transparent !important; 
        border: 1px solid transparent !important; 
        color: #fff !important; 
        width: 100%; height: auto; min-height: 38px; min-width: 0px !important;
        padding: 0px !important; margin: 0px !important;
        display: flex !important; justify-content: center !important; align-items: center !important; line-height: 1 !important;
    }
    div.stButton > button p { width: 100% !important; text-align: center !important; margin: 0 !important; color: #ffffff !important; }
    div.stButton > button:hover { background-color: #222 !important; border: 1px solid #444 !important; color: #00ADB5 !important; border-radius: 8px; }
    div.stButton > button:hover p { color: #00ADB5 !important; }
    div.stButton > button[kind="primary"] { background-color: #E03131 !important; border: none !important; color: white !important; }
    div.stButton > button[kind="primary"]:hover { background-color: #c92a2a !important; }
    
    /* [6] 헤더 및 리스트 스타일 */
    .list-header-row { display: flex; align-items: center; height: 35px; font-weight: bold; color: #888; font-size: 0.85rem; }
    .list-content-row { display: flex; align-items: center; height: 46px; }
    .col-center { justify-content: center; width: 100%; display: flex; }
    .tight-header { font-size: 1.5rem; font-weight: 600; margin-bottom: 0px !important; padding-bottom: 0px !important; }
    .tight-hr { margin-top: 5px !important; margin-bottom: 15px !important; border: 0; border-top: 1px solid #333; }
    div[data-testid="stPopover"] > button { background-color: transparent !important; border: 1px solid transparent !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SESSION STATE
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

# --- 설정 로드 ---
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

# --- 데이터 로드 ---
if not st.session_state['nodes_db']: 
    st.session_state['nodes_db'] = load_nodes()

# ==========================================
# 3. LOGIN & MAIN LAYOUT
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
    # [LAYOUT] 좌측(사이드바) : 우측(메인)
    left, main = st.columns([0.8, 5.2])
    
    # [1] 공통 사이드바 렌더링 (어떤 메뉴든 항상 보임)
    render_sidebar(left)
    
    # [2] 메인 컨텐츠 영역
    with main:
        # 메뉴 바 (우측 정렬)
        menu_cols = st.columns([6, 1, 1, 1, 1]) 
        
        # Node 메뉴
        with menu_cols[1]:
            with st.popover("Node", use_container_width=True):
                if st.button("Graph", key="nav_node_graph", use_container_width=True): 
                    st.session_state['menu_mode'] = "Knowledge Graph"; st.rerun()
                if st.button("List", key="nav_node_list", use_container_width=True): 
                    st.session_state['menu_mode'] = "List View"; st.rerun()
                if st.button("Add", key="nav_node_add", use_container_width=True): 
                    st.session_state['menu_mode'] = "Add Data"; st.rerun()
        
        # Stock 메뉴
        with menu_cols[2]:
            with st.popover("Stock", use_container_width=True):
                if st.button("List", key="nav_stock_list", use_container_width=True): 
                    st.session_state['menu_mode'] = "Stock Analysis"
                    st.session_state['stock_view_mode'] = "list"
                    st.rerun()
                if st.button("Add", key="nav_stock_add", use_container_width=True): 
                    st.session_state['menu_mode'] = "Stock Analysis"
                    st.session_state['stock_view_mode'] = "add"
                    st.session_state['edit_target_id'] = None
                    st.rerun()

        # Trash & Out
        if menu_cols[3].button("Trash", key="nav_trash", use_container_width=True): 
            st.session_state['menu_mode'] = "Trash Can"; st.rerun()
        if menu_cols[4].button("Out", key="nav_out", use_container_width=True): 
            st.session_state['logged_in'] = False; st.rerun()

        # 헤더 표시
        st.markdown(f"<div class='tight-header' style='text-align: right;'>📂 {st.session_state['menu_mode']}</div>", unsafe_allow_html=True)
        st.markdown("<hr class='tight-hr'>", unsafe_allow_html=True)

        # 라우팅 (페이지 연결)
        current_mode = st.session_state['menu_mode']

        if current_mode in ["Knowledge Graph", "List View", "Add Data"]:
            # [수정] 메인 컬럼만 넘김 (사이드바는 이미 그렸으므로)
            render_node_page(main)
            
        elif current_mode == "Stock Analysis":
            if render_stock_page: 
                # Stock 페이지는 메인 컬럼 안에서 스스로를 그립니다.
                render_stock_page()
            else: st.warning("Stock Module Error")
            
        elif current_mode == "Trash Can":
            # Trash Page Logic
            st.markdown("### 🗑️ Trash Can (Recycle Bin)")
            st.caption("삭제된 노드는 여기에 30일간 보관됩니다.")
            trash_data = load_trash()
            if trash_data:
                now = datetime.now()
                for row in trash_data:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([7, 1.5, 1.5])
                        del_date_str = str(row.get('deleted_at', ''))
                        try:
                            del_date = datetime.strptime(del_date_str, "%y-%m-%d %H:%M")
                            days_left = 30 - (now - del_date).days
                        except: days_left = 0
                        c1.markdown(f"**{row['label']}** :gray[| {row['keywords']}]")
                        c1.caption(f"Deleted: {del_date_str} (남은 기간: {days_left}일)")
                        if c2.button("♻️ Restore", key=f"res_{row['id']}", use_container_width=True):
                            restore_node(row)
                            st.session_state['nodes_db'].append({
                                "id": str(row['id']), "label": row['label'], "group": row['group'], 
                                "summary": row['summary'], "keywords": str(row['keywords']).split(','), "timestamp": row['created_at']
                            })
                            st.success("Restored!"); time.sleep(0.5); st.rerun()
                        if c3.button("🔥 Delete", key=f"per_del_{row['id']}", type="primary", use_container_width=True):
                            permanent_delete(row['id']); st.warning("Permanently Deleted."); time.sleep(0.5); st.rerun()
            else: st.info("휴지통이 비어있습니다.")
