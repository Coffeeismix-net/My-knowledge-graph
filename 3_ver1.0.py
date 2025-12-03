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
# 0. GOOGLE SHEETS CONNECTION
# ==========================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_db_connection():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            client = gspread.authorize(creds)
            return client.open("knowledge_graph_db").sheet1
        return None
    except Exception:
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
    sheet = get_db_connection()
    if not sheet: return False
    try:
        import uuid
        new_id = str(uuid.uuid4())[:8]
        kw_str = ",".join(keywords)
        sheet.append_row([new_id, label, group, summary, kw_str])
        return True
    except: return False

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
# 3. AI ENGINE (DEBUGGING VERSION)
# ==========================================
def ai_process(text):
    # [CHECK 1] Secrets에서 API Key가 제대로 로드되는지 확인
    if "gemini" not in st.secrets or "api_key" not in st.secrets["gemini"]:
        return {"success": False, "error": "Secrets 설정 오류: [gemini] api_key를 찾을 수 없습니다."}
    
    api_key = st.secrets["gemini"]["api_key"]
    genai.configure(api_key=api_key)
    
    # 모델 후보군 (터미널 로그 기반 + 표준 모델)
    candidates = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-exp']
    
    last_err = "No models tried yet."
    
    for model_name in candidates:
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
            # 실패한 이유를 기록 (화면에 보여주기 위함)
            last_err = str(e)
            continue
            
    # 모든 모델이 실패했을 때, 마지막 에러 메시지를 반환
    return {"success": False, "error": f"AI 처리 실패 ({last_err})"}

# ==========================================
# 4. UI STYLE & LAYOUT
# ==========================================
st.set_page_config(layout="wide", page_title="Neural Knowledge Base", page_icon="🧠")

