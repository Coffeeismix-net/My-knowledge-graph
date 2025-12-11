import streamlit as st
import pandas as pd
from streamlit_agraph import agraph, Node, Edge, Config
import time
import google.generativeai as genai
import json
import hashlib
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# ==========================================
# 4. UI STYLE & LAYOUT
# ==========================================
st.set_page_config(layout="wide", page_title="나만의 지식 센터", page_icon="🔗")

# ==========================================
# 0. GOOGLE SHEETS CONNECTION
# ==========================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_db_connection():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("❌ Secrets 설정 오류")
            return None
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet_id = "1ryBvLf_iUwoFR7Cx9zjZEldV6WHe26Jngxu0fs-BZMc"
        return client.open_by_key(sheet_id)
    except Exception as e:
        st.error(f"❌ DB 연결 에러: {e}")
        return None

# ==========================================
# [SYSTEM] SETTINGS MANAGER
# ==========================================
def load_settings():
    wb = get_db_connection()
    if not wb: return {}
    try:
        try: ws = wb.worksheet("settings")
        except: 
            ws = wb.add_worksheet(title="settings", rows=20, cols=2)
            ws.append_row(["key", "value"])
            return {}
        records = ws.get_all_records()
        return {str(r['key']): str(r['value']) for r in records}
    except: return {}

def save_setting(key, value):
    wb = get_db_connection()
    if not wb: return
    try:
        ws = wb.worksheet("settings")
        cell = ws.find(key)
        if cell: ws.update_cell(cell.row, 2, str(value))
        else: ws.append_row([key, str(value)])
    except: pass

if 'settings_loaded' not in st.session_state:
    saved = load_settings()
    def get_val(k, default, type_func):
        val = saved.get(k, str(default))
        try:
            if type_func == bool: return str(val).strip().lower() == 'true'
            return type_func(val)
        except: return default

    if 'phy_active' not in st.session_state: st.session_state['phy_active'] = get_val('phy_active', True, bool)
    if 'phy_damping' not in st.session_state: st.session_state['phy_damping'] = get_val('phy_damping', 0.9, float)
    if 'phy_repulsion' not in st.session_state: st.session_state['phy_repulsion'] = get_val('phy_repulsion', -1000, int)
    if 'phy_len' not in st.session_state: st.session_state['phy_len'] = get_val('phy_len', 200, int)
    if 'phy_overlap' not in st.session_state: st.session_state['phy_overlap'] = get_val('phy_overlap', True, bool)
    st.session_state['settings_loaded'] = True

if 'card_stack' not in st.session_state: st.session_state['card_stack'] = []

# ==========================================
# 1. HELPER: Dynamic Color
# ==========================================
FIXED_COLORS = { "Antenna": "#FF0055", "Stock": "#00FFC2", "Tech": "#00ADB5", "Space": "#9D00FF", "Chip": "#FFE600", "Economy": "#FF8800", "General": "#888" }
COLOR_PALETTE = ["#FF0055", "#00FFC2", "#00ADB5", "#9D00FF", "#FFE600", "#FF8800", "#FF3333", "#33FF33", "#3333FF", "#FF33FF", "#33FFFF", "#FFFF33"]

def get_group_color(group_name):
    if group_name in FIXED_COLORS: return FIXED_COLORS[group_name]
    hash_val = int(hashlib.sha256(group_name.encode('utf-8')).hexdigest(), 16)
    return COLOR_PALETTE[hash_val % len(COLOR_PALETTE)]

# ==========================================
# 2. DATABASE OPERATIONS
# ==========================================
def load_nodes():
    wb = get_db_connection()
    if not wb: return []
    try:
        sheet = wb.sheet1
        data = sheet.get_all_records()
        nodes = []
        for row in data:
            k_str = str(row['keywords']) if row['keywords'] else ""
            kws = [k.strip() for k in k_str.split(',')] if k_str else []
            ts = row.get('timestamp')
            if not ts: ts = "25-12-10 00:00"
            nodes.append({
                "id": str(row['id']), "label": row['label'], "group": row['group_name'],
                "summary": row['summary'], "keywords": kws, "timestamp": ts
            })
        return nodes
    except: return []

