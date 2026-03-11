"""
node_ui.py — Knowledge Graph / List View / Add Data UI
"""
import streamlit as st
import pandas as pd
import time
from streamlit_agraph import agraph, Node, Edge, Config
from utils.db_node import update_node, move_to_trash, add_node, ai_process, get_group_color
from utils.db_common import (
    save_setting_to_db, copy_to_clipboard, strip_html, highlight_text
)

try:
    from streamlit_quill import st_quill
except ImportError:
    st_quill = None

from utils.style import QUILL_TOOLBAR

# ==========================================
# ACTION HELPERS
# ==========================================
def _add_to_workspace(node_id):
    """노드를 워크스페이스에 추가"""
    tid = str(node_id)
    if tid not in [str(n['id']) for n in st.session_state['workspace_nodes']]:
        tgt = next((n for n in st.session_state['nodes_db'] if str(n['id']) == tid), None)
        if tgt:
            st.session_state['workspace_nodes'].append(tgt)

def _close_workspace(nid):
    """워크스페이스에서 노드 제거"""
    st.session_state['workspace_nodes'] = [
        n for n in st.session_state['workspace_nodes'] if str(n['id']) != str(nid)
    ]

def _clear_workspace():
    """워크스페이스 전체 비우기"""
    st.session_state['workspace_nodes'] = []

def _do_update(nid, label, summary, kw_str):
    """노드 업데이트 (DB + session)"""
    k_list = [k.strip() for k in kw_str.split(',') if k.strip()]
    update_node(nid, label, summary, k_list)
    for collection in [st.session_state['nodes_db'], st.session_state['workspace_nodes']]:
        for n in collection:
            if str(n['id']) == str(nid):
                n['label'] = label
                n['summary'] = summary
                n['keywords'] = k_list
    st.success("Updated!")
    time.sleep(0.5)
    st.rerun()

def _do_trash(nid):
    """노드 휴지통 이동 (DB + session)"""
    tgt = next((n for n in st.session_state['nodes_db'] if str(n['id']) == str(nid)), None)
    if tgt:
        move_to_trash(nid, tgt)
        st.session_state['nodes_db'] = [n for n in st.session_state['nodes_db'] if str(n['id']) != str(nid)]
        st.session_state['card_stack'] = [n for n in st.session_state['card_stack'] if str(n['id']) != str(nid)]
        _close_workspace(nid)
        st.success("Moved to Trash 🗑️")
        time.sleep(0.5)
        st.rerun()

def _on_setting_change(key):
    """물리 엔진 설정 변경 콜백"""
    save_setting_to_db(key, st.session_state[key])

# ==========================================
# SIDEBAR
# ==========================================
def render_sidebar(left_col):
    """좌측 키워드 사이드바 렌더링"""
    df = pd.DataFrame(st.session_state['nodes_db'])
    kw_counts = pd.DataFrame()
    if not df.empty:
        all_kw = []
        for ks in df['keywords']:
            all_kw.extend(ks)
        if all_kw:
            kw_counts = pd.Series(all_kw).value_counts().reset_index()
            kw_counts.columns = ['keyword', 'count']

    with left_col:
        all_kws = kw_counts['keyword'].tolist() if not kw_counts.empty else []
        # 검색 이력 우선 정렬
        options = [h for h in st.session_state['search_history'] if h in all_kws] + \
                  [k for k in all_kws if k not in st.session_state['search_history']]

        current_kw = st.session_state['selected_keyword']
        default_val = [current_kw] if current_kw in options else []

        selected = st.multiselect(
            "Search (Keywords)", options=options, default=default_val,
            max_selections=1, placeholder="🔍 Select Keyword...", label_visibility="collapsed"
        )

        if selected:
            if selected[0] != current_kw:
                st.session_state['selected_keyword'] = selected[0]
                hist = st.session_state['search_history']
                if selected[0] in hist:
                    hist.remove(selected[0])
                hist.insert(0, selected[0])
                st.rerun()
        elif current_kw:
            st.session_state['selected_keyword'] = None
            st.rerun()

        c1, c2 = st.columns([0.65, 0.35])
        with c1:
            st.markdown("<div class='tight-header'>🔑 Key</div>", unsafe_allow_html=True)
        with c2:
            if st.button("Reset", key="rk"):
                st.session_state['selected_keyword'] = None
                st.rerun()

        st.markdown("<hr class='tight-hr'>", unsafe_allow_html=True)

        with st.container(height=600):
            if not kw_counts.empty:
                for i, row in enumerate(kw_counts.itertuples(), 1):
                    kw = row.keyword
                    color = "#00ADB5" if kw == st.session_state['selected_keyword'] else "#fff"
                    rc = st.columns([0.8, 3, 1.2])
                    rc[0].markdown(f"<div class='list-content-row col-center' style='color:{color}'>{i}</div>", unsafe_allow_html=True)
                    if rc[1].button(kw, key=f"kbtn_{i}", use_container_width=True):
                        st.session_state['selected_keyword'] = None if st.session_state['selected_keyword'] == kw else kw
                        st.rerun()
                    rc[2].markdown(f"<div class='list-content-row col-center' style='color:#888'>{row.count}</div>", unsafe_allow_html=True)
                    st.markdown("<div style='border-bottom: 1px solid #222; margin-bottom: 2px;'></div>", unsafe_allow_html=True)

