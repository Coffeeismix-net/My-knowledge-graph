import streamlit as st
import pandas as pd
import json
import time
import streamlit.components.v1 as components
from utils.db_api import load_valuechains, add_valuechain, delete_valuechain, get_kst_now_str, copy_to_clipboard

# [HELPER] JSON -> Mermaid 변환기
def json_to_mermaid(data):
    try:
        if isinstance(data, str): data = json.loads(data)
        
        mermaid_code = "graph TD\n"
        
        mermaid_code += "    classDef groupNode fill:#f9f9f9,stroke:#333,stroke-width:2px;\n"
        mermaid_code += "    classDef itemNode fill:#fff,stroke:#333,stroke-width:1px;\n\n"
        
        for grp in data.get('groups', []):
            clean_name = grp['name'].replace(" ", "_")
            color = grp.get('color', '#eee')
            mermaid_code += f"    subgraph {clean_name} [{grp['name']}]\n"
            mermaid_code += f"        direction TB\n"
            mermaid_code += f"        style {clean_name} fill:{color},stroke:#333,stroke-width:2px\n"
            
            for node in grp.get('nodes', []):
                nid = node['id']
                label = node['label']
                desc = node.get('desc', '')
                display = f"{label}<br/>running: {desc}" if desc else label
                mermaid_code += f"        {nid}({display})\n"
                mermaid_code += f"        class {nid} itemNode\n"
            mermaid_code += "    end\n\n"
            
        for flow in data.get('flows', []):
            src = flow['from']
            dst = flow['to']
            lbl = flow.get('label', '')
            if lbl:
                mermaid_code += f"    {src} -- {lbl} --> {dst}\n"
            else:
                mermaid_code += f"    {src} --> {dst}\n"
                
        return mermaid_code
    except Exception as e:
        return f"graph TD\nA[Error Parsing JSON: {e}]"

# [HELPER] Mermaid 렌더링
def render_mermaid(code, height=600):
    html_code = f"""
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
    </script>
    <div class="mermaid">
        {code}
    </div>
    """
    components.html(html_code, height=height, scrolling=True)