def add_node(label, group, summary, keywords):
    wb = get_db_connection()
    if not wb: return None
    try:
        sheet = wb.sheet1
        import uuid
        new_id = str(uuid.uuid4())[:8]
        kw_str = ",".join(keywords)
        now_ts = datetime.now().strftime("%y-%m-%d %H:%M")
        sheet.append_row([new_id, label, group, summary, kw_str, now_ts])
        return {"id": new_id, "label": label, "group": group, "summary": summary, "keywords": keywords, "timestamp": now_ts}
    except: return None

def update_node(node_id, label, summary, keywords):
    wb = get_db_connection()
    if not wb: return
    try:
        sheet = wb.sheet1
        cell = sheet.find(str(node_id))
        if cell:
            r = cell.row
            sheet.update_cell(r, 2, label)
            sheet.update_cell(r, 3, keywords[0] if keywords else "General")
            sheet.update_cell(r, 4, summary)
            sheet.update_cell(r, 5, ",".join(keywords))
    except: pass

def move_to_trash(node_id, node_data):
    wb = get_db_connection()
    if not wb: return
    try:
        try: trash_sheet = wb.worksheet("trash")
        except: 
            trash_sheet = wb.add_worksheet(title="trash", rows=100, cols=7)
            trash_sheet.append_row(["id", "label", "group", "summary", "keywords", "created_at", "deleted_at"])
        
        del_time = datetime.now().strftime("%y-%m-%d %H:%M")
        k_str = ",".join(node_data['keywords'])
        trash_sheet.append_row([
            node_data['id'], node_data['label'], node_data['group'], 
            node_data['summary'], k_str, node_data['timestamp'], del_time
        ])
        
        main_sheet = wb.sheet1
        cell = main_sheet.find(str(node_id))
        if cell: main_sheet.delete_rows(cell.row)
        st.session_state['card_stack'] = [n for n in st.session_state['card_stack'] if n['id'] != node_id]
        
    except Exception as e: st.error(f"휴지통 이동 실패: {e}")

def load_trash():
    wb = get_db_connection()
    if not wb: return []
    try:
        trash_sheet = wb.worksheet("trash")
        return trash_sheet.get_all_records()
    except: return []

def restore_node(node_row):
    wb = get_db_connection()
    if not wb: return
    try:
        wb.sheet1.append_row([
            node_row['id'], node_row['label'], node_row['group'], 
            node_row['summary'], node_row['keywords'], node_row['created_at']
        ])
        permanent_delete(node_row['id'])
    except: pass

def permanent_delete(node_id):
    wb = get_db_connection()
    if not wb: return
    try:
        trash_sheet = wb.worksheet("trash")
        cell = trash_sheet.find(str(node_id))
        if cell: trash_sheet.delete_rows(cell.row)
    except: pass

# ==========================================
# 3. AI ENGINE
# ==========================================
def ai_process(text):
    if "gemini" not in st.secrets or "api_key" not in st.secrets["gemini"]:
        return {"success": False, "error": "Secrets Error"}
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        prompt = f"Analyze:\n{text}\n\nOutput JSON: {{'summary': 'Korean summary (max 2 sentences)', 'keywords': '3-5 keywords (comma separated)'}}"
        res = model.generate_content(prompt)
        data = json.loads(res.text.replace('```json','').replace('```','').strip())
        return {"success": True, "summary": data.get('summary',''), "keywords": data.get('keywords',''), "error": None}
    except Exception as e: return {"success": False, "error": str(e)}