st.markdown("""
<style>
    .stApp { background-color: #000000 !important; color: #ffffff !important; }
    header { visibility: hidden; }
    .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
    iframe { filter: invert(1) hue-rotate(180deg) !important; border: 1px solid #333 !important; border-radius: 12px; background-color: white !important; }
    .node-card { background-color: #111; border: 1px solid #444; padding: 15px; border-radius: 8px; margin-bottom: 10px; }

    div[data-testid="column"] button { 
        background: transparent !important; border: none !important; color: #ccc !important; 
        text-align: left !important; padding: 0 !important; margin: 0 !important; font-size: 0.95rem !important;
    }
    div[data-testid="column"] button:hover { color: #00ADB5 !important; font-weight: bold; }
    
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { background-color: #1a1a1a !important; color: white !important; border: 1px solid #333 !important; }
    
    .stMultiSelect div[data-baseweb="select"] > div { background-color: #111 !important; border-color: #333 !important; color: white !important; }
    .stMultiSelect div[data-baseweb="tag"] { background-color: #00ADB5 !important; color: black !important; }
    
    div.stButton > button { background-color: #222 !important; color: #fff !important; border: 1px solid #444 !important; width: 100%; }
    div.stButton > button:hover { border-color: #00ADB5 !important; color: #00ADB5 !important; }
    div.stButton > button[kind="primary"] { background-color: #E03131 !important; border: none !important; }
</style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'menu_mode' not in st.session_state: st.session_state['menu_mode'] = "Knowledge Graph"
if 'workspace_nodes' not in st.session_state: st.session_state['workspace_nodes'] = []
if 'selected_keyword' not in st.session_state: st.session_state['selected_keyword'] = None
if 'temp_analysis' not in st.session_state: st.session_state['temp_analysis'] = None
if 'search_history' not in st.session_state: st.session_state['search_history'] = []
if 'last_selection' not in st.session_state: st.session_state['last_selection'] = None

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

if not st.session_state['logged_in']:
    _, c, _ = st.columns([1,1,1])
    with c:
        st.markdown("<br><br><h1 style='text-align: center;'>🧠 Neural Base</h1>", unsafe_allow_html=True)
        with st.form("login"):
            st.markdown("### User Login")
            uid = st.text_input("ID"); upw = st.text_input("PW", type="password")
            if st.form_submit_button("Login", type="primary", use_container_width=True):
                if uid == 'admin' and upw == '1234': st.session_state['logged_in'] = True; st.rerun()
                else: st.error("Check ID/PW")
else:
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
        h1, h2, h3 = st.columns([0.8, 3, 1.2])
        h1.markdown("**No.**"); h2.markdown("**Keyword**"); h3.markdown("**Cnt**")
        st.markdown("<div style='border-bottom: 1px solid #333; margin-bottom: 5px;'></div>", unsafe_allow_html=True)
        
        with st.container(height=650):
            if not kw_counts.empty:
                for i, row in enumerate(kw_counts.itertuples(), 1):
                    kw = row.keyword
                    act = "#00ADB5" if kw == st.session_state['selected_keyword'] else "#fff"
                    rc = st.columns([0.8, 3, 1.2])
                    rc[0].markdown(f"<span style='color:{act}'>{i}</span>", unsafe_allow_html=True)
                    if rc[1].button(kw, key=f"kbtn_{i}"): st.session_state['selected_keyword'] = None if st.session_state['selected_keyword'] == kw else kw; st.rerun()
                    rc[2].markdown(f"<span style='color:#888'>{row.count}</span>", unsafe_allow_html=True)
                    st.markdown("<div style='border-bottom: 1px solid #222; margin-bottom: 2px;'></div>", unsafe_allow_html=True)

    with main:
        m1, m2, m3, m4, m5 = st.columns([5, 1, 1, 1, 1])
        m1.markdown("<h2 style='margin:0'>Graph View</h2>", unsafe_allow_html=True)
        if m2.button("Graph"): st.session_state['menu_mode'] = "Knowledge Graph"; st.rerun()
        if m3.button("Add"): st.session_state['menu_mode'] = "Add Data"; st.rerun()
        if m4.button("Set"): st.session_state['menu_mode'] = "Settings"; st.rerun()
        if m5.button("Out"): st.session_state['logged_in'] = False; st.rerun()

        if st.session_state['menu_mode'] == "Knowledge Graph":
            ag_nodes = []
            sel_kw = st.session_state['selected_keyword']
            if not df.empty:
                for _, r in df.iterrows():
                    base_color = get_group_color(r['group'])
                    d = node_degree.get(r['id'], 0)
                    sz = min(20 + d*5, 60)
                    clr, fclr, bw, sc = base_color, "black", 1, base_color
                    if sel_kw:
                        if sel_kw in r['keywords']: clr, sz, fclr, bw, sc = "#00FF00", sz*1.5, "black", 4, "#FFFFFF"
                        else: clr, fclr, sz, bw, sc = "#222", "#444", 15, 1, "#333"
                    ag_nodes.append(Node(id=r['id'], label=r['label'], size=sz, color=clr, font={'color':fclr}, borderWidth=bw, borderColor=sc))
            
            cfg = Config(width="100%", height=600, directed=False, physics={"enabled":True, "stabilization":{"enabled":True, "iterations":200}}, node={'labelProperty':'label', 'renderLabel':True})
            sel = agraph(nodes=ag_nodes, edges=edges, config=cfg)
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
                            # [FIX Nesting Error] 버튼들을 세로로 배치
                            if st.button("💾 Update", key=f"up_{n['id']}"): update_act(n['id'], nl, ns, nk)
                            if st.button("🗑️ Delete", key=f"del_{n['id']}"): delete_act(n['id'])
                            if st.button("❌ Close", key=f"cl_{n['id']}"): close_ws(n['id']); st.rerun()

        elif st.session_state['menu_mode'] == "Add Data":
            st.info("AI Auto-Analysis Node Creator")
            if not st.session_state['temp_analysis']:
                ti = st.text_input("Title"); co = st.text_area("Content", height=200)
                if st.button("🔍 AI Analyze", type="primary"):
                    if ti and co:
                        with st.spinner("Thinking..."):
                            res = ai_process(co)
                            st.session_state['temp_analysis'] = { "title": ti, "content": co, "summary": res.get('summary',''), "keywords": res.get('keywords',''), "success": res['success'], "error": res.get('error','') }
                            st.rerun()
            else:
                tmp = st.session_state['temp_analysis']
                if not tmp['success']: st.error(f"⚠️ {tmp['error']}")
                else: st.success("Analysis Complete!")
                st.markdown(f"**Title:** {tmp['title']}")
                n_sum = st.text_area("Summary", value=tmp['summary'])
                n_kw = st.text_input("Keywords", value=tmp['keywords'])
                
                # [FIX Nesting Error] 여기서도 컬럼 대신 수직 배치 (안정성 우선)
                if st.button("💾 Save", type="primary", use_container_width=True):
                    add_node(tmp['title'], n_kw.split(',')[0].strip() if n_kw else "General", n_sum, [k.strip() for k in n_kw.split(',')])
                    st.session_state['temp_analysis'] = None; st.success("Saved!"); time.sleep(1); st.session_state['menu_mode'] = "Knowledge Graph"; st.rerun()
                if st.button("Cancel", use_container_width=True): st.session_state['temp_analysis'] = None; st.rerun()

        elif st.session_state['menu_mode'] == "Settings":
            st.header("Settings")
            st.info("Connected to Google Sheets & Gemini")
