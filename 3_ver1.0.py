import streamlit as st
import pandas as pd
import streamlit.components.v1 as components # HTML 컴포넌트용 (그래프 시각화 변경)
import time
import google.generativeai as genai
import json
import hashlib
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 0. GOOGLE SHEETS CONNECTION (기존 동일)
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
# 1. HELPER: Dynamic Color (기존 동일)
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
# 2. DATABASE OPERATIONS (기존 동일)
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
# 3. AI ENGINE (기존 동일)
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
# 4. NEW VISUALIZATION: ORGANIC FORCE GRAPH
# ==========================================
def render_organic_graph(nodes_data, selected_keyword=None):
    """
    물방울처럼 유영하는 유기적 그래프를 렌더링하는 HTML/JS 생성 함수
    """
    # [데이터 준비] Python List -> JSON 변환
    nodes_json = []
    edges_json = []
    
    # 1. 노드 생성
    for n in nodes_data:
        color = get_group_color(n['group'])
        val = 10 # 기본 크기
        
        # 키워드 검색 시 하이라이트 처리
        is_highlight = False
        if selected_keyword and selected_keyword in n['keywords']:
            is_highlight = True
            color = "#00FF00" # 하이라이트 색상 (형광 초록)
            val = 20
        elif selected_keyword:
            color = "#333333" # 비활성 노드는 어둡게

        nodes_json.append({
            "id": n['id'], 
            "name": n['label'], 
            "group": n['group'], 
            "color": color, 
            "val": val,
            "is_highlight": is_highlight
        })

    # 2. 엣지 생성 (키워드 공유 시 연결)
    for i in range(len(nodes_data)):
        for j in range(i+1, len(nodes_data)):
            src = nodes_data[i]
            tgt = nodes_data[j]
            common = set(src['keywords']) & set(tgt['keywords'])
            if common:
                width = 1
                color = "#444444" # 기본 엣지 색상
                if selected_keyword and selected_keyword in common:
                    width = 3
                    color = "#00FF00" # 하이라이트 엣지
                
                edges_json.append({
                    "source": src['id'], 
                    "target": tgt['id'], 
                    "color": color,
                    "width": width
                })

    data_json = json.dumps({"nodes": nodes_json, "links": edges_json})

    # [프론트엔드] HTML + JS 템플릿 (Force-Graph 라이브러리)
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <style> 
        body {{ margin: 0; background-color: #000000; overflow: hidden; }} 
        #graph {{ width: 100%; height: 600px; }}
      </style>
      <script src="//unpkg.com/force-graph"></script>
    </head>
    <body>
      <div id="graph"></div>
      <script>
        const gData = {data_json};

        const Graph = ForceGraph()
          (document.getElementById('graph'))
            .graphData(gData)
            .backgroundColor('#000000') // 배경 리얼 블랙
            .nodeId('id')
            .nodeVal('val')
            .nodeLabel('name')
            .nodeColor('color')
            .linkColor('color')
            .linkWidth('width')
            
            // ---------------------------------------------
            // [물리 엔진 튜닝] "물멍" 효과 구현 파트
            // ---------------------------------------------
            .d3VelocityDecay(0.6)  // (1) 점성: 높을수록 물속처럼 묵직하게 움직임 (기본 0.4 -> 0.6)
            .d3AlphaDecay(0)       // (2) 감쇠 제거: 에너지가 줄어들지 않도록 설정
            
            // 노드 그리기 (Canvas API)
            .nodeCanvasObject((node, ctx, globalScale) => {{
              const label = node.name;
              const fontSize = 12/globalScale;
              ctx.font = `${{fontSize}}px Sans-Serif`;
              
              // 노드 원
              const r = Math.sqrt(node.val) * 4;
              ctx.beginPath();
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
              ctx.fillStyle = node.color;
              ctx.fill();
              
              // 하이라이트 테두리
              if (node.is_highlight) {{
                  ctx.strokeStyle = '#FFFFFF';
                  ctx.lineWidth = 2 / globalScale;
                  ctx.stroke();
              }}

              // 텍스트 라벨
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = '#FFFFFF';
              ctx.fillText(label, node.x, node.y + r + fontSize);
            }})
            .onNodeHover(node => {{
                document.getElementById('graph').style.cursor = node ? 'pointer' : null;
            }});

        // ---------------------------------------------
        // [영원한 유영] 초기 안정화 후 부유 모드 진입
        // ---------------------------------------------
        Graph.d3Force('charge').strength(-150); // 서로 밀어내는 힘
        Graph.d3Force('link').distance(100);    // 연결 거리
        
        // 시작 1초 후, 목표 에너지(alphaTarget)를 미세하게 주어 계속 움직이게 함
        setTimeout(() => {{
            Graph.d3Force('charge').strength(-100); 
            Graph.d3AlphaTarget(0.01); // (3) 멈추지 않는 미세한 움직임
        }}, 1000);

      </script>
    </body>
    </html>
    """
    # Streamlit 화면에 렌더링
    components.html(html_code, height=600, scrolling=False)


# ==========================================
# 5. UI STYLE & LAYOUT (메인 앱 시작)
# ==========================================
st.set_page_config(layout="wide", page_title="나만의 지식 센터", page_icon="node_icon.png")

# CSS: 배경 블랙 강제
st.markdown("""
<style>
    .stApp { background-color: #000000 !important; color: #ffffff !important; }
    header { visibility: hidden; }
    h1 { margin: 0; padding: 0; }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { background-color: #1a1a1a !important; color: white !important; border: 1px solid #333 !important; }
</style>
""", unsafe_allow_html=True)

# 헤더 (아이콘 + 제목)
st.markdown("<br>", unsafe_allow_html=True)
_, center_col, _ = st.columns([1, 2, 1]) 
with center_col:
    c1, c2 = st.columns([0.2, 0.8]) 
    with c1: st.image("node_icon.png", width=60)
    with c2: st.markdown("<h1 style='padding-top: 10px; margin: 0;'>나만의 지식 센터</h1>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# 세션 초기화
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'menu_mode' not in st.session_state: st.session_state['menu_mode'] = "Knowledge Graph"
if 'workspace_nodes' not in st.session_state: st.session_state['workspace_nodes'] = []
if 'selected_keyword' not in st.session_state: st.session_state['selected_keyword'] = None
if 'temp_analysis' not in st.session_state: st.session_state['temp_analysis'] = None
if 'search_history' not in st.session_state: st.session_state['search_history'] = []

if 'nodes_db' not in st.session_state or not st.session_state['nodes_db']:
    st.session_state['nodes_db'] = load_nodes()

# ------------------------------------
# 로그인 화면
# ------------------------------------
if not st.session_state['logged_in']:
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
                else: st.error("⚠️ Secrets 설정 확인 필요")

# ------------------------------------
# 메인 화면
# ------------------------------------
else:
    left, main = st.columns([1.5, 4.5])

    # [왼쪽] 검색 패널
    with left:
        st.markdown("### 🔍 Search")
        all_kw = []
        for n in st.session_state['nodes_db']: all_kw.extend(n['keywords'])
        kw_counts = pd.Series(all_kw).value_counts().reset_index()
        kw_counts.columns = ['keyword', 'count']
        
        # 검색창
        options = kw_counts['keyword'].tolist()
        selected = st.multiselect("Keyword", options=options, default=([st.session_state['selected_keyword']] if st.session_state['selected_keyword'] else []), max_selections=1)
        
        if selected: st.session_state['selected_keyword'] = selected[0]
        else: st.session_state['selected_keyword'] = None

        # 키워드 리스트
        st.markdown("---")
        with st.container(height=500):
            for row in kw_counts.itertuples():
                col_l, col_r = st.columns([3, 1])
                label = row.keyword
                if label == st.session_state['selected_keyword']:
                    col_l.markdown(f":green[**{label}**]")
                else:
                    if col_l.button(label, key=f"btn_{label}"):
                        st.session_state['selected_keyword'] = label
                        st.rerun()
                col_r.caption(f"{row.count}")

    # [오른쪽] 메인 콘텐츠
    with main:
        # 상단 메뉴바
        m1, m2, m3, m4 = st.columns([6, 1, 1, 1])
        m1.markdown("### 🌌 Knowledge Universe")
        if m2.button("Graph"): st.session_state['menu_mode'] = "Knowledge Graph"; st.rerun()
        if m3.button("Add"): st.session_state['menu_mode'] = "Add Data"; st.rerun()
        if m4.button("Out"): st.session_state['logged_in'] = False; st.rerun()

        # 1. 그래프 뷰 (Organic Mode 적용)
        if st.session_state['menu_mode'] == "Knowledge Graph":
            render_organic_graph(st.session_state['nodes_db'], st.session_state['selected_keyword'])
            st.info("💡 팁: 노드들은 물속에 떠 있는 것처럼 천천히 움직입니다. 마우스로 드래그하여 던져보세요!")

        # 2. 데이터 추가 뷰 (기존 로직)
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
                                "title": ti, "content": co, 
                                "summary": res.get('summary',''), "keywords": res.get('keywords',''), 
                                "success": res['success'], "error": res.get('error','') 
                            }
                            st.rerun()
            else:
                tmp = st.session_state['temp_analysis']
                if not tmp['success']: st.error(f"{tmp['error']}")
                else: st.success("Analysis Complete!")
                
                st.markdown(f"**Title:** {tmp['title']}")
                n_sum = st.text_area("Summary", value=tmp['summary'])
                n_kw = st.text_input("Keywords", value=tmp['keywords'])
                
                if st.button("💾 Save", type="primary", use_container_width=True):
                    final_keywords = [k.strip() for k in n_kw.split(',')]
                    grp = final_keywords[0] if final_keywords else "General"
                    new_node = add_node(tmp['title'], grp, n_sum, final_keywords)
                    if new_node:
                        st.session_state['nodes_db'].append(new_node)
                        st.session_state['temp_analysis'] = None
                        st.success("Saved!"); time.sleep(1); 
                        st.session_state['menu_mode'] = "Knowledge Graph"; st.rerun()

                if st.button("Cancel", use_container_width=True): 
                    st.session_state['temp_analysis'] = None; st.rerun()
