import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from streamlit_agraph import Edge # 데이터 처리용으로만 남김
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
        if "gcp_service_account" not in st.secrets:
            st.error("❌ Secrets 설정 오류: 'gcp_service_account' 섹션이 없습니다.")
            return None

        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        # [ID로 직접 연결]
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
        if not sheet:
            st.error("❌ Google Sheets 연결 실패")
            return None

        import uuid
        new_id = str(uuid.uuid4())[:8]
        kw_str = ",".join(keywords)
        
        sheet.append_row([new_id, label, group, summary, kw_str])
        
        return {
            "id": new_id, 
            "label": label, 
            "group": group, 
            "summary": summary, 
            "keywords": keywords
        }
    except Exception as e:
        st.error(f"❌ 데이터 저장 중 상세 에러: {e}")
        return None

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
    
    model_name = 'gemini-2.0-flash'
    
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
        err_msg = str(e)
        if "429" in err_msg or "Quota" in err_msg:
            return {"success": False, "error": "⚠️ 구글 AI 사용량 초과 (1~2분 뒤 다시 시도해주세요)."}
        return {"success": False, "error": f"AI Error: {err_msg}"}

# ==========================================
# 4. CUSTOM HTML COMPONENT (FLOATING GRAPH)
# ==========================================
def render_floating_graph(nodes_data, edges_data, height=600):
    """
    Force-Graph 라이브러리를 사용해 '물속 유영' 효과를 내는 HTML을 생성합니다.
    """
    # Python 데이터를 JSON 문자열로 변환
    graph_data = {
        "nodes": nodes_data,
        "links": edges_data
    }
    json_data = json.dumps(graph_data)

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <style> 
        body {{ margin: 0; background-color: #000000; overflow: hidden; }} 
        .graph-tooltip {{ 
            background: rgba(0,0,0,0.8) !important; 
            color: #fff !important; 
            border: 1px solid #444 !important;
            border-radius: 4px;
            padding: 5px;
        }}
      </style>
      <script src="//unpkg.com/force-graph"></script>
    </head>
    <body>
      <div id="graph"></div>
      <script>
        const gData = {json_data};

        // [핵심] 물멍 효과를 위한 물리 엔진 설정
        const Graph = ForceGraph()
          (document.getElementById('graph'))
          .graphData(gData)
          .backgroundColor('#000000')
          .nodeId('id')
          .nodeLabel('label')
          .nodeColor(node => node.color)
          .nodeVal(node => node.size) // 노드 크기 반영
          
          // [1] 물리 엔진 튜닝: 점성 및 유동성
          .d3VelocityDecay(0.6)     // 0.6: 물속 저항처럼 묵직하게 (기본값 0.4)
          .d3AlphaTarget(0.05)      // 0.05: 멈추지 않고 계속 미세하게 움직임 (0이면 멈춤)
          
          // [2] 힘(Force) 설정: 척력과 연결
          .d3Force('charge', d3.forceManyBody().strength(-100)) // 서로 밀어내는 힘
          .d3Force('link', d3.forceLink().id(d => d.id).distance(70)) // 링크 길이
          
          // [3] 시각적 설정
          .linkColor(link => link.color)
          .linkWidth(link => link.width)
          .nodeCanvasObject((node, ctx, globalScale) => {{
            const label = node.label;
            const fontSize = 12/globalScale;
            ctx.font = `${{fontSize}}px Sans-Serif`;
            const textWidth = ctx.measureText(label).width;
            const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2); 

            // 노드 원 그리기
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.size/4, 0, 2 * Math.PI, false);
            ctx.fillStyle = node.color;
            ctx.fill();
            
            // 선택된 노드 테두리 효과 (옵션)
            if (node.is_selected) {{
                ctx.lineWidth = 2;
                ctx.strokeStyle = '#fff';
                ctx.stroke();
            }}

            // 텍스트 라벨 그리기
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = node.textColor || 'rgba(255, 255, 255, 0.8)';
            ctx.fillText(label, node.x, node.y + node.size/4 + fontSize + 2);
            
            node.__bckgDimensions = bckgDimensions; // for interaction
          }})
          .onNodeClick(node => {{
            // Streamlit으로 데이터 전송은 현재 iframe 제약으로 어려움.
            // 대신 시각적으로 강조하거나 툴팁으로 확인.
            Graph.centerAt(node.x, node.y, 1000);
            Graph.zoom(4, 2000);
          }});
          
          // 화면 리사이즈 대응
          window.addEventListener('resize', () => {{
            Graph.width(window.innerWidth);
            Graph.height(window.innerHeight);
          }});
      </script>
    </body>
    </html>
    """
    return html_code

# ==========================================
# 5. UI STYLE & LAYOUT
# ==========================================
st.set_page_config(layout="wide", page_title="My Knowledge Center", page_icon="🧠")

st.markdown("""
<style>
    /* [1] 앱 전체 배경: 리얼 블랙 */
    .stApp { background-color: #000000 !important; color: #ffffff !important; }
    header { visibility: hidden; }
    .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
    
    /* [2] IFRAME 강제 블랙 */
    iframe { 
        background-color: #000000 !important; 
        border: 1px solid #444 !important;
        border-radius: 12px; 
    }
    div[data-testid="column"] button { 
        background: transparent !important; border: none !important; color: #ccc !important; 
        text-align: left !important; padding: 0 !important; margin: 0 !important; font-size: 0.95rem !important;
    }
    div[data-testid="column"] button:hover { color: #00ADB5 !important; font-weight: bold; }
    
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { background-color: #1a1a1a !important; color: white !important; border: 1px solid #333 !important; }
    
    div.stButton > button { background-color: #222 !important; color: #fff !important; border: 1px solid #444 !important; width: 100%; }
    div.stButton > button:hover { border-color: #00ADB5 !important; color: #00ADB5 !important; }
    div.stButton > button[kind="primary"] { background-color: #E03131 !important; border: none !important; }
    
    .list-header-row { display: flex; align-items: center; height: 46px; border-bottom: 1px solid #333; font-weight: bold; color: #888; font-size: 0.85rem; }
    .list-content-row { display: flex; align-items: center; height: 46px; }
    .col-center { justify-content: center; width: 100%; display: flex; }
    .col-left { justify-content: flex-start; width: 100%; display: flex; padding-left: 12px; }
</style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'menu_mode' not in st.session_state: st.session_state['menu_mode'] = "Knowledge Graph"
if 'workspace_nodes' not in st.session_state: st.session_state['workspace_nodes'] = []
if 'selected_keyword' not in st.session_state: st.session_state['selected_keyword'] = None
if 'temp_analysis' not in st.session_state: st.session_state['temp_analysis'] = None
if 'search_history' not in st.session_state: st.session_state['search_history'] = []
# force-graph는 iframe 내부 state이므로 Streamlit 세션 연동은 단방향(Py->JS) 위주로 구성합니다.

if 'nodes_db' not in st.session_state or not st.session_state['nodes_db']:
    st.session_state['nodes_db'] = load_nodes()

def add_ws(node_id):
    # force-graph는 클릭 이벤트를 Python으로 직접 보내기 까다로우므로
    # 필요하다면 검색이나 별도 리스트에서 선택하여 Workspace에 추가하는 방식을 사용
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
def delete_act(nid): delete_node(str(nid)); close_ws(nid); st.rerun()

if not st.session_state['logged_in']:
    _, c, _ = st.columns([1,1,1])
    with c:
        st.markdown("<br><br><h1 style='text-align: center;'>🧠 My Knowledge Center</h1>", unsafe_allow_html=True)
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
                    else:
                        st.error("Check ID/PW")
                else:
                    st.error("⚠️ Secrets에 [login] 설정이 없습니다.")
else:
    left, main = st.columns([1.5, 4.5])
    df = pd.DataFrame(st.session_state['nodes_db'])
    
    # [데이터 전처리: edges 계산]
    edges_list = []
    kw_counts = pd.DataFrame()
    
    if not df.empty:
        df['id'] = df['id'].astype(str)
        all_kw = []
        for ks in df['keywords']: all_kw.extend(ks)
        if all_kw:
            kw_counts = pd.Series(all_kw).value_counts().reset_index()
            kw_counts.columns = ['keyword', 'count']
        
        # 간단한 엣지 생성 로직 (키워드 공유 시 연결)
        for i in range(len(df)):
            for j in range(i+1, len(df)):
                common = set(df.iloc[i]['keywords']) & set(df.iloc[j]['keywords'])
                if common:
                    # width 가중치
                    edges_list.append({
                        "source": df.iloc[i]['id'], 
                        "target": df.iloc[j]['id'], 
                        "color": "#333",
                        "width": 1
                    })

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
        
        # 키워드 리스트
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

    with main:
        m1, m2, m3, m4, m5 = st.columns([5, 1, 1, 1, 1])
        m1.markdown("<h2 style='margin:0'>Graph View</h2>", unsafe_allow_html=True)
        if m2.button("Graph"): st.session_state['menu_mode'] = "Knowledge Graph"; st.rerun()
        if m3.button("Add"): st.session_state['menu_mode'] = "Add Data"; st.rerun()
        if m4.button("Set"): st.session_state['menu_mode'] = "Settings"; st.rerun()
        if m5.button("Out"): st.session_state['logged_in'] = False; st.rerun()

        # ==========================================
        # 🌊 WATER FLOATING GRAPH MODE
        # ==========================================
        if st.session_state['menu_mode'] == "Knowledge Graph":
            
            # 1. 데이터 준비 (Force-Graph용 JSON 구조)
            fg_nodes = []
            fg_edges = []
            sel_kw = st.session_state['selected_keyword']
            
            # 노드 데이터 변환
            if not df.empty:
                for _, r in df.iterrows():
                    base_color = get_group_color(r['group'])
                    
                    # 기본 스타일
                    size = 10
                    color = base_color
                    text_color = "rgba(255,255,255,0.6)"
                    is_selected = False

                    # 키워드 선택 시 하이라이트
                    if sel_kw:
                        if sel_kw in r['keywords']:
                            size = 20
                            color = "#00FF00" # 네온 그린
                            text_color = "#FFFFFF"
                            is_selected = True
                            # 선택된 노드는 workspace에 자동 추가 로직을 원한다면 여기 추가
                            add_ws(r['id']) 
                        else:
                            color = "#333" # 비활성 노드는 어둡게
                            text_color = "#444"
                    
                    fg_nodes.append({
                        "id": str(r['id']),
                        "label": r['label'],
                        "group": r['group'],
                        "size": size,
                        "color": color,
                        "textColor": text_color,
                        "is_selected": is_selected
                    })

            # 엣지 데이터 변환
            for e in edges_list:
                width = 1
                color = "#444"
                
                if sel_kw:
                    # 선택된 키워드를 포함하는 노드끼리의 연결만 강조
                    src_kw = df[df['id'] == e['source']].iloc[0]['keywords']
                    tgt_kw = df[df['id'] == e['target']].iloc[0]['keywords']
                    
                    if sel_kw in src_kw and sel_kw in tgt_kw:
                        width = 3
                        color = "#00FF00"
                    else:
                        color = "#222" # 매우 어둡게

                fg_edges.append({
                    "source": str(e['source']),
                    "target": str(e['target']),
                    "color": color,
                    "width": width
                })
            
            # 2. HTML 생성 및 렌더링
            html_content = render_floating_graph(fg_nodes, fg_edges, height=650)
            components.html(html_content, height=650, scrolling=False)

            # 3. Workspace (편집창)
            wsn = st.session_state['workspace_nodes']
            if wsn:
                st.markdown("---")
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
                    st.error(f"{tmp['error']}")
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