# ==========================================
# MAIN APP UI
# ==========================================
st.markdown("""
<style>
    .stApp { background-color: #000000 !important; color: #ffffff !important; }
    header { visibility: hidden; }
    .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
    iframe { background-color: #000000 !important; border: 1px solid #444 !important; border-radius: 12px; }
    
    div[data-testid="column"] button { background: transparent !important; border: none !important; color: #ccc !important; }
    div[data-testid="column"] button:hover { color: #00ADB5 !important; font-weight: bold; }
    
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { background-color: #1a1a1a !important; color: white !important; border: 1px solid #333 !important; }
    .stMultiSelect div[data-baseweb="select"] > div { background-color: #111 !important; border-color: #333 !important; color: white !important; }
    .stMultiSelect div[data-baseweb="tag"] { background-color: #00ADB5 !important; color: black !important; }
    
    /* [수정] 버튼 스타일: 아이콘 중앙 정렬을 위해 padding 제거 및 flex 적용 */
    div.stButton > button { 
        background-color: #222 !important; 
        color: #fff !important; 
        border: 1px solid #444 !important; 
        width: 100%; 
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        padding: 0px !important; /* 핵심: 패딩을 0으로 만들어 아이콘 쏠림 방지 */
    }
    div.stButton > button:hover { border-color: #00ADB5 !important; color: #00ADB5 !important; }
    div.stButton > button[kind="primary"] { background-color: #E03131 !important; border: none !important; }
    
    .list-header-row { display: flex; align-items: center; height: 40px; font-weight: bold; color: #888; font-size: 0.85rem; }
    .list-content-row { display: flex; align-items: center; height: 46px; }
    .col-center { justify-content: center; width: 100%; display: flex; }
    .col-left { justify-content: flex-start; width: 100%; display: flex; padding-left: 12px; }
</style>
""", unsafe_allow_html=True)

# 세션 초기화
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'menu_mode' not in st.session_state: st.session_state['menu_mode'] = "Knowledge Graph"
if 'workspace_nodes' not in st.session_state: st.session_state['workspace_nodes'] = []
if 'selected_keyword' not in st.session_state: st.session_state['selected_keyword'] = None
if 'temp_analysis' not in st.session_state: st.session_state['temp_analysis'] = None
if 'search_history' not in st.session_state: st.session_state['search_history'] = []
if 'last_selection' not in st.session_state: st.session_state['last_selection'] = None

if 'nodes_db' not in st.session_state or not st.session_state['nodes_db']:
    st.session_state['nodes_db'] = load_nodes()

# 액션 함수
def add_ws(node_id):
    tid = str(node_id)
    if tid not in [str(n['id']) for n in st.session_state['workspace_nodes']]:
        tgt = next((n for n in st.session_state['nodes_db'] if str(n['id']) == tid), None)
        if tgt: st.session_state['workspace_nodes'].append(tgt)

def close_ws(nid): 
    st.session_state['workspace_nodes'] = [n for n in st.session_state['workspace_nodes'] if str(n['id']) != str(nid)]

def clear_ws(): st.session_state['workspace_nodes'] = []

def update_act(nid, label, summary, kw_str):
    k_list = [k.strip() for k in kw_str.split(',')]
    update_node(nid, label, summary, k_list)
    for n in st.session_state['workspace_nodes']:
        if str(n['id']) == str(nid):
            n['label'] = label; n['summary'] = summary; n['keywords'] = k_list
    st.success("Updated!"); time.sleep(0.5); st.rerun()

def delete_to_trash_act(nid):
    tgt = next((n for n in st.session_state['nodes_db'] if str(n['id']) == str(nid)), None)
    if tgt:
        move_to_trash(nid, tgt)
        st.session_state['nodes_db'] = [n for n in st.session_state['nodes_db'] if str(n['id']) != str(nid)]
        close_ws(nid)
        st.success("Moved to Trash 🗑️"); time.sleep(0.5); st.rerun()

