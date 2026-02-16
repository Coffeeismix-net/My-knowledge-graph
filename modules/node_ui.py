import streamlit as st
import pandas as pd
import time
import re
from streamlit_agraph import agraph, Node, Edge, Config
from utils.db_node import update_node, move_to_trash, add_node, ai_process, get_group_color
from utils.db_common import get_workbook, save_setting_to_db, copy_to_clipboard, strip_html

try:
    from streamlit_quill import st_quill
except ImportError:
    st_quill = None

# [HELPER] 하이라이팅
def highlight_text(text, query):
    if not query or not text: return text
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(lambda m: f"<span style='background-color: #ffd700; color: black; padding: 0 2px; border-radius: 2px;'>{m.group(0)}</span>", str(text))

def act_add_ws(node_id):
    tid = str(node_id)
    if tid not in [str(n['id']) for n in st.session_state['workspace_nodes']]:
        tgt = next((n for n in st.session_state['nodes_db'] if str(n['id']) == tid), None)
        if tgt: st.session_state['workspace_nodes'].append(tgt)

def act_close_ws(nid): 
    st.session_state['workspace_nodes'] = [n for n in st.session_state['workspace_nodes'] if str(n['id']) != str(nid)]

def act_clear_ws(): 
    st.session_state['workspace_nodes'] = []

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
    if tgt: 
        move_to_trash(nid, tgt)
        st.session_state['nodes_db'] = [n for n in st.session_state['nodes_db'] if str(n['id']) != str(nid)]
        st.session_state['card_stack'] = [n for n in st.session_state['card_stack'] if str(n['id']) != str(nid)]
        act_close_ws(nid)
        st.success("Moved to Trash 🗑️"); time.sleep(0.5); st.rerun()

def on_update_setting(key):
    wb = get_workbook()
    try:
        ws = wb.worksheet("settings")
        cell = ws.find(key)
        if cell: ws.update_cell(cell.row, 2, str(st.session_state[key]))
        else: ws.append_row([key, str(st.session_state[key])])
    except: pass

def render_sidebar(left_col):
    df = pd.DataFrame(st.session_state['nodes_db'])
    kw_counts = pd.DataFrame()
    if not df.empty:
        all_kw = []
        for ks in df['keywords']: all_kw.extend(ks)
        if all_kw:
            kw_counts = pd.Series(all_kw).value_counts().reset_index()
            kw_counts.columns = ['keyword', 'count']

    with left_col:
        all_kws = kw_counts['keyword'].tolist() if not kw_counts.empty else []
        options = [h for h in st.session_state['search_history'] if h in all_kws] + [k for k in all_kws if k not in st.session_state['search_history']]
        selected = st.multiselect("Search (Keywords)", options=options, default=[st.session_state['selected_keyword']] if st.session_state['selected_keyword'] in options else [], max_selections=1, placeholder="🔍 Select Keyword...", label_visibility="collapsed")
        
        if selected:
            if selected[0] != st.session_state['selected_keyword']:
                st.session_state['selected_keyword'] = selected[0]
                if selected[0] in st.session_state['search_history']: st.session_state['search_history'].remove(selected[0])
                st.session_state['search_history'].insert(0, selected[0])
                st.rerun()
        elif st.session_state['selected_keyword']: st.session_state['selected_keyword'] = None; st.rerun()

        c1, c2 = st.columns([0.65, 0.35]) 
        with c1: st.markdown("<div class='tight-header'>🔑 Key</div>", unsafe_allow_html=True)
        with c2: 
            if st.button("Reset", key="rk"): st.session_state['selected_keyword'] = None; st.rerun()
        st.markdown("<hr class='tight-hr'>", unsafe_allow_html=True)
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