# ==========================================
# MAIN PAGE ROUTER
# ==========================================
def render_node_page(main_col):
    """Node 관련 페이지 렌더링 (Graph / List / Add)"""
    df = pd.DataFrame(st.session_state['nodes_db'])
    node_degree, edges = {}, []

    if not df.empty:
        df['id'] = df['id'].astype(str)
        node_degree = {r['id']: 0 for _, r in df.iterrows()}
        for i in range(len(df)):
            for j in range(i + 1, len(df)):
                if set(df.iloc[i]['keywords']) & set(df.iloc[j]['keywords']):
                    edges.append(Edge(source=df.iloc[i]['id'], target=df.iloc[j]['id'], color="#555"))
                    node_degree[df.iloc[i]['id']] += 1
                    node_degree[df.iloc[j]['id']] += 1

    current_mode = st.session_state['menu_mode']

    with main_col:
        if current_mode == "Knowledge Graph":
            _render_graph_view(df, node_degree, edges)
        elif current_mode == "List View":
            _render_list_view(df)
        elif current_mode == "Add Data":
            _render_add_view()

# ==========================================
# [VIEW 1] GRAPH
# ==========================================
def _render_graph_view(df, node_degree, edges):
    c_g1, c_g2 = st.columns([8, 2])
    with c_g2:
        with st.expander("⚙️ 효과 설정", expanded=False):
            st.caption("🌊 물방울 물리 엔진")
            st.checkbox("💧 물방울 모드", value=st.session_state['phy_active'], key="phy_active", on_change=_on_setting_change, args=("phy_active",))
            st.divider()
            st.slider("점성", 0.1, 1.0, value=st.session_state['phy_damping'], step=0.05, key="phy_damping", on_change=_on_setting_change, args=("phy_damping",))
            st.slider("척력", -2000, -100, value=st.session_state['phy_repulsion'], step=100, key="phy_repulsion", on_change=_on_setting_change, args=("phy_repulsion",))
            st.slider("간격", 50, 400, value=st.session_state['phy_len'], step=10, key="phy_len", on_change=_on_setting_change, args=("phy_len",))
            st.checkbox("겹침 방지", value=st.session_state['phy_overlap'], key="phy_overlap", on_change=_on_setting_change, args=("phy_overlap",))

    ag_nodes, final_edges = [], []
    sel_kw = st.session_state['selected_keyword']

    if not df.empty:
        for _, r in df.iterrows():
            base_color = get_group_color(r['group'])
            sz = min(20 + node_degree.get(r['id'], 0) * 5, 60)
            clr, fclr, bw, sc = base_color, "white", 1, base_color
            if sel_kw:
                if sel_kw in r['keywords']:
                    clr, sz, fclr, bw, sc = "#00FF00", sz * 1.5, "#FFFFFF", 4, "#FFFFFF"
                else:
                    clr, fclr, sz, bw, sc = "#222", "#666", 15, 1, "#333"
            ag_nodes.append(Node(
                id=r['id'], label=r['label'],
                title=f"{r['label']}\n{r['keywords']}",
                size=sz, color=clr, font={'color': fclr},
                borderWidth=bw, borderColor=sc
            ))
        for e in edges:
            e_w, e_c = 1, "#555"
            if sel_kw:
                src_k = set(df[df['id'] == e.source]['keywords'].iloc[0])
                tgt_k = set(df[df['id'] == e.to]['keywords'].iloc[0])
                if sel_kw in src_k and sel_kw in tgt_k:
                    e_w, e_c = 4, "#00FF00"
                else:
                    e_c = "#222"
            final_edges.append(Edge(source=e.source, target=e.to, color=e_c, width=e_w))

    cfg = Config(
        width="100%", height=600, directed=False,
        nodeHighlightBehavior=True, highlightColor="#F7A7A6", collapsible=False,
        node={'labelProperty': 'label', 'renderLabel': True, 'font': {'color': 'white'}},
        interaction={'hover': True, 'navigationButtons': False, 'keyboard': False},
        backgroundColor="#000000"
    )
    cfg.physics = {
        "enabled": True, "solver": "forceAtlas2Based",
        "forceAtlas2Based": {
            "theta": 0.5,
            "gravitationalConstant": st.session_state['phy_repulsion'],
            "centralGravity": 0.01, "springConstant": 0.08,
            "springLength": st.session_state['phy_len'],
            "damping": st.session_state['phy_damping'],
            "avoidOverlap": 1 if st.session_state['phy_overlap'] else 0
        },
        "stabilization": {"enabled": not st.session_state['phy_active'], "iterations": 1000}
    }

    sel = agraph(nodes=ag_nodes, edges=final_edges, config=cfg)
    if sel and sel != st.session_state['last_selection']:
        st.session_state['last_selection'] = sel
        _add_to_workspace(sel)
        st.rerun()

    # Workspace (Active Nodes)
    wsn = st.session_state['workspace_nodes']
    if wsn:
        wc1, wc2 = st.columns([8, 2])
        wc1.markdown("#### 📑 Active Nodes (Edit Mode)")
        if wc2.button("🧹 Clear All", use_container_width=True):
            _clear_workspace()
            st.rerun()

        w_cols = st.columns(3)
        for idx, n in enumerate(wsn):
            with w_cols[idx % 3]:
                with st.container(border=True):
                    b1, b2, b3, b4 = st.columns(4)
                    nl = st.text_input("Title", value=n['label'], key=f"l_{n['id']}")
                    nk = st.text_input("Keywords", value=", ".join(n['keywords']), key=f"k_{n['id']}")
                    ns = st.text_area("Summary", value=n['summary'], height=100, key=f"s_{n['id']}")

                    if b1.button("💾", key=f"up_{n['id']}", use_container_width=True):
                        _do_update(n['id'], nl, ns, nk)
                    with b2:
                        if st.button("📋", key=f"cp_g_{n['id']}", help="복사"):
                            copy_to_clipboard(f"Title: {n['label']}\n{n['summary']}")
                            st.toast("Copied!")
                    if b3.button("🗑️", key=f"del_{n['id']}", use_container_width=True):
                        _do_trash(n['id'])
                    if b4.button("✕", key=f"cl_{n['id']}", use_container_width=True):
                        _close_workspace(n['id'])
                        st.rerun()

