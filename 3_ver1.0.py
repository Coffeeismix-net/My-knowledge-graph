import streamlit as st
import pandas as pd
from streamlit_agraph import agraph, Node, Edge, Config
import time
import google.generativeai as genai
import json
import hashlib
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ==========================================
# 1. PAGE & STYLE CONFIGURATION
# ==========================================
st.set_page_config(layout="wide", page_title="Obsidian Knowledge Graph", page_icon="🔗")

st.markdown("""
<style>
    /* [1] 기본 앱 스타일 - Obsidian Dark Theme 느낌 */
    .stApp { background-color: #0b0c10 !important; color: #c5c6c7 !important; }
    header { visibility: hidden; }
    .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
    
    /* [2] Iframe (그래프) 스타일 */
    iframe { background-color: #0b0c10 !important; border: 1px solid #1f2833 !important; border-radius: 12px; }
    
    /* [3] 입력 폼 스타일 */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { 
        background-color: #1f2833 !important; color: #66fcf1 !important; border: 1px solid #45a29e !important; 
    }
    
    /* [4] 멀티셀렉트 & 버튼 스타일 */
    .stMultiSelect div[data-baseweb="select"] > div { background-color: #1f2833 !important; border-color: #45a29e !important; color: white !important; }
    div.stButton > button { 
        background-color: transparent !important; border: 1px solid #45a29e !important; color: #66fcf1 !important; 
        border-radius: 5px; transition: all 0.3s ease;
    }
    div.stButton > button:hover { 
        background-color: #45a29e !important; color: #0b0c10 !important; 
    }
    div.stButton > button[kind="primary"] { 
        background-color: #45a29e !important; color: #0b0c10 !important; border: none !important;
    }
    
    /* [5] 헤더 스타일 */
    .tight-header { font-size: 1.5rem; font-weight: 700; color: #66fcf1; margin-bottom: 0px; }
    .tight-hr { margin: 10px 0 20px 0; border: 0; border-top: 1px solid #1f2833; }
    
    /* 리스트 스타일 */
    .list-row { display: flex; align-items: center; padding: 4px 0; border-bottom: 1px solid #1f2833; }
    .list-row:hover { background-color: #1f2833; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SESSION STATE
# ==========================================
def init_session_state():
    defaults = {
        'logged_in': False, 'menu_mode': "Knowledge Graph", 'nodes_db': [], 'workspace_nodes': [],
        'selected_keyword': None, 'temp_analysis': None, 'search_history': [], 
        'last_selection': None, 'card_stack': [], 'settings_loaded': False,
        
        # [NEW] Obsidian Physics & View Settings
        'view_mode': 'Global', # Global or Local
        'perf_mode': False,    # High Performance Mode (Straight edges, No shadows)
        'phy_solver': 'barnesHut', 
        'phy_gravity': -2000, 
        'phy_central_gravity': 0.3,
        'phy_spring_len': 100, 
        'phy_spring_strength': 0.05,
        'phy_damping': 0.09
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

init_session_state()

# ==========================================
# 3. BACKEND: DB & SETTINGS
# ==========================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_db_client():
    try:
        if "gcp_service_account" not in st.secrets: return None
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
        return gspread.authorize(creds)
    except: return None

def get_workbook():
    client = get_db_client()
    return client.open_by_key("1ryBvLf_iUwoFR7Cx9zjZEldV6WHe26Jngxu0fs-BZMc") if client else None

# --- 데이터 관리 ---
def load_nodes():
    wb = get_workbook()
    if not wb: return []
    try:
        data = wb.sheet1.get_all_records()
        nodes = []
        for row in data:
            k_str = str(row.get('keywords', ''))
            kws = [k.strip() for k in k_str.split(',')] if k_str else []
            ts = row.get('timestamp') or "25-12-10 00:00"
            nodes.append({
                "id": str(row['id']), "label": row['label'], "group": row['group_name'],
                "summary": row['summary'], "keywords": kws, "timestamp": ts
            })
        return nodes
    except: return []

def add_node(label, group, summary, keywords):
    wb = get_workbook()
    if not wb: return None
    try:
        import uuid
        new_id = str(uuid.uuid4())[:8]
        kw_str = ",".join(keywords)
        now_ts = datetime.now().strftime("%y-%m-%d %H:%M")
        wb.sheet1.append_row([new_id, label, group, summary, kw_str, now_ts])
        return {"id": new_id, "label": label, "group": group, "summary": summary, "keywords": keywords, "timestamp": now_ts}
    except: return None

def update_node(node_id, label, summary, keywords):
    wb = get_workbook()
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
    wb = get_workbook()
    if not wb: return
    try:
        try: trash_sheet = wb.worksheet("trash")
        except: 
            trash_sheet = wb.add_worksheet(title="trash", rows=100, cols=7)
            trash_sheet.append_row(["id", "label", "group", "summary", "keywords", "created_at", "deleted_at"])
        del_time = datetime.now().strftime("%y-%m-%d %H:%M")
        k_str = ",".join(node_data['keywords'])
        trash_sheet.append_row([node_data['id'], node_data['label'], node_data['group'], node_data['summary'], k_str, node_data['timestamp'], del_time])
        main_sheet = wb.sheet1
        cell = main_sheet.find(str(node_id))
        if cell: main_sheet.delete_rows(cell.row)
        st.session_state['nodes_db'] = [n for n in st.session_state['nodes_db'] if str(n['id']) != str(node_id)]
        st.session_state['card_stack'] = [n for n in st.session_state['card_stack'] if str(n['id']) != str(node_id)]
    except Exception as e: st.error(f"Error: {e}")

def load_trash():
    wb = get_workbook()
    if not wb: return []
    try: return wb.worksheet("trash").get_all_records()
    except: return []

def restore_node(node_row):
    wb = get_workbook()
    if not wb: return
    try:
        wb.sheet1.append_row([node_row['id'], node_row['label'], node_row['group'], node_row['summary'], node_row['keywords'], node_row['created_at']])
        permanent_delete(node_row['id'])
    except: pass

def permanent_delete(node_id):
    wb = get_workbook()
    if not wb: return
    try:
        trash_sheet = wb.worksheet("trash")
        cell = trash_sheet.find(str(node_id))
        if cell: trash_sheet.delete_rows(cell.row)
    except: pass

# ==========================================
# 4. AI ENGINE & HELPERS
# ==========================================
def ai_process(text):
    if "gemini" not in st.secrets: return {"success": False, "error": "Secrets Error"}
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        prompt = f"Analyze:\n{text}\n\nOutput JSON: {{'summary': 'Korean summary (max 2 sentences)', 'keywords': '3-5 keywords (comma separated)'}}"
        res = model.generate_content(prompt)
        data = json.loads(res.text.replace('```json','').replace('```','').strip())
        return {"success": True, "summary": data.get('summary',''), "keywords": data.get('keywords',''), "error": None}
    except Exception as e: return {"success": False, "error": str(e)}

def get_group_color(group_name):
    # Obsidian Color Palette
    PALETTE = ["#FF0055", "#00FFC2", "#45A29E", "#9D00FF", "#FFE600", "#FF8800"]
    hash_val = int(hashlib.sha256(group_name.encode('utf-8')).hexdigest(), 16)
    return PALETTE[hash_val % len(PALETTE)]

def act_add_ws(node_id):
    tid = str(node_id)
    if tid not in [str(n['id']) for n in st.session_state['workspace_nodes']]:
        tgt = next((n for n in st.session_state['nodes_db'] if str(n['id']) == tid), None)
        if tgt: st.session_state['workspace_nodes'].append(tgt)
def act_close_ws(nid): st.session_state['workspace_nodes'] = [n for n in st.session_state['workspace_nodes'] if str(n['id']) != str(nid)]
def act_clear_ws(): st.session_state['workspace_nodes'] = []
def act_update(nid, label, summary, kw_str):
    k_list = [k.strip() for k in kw_str.split(',')]
    update_node(nid, label, summary, k_list)
    for n in st.session_state['nodes_db']:
        if str(n['id']) == str(nid): n['label']=label; n['summary']=summary; n['keywords']=k_list
    for n in st.session_state['workspace_nodes']:
        if str(n['id']) == str(nid): n['label']=label; n['summary']=summary; n['keywords']=k_list
    st.success("Updated!"); time.sleep(0.5); st.rerun()
def act_trash(nid):
    tgt = next((n for n in st.session_state['nodes_db'] if str(n['id']) == str(nid)), None)
    if tgt: move_to_trash(nid, tgt); act_close_ws(nid); st.success("Moved to Trash 🗑️"); time.sleep(0.5); st.rerun()

# ==========================================
# 5. MAIN LOGIC
# ==========================================
if not st.session_state['nodes_db']: st.session_state['nodes_db'] = load_nodes()

if not st.session_state['logged_in']:
    st.markdown("<br><br><h1 style='text-align: center; color: #66fcf1;'>🔗 Obsidian Knowledge Center</h1><br>", unsafe_allow_html=True)
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
    left, main = st.columns([1.5, 4.5])
    
    # ----------------------------------------------------
    # [LOGIC] GLOBAL vs LOCAL FILTERING
    # ----------------------------------------------------
    full_df = pd.DataFrame(st.session_state['nodes_db'])
    display_df = full_df.copy()
    
    # [Step 2] 로컬 그래프 로직: 선택된 노드가 있다면 그 이웃만 필터링
    is_local_view = (st.session_state['view_mode'] == 'Local Focus')
    center_node_id = st.session_state.get('last_selection')
    
    if is_local_view and center_node_id and not full_df.empty:
        # 1. 타겟 노드 찾기
        target_node = full_df[full_df['id'] == center_node_id]
        if not target_node.empty:
            target_kws = set(target_node.iloc[0]['keywords'])
            # 2. 이웃 찾기 (키워드를 공유하는 노드들)
            neighbor_ids = []
            for _, row in full_df.iterrows():
                if row['id'] == center_node_id: continue
                if set(row['keywords']) & target_kws:
                    neighbor_ids.append(row['id'])
            
            # 3. DF 필터링 (타겟 + 이웃)
            display_df = full_df[full_df['id'].isin(neighbor_ids + [center_node_id])]

    # ----------------------------------------------------
    # [SIDEBAR]
    # ----------------------------------------------------
    with left:
        st.markdown("<div class='tight-header'>🔍 Search</div>", unsafe_allow_html=True)
        
        # 키워드 검색
        all_kws = []
        if not full_df.empty:
            for ks in full_df['keywords']: all_kws.extend(ks)
        kw_counts = pd.Series(all_kws).value_counts().reset_index()
        kw_counts.columns = ['keyword', 'count']
        
        options = [h for h in st.session_state['search_history'] if h in kw_counts['keyword'].tolist()] + kw_counts['keyword'].tolist()
        selected = st.multiselect("Keywords", options=list(set(options)), default=[st.session_state['selected_keyword']] if st.session_state['selected_keyword'] else [], max_selections=1, label_visibility="collapsed")
        
        if selected:
            if selected[0] != st.session_state['selected_keyword']:
                st.session_state['selected_keyword'] = selected[0]
                st.rerun()
        elif st.session_state['selected_keyword']:
            st.session_state['selected_keyword'] = None; st.rerun()

        st.markdown("<hr class='tight-hr'>", unsafe_allow_html=True)
        
        # [NEW] Obsidian Style Settings Panel
        with st.expander("🛠️ Graph Settings", expanded=True):
            # View Mode
            st.caption("👁️ View Mode")
            mode_col1, mode_col2 = st.columns(2)
            if mode_col1.button("Global", type="primary" if st.session_state['view_mode']=="Global" else "secondary", use_container_width=True):
                st.session_state['view_mode'] = "Global"; st.rerun()
            if mode_col2.button("Local", type="primary" if st.session_state['view_mode']=="Local Focus" else "secondary", use_container_width=True):
                st.session_state['view_mode'] = "Local Focus"; st.rerun()

            # Performance Mode
            st.divider()
            st.caption("🚀 Performance")
            st.session_state['perf_mode'] = st.checkbox("High Perf. Mode", value=st.session_state['perf_mode'], help="직선 엣지 사용 및 그림자 제거로 속도 향상")

            # Physics (Barnes-Hut)
            st.divider()
            st.caption("⚛️ Physics (Barnes-Hut)")
            st.session_state['phy_gravity'] = st.slider("Gravity (Repulsion)", -30000, -1000, st.session_state['phy_gravity'], step=500)
            st.session_state['phy_central_gravity'] = st.slider("Central Gravity", 0.0, 1.0, st.session_state['phy_central_gravity'], step=0.1)
            st.session_state['phy_spring_len'] = st.slider("Spring Length", 10, 300, st.session_state['phy_spring_len'], step=10)
            st.session_state['phy_spring_strength'] = st.slider("Spring Strength", 0.0, 0.2, st.session_state['phy_spring_strength'], step=0.01)

        # Keyword List
        st.markdown("<hr class='tight-hr'>", unsafe_allow_html=True)
        st.markdown("##### 🔥 Top Keywords")
        with st.container(height=300):
            for i, row in kw_counts.head(20).iterrows():
                kw = row.keyword
                color = "#66fcf1" if kw == st.session_state['selected_keyword'] else "#888"
                if st.button(f"{kw} ({row['count']})", key=f"kbtn_{i}", use_container_width=True):
                    st.session_state['selected_keyword'] = kw if st.session_state['selected_keyword'] != kw else None
                    st.rerun()

    # ----------------------------------------------------
    # [MAIN]
    # ----------------------------------------------------
    with main:
        # Nav Menu
        m_cols = st.columns([4, 1, 1, 1, 1, 1])
        m_cols[0].markdown(f"<div class='tight-header'>📂 {st.session_state['menu_mode']}</div>", unsafe_allow_html=True)
        if m_cols[1].button("Graph", key="n1"): st.session_state['menu_mode'] = "Knowledge Graph"; st.rerun()
        if m_cols[2].button("List", key="n2"): st.session_state['menu_mode'] = "List View"; st.rerun()
        if m_cols[3].button("Add", key="n3"): st.session_state['menu_mode'] = "Add Data"; st.rerun()
        if m_cols[4].button("Trash", key="n4"): st.session_state['menu_mode'] = "Trash Can"; st.rerun()
        if m_cols[5].button("Out", key="n5"): st.session_state['logged_in'] = False; st.rerun()
        st.markdown("<hr class='tight-hr'>", unsafe_allow_html=True)

        # ------------------------------------------------
        # 1. KNOWLEDGE GRAPH VIEW
        # ------------------------------------------------
        if st.session_state['menu_mode'] == "Knowledge Graph":
            
            # Info Bar
            st.info(f"📊 Displaying **{len(display_df)}** Nodes in **{st.session_state['view_mode']}** Mode")

            # Graph Generation
            ag_nodes, final_edges = [], []
            node_degree = {}
            
            # [Optimization] Calculate edges only for display_df
            if not display_df.empty:
                display_df['id'] = display_df['id'].astype(str)
                # Init degree
                for nid in display_df['id']: node_degree[nid] = 0
                
                # Build Edges
                ids = display_df['id'].tolist()
                kws = display_df['keywords'].tolist()
                
                for i in range(len(ids)):
                    for j in range(i+1, len(ids)):
                        # Intersection of keywords
                        shared = set(kws[i]) & set(kws[j])
                        if shared:
                            edge_width = 1
                            edge_color = "#333" # Default Dark
                            
                            # Highlight if keyword selected
                            if st.session_state['selected_keyword'] and st.session_state['selected_keyword'] in shared:
                                edge_width = 3
                                edge_color = "#66fcf1"
                            
                            # [Step 3] Performance Mode: 직선 vs 곡선
                            smooth_opt = False if st.session_state['perf_mode'] else {'type': 'continuous'}
                            
                            final_edges.append(Edge(source=ids[i], target=ids[j], color=edge_color, width=edge_width, smooth=smooth_opt))
                            node_degree[ids[i]] += 1
                            node_degree[ids[j]] += 1
                
                # Build Nodes
                for _, r in display_df.iterrows():
                    nid = str(r['id'])
                    # Visual properties
                    base_color = get_group_color(r['group'])
                    size = 15 + (node_degree.get(nid, 0) * 3)
                    
                    # Highlight selected node or keyword
                    if nid == st.session_state['last_selection']:
                        base_color = "#ffffff"
                        size *= 1.2
                    elif st.session_state['selected_keyword'] in r['keywords']:
                        base_color = "#66fcf1"
                    
                    # [Step 3] Performance Mode: 그림자 제거
                    shadow_opt = False if st.session_state['perf_mode'] else True

                    ag_nodes.append(Node(
                        id=nid, 
                        label=r['label'], 
                        title=f"{r['label']}\n{', '.join(r['keywords'])}",
                        size=size, 
                        color=base_color,
                        font={'color': 'white', 'size': 14},
                        shadow=shadow_opt
                    ))

            # [Step 1] Barnes-Hut Physics Config
            cfg = Config(
                width="100%", height=600, 
                directed=False, 
                nodeHighlightBehavior=True, 
                highlightColor="#66fcf1",
                collapsible=False,
                backgroundColor="#0b0c10",
                physics={
                    "enabled": True,
                    "solver": "barnesHut",
                    "barnesHut": {
                        "gravitationalConstant": st.session_state['phy_gravity'],
                        "centralGravity": st.session_state['phy_central_gravity'],
                        "springLength": st.session_state['phy_spring_len'],
                        "springConstant": st.session_state['phy_spring_strength'],
                        "damping": st.session_state['phy_damping'],
                        "avoidOverlap": 0.2
                    },
                    "stabilization": {
                        "enabled": True,
                        "iterations": 150 # 초기 안정화 반복
                    }
                }
            )
            
            sel = agraph(nodes=ag_nodes, edges=final_edges, config=cfg)
            
            # Handle Selection
            if sel and sel != st.session_state['last_selection']: 
                st.session_state['last_selection'] = sel
                act_add_ws(sel)
                st.rerun()

            # Workspace (Edit Panel)
            wsn = st.session_state['workspace_nodes']
            if wsn:
                st.divider()
                st.markdown("#### 📝 Edit Node")
                for n in wsn:
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        nl = c1.text_input("Title", value=n['label'], key=f"l_{n['id']}")
                        nk = c1.text_input("Keywords", value=", ".join(n['keywords']), key=f"k_{n['id']}")
                        ns = c1.text_area("Summary", value=n['summary'], height=80, key=f"s_{n['id']}")
                        
                        b1, b2, b3 = c2.columns(3)
                        if b1.button("💾", key=f"sv_{n['id']}", use_container_width=True): act_update(n['id'], nl, ns, nk)
                        if b2.button("🗑️", key=f"tr_{n['id']}", use_container_width=True): act_trash(n['id'])
                        if b3.button("✖️", key=f"cl_{n['id']}", use_container_width=True): act_close_ws(n['id']); st.rerun()

        # ------------------------------------------------
        # 2. LIST VIEW
        # ------------------------------------------------
        elif st.session_state['menu_mode'] == "List View":
            st.markdown(f"### 📋 List ({len(display_df)} nodes)")
            
            # Card Stack
            if st.session_state['card_stack']:
                st.caption("Active Cards")
                cols = st.columns(3)
                for i, node in enumerate(st.session_state['card_stack']):
                    with cols[i%3]:
                        with st.container(border=True):
                            st.markdown(f"**{node['label']}**")
                            st.caption(node['timestamp'])
                            if st.button("Close", key=f"cc_{i}"): 
                                st.session_state['card_stack'].pop(i); st.rerun()
            
            st.divider()
            
            # Table List
            for _, row in display_df.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([8, 2])
                    c1.markdown(f"**{row['label']}** :gray[{', '.join(row['keywords'])}]")
                    c1.caption(row['summary'][:100] + "...")
                    if c2.button("Edit", key=f"le_{row['id']}", use_container_width=True):
                        st.session_state['menu_mode'] = "Knowledge Graph"
                        st.session_state['last_selection'] = row['id']
                        act_add_ws(row['id'])
                        st.rerun()

        # ------------------------------------------------
        # 3. ADD DATA (AI)
        # ------------------------------------------------
        elif st.session_state['menu_mode'] == "Add Data":
            st.markdown("### 🤖 AI Analysis & Add")
            if not st.session_state['temp_analysis']:
                ti = st.text_input("Title")
                co = st.text_area("Content", height=300)
                if st.button("Analyze", type="primary"):
                    with st.spinner("Processing..."):
                        res = ai_process(co)
                        st.session_state['temp_analysis'] = { 
                            "title": ti, "content": co, 
                            "summary": res.get('summary',''), 
                            "keywords": res.get('keywords',''), 
                            "success": res['success']
                        }
                        st.rerun()
            else:
                tmp = st.session_state['temp_analysis']
                st.markdown(f"**Title:** {tmp['title']}")
                s_sum = st.text_area("Summary", value=tmp['summary'])
                s_key = st.text_input("Keywords", value=tmp['keywords'])
                
                c1, c2 = st.columns(2)
                if c1.button("Save", type="primary", use_container_width=True):
                    k_list = [k.strip() for k in s_key.split(',')]
                    grp = k_list[0] if k_list else "General"
                    add_node(tmp['title'], grp, s_sum, k_list)
                    st.session_state['temp_analysis'] = None
                    st.success("Saved!")
                    time.sleep(1)
                    st.session_state['menu_mode'] = "Knowledge Graph"
                    st.rerun()
                if c2.button("Cancel", use_container_width=True):
                    st.session_state['temp_analysis'] = None; st.rerun()

        # ------------------------------------------------
        # 4. TRASH CAN
        # ------------------------------------------------
        elif st.session_state['menu_mode'] == "Trash Can":
            st.markdown("### 🗑️ Trash Can")
            trash_data = load_trash()
            if trash_data:
                for row in trash_data:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([6, 2, 2])
                        c1.markdown(f"**{row['label']}**")
                        c1.caption(f"Del: {row['deleted_at']}")
                        if c2.button("Restore", key=f"r_{row['id']}", use_container_width=True):
                            restore_node(row)
                            st.session_state['nodes_db'].append({
                                "id": str(row['id']), "label": row['label'], "group": row['group'],
                                "summary": row['summary'], "keywords": str(row['keywords']).split(','), 
                                "timestamp": row['created_at']
                            })
                            st.rerun()
                        if c3.button("Delete", key=f"pd_{row['id']}", type="primary", use_container_width=True):
                            permanent_delete(row['id']); st.rerun()
            else:
                st.info("Trash is empty.")