# [MAIN RENDERER]
def render_valuechain_page(main_col):
    if 'vc_list' not in st.session_state:
        st.session_state['vc_list'] = load_valuechains()
    if 'vc_mode' not in st.session_state:
        st.session_state['vc_mode'] = 'list'
    if 'selected_vc_id' not in st.session_state:
        st.session_state['selected_vc_id'] = None

    st.markdown("""
    <style>
        .date-label { color: #666; font-size: 0.75rem; margin-left: 8px; white-space: nowrap; }
        div[data-testid="column"] button[kind="secondary"] { justify-content: flex-start !important; text-align: left !important; padding-left: 0px !important; border: none !important; }
        div[data-testid="column"] button[kind="secondary"] p { text-align: left !important; }
        div[data-testid="stPopover"] > button { border: none !important; background: transparent !important; color: #888 !important; }
        div[data-testid="stPopover"] > button:hover { color: white !important; }
    </style>
    """, unsafe_allow_html=True)
        
    with main_col:
        # ==========================================
        # [VIEW 1] LIST MODE
        # ==========================================
        if st.session_state['vc_mode'] == 'list':
            # [수정] 상단 Add 버튼 제거, 검색창만 남김
            st.text_input("🔍 밸류체인 검색", placeholder="Search...", label_visibility="collapsed", key="vc_search_query")
            search_query = st.session_state.get("vc_search_query", "")
            
            with st.container(height=280):
                if not st.session_state['vc_list']:
                    st.caption("등록된 밸류체인이 없습니다.")
                else:
                    sorted_list = sorted(st.session_state['vc_list'], key=lambda x: x['created_at'], reverse=True)
                    for vc in sorted_list:
                        if search_query and (search_query.lower() not in vc['title'].lower()):
                            continue
                        
                        r1, r2, r3 = st.columns([6, 3, 1])
                        with r1:
                            if st.button(f"⛓️ {vc['title']}", key=f"open_vc_{vc['id']}", use_container_width=True):
                                st.session_state['selected_vc_id'] = vc['id']
                                st.rerun()
                        with r2:
                            d_str = vc['created_at'][:16]
                            st.markdown(f"<div style='text-align: right; padding-top: 5px;'><span class='date-label'>{d_str}</span></div>", unsafe_allow_html=True)
                        with r3:
                            with st.popover("⋮", use_container_width=True):
                                if st.button("Trash", key=f"del_vc_{vc['id']}", use_container_width=True):
                                    delete_valuechain(vc['id'])
                                    st.session_state['vc_list'] = load_valuechains()
                                    if st.session_state['selected_vc_id'] == vc['id']:
                                        st.session_state['selected_vc_id'] = None
                                    st.toast("삭제되었습니다.")
                                    time.sleep(0.5)
                                    st.rerun()

            st.divider()

            if st.session_state['selected_vc_id']:
                target_vc = next((item for item in st.session_state['vc_list'] if item['id'] == st.session_state['selected_vc_id']), None)
                if target_vc:
                    with st.container(border=True):
                        h1, h2, h3 = st.columns([8, 1, 1])
                        with h1:
                            st.markdown(f"### {target_vc['title']}")
                            st.caption(f"Created: {target_vc['created_at']}")
                        with h2:
                            if st.button("📋", key="cp_vc_json", help="JSON 데이터 복사", use_container_width=True):
                                copy_to_clipboard(target_vc['json_data'])
                                st.toast("JSON 데이터가 복사되었습니다.")
                        with h3:
                            if st.button("✕", key="close_vc_viewer", help="닫기", use_container_width=True):
                                st.session_state['selected_vc_id'] = None
                                st.rerun()
                        
                        st.divider()
                        mm_code = json_to_mermaid(target_vc['json_data'])
                        render_mermaid(mm_code, height=600)
                        
                        with st.expander("🔍 원본 JSON 데이터 확인"):
                            st.json(target_vc['json_data'])
                else:
                    st.info("선택된 문서가 삭제되었거나 존재하지 않습니다.")
            else:
                st.info("👆 위 리스트에서 밸류체인을 선택하면 다이어그램이 표시됩니다.")

        # ==========================================
        # [VIEW 2] ADD MODE
        # ==========================================
        elif st.session_state['vc_mode'] == 'add':
            st.subheader("📝 새 밸류체인 작성")
            
            vc_title = st.text_input("제목", placeholder="예: 국내 원전 산업 밸류체인")
            st.info("💡 Gems(AI)에게 받은 JSON 코드를 아래에 붙여넣으세요.")
            
            default_json = """{
  "title": "예시 밸류체인",
  "groups": [
    { "name": "Group A", "color": "#e1f5fe", "nodes": [{ "id": "A1", "label": "Node 1" }] },
    { "name": "Group B", "color": "#e8f5e9", "nodes": [{ "id": "B1", "label": "Node 2" }] }
  ],
  "flows": [{ "from": "A1", "to": "B1", "label": "Flow" }]
}"""
            vc_json = st.text_area("JSON 데이터 입력", value=default_json, height=400)
            
            b1, b2 = st.columns([1, 1])
            with b1:
                # 취소 버튼만 남기고 뒤로가기 버튼은 상단 메뉴 사용
                if st.button("취소 (목록으로)", use_container_width=True):
                    st.session_state['vc_mode'] = 'list'
                    st.rerun()
            with b2:
                if st.button("💾 저장하기", type="primary", use_container_width=True):
                    if not vc_title:
                        st.warning("제목을 입력해주세요.")
                    else:
                        try:
                            json.loads(vc_json)
                            add_valuechain(vc_title, vc_json)
                            st.success("저장되었습니다!")
                            st.session_state['vc_list'] = load_valuechains()
                            st.session_state['vc_mode'] = 'list'
                            time.sleep(0.5)
                            st.rerun()
                        except json.JSONDecodeError:
                            st.error("JSON 형식이 올바르지 않습니다.")