# ==========================================
# [VIEW 2] LIST
# ==========================================
def _render_list_view(df):
    st.text_input("🔍 노드 검색 (제목/내용)", placeholder="Search...", label_visibility="collapsed", key="node_search_query")
    search_query = st.session_state.get("node_search_query", "")

    # Active Stack
    if st.session_state['card_stack']:
        st.markdown("### 🗂️ Active Stack")
        stack_cols = st.columns(3)
        for i, node_data in enumerate(st.session_state['card_stack']):
            with stack_cols[i % 3]:
                with st.container(border=True):
                    sc1, sc2, sc3, sc4, sc5 = st.columns([6, 0.8, 0.8, 0.8, 0.8])
                    sc1.markdown(f"#### {node_data['label']}")
                    with sc2:
                        if st.button("📋", key=f"cp_l_{node_data['id']}", help="복사"):
                            copy_to_clipboard(f"Title: {node_data['label']}\n{node_data['summary']}")
                            st.toast("Copied!")
                    if sc3.button("✏️", key=f"se_{node_data['id']}_{i}", use_container_width=True):
                        st.session_state['menu_mode'] = "Knowledge Graph"
                        _add_to_workspace(node_data['id'])
                        st.rerun()
                    if sc4.button("🗑️", key=f"sd_{node_data['id']}_{i}", use_container_width=True):
                        _do_trash(node_data['id'])
                    if sc5.button("✕", key=f"sc_{node_data['id']}_{i}", use_container_width=True):
                        st.session_state['card_stack'].pop(i)
                        st.rerun()

                    st.info(node_data['summary'])
                    if node_data.get('content'):
                        with st.expander("📄 View Full Content"):
                            st.markdown(node_data['content'], unsafe_allow_html=True)
                    st.caption(f"🕒 {node_data['timestamp']} | 🏷️ {', '.join(node_data['keywords'])}")
        st.divider()

    # Filtered List
    filtered_df = df
    if st.session_state['selected_keyword'] and not df.empty:
        filtered_df = df[df['keywords'].apply(lambda x: st.session_state['selected_keyword'] in x)]

    if not filtered_df.empty:
        if search_query:
            mask = filtered_df.apply(
                lambda row: search_query.lower() in (
                    row['label'] + row['summary'] + str(row['keywords']) + str(row.get('content', ''))
                ).lower(), axis=1
            )
            filtered_df = filtered_df[mask]

        # 날짜순 정렬
        try:
            filtered_df = filtered_df.copy()
            filtered_df['sort_dt'] = pd.to_datetime(filtered_df['timestamp'], format="%y-%m-%d %H:%M", errors='coerce')
            filtered_df['sort_dt'] = filtered_df['sort_dt'].fillna(pd.Timestamp.now())
            filtered_df = filtered_df.sort_values(by='sort_dt', ascending=False)
        except Exception:
            pass

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
                            st.session_state['card_stack'].append(row.to_dict())
                            st.rerun()
                    if st.button("Edit", key=f"lv_e_{row['id']}", use_container_width=True):
                        st.session_state['menu_mode'] = "Knowledge Graph"
                        _add_to_workspace(row['id'])
                        st.rerun()
                    if st.button("Trash", key=f"lv_d_{row['id']}", use_container_width=True):
                        _do_trash(row['id'])
    else:
        st.info("No data found.")

