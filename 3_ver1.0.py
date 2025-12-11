import streamlit as st
import pandas as pd
from streamlit_agraph import agraph, Node, Edge, Config
import time
import google.generativeai as genai
import json
import hashlib
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 4. UI STYLE & LAYOUT
# ==========================================
st.set_page_config(layout="wide", page_title="나만의 지식 센터", page_icon="🔗")

# 물리 엔진 설정값 유지 (초기화)
if 'phy_active' not in st.session_state: st.session_state['phy_active'] = True
if 'phy_damping' not in st.session_state: st.session_state['phy_damping'] = 0.9
if 'phy_repulsion' not in st.session_state: st.session_state['phy_repulsion'] = -1000
if 'phy_len' not in st.session_state: st.session_state['phy_len'] = 200
if 'phy_overlap' not in st.session_state: st.session_state['phy_overlap'] = True

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
            st.error("❌ Secrets 설정 오류: 'gcp_service_account' 섹션이 없습니다.")
            return None

        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        sheet_id = "1ryBvLf_iUwoFR7Cx9zjZEldV6WHe26Jngxu0fs-BZMc" 
        return client.open_by_key(sheet_id).sheet1
    except Exception as e:
        st.error(f"❌ DB 연결 상세 에러: {e}")
        return None

# ==========================================
# 1. HELPER: Dynamic Color
# ==========================================
FIXED_COLORS = { 
    "Antenna": "#FF0055", "Stock": "#00FFC2", "Tech": "#00ADB5", 
    "Space": "#9D00FF", "Chip": "#FFE600", "Economy": "#FF8800", "General": "#888" 
}
COLOR_PALETTE = ["#FF0055", "#00FFC2", "#00ADB5", "#9D00FF", "#FFE600", "#FF8800", "#FF3333", "#33FF33", "#3333FF", "#FF33FF", "#33FFFF", "#FFFF33"]

def get_group_color(group_name):
    if group_name in FIXED_COLORS: return FIXED_COLORS[group_name]
    hash_val = int(hashlib.sha256(group_name.encode('utf-8')).hexdigest(), 16)
    return COLOR_PALETTE[hash_val % len(COLOR_PALETTE)]

# ==========================================
# 2. DATABASE OPERATIONS
# ==========================================
def load_nodes():
    sheet = get_db_connection()
    if not sheet: return []
    try:
        data = sheet.get_all_records()
        nodes = []
        for row in data:
            k_str = str(row['keywords']) if row['keywords'] else ""
            kws = [k.strip() for k in k_str.split(',')] if k_str else []
            nodes.append({
                "id": str(row['id']), "label": row['label'], "group": row['group_name'],
                "summary": row['summary'], "keywords": kws
            })
        return nodes
    except: return []

def add_node(label, group, summary, keywords):
    try:
        sheet = get_db_connection()
        if not sheet: return None
        import uuid
        new_id = str(uuid.uuid4())[:8]
        kw_str = ",".join(keywords)
        sheet.append_row([new_id, label, group, summary, kw_str])
        return {
            "id": new_id, "label": label, "group": group, 
            "summary": summary, "keywords": keywords
        }
    except: return None

def update_node(node_id, label, summary, keywords):
    sheet = get_db_connection()
    if not sheet: return
    try:
        cell = sheet.find(str(node_id))
        if cell:
            r = cell.row
            kw_str = ",".join(keywords)
            grp = keywords[0] if keywords else "General"
            sheet.update_cell(r, 2, label)
            sheet.update_cell(r, 3, grp)
            sheet.update_cell(r, 4, summary)
            sheet.update_cell(r, 5, kw_str)
    except: pass

def delete_node(node_id):
    sheet = get_db_connection()
    if not sheet: return
    try:
        cell = sheet.find(str(node_id))
        if cell: sheet.delete_rows(cell.row)
    except: pass

# ==========================================
# 3. AI ENGINE
# ==========================================
def ai_process(text):
    if "gemini" not in st.secrets or "api_key" not in st.secrets["gemini"]:
        return {"success": False, "error": "Secrets Error: API Key Missing"}
    api_key = st.secrets["gemini"]["api_key"]
    genai.configure(api_key=api_key)
    
    # 안정적인 최신 모델 사용
    model_name = 'gemini-flash-latest' 
    
    try:
        model = genai.GenerativeModel(model_name)
        prompt = f"""
        Analyze the text.
        1. Summarize in Korean (max 2 sentences).
        2. Extract 3-5 keywords (comma separated).
        Return JSON ONLY: {{ "summary": "...", "keywords": "..." }}
        Text: {text}
        """
        response = model.generate_content(prompt)
        data = json.loads(response.text.replace('```json','').replace('```','').strip())
        return {"success": True, "summary": data.get('summary',''), "keywords": data.get('keywords',''), "error": None}
    except Exception as e:
        return {"success": False, "error": f"🛑 AI Error: {str(e)}"}