# ----------------------------------------------------
# 로그인
# ----------------------------------------------------
if not st.session_state['logged_in']:
    st.markdown("<br><br><h1 style='text-align: center;'>🔗 나만의 지식 센터</h1>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    _, c, _ = st.columns([1,1,1])
    with c:
        with st.form("login"):
            st.markdown("### User Login")
            uid = st.text_input("ID"); upw = st.text_input("PW", type="password")
            if st.form_submit_button("Login", type="primary", use_container_width=True):
                if "login" in st.secrets and uid == st.secrets["login"]["id"] and upw == st.secrets["login"]["pw"]:
                    st.session_state['logged_in'] = True
                    st.rerun()
                else: st.error("Check ID/PW")
else:
    left, main = st.columns([1.5, 4.5])
    
    # 데이터 준비
    df = pd.DataFrame(st.session_state['nodes_db'])
    node_degree, edges, kw_counts = {}, [], pd.DataFrame()
    if not df.empty:
        df['id'] = df['id'].astype(str)
        all_kw = []
        for ks in df['keywords']: all_kw.extend(ks)
        if all_kw:
            kw_counts = pd.Series(all_kw).value_counts().reset_index()
            kw_counts.columns = ['keyword', 'count']
        node_degree = {r['id']:0 for _,r in df.iterrows()}
        for i in range(len(df)):
            for j in range(i+1, len(df)):
                if set(df.iloc[i]['keywords']) & set(df.iloc[j]['keywords']):
                    edges.append(Edge(source=df.iloc[i]['id'], target=df.iloc[j]['id'], color="#555"))
                    node_degree[df.iloc[i]['id']] += 1; node_degree[df.iloc[j]['id']] += 1

    # [왼쪽 사이드바]
    with left:
        all_kws = kw_counts['keyword'].tolist() if not kw_counts.empty else []
        options = [h for h in st.session_state['search_history'] if h in all_kws] + [k for k in all_kws if k not in st.session_state['search_history']]
        selected = st.multiselect("Search", options=options, default=[st.session_state['selected_keyword']] if st.session_state['selected_keyword'] in options else [], max_selections=1, placeholder="🔍 Select keyword...", label_visibility="collapsed")
        
        if selected:
            if selected[0] != st.session_state['selected_keyword']:
                st.session_state['selected_keyword'] = selected[0]
                if selected[0] in st.session_state['search_history']: st.session_state['search_history'].remove(selected[0])
                st.session_state['search_history'].insert(0, selected[0])
                st.rerun()
        else:
            if st.session_state['selected_keyword']: st.session_state['selected_keyword'] = None; st.rerun()

        c1, c2 = st.columns([2, 1])
        c1.markdown("### 🔑 Keywords")
        if c2.button("Reset", key="rk"): st.session_state['selected_keyword'] = None; st.rerun()
        
        st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)
        h_cols = st.columns([0.8, 3, 1.2])
        h_cols[0].markdown("<div class='list-header-row col-center'>No.</div>", unsafe_allow_html=True)
        h_cols[1].markdown("<div class='list-header-row col-left'>Keyword</div>", unsafe_allow_html=True)
        h_cols[2].markdown("<div class='list-header-row col-center'>Cnt</div>", unsafe_allow_html=True)
        st.divider()
        
        with st.container(height=600):
            if not kw_counts.empty:
                for i, row in enumerate(kw_counts.itertuples(), 1):
                    kw = row.keyword
                    act = "#00ADB5" if kw == st.session_state['selected_keyword'] else "#fff"
                    rc = st.columns([0.8, 3, 1.2])
                    rc[0].markdown(f"<div class='list-content-row col-center' style='color:{act}'>{i}</div>", unsafe_allow_html=True)
                    if rc[1].button(kw, key=f"kbtn_{i}", use_container_width=True): st.session_state['selected_keyword'] = None if st.session_state['selected_keyword'] == kw else kw; st.rerun()
                    rc[2].markdown(f"<div class='list-content-row col-center' style='color:#888'>{row.count}</div>", unsafe_allow_html=True)
                    st.markdown("<div style='border-bottom: 1px solid #222; margin-bottom: 2px;'></div>", unsafe_allow_html=True)

    # [오른쪽 메인]
    with main:
        menu_cols = st.columns([5, 1, 1, 1, 1, 1])
        menu_cols[0].subheader(f"📂 {st.session_state['menu_mode']}")
        if menu_cols[1].button("Graph", key="nav_graph", use_container_width=True): st.session_state['menu_mode'] = "Knowledge Graph"; st.rerun()
        if menu_cols[2].button("List", key="nav_list", use_container_width=True): st.session_state['menu_mode'] = "List View"; st.rerun()
        if menu_cols[3].button("Add", key="nav_add", use_container_width=True): st.session_state['menu_mode'] = "Add Data"; st.rerun()
        if menu_cols[4].button("Trash", key="nav_trash", use_container_width=True): st.session_state['menu_mode'] = "Trash Can"; st.rerun()
        if menu_cols[5].button("Out", key="nav_out", use_container_width=True): st.session_state['logged_in'] = False; st.rerun()
        st.divider()

        # ----------------------
        # 1. Knowledge Graph
        # ----------------------
        if st.session_state['menu_mode'] == "Knowledge Graph":
            
            c_g1, c_g2 = st.columns([8, 2])
            with c_g2:
                with st.expander("⚙️ 효과 설정", expanded=False):
                    st.caption("🌊 물방울 물리 엔진")
                    def save_phy(k):
                        st.session_state[k] = st.session_state[k] # Session Update
                        save_setting(k, st.session_state[k])      # DB Update

                    st.checkbox("💧 물방울 모드", key="phy_active", on_change=save_phy, args=("phy_active",))
                    st.divider()
                    st.slider("점성", 0.1, 1.0, step=0.05, key="phy_damping", on_change=save_phy, args=("phy_damping",))
                    st.slider("척력", -2000, -100, step=100, key="phy_repulsion", on_change=save_phy, args=("phy_repulsion",))
                    st.slider("간격", 50, 400, step=10, key="phy_len", on_change=save_phy, args=("phy_len",))
                    st.checkbox("겹침 방지", key="phy_overlap", on_change=save_phy, args=("phy_overlap",))

            ag_nodes, final_edges = [], []
            sel_kw = st.session_state['selected_keyword']
            if not df.empty:
                for _, r in df.iterrows():
                    base_color = get_group_color(r['group'])
                    sz = min(20 + node_degree.get(r['id'], 0)*5, 60)
                    clr, fclr, bw, sc = base_color, "white", 1, base_color
                    if sel_kw:
                        if sel_kw in r['keywords']: clr, sz, fclr, bw, sc = "#00FF00", sz*1.5, "#FFFFFF", 4, "#FFFFFF"
                        else: clr, fclr, sz, bw, sc = "#222", "#666", 15, 1, "#333"
                    ag_nodes.append(Node(id=r['id'], label=r['label'], size=sz, color=clr, font={'color':fclr}, borderWidth=bw, borderColor=sc))
                for e in edges:
                    e_w, e_c = 1, "#555"
                    if sel_kw:
                        src = df[df['id'] == e.source].iloc[0]; tgt = df[df['id'] == e.to].iloc[0]
                        if sel_kw in src['keywords'] and sel_kw in tgt['keywords']: e_w, e_c = 4, "#00FF00"
                        else: e_c = "#222"
                    final_edges.append(Edge(source=e.source, target=e.to, color=e_c, width=e_w))

            cfg = Config(width="100%", height=600, directed=False, nodeHighlightBehavior=True, highlightColor="#F7A7A6", collapsible=False, node={'labelProperty':'label', 'renderLabel':True, 'font': {'color': 'white'}}, backgroundColor="#000000")
            cfg.physics = {
                "enabled": True, "solver": "forceAtlas2Based",
                "forceAtlas2Based": { "theta": 0.5, "gravitationalConstant": st.session_state['phy_repulsion'], "centralGravity": 0.01, "springConstant": 0.08, "springLength": st.session_state['phy_len'], "damping": st.session_state['phy_damping'], "avoidOverlap": 1 if st.session_state['phy_overlap'] else 0 },
                "stabilization": { "enabled": not st.session_state['phy_active'], "iterations": 1000 }
            }
            
            sel = agraph(nodes=ag_nodes, edges=final_edges, config=cfg)
            if sel and sel != st.session_state['last_selection']: st.session_state['last_selection'] = sel; add_ws(sel); st.rerun()

            wsn = st.session_state['workspace_nodes']
            if wsn:
                wc1, wc2 = st.columns([8, 2])
                wc1.markdown("#### 📑 Active Nodes (Edit Mode)")
                if wc2.button("🧹 Clear All", use_container_width=True): clear_ws(); st.rerun()
                w_cols = st.columns(3) 
                for idx, n in enumerate(wsn):
                    with w_cols[idx % 3]:
                        with st.container(border=True):
                            nl = st.text_input("Title", value=n['label'], key=f"l_{n['id']}")
                            nk = st.text_input("Keywords", value=", ".join(n['keywords']), key=f"k_{n['id']}")
                            ns = st.text_area("Summary", value=n['summary'], height=100, key=f"s_{n['id']}")
                            b1, b2, b3 = st.columns(3)
                            if b1.button("💾", key=f"up_{n['id']}", help="Update"): update_act(n['id'], nl, ns, nk)
                            if b2.button("🗑️", key=f"del_{n['id']}", help="Trash"): delete_to_trash_act(n['id'])
                            if b3.button("❌", key=f"cl_{n['id']}", help="Close"): close_ws(n['id']); st.rerun()

        # ----------------------
        # 2. List View
        # ----------------------
        elif st.session_state['menu_mode'] == "List View":
            if st.session_state['card_stack']:
                st.markdown("### 🗂️ Active Stack")
                stack_cols = st.columns(3)
                for i, node_data in enumerate(st.session_state['card_stack']):
                    with stack_cols[i % 3]:
                        with st.container(border=True):
                            # [버튼 정렬 수정] 제목(7) | 편집(1) | 삭제(1) | 닫기(1)
                            st_c1, st_c2, st_c3, st_c4 = st.columns([7, 1, 1, 1])
                            st_c1.markdown(f"#### {node_data['label']}")
                            
                            # use_container_width=True로 버튼이 컬럼 꽉 채우게 하여 중앙 정렬 유도
                            if st_c2.button("✏️", key=f"se_{i}", use_container_width=True, help="Edit"):
                                st.session_state['menu_mode'] = "Knowledge Graph"; add_ws(node_data['id']); st.rerun()
                            if st_c3.button("🗑️", key=f"sd_{i}", use_container_width=True, help="Trash"):
                                delete_to_trash_act(node_data['id'])
                            if st_c4.button("✕", key=f"sc_{i}", use_container_width=True, help="Close"):
                                st.session_state['card_stack'].pop(i); st.rerun()
                            
                            st.info(node_data['summary'])
                            st.caption(f"🕒 {node_data['timestamp']} | 🏷️ {', '.join(node_data['keywords'])}")
                st.divider()

            filtered_df = df
            if st.session_state['selected_keyword']:
                filtered_df = df[df['keywords'].apply(lambda x: st.session_state['selected_keyword'] in x)]
            
            if not filtered_df.empty:
                st.caption(f"Total: {len(filtered_df)} Cards")
                for _, row in filtered_df.iterrows():
                    row_col1, row_col2 = st.columns([0.95, 0.05])
                    with row_col1:
                        list_label = f"**{row['label']}** :gray[| {', '.join(row['keywords'])}]"
                        with st.expander(list_label, expanded=False):
                            st.write(row['summary'])
                            st.caption(f"Created: {row['timestamp']}")
                    with row_col2:
                        with st.popover("⋮"):
                            if st.button("View", key=f"lv_v_{row['id']}", use_container_width=True):
                                if row['id'] not in [n['id'] for n in st.session_state['card_stack']]:
                                    st.session_state['card_stack'].append(row.to_dict()); st.rerun()
                            if st.button("Edit", key=f"lv_e_{row['id']}", use_container_width=True):
                                st.session_state['menu_mode'] = "Knowledge Graph"; add_ws(row['id']); st.rerun()
                            if st.button("Trash", key=f"lv_d_{row['id']}", use_container_width=True):
                                delete_to_trash_act(row['id'])
            else: st.info("No data found.")

        # ----------------------
        # 3. Add Data
        # ----------------------
        elif st.session_state['menu_mode'] == "Add Data":
            st.info("AI Auto-Analysis Node Creator")
            if not st.session_state['temp_analysis']:
                ti = st.text_input("Title")
                co = st.text_area("Content", height=200)
                if st.button("🔍 AI Analyze", type="primary"):
                    if ti and co:
                        with st.spinner("Thinking..."):
                            res = ai_process(co)
                            st.session_state['temp_analysis'] = { "title": ti, "content": co, "summary": res.get('summary',''), "keywords": res.get('keywords',''), "success": res['success'], "error": res.get('error','') }
                            st.rerun()
            else:
                tmp = st.session_state['temp_analysis']
                if not tmp['success']: st.warning(f"{tmp['error']}") 
                else: st.success("Analysis Complete!")
                st.markdown(f"**Title:** {tmp['title']}")
                n_sum = st.text_area("Summary", value=tmp['summary'])
                n_kw = st.text_input("Keywords", value=tmp['keywords'])
                if st.button("💾 Save", type="primary", use_container_width=True):
                    final_keywords = [k.strip() for k in n_kw.split(',')]
                    group_name = final_keywords[0] if final_keywords else "General"
                    new_node_data = add_node(tmp['title'], group_name, n_sum, final_keywords)
                    if new_node_data:
                        st.session_state['nodes_db'].append(new_node_data)
                        st.session_state['temp_analysis'] = None
                        st.success("Saved!"); time.sleep(1); st.session_state['menu_mode'] = "Knowledge Graph"; st.rerun()
                    else: st.error("Save Error")
                if st.button("Cancel", use_container_width=True): st.session_state['temp_analysis'] = None; st.rerun()

        # ----------------------
        # 4. Trash Can
        # ----------------------
        elif st.session_state['menu_mode'] == "Trash Can":
            st.markdown("### 🗑️ Trash Can (Recycle Bin)")
            st.caption("삭제된 노드는 여기에 30일간 보관됩니다.")
            trash_data = load_trash()
            if trash_data:
                now = datetime.now()
                for row in trash_data:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([7, 1.5, 1.5])
                        del_date_str = row.get('deleted_at', '')
                        try:
                            del_date = datetime.strptime(del_date_str, "%y-%m-%d %H:%M")
                            days_left = 30 - (now - del_date).days
                        except: days_left = 0
                        c1.markdown(f"**{row['label']}** :gray[| {row['keywords']}]")
                        c1.caption(f"Deleted: {del_date_str} (남은 기간: {days_left}일)")
                        if c2.button("♻️ Restore", key=f"res_{row['id']}", use_container_width=True):
                            restore_node(row); st.success("Restored!"); time.sleep(0.5); st.rerun()
                        if c3.button("🔥 Delete", key=f"per_del_{row['id']}", type="primary", use_container_width=True):
                            permanent_delete(row['id']); st.warning("Permanently Deleted."); time.sleep(0.5); st.rerun()
            else: st.info("휴지통이 비어있습니다.")