# ==========================================
# [VIEW 3] ADD DATA
# ==========================================
def _render_add_view():
    st.subheader("📝 Add New Knowledge Node")

    if 'node_form_id' not in st.session_state:
        st.session_state['node_form_id'] = 0
    form_id = st.session_state['node_form_id']

    # Title
    title = st.text_input("Title", key=f"n_title_{form_id}", placeholder="노드 제목을 입력하세요...")

    # Content (Quill or TextArea)
    st.markdown("###### Content (Rich Text & Image)")
    content_val = ""
    if st_quill:
        content_val = st_quill(
            placeholder="내용을 입력하거나 이미지를 붙여넣으세요...",
            html=True, toolbar=QUILL_TOOLBAR, key=f"n_quill_{form_id}"
        )
    else:
        content_val = st.text_area("Content", height=300, key=f"n_content_{form_id}")

    # AI 분석 임시 저장소
    if 'ai_result_summary' not in st.session_state:
        st.session_state['ai_result_summary'] = ""
    if 'ai_result_kw' not in st.session_state:
        st.session_state['ai_result_kw'] = ""

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
                        st.toast("AI 분석 완료!")
                        st.rerun()
                    else:
                        st.error(f"AI 분석 실패: {res['error']}")
            else:
                st.warning("내용(Content)을 먼저 입력해주세요.")

    # Summary & Keywords
    c1, c2 = st.columns(2)
    with c1:
        summary = st.text_area("Summary", value=st.session_state['ai_result_summary'], key=f"n_sum_{form_id}", height=100, placeholder="요약 내용...")
    with c2:
        kw_str = st.text_input("Keywords (쉼표로 구분)", value=st.session_state['ai_result_kw'], key=f"n_kw_{form_id}", placeholder="tag1, tag2...")

    st.markdown("<br>", unsafe_allow_html=True)

    # Save
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
                st.session_state['ai_result_summary'] = ""
                st.session_state['ai_result_kw'] = ""
                st.session_state['node_form_id'] += 1
                st.success("노드가 저장되었습니다!")
                time.sleep(1)
                st.session_state['menu_mode'] = "Knowledge Graph"
                st.rerun()
            else:
                st.error("저장 중 오류가 발생했습니다.")
