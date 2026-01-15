import streamlit as st
import pandas as pd
import time
from streamlit_agraph import agraph, Node, Edge, Config
from utils.db_api import update_node, move_to_trash, add_node, ai_process, get_group_color, get_workbook, save_setting_to_db

# [Actions]
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

# [Sidebar]
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
        selected = st.multiselect("Search", options=options, default=[st.session_state['selected_keyword']] if st.session_state['selected_keyword'] in options else [], max_selections=1, placeholder="🔍 Select...", label_visibility="collapsed")
        
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

# [Main Renderer]
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
        # 1. Graph View
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
                            # [NEW] Active Node Card에도 복사 버튼 추가
                            # Save(Update) | Copy | Trash | Close
                            b1, b2, b3, b4 = st.columns(4)
                            nl = st.text_input("Title", value=n['label'], key=f"l_{n['id']}")
                            nk = st.text_input("Keywords", value=", ".join(n['keywords']), key=f"k_{n['id']}")
                            ns = st.text_area("Summary", value=n['summary'], height=100, key=f"s_{n['id']}")
                            
                            if b1.button("💾", key=f"up_{n['id']}", use_container_width=True): act_update(n['id'], nl, ns, nk)
                            # 복사 버튼 (Popover)
                            with b2:
                                with st.popover("📋", use_container_width=True): st.code(n['summary'], language='text')
                            if b3.button("🗑️", key=f"del_{n['id']}", use_container_width=True): act_trash(n['id'])
                            if b4.button("✕", key=f"cl_{n['id']}", use_container_width=True): act_close_ws(n['id']); st.rerun()

        # 2. List View
        elif current_mode == "List View":
            if st.session_state['card_stack']:
                st.markdown("### 🗂️ Active Stack")
                stack_cols = st.columns(3)
                for i, node_data in enumerate(st.session_state['card_stack']):
                    with stack_cols[i % 3]:
                        with st.container(border=True):
                            # [NEW] Header: Label(6) | Copy(0.8) | Edit(0.8) | Del(0.8) | Close(0.8)
                            st_c1, st_c2, st_c3, st_c4, st_c5 = st.columns([6, 0.8, 0.8, 0.8, 0.8])
                            st_c1.markdown(f"#### {node_data['label']}")
                            
                            with st_c2:
                                with st.popover("📋", use_container_width=True): st.code(node_data['summary'], language='text')
                            
                            if st_c3.button("✏️", key=f"se_{node_data['id']}_{i}", use_container_width=True):
                                st.session_state['menu_mode'] = "Knowledge Graph"; act_add_ws(node_data['id']); st.rerun()
                            if st_c4.button("🗑️", key=f"sd_{node_data['id']}_{i}", use_container_width=True): act_trash(node_data['id'])
                            if st_c5.button("✕", key=f"sc_{node_data['id']}_{i}", use_container_width=True):
                                st.session_state['card_stack'].pop(i); st.rerun()
                                
                            st.info(node_data['summary'])
                            st.caption(f"🕒 {node_data['timestamp']} | 🏷️ {', '.join(node_data['keywords'])}")
                st.divider()

            filtered_df = df
            if st.session_state['selected_keyword']:
                filtered_df = df[df['keywords'].apply(lambda x: st.session_state['selected_keyword'] in x)]
            
            if not filtered_df.empty:
                try:
                    filtered_df['sort_dt'] = pd.to_datetime(filtered_df['timestamp'], format="%y-%m-%d %H:%M", errors='coerce')
                    filtered_df['sort_dt'] = filtered_df['sort_dt'].fillna(pd.Timestamp.now())
                    filtered_df = filtered_df.sort_values(by='sort_dt', ascending=False)
                except Exception: pass

                st.caption(f"Total: {len(filtered_df)} Nodes")
                for _, row in filtered_df.iterrows():
                    row_col1, row_col2 = st.columns([0.95, 0.05])
                    with row_col1:
                        date_str = str(row['timestamp']).split()[0]
                        final_label = f"**{row['label']}** :gray[| {', '.join(row['keywords'])}] :gray[({date_str})]"
                        with st.expander(final_label, expanded=False):
                            st.write(row['summary'])
                            st.caption(f"Full Timestamp: {row['timestamp']}")
                    with row_col2:
                        with st.popover("⋮"):
                            # Popover 내부에도 복사 버튼 추가 가능
                            if st.button("Copy Content", key=f"cp_{row['id']}", use_container_width=True):
                                # 하지만 Popover 안에서 Code를 띄우는 건 UX가 좋지 않을 수 있어 상단 Card Stack 방식을 권장함.
                                pass 
                            if st.button("View", key=f"lv_v_{row['id']}", use_container_width=True):
                                if row['id'] not in [n['id'] for n in st.session_state['card_stack']]:
                                    st.session_state['card_stack'].append(row.to_dict()); st.rerun()
                            if st.button("Edit", key=f"lv_e_{row['id']}", use_container_width=True):
                                st.session_state['menu_mode'] = "Knowledge Graph"; act_add_ws(row['id']); st.rerun()
                            if st.button("Trash", key=f"lv_d_{row['id']}", use_container_width=True): act_trash(row['id'])
            else: st.info("No data found.")

        # 3. Add Data View
        elif current_mode == "Add Data":
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
                if not tmp['success']: st.error(f"{tmp['error']}") 
                else: st.success("Analysis Complete!")
                n_title = st.text_input("Title", value=tmp['title'])
                st.caption("Original Content")
                st.text_area("Original Content", value=tmp['content'], height=150, disabled=True, label_visibility="collapsed")
                n_sum = st.text_area("AI Summary", value=tmp['summary'], height=100)
                n_kw = st.text_input("Keywords", value=tmp['keywords'])
                if st.button("💾 Save", type="primary", use_container_width=True):
                    final_keywords = [k.strip() for k in n_kw.split(',')]
                    group_name = final_keywords[0] if final_keywords else "General"
                    new_node_data = add_node(n_title, group_name, n_sum, final_keywords)
                    if new_node_data:
                        st.session_state['nodes_db'].append(new_node_data)
                        st.session_state['temp_analysis'] = None
                        st.success("Saved!"); time.sleep(1); st.session_state['menu_mode'] = "Knowledge Graph"; st.rerun()
                    else: st.error("Save Error")
                if st.button("Cancel", use_container_width=True): st.session_state['temp_analysis'] = None; st.rerun()