# ==========================================
# MAIN APP UI
# ==========================================
st.markdown("""
<style>
    .stApp { background-color: #000000 !important; color: #ffffff !important; }
    header { visibility: hidden; }
    .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
    iframe { 
        background-color: #000000 !important; 
        color-scheme: dark !important; 
        border: 1px solid #444 !important;
        border-radius: 12px; 
    }
    .node-card { background-color: #111; border: 1px solid #444; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    div[data-testid="column"] button { 
        background: transparent !important; border: none !important; color: #ccc !important; 
        text-align: left !important; padding: 0 !important; margin: 0 !important; font-size: 0.95rem !important;
    }
    div[data-testid="column"] button:hover { color: #00ADB5 !important; font-weight: bold; }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { background-color: #1a1a1a !important; color: white !important; border: 1px solid #333 !important; }
    .stMultiSelect div[data-baseweb="select"] > div { background-color: #111 !important; border-color: #333 !important; color: white !important; }
    .stMultiSelect div[data-baseweb="tag"] { background-color: #00ADB5 !important; color: black !important; }
    
    /* 버튼 스타일 통일 */
    div.stButton > button { background-color: #222 !important; color: #fff !important; border: 1px solid #444 !important; width: 100%; }
    div.stButton > button:hover { border-color: #00ADB5 !important; color: #00ADB5 !important; }
    div.stButton > button[kind="primary"] { background-color: #E03131 !important; border: none !important; }
    
    .list-header-row { display: flex; align-items: center; height: 46px; border-bottom: 1px solid #333; font-weight: bold; color: #888; font-size: 0.85rem; }
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

def add_ws(node_id):
    tid = str(node_id)
    if tid not in [str(n['id']) for n in st.session_state['workspace_nodes']]:
        tgt = next((n for n in st.session_state['nodes_db'] if str(n['id']) == tid), None)
        if tgt: st.session_state['workspace_nodes'].append(tgt)
def close_ws(nid): st.session_state['workspace_nodes'] = [n for n in st.session_state['workspace_nodes'] if str(n['id']) != str(nid)]
def clear_ws(): st.session_state['workspace_nodes'] = []
def update_act(nid, label, summary, kw_str):
    k_list = [k.strip() for k in kw_str.split(',')]
    update_node(nid, label, summary, k_list)
    for n in st.session_state['workspace_nodes']:
        if str(n['id']) == str(nid):
            n['label'] = label; n['summary'] = summary; n['keywords'] = k_list
    st.success("Updated!"); time.sleep(0.5); st.rerun()
def delete_act(nid): delete_node(str(nid)); close_ws(nid); st.session_state['last_selection'] = None; st.rerun()

# ----------------------------------------------------
# 로그인 화면
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
                if "login" in st.secrets:
                    secret_id = st.secrets["login"]["id"]
                    secret_pw = st.secrets["login"]["pw"]
                    if uid == secret_id and upw == secret_pw:
                        st.session_state['logged_in'] = True
                        st.rerun()
                    else: st.error("Check ID/PW")
                else: st.error("⚠️ Secrets에 [login] 설정이 없습니다. 설정해주세요.")

# ----------------------------------------------------
# 메인 화면 (로그인 후)
# ----------------------------------------------------
else:
    # [요청 2] 로그인 후에는 큰 제목 숨김 (깔끔하게)
    
    left, main = st.columns([1.5, 4.5])
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

    # ------------------------------------
    # [왼쪽] 공통 사이드바 (검색 및 순위)
    # ------------------------------------
    with left:
        all_kws_unique = kw_counts['keyword'].tolist() if not kw_counts.empty else []
        options = [h for h in st.session_state['search_history'] if h in all_kws_unique] + [k for k in all_kws_unique if k not in st.session_state['search_history']]
        default_val = [st.session_state['selected_keyword']] if st.session_state['selected_keyword'] in options else []
        selected = st.multiselect("Search", options=options, default=default_val, max_selections=1, placeholder="🔍 Select keyword...", label_visibility="collapsed")
        
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
        st.markdown("<hr style='margin:5px 0; border-color:#333;'>", unsafe_allow_html=True)
        
        h_cols = st.columns([0.8, 3, 1.2])
        h_cols[0].markdown("<div class='list-header-row col-center'>No.</div>", unsafe_allow_html=True)
        h_cols[1].markdown("<div class='list-header-row col-left'>Keyword</div>", unsafe_allow_html=True)
        h_cols[2].markdown("<div class='list-header-row col-center'>Cnt</div>", unsafe_allow_html=True)
        
        with st.container(height=650):
            if not kw_counts.empty:
                for i, row in enumerate(kw_counts.itertuples(), 1):
                    kw = row.keyword
                    act = "#00ADB5" if kw == st.session_state['selected_keyword'] else "#fff"
                    rc = st.columns([0.8, 3, 1.2])
                    rc[0].markdown(f"<div class='list-content-row col-center' style='color:{act}'>{i}</div>", unsafe_allow_html=True)
                    if rc[1].button(kw, key=f"kbtn_{i}", use_container_width=True): st.session_state['selected_keyword'] = None if st.session_state['selected_keyword'] == kw else kw; st.rerun()
                    rc[2].markdown(f"<div class='list-content-row col-center' style='color:#888'>{row.count}</div>", unsafe_allow_html=True)
                    st.markdown("<div style='border-bottom: 1px solid #222; margin-bottom: 2px;'></div>", unsafe_allow_html=True)

    # ------------------------------------
    # [오른쪽] 메인 콘텐츠 영역
    # ------------------------------------
    with main:
        # [요청 1] 상단 메뉴바 정렬 개선
        # 비율을 조정하여 버튼들이 예쁘게 나열되도록 수정
        # Set 버튼 삭제 -> List 버튼 추가
        h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([6, 1, 1, 1, 1])
        
        # 현재 모드 표시
        current_mode = st.session_state['menu_mode']
        h_col1.subheader(f"📂 {current_mode}")

        # 메뉴 버튼 (use_container_width=True로 정렬 맞춤)
        if h_col2.button("Graph", use_container_width=True): 
            st.session_state['menu_mode'] = "Knowledge Graph"
            st.rerun()
        if h_col3.button("List", use_container_width=True): # [요청 3, 4] Set -> List 변경
            st.session_state['menu_mode'] = "List View"
            st.rerun()
        if h_col4.button("Add", use_container_width=True): 
            st.session_state['menu_mode'] = "Add Data"
            st.rerun()
        if h_col5.button("Out", use_container_width=True): 
            st.session_state['logged_in'] = False
            st.rerun()

        st.divider() # 메뉴와 내용 구분선

        # --------------------------------------
        # MODE 1: Knowledge Graph (기존)
        # --------------------------------------
        if st.session_state['menu_mode'] == "Knowledge Graph":
            
            # 물방울 효과 제어 패널
            ctrl_col1, ctrl_col2 = st.columns([8, 2])
            with ctrl_col2:
                with st.expander("⚙️ 효과 설정", expanded=False):
                    st.caption("🌊 물방울 물리 엔진")
                    
                    def dummy(): pass 

                    st.checkbox("💧 물방울 모드", key="phy_active", on_change=dummy)
                    st.divider()
                    st.slider("점성", 0.1, 1.0, step=0.05, key="phy_damping", on_change=dummy)
                    st.slider("척력", -2000, -100, step=100, key="phy_repulsion", on_change=dummy)
                    st.slider("간격", 50, 400, step=10, key="phy_len", on_change=dummy)
                    st.checkbox("겹침 방지", key="phy_overlap", on_change=dummy)

            ag_nodes = []
            final_edges = []
            sel_kw = st.session_state['selected_keyword']
            if not df.empty:
                for _, r in df.iterrows():
                    base_color = get_group_color(r['group'])
                    d = node_degree.get(r['id'], 0)
                    sz = min(20 + d*5, 60)
                    clr, fclr, bw, sc = base_color, "white", 1, base_color
                    if sel_kw:
                        if sel_kw in r['keywords']: 
                            clr, sz, fclr, bw, sc = "#00FF00", sz*1.5, "#FFFFFF", 4, "#FFFFFF"
                        else: 
                            clr, fclr, sz, bw, sc = "#222", "#666", 15, 1, "#333"
                    ag_nodes.append(Node(id=r['id'], label=r['label'], size=sz, color=clr, font={'color':fclr}, borderWidth=bw, borderColor=sc))
            
                for e in edges:
                    e_w, e_c = 1, "#555"
                    if sel_kw:
                        src = df[df['id'] == e.source].iloc[0]
                        tgt = df[df['id'] == e.to].iloc[0]
                        if sel_kw in src['keywords'] and sel_kw in tgt['keywords']: e_w, e_c = 4, "#00FF00"
                        else: e_c = "#222"
                    final_edges.append(Edge(source=e.source, target=e.to, color=e_c, width=e_w))

            cfg = Config(
                width="100%", 
                height=600, 
                directed=False, 
                nodeHighlightBehavior=True,
                highlightColor="#F7A7A6",
                collapsible=False,
                node={'labelProperty':'label', 'renderLabel':True, 'font': {'color': 'white'}},
                backgroundColor="#000000"
            )
            
            cfg.physics = {
                "enabled": True,
                "solver": "forceAtlas2Based",
                "forceAtlas2Based": {
                    "theta": 0.5,
                    "gravitationalConstant": st.session_state['phy_repulsion'],
                    "centralGravity": 0.01,
                    "springConstant": 0.08,
                    "springLength": st.session_state['phy_len'],
                    "damping": st.session_state['phy_damping'],
                    "avoidOverlap": 1 if st.session_state['phy_overlap'] else 0
                },
                "stabilization": {
                    "enabled": not st.session_state['phy_active'], 
                    "iterations": 1000
                }
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
                            
                            if st.button("💾 Update", key=f"up_{n['id']}"): update_act(n['id'], nl, ns, nk)
                            if st.button("🗑️ Delete", key=f"del_{n['id']}"): delete_act(n['id'])
                            if st.button("❌ Close", key=f"cl_{n['id']}"): close_ws(n['id']); st.rerun()

        # --------------------------------------
        # [요청 4, 5] MODE 2: List View (New)
        # --------------------------------------
        elif st.session_state['menu_mode'] == "List View":
            
            # 검색 필터링 적용
            filtered_df = df
            if st.session_state['selected_keyword']:
                # 해당 키워드가 포함된 행만 필터링
                filtered_df = df[df['keywords'].apply(lambda x: st.session_state['selected_keyword'] in x)]
            
            if not filtered_df.empty:
                st.caption(f"총 {len(filtered_df)}개의 지식 카드가 있습니다.")
                
                # 리스트 형태로 출력
                for _, row in filtered_df.iterrows():
                    with st.container(border=True):
                        # 상단: 그룹(색상) 및 제목
                        c_top1, c_top2 = st.columns([0.2, 9.8])
                        grp_color = get_group_color(row['group'])
                        c_top1.markdown(f"<div style='width:15px; height:15px; background-color:{grp_color}; border-radius:50%; margin-top:10px;'></div>", unsafe_allow_html=True)
                        c_top2.markdown(f"### {row['label']}")
                        
                        # 내용: 요약 및 키워드
                        st.info(row['summary'])
                        st.markdown(f"**Keywords:** {', '.join(row['keywords'])}")
                        
                        # 수정 버튼 (Graph View의 수정창으로 연결)
                        if st.button("Edit", key=f"list_edit_{row['id']}"):
                            st.session_state['menu_mode'] = "Knowledge Graph" # 그래프 뷰로 이동해서
                            add_ws(row['id']) # 수정창 열기
                            st.rerun()
            else:
                st.info("조건에 맞는 데이터가 없습니다.")

        # --------------------------------------
        # MODE 3: Add Data
        # --------------------------------------
        elif st.session_state['menu_mode'] == "Add Data":
            st.info("AI Auto-Analysis Node Creator")
            if not st.session_state['temp_analysis']:
                ti = st.text_input("Title")
                co = st.text_area("Content", height=200)
                if st.button("🔍 AI Analyze", type="primary"):
                    if ti and co:
                        with st.spinner("Thinking..."):
                            res = ai_process(co)
                            st.session_state['temp_analysis'] = { 
                                "title": ti, 
                                "content": co, 
                                "summary": res.get('summary',''), 
                                "keywords": res.get('keywords',''), 
                                "success": res['success'], 
                                "error": res.get('error','') 
                            }
                            st.rerun()
            else:
                tmp = st.session_state['temp_analysis']
                if not tmp['success']: 
                    st.warning(f"{tmp['error']}") 
                else: 
                    st.success("Analysis Complete!")
                
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
                        st.success("Saved!")
                        time.sleep(1)
                        st.session_state['menu_mode'] = "Knowledge Graph"
                        st.rerun()
                    else:
                        st.error("저장 중 오류가 발생했습니다.")

                if st.button("Cancel", use_container_width=True): 
                    st.session_state['temp_analysis'] = None
                    st.rerun()