def render_node_page(main_col):
    df = pd.DataFrame(st.session_state['nodes_db'])
    node_degree, edges = {}, []
    if not df.empty:
        df['id'] = df['id'].astype(str)
        node_degree = {r['id']:0 for _,r in df.iterrows()}
        for i in range(len(df)):
            for j in range(i+1, len(df)):
                if set(df.iloc[i]['keywords']) & set(df.iloc[j]['keywords']):
                    edges.append(Edge(source=df.iloc[i]['id'], target=df.iloc[j]['id'], color="#555"))
                    node_degree[df.iloc[i]['id']] += 1; node_degree[df.iloc[j]['id']] += 1

    current_mode = st.session_state['menu_mode']
    
    with main_col:
        # [VIEW 1] GRAPH
        if current_mode == "Knowledge Graph":
            c_g1, c_g2 = st.columns([8, 2])
            with c_g2:
                with st.expander("⚙️ 효과 설정", expanded=False):
                    st.caption("🌊 물방울 물리 엔진")
                    st.checkbox("💧 물방울 모드", value=st.session_state['phy_active'], key="phy_active", on_change=on_update_setting, args=("phy_active",))
                    st.divider()
                    st.slider("점성", 0.1, 1.0, value=st.session_state['phy_damping'], step=0.05, key="phy_damping", on_change=on_update_setting, args=("phy_damping",))
                    st.slider("척력", -2000, -100, value=st.session_state['phy_repulsion'], step=100, key="phy_repulsion", on_change=on_update_setting, args=("phy_repulsion",))
                    st.slider("간격", 50, 400, value=st.session_state['phy_len'], step=10, key="phy_len", on_change=on_update_setting, args=("phy_len",))
                    st.checkbox("겹침 방지", value=st.session_state['phy_overlap'], key="phy_overlap", on_change=on_update_setting, args=("phy_overlap",))

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
                    ag_nodes.append(Node(id=r['id'], label=r['label'], title=f"{r['label']}\n{r['keywords']}", size=sz, color=clr, font={'color':fclr}, borderWidth=bw, borderColor=sc))
                for e in edges:
                    e_w, e_c = 1, "#555"
                    if sel_kw:
                        src_k = set(df[df['id']==e.source]['keywords'].iloc[0]); tgt_k = set(df[df['id']==e.to]['keywords'].iloc[0])
                        if sel_kw in src_k and sel_kw in tgt_k: e_w, e_c = 4, "#00FF00"
                        else: e_c = "#222"
                    final_edges.append(Edge(source=e.source, target=e.to, color=e_c, width=e_w))

            cfg = Config(width="100%", height=600, directed=False, nodeHighlightBehavior=True, highlightColor="#F7A7A6", collapsible=False, 
                         node={'labelProperty':'label', 'renderLabel':True, 'font': {'color': 'white'}},
                         interaction={'hover':True, 'navigationButtons':False, 'keyboard':False}, 
                         backgroundColor="#000000")
            cfg.physics = {
                "enabled": True, "solver": "forceAtlas2Based",
                "forceAtlas2Based": { "theta": 0.5, "gravitationalConstant": st.session_state['phy_repulsion'], "centralGravity": 0.01, "springConstant": 0.08, "springLength": st.session_state['phy_len'], "damping": st.session_state['phy_damping'], "avoidOverlap": 1 if st.session_state['phy_overlap'] else 0 },
                "stabilization": { "enabled": not st.session_state['phy_active'], "iterations": 1000 }
            }
            sel = agraph(nodes=ag_nodes, edges=final_edges, config=cfg)
            if sel and sel != st.session_state['last_selection']: 
                st.session_state['last_selection'] = sel; act_add_ws(sel); st.rerun()

            wsn = st.session_state['workspace_nodes']
            if wsn:
                wc1, wc2 = st.columns([8, 2])
                wc1.markdown("#### 📑 Active Nodes (Edit Mode)")
                if wc2.button("🧹 Clear All", use_container_width=True): act_clear_ws(); st.rerun()
                w_cols = st.columns(3) 
                for idx, n in enumerate(wsn):
                    with w_cols[idx % 3]:
                        with st.container(border=True):
                            b1, b2, b3, b4 = st.columns(4)
                            nl = st.text_input("Title", value=n['label'], key=f"l_{n['id']}")
                            nk = st.text_input("Keywords", value=", ".join(n['keywords']), key=f"k_{n['id']}")
                            ns = st.text_area("Summary", value=n['summary'], height=100, key=f"s_{n['id']}")
                            
                            if b1.button("💾", key=f"up_{n['id']}", use_container_width=True): act_update(n['id'], nl, ns, nk)
                            with b2:
                                if st.button("📋", key=f"cp_g_{n['id']}", help="복사"):
                                    copy_to_clipboard(f"Title: {n['label']}\n{n['summary']}")
                                    st.toast("Copied!")
                            if b3.button("🗑️", key=f"del_{n['id']}", use_container_width=True): act_trash(n['id'])
                            if b4.button("✕", key=f"cl_{n['id']}", use_container_width=True): act_close_ws(n['id']); st.rerun()

        # [VIEW 2] LIST MODE
        elif current_mode == "List View":
            st.text_input("🔍 노드 검색 (제목/내용)", placeholder="Search...", label_visibility="collapsed", key="node_search_query")
            search_query = st.session_state.get("node_search_query", "")

            if st.session_state['card_stack']:
                st.markdown("### 🗂️ Active Stack")
                stack_cols = st.columns(3)
                for i, node_data in enumerate(st.session_state['card_stack']):
                    with stack_cols[i % 3]:
                        with st.container(border=True):
                            st_c1, st_c2, st_c3, st_c4, st_c5 = st.columns([6, 0.8, 0.8, 0.8, 0.8])
                            st_c1.markdown(f"#### {node_data['label']}")
                            
                            with st_c2:
                                if st.button("📋", key=f"cp_l_{node_data['id']}", help="복사"):
                                    copy_to_clipboard(f"Title: {node_data['label']}\n{node_data['summary']}")
                                    st.toast("Copied!")
                            if st_c3.button("✏️", key=f"se_{node_data['id']}_{i}", use_container_width=True):
                                st.session_state['menu_mode'] = "Knowledge Graph"; act_add_ws(node_data['id']); st.rerun()
                            if st_c4.button("🗑️", key=f"sd_{node_data['id']}_{i}", use_container_width=True): act_trash(node_data['id'])
                            if st_c5.button("✕", key=f"sc_{node_data['id']}_{i}", use_container_width=True):
                                st.session_state['card_stack'].pop(i); st.rerun()
                                
                            st.info(node_data['summary'])
                            if node_data.get('content'):
                                with st.expander("📄 View Full Content"):
                                    st.markdown(node_data['content'], unsafe_allow_html=True)
                            st.caption(f"🕒 {node_data['timestamp']} | 🏷️ {', '.join(node_data['keywords'])}")
                st.divider()

            filtered_df = df
            if st.session_state['selected_keyword']:
                filtered_df = df[df['keywords'].apply(lambda x: st.session_state['selected_keyword'] in x)]
            
            if not filtered_df.empty:
                if search_query:
                    mask = filtered_df.apply(lambda row: search_query.lower() in (row['label'] + row['summary'] + str(row['keywords']) + str(row.get('content',''))).lower(), axis=1)
                    filtered_df = filtered_df[mask]

                try:
                    filtered_df['sort_dt'] = pd.to_datetime(filtered_df['timestamp'], format="%y-%m-%d %H:%M", errors='coerce')
                    filtered_df['sort_dt'] = filtered_df['sort_dt'].fillna(pd.Timestamp.now())
                    filtered_df = filtered_df.sort_values(by='sort_dt', ascending=False)
                except: pass

                st.caption(f"Total: {len(filtered_df)} Nodes")
                for _, row in filtered_df.iterrows():
                    row_col1, row_col2 = st.columns([0.95, 0.05])
                    with row_col1:
                        h_label = highlight_text(row['label'], search_query)
                        h_summary = highlight_text(row['summary'], search_query)
                        date_str = str(row['timestamp']).split()[0]
                        
                        with st.expander(f"{row['label']} | {', '.join(row['keywords'])} ({date_str})", expanded=bool(search_query)):
                            st.markdown(f"**Title:** {h_label}", unsafe_allow_html=True)
                            st.markdown(h_summary, unsafe_allow_html=True)
                            if row.get('content'):
                                st.markdown("---")
                                st.markdown(row['content'], unsafe_allow_html=True)
                    with row_col2:
                        with st.popover("⋮"):
                            if st.button("View", key=f"lv_v_{row['id']}", use_container_width=True):
                                if row['id'] not in [n['id'] for n in st.session_state['card_stack']]:
                                    st.session_state['card_stack'].append(row.to_dict()); st.rerun()
                            if st.button("Edit", key=f"lv_e_{row['id']}", use_container_width=True):
                                st.session_state['menu_mode'] = "Knowledge Graph"; act_add_ws(row['id']); st.rerun()
                            if st.button("Trash", key=f"lv_d_{row['id']}", use_container_width=True): act_trash(row['id'])
            else: st.info("No data found.")

        # ==========================================
        # [VIEW 3] ADD DATA (SAFE FORM)
        # ==========================================
        elif current_mode == "Add Data":
            st.subheader("📝 Add New Knowledge Node")
            
            # [KEY ROTATION] 폼 초기화를 위한 ID 생성
            if 'node_form_id' not in st.session_state:
                st.session_state['node_form_id'] = 0
            
            # Form ID를 키에 포함시켜서, ID가 바뀌면 아예 새로운 입력창이 생성되게 함
            form_id = st.session_state['node_form_id']
            
            # 1. Title
            title = st.text_input("Title", key=f"n_title_{form_id}", placeholder="노드 제목을 입력하세요...")
            
            # 2. Content (Quill or Text)
            st.markdown("###### Content (Rich Text & Image)")
            toolbar = [['bold', 'italic', 'underline', 'strike'], ['blockquote', 'code-block'], [{'header': 1}, {'header': 2}], [{'list': 'ordered'}, {'list': 'bullet'}], [{'indent': '-1'}, {'indent': '+1'}], ['link', 'image'], ['clean']]
            
            content_val = ""
            if st_quill:
                # Quill은 내용을 직접 리턴함
                content_val = st_quill(placeholder="내용을 입력하거나 이미지를 붙여넣으세요...", html=True, toolbar=toolbar, key=f"n_quill_{form_id}")
            else:
                content_val = st.text_area("Content", height=300, key=f"n_content_{form_id}")

            # 3. AI Summary Button
            # (AI 결과는 폼 ID와 무관하게 임시 저장소에 담았다가, 키워드/요약 입력창의 value로 넣어줌)
            if 'ai_result_summary' not in st.session_state: st.session_state['ai_result_summary'] = ""
            if 'ai_result_kw' not in st.session_state: st.session_state['ai_result_kw'] = ""

            c_ai, _ = st.columns([2, 8])
            with c_ai:
                if st.button("✨ AI 요약 실행 (선택)", use_container_width=True):
                    if content_val:
                        with st.spinner("AI가 분석 중입니다..."):
                            clean_text = strip_html(content_val)
                            res = ai_process(clean_text)
                            if res['success']:
                                st.session_state['ai_result_summary'] = res.get('summary', '')
                                st.session_state['ai_result_kw'] = res.get('keywords', '')
                                st.toast("AI 분석 완료! 아래 필드가 채워졌습니다.")
                                st.rerun()
                            else:
                                st.error(f"AI 분석 실패: {res['error']}")
                    else:
                        st.warning("내용(Content)을 먼저 입력해주세요.")

            # 4. Summary & Keywords
            c1, c2 = st.columns(2)
            with c1:
                # AI 결과가 있으면 그걸 기본값으로 보여줌
                summary = st.text_area("Summary", value=st.session_state['ai_result_summary'], key=f"n_sum_{form_id}", height=100, placeholder="요약 내용...")
            with c2:
                kw_str = st.text_input("Keywords (쉼표로 구분)", value=st.session_state['ai_result_kw'], key=f"n_kw_{form_id}", placeholder="tag1, tag2...")
            
            st.markdown("<br>", unsafe_allow_html=True)

            # 5. Save Button
            if st.button("💾 저장하기", type="primary", use_container_width=True):
                if not title:
                    st.warning("제목(Title)은 필수입니다.")
                else:
                    clean_content = strip_html(content_val)
                    final_summary = summary if summary else (clean_content[:100] + "..." if clean_content else "No Summary")
                    final_keywords = [k.strip() for k in kw_str.split(',') if k.strip()]
                    group_name = final_keywords[0] if final_keywords else "General"
                    
                    new_node_data = add_node(title, group_name, final_summary, final_keywords, content_val)
                    
                    if new_node_data:
                        st.session_state['nodes_db'].append(new_node_data)
                        
                        # [SUCCESS ACTION]
                        # 1. AI 임시 저장소 초기화
                        st.session_state['ai_result_summary'] = ""
                        st.session_state['ai_result_kw'] = ""
                        # 2. Form ID 증가 -> 다음 렌더링 때 새로운 빈 위젯들이 생성됨 (자동 초기화 효과)
                        st.session_state['node_form_id'] += 1
                        
                        st.success("노드가 저장되었습니다!")
                        time.sleep(1)
                        st.session_state['menu_mode'] = "Knowledge Graph"
                        st.rerun()
                    else:
                        st.error("저장 중 오류가 발생했습니다.")
