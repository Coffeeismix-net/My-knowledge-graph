import streamlit as st
import pandas as pd
import json
import time
import streamlit.components.v1 as components
from utils.db_api import load_valuechains, add_valuechain, delete_valuechain

# [HELPER] JSON -> Mermaid 변환기
def json_to_mermaid(data):
    try:
        if isinstance(data, str): data = json.loads(data)
        
        mermaid_code = "graph TD\n"
        
        # 스타일 정의
        mermaid_code += "    classDef groupNode fill:#f9f9f9,stroke:#333,stroke-width:2px;\n"
        mermaid_code += "    classDef itemNode fill:#fff,stroke:#333,stroke-width:1px;\n\n"
        
        # 그룹(서브그래프) 그리기
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
                # 노드 모양: id(이름<br/>설명)
                display = f"{label}<br/>running: {desc}" if desc else label
                mermaid_code += f"        {nid}({display})\n"
                # 주식 코드가 있으면 클릭 이벤트용 클래스 추가 가능 (여기선 단순화)
                mermaid_code += f"        class {nid} itemNode\n"
            mermaid_code += "    end\n\n"
            
        # 화살표(Flow) 그리기
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

# [HELPER] Mermaid 렌더링 컴포넌트
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
    # 초기화
    if 'vc_list' not in st.session_state:
        st.session_state['vc_list'] = load_valuechains()
    if 'vc_mode' not in st.session_state:
        st.session_state['vc_mode'] = 'list'
        
    with main_col:
        # 상단 네비게이션 (List <-> Add)
        c1, c2 = st.columns([8, 2])
        with c1: st.subheader("⛓️ Value Chain Analysis")
        with c2:
            if st.session_state['vc_mode'] == 'list':
                if st.button("➕ Add New", use_container_width=True):
                    st.session_state['vc_mode'] = 'add'
                    st.rerun()
            else:
                if st.button("⬅️ Back to List", use_container_width=True):
                    st.session_state['vc_mode'] = 'list'
                    st.rerun()
        
        st.divider()

        # [VIEW 1] LIST MODE
        if st.session_state['vc_mode'] == 'list':
            if not st.session_state['vc_list']:
                st.info("등록된 밸류체인이 없습니다. 'Add New'를 눌러 추가해보세요.")
            else:
                # 탭으로 여러 밸류체인을 전환하며 보기
                tabs = st.tabs([vc['title'] for vc in st.session_state['vc_list']])
                
                for i, tab in enumerate(tabs):
                    vc_data = st.session_state['vc_list'][i]
                    with tab:
                        c_h1, c_h2 = st.columns([9, 1])
                        with c_h1: st.caption(f"Created: {vc_data['created_at']}")
                        with c_h2:
                            if st.button("🗑️", key=f"del_vc_{vc_data['id']}", help="삭제"):
                                delete_valuechain(vc_data['id'])
                                st.session_state['vc_list'] = load_valuechains() # 갱신
                                st.rerun()
                        
                        # 다이어그램 그리기
                        mm_code = json_to_mermaid(vc_data['json_data'])
                        render_mermaid(mm_code)
                        
                        with st.expander("🔍 원본 JSON 보기"):
                            st.json(vc_data['json_data'])

        # [VIEW 2] ADD MODE
        elif st.session_state['vc_mode'] == 'add':
            st.markdown("### 새 밸류체인 만들기")
            st.info("💡 Gems(AI)에게 받은 JSON 코드를 아래에 붙여넣으세요.")
            
            vc_title = st.text_input("제목", placeholder="예: 국내 원전 산업 밸류체인")
            
            default_json = """{
  "title": "예시 밸류체인",
  "groups": [
    {
      "name": "생산",
      "color": "#e1f5fe",
      "nodes": [
        { "id": "A1", "label": "기업A", "desc": "핵심부품" }
      ]
    },
    {
      "name": "유통",
      "color": "#e8f5e9",
      "nodes": [
        { "id": "B1", "label": "기업B", "desc": "글로벌 유통" }
      ]
    }
  ],
  "flows": [
    { "from": "A1", "to": "B1", "label": "공급" }
  ]
}"""
            vc_json = st.text_area("JSON 데이터 입력", value=default_json, height=300)
            
            # 미리보기
            st.markdown("#### 미리보기")
            try:
                preview_code = json_to_mermaid(vc_json)
                render_mermaid(preview_code, height=300)
            except:
                st.error("JSON 형식이 올바르지 않습니다.")

            if st.button("💾 저장하기", type="primary", use_container_width=True):
                if not vc_title:
                    st.warning("제목을 입력해주세요.")
                else:
                    try:
                        # JSON 유효성 검사
                        json.loads(vc_json)
                        if add_valuechain(vc_title, vc_json):
                            st.success("저장되었습니다!")
                            st.session_state['vc_list'] = load_valuechains()
                            st.session_state['vc_mode'] = 'list'
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("저장 중 오류가 발생했습니다.")
                    except json.JSONDecodeError:
                        st.error("올바른 JSON 형식이 아닙니다.")
