import streamlit as st
import pandas as pd
import json
import time
from utils.db_api import load_valuechains, add_valuechain, delete_valuechain, copy_to_clipboard

# ==========================================
# [CORE] 재귀적 트리 렌더러 (폴더 구조 구현)
# ==========================================
def render_tree_node(nodes, level=0):
    """
    JSON의 'children'을 순회하며 폴더(Expander)와 파일(Text/Button)을 그립니다.
    재귀 함수를 사용하여 폴더 안에 폴더가 계속 들어갈 수 있습니다.
    """
    if not nodes: return

    for node in nodes:
        # [CASE 1] 폴더 (Folder) -> Expander로 구현
        if node.get('type') == 'folder':
            # 폴더 아이콘과 이름
            folder_label = f"📂 {node.get('name', 'Unnamed Folder')}"
            
            # Streamlit Expander 사용
            with st.expander(folder_label, expanded=True): # 기본적으로 펼쳐서 보여줌
                # 자식이 있다면 재귀 호출 (Level + 1)
                if 'children' in node and node['children']:
                    render_tree_node(node['children'], level + 1)
                else:
                    st.caption("(비어있음)")

        # [CASE 2] 파일 (File/Item) -> 기업 정보 표시
        else:
            # 파일 정보 추출
            name = node.get('name', 'Unknown')
            code = node.get('code', '')
            desc = node.get('desc', '')
            
            # 디자인: [종목명(코드)] - [설명]
            # Streamlit 컬럼으로 깔끔하게 배치
            c1, c2 = st.columns([4, 6])
            
            with c1:
                if code:
                    # 종목 코드가 있으면 굵게 표시
                    st.markdown(f"📄 **{name}** <span style='color:#888; font-size:0.8em;'>({code})</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"📄 **{name}**", unsafe_allow_html=True)
            
            with c2:
                if desc:
                    st.markdown(f"<span style='color:#bbb;'>{desc}</span>", unsafe_allow_html=True)

            # 항목 간 간격 미세 조정
            st.markdown("<hr style='margin: 5px 0; border-top: 1px solid #333;'>", unsafe_allow_html=True)

# [MAIN RENDERER]
def render_valuechain_page(main_col):
    # 데이터 초기화
    if 'vc_list' not in st.session_state:
        st.session_state['vc_list'] = load_valuechains()
    if 'vc_mode' not in st.session_state:
        st.session_state['vc_mode'] = 'list'
    if 'selected_vc_id' not in st.session_state:
        st.session_state['selected_vc_id'] = None

    # 스타일링
    st.markdown("""
    <style>
        .date-label { color: #666; font-size: 0.75rem; margin-left: 8px; white-space: nowrap; }
        /* Expander 스타일 조정 */
        .streamlit-expanderHeader { font-size: 1rem; font-weight: 600; color: #e0e0e0; background-color: #222; border-radius: 5px; }
        div[data-testid="stExpander"] { border: none; box-shadow: none; background-color: transparent; }
        div[data-testid="stExpanderDetails"] { border-left: 2px solid #444; margin-left: 10px; padding-left: 15px; }
        
        div[data-testid="column"] button[kind="secondary"] { justify-content: flex-start !important; text-align: left !important; padding-left: 0px !important; border: none !important; }
        div[data-testid="stPopover"] > button { border: none !important; background: transparent !important; color: #888 !important; }
        div[data-testid="stPopover"] > button:hover { color: white !important; }
    </style>
    """, unsafe_allow_html=True)
        
    with main_col:
        # ==========================================
        # [VIEW 1] LIST MODE
        # ==========================================
        if st.session_state['vc_mode'] == 'list':
            # 검색창 (Add 버튼 없음)
            st.text_input("🔍 밸류체인 검색", placeholder="Search...", label_visibility="collapsed", key="vc_search_query")
            search_query = st.session_state.get("vc_search_query", "")
            
            # 리스트 영역
            with st.container(height=280):
                if not st.session_state['vc_list']:
                    st.caption("등록된 밸류체인이 없습니다. 상단 메뉴 Chain > Add를 이용하세요.")
                else:
                    sorted_list = sorted(st.session_state['vc_list'], key=lambda x: x['created_at'], reverse=True)
                    for vc in sorted_list:
                        if search_query and (search_query.lower() not in vc['title'].lower()): continue
                        
                        r1, r2, r3 = st.columns([6, 3, 1])
                        with r1:
                            if st.button(f"🗂️ {vc['title']}", key=f"open_vc_{vc['id']}", use_container_width=True):
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
                                    time.sleep(0.5); st.rerun()
            st.divider()

            # 뷰어 영역 (트리 뷰)
            if st.session_state['selected_vc_id']:
                target_vc = next((item for item in st.session_state['vc_list'] if item['id'] == st.session_state['selected_vc_id']), None)
                if target_vc:
                    with st.container(border=True):
                        # 헤더
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
                        
                        # [핵심] JSON 파싱 및 트리 렌더링
                        try:
                            json_data = json.loads(target_vc['json_data'])
                            
                            # 1. 'structure' 키가 있는 경우 (Gems 신규 포맷)
                            if "structure" in json_data:
                                render_tree_node(json_data["structure"])
                                
                            # 2. 'groups' 키가 있는 경우 (구형 포맷 호환)
                            elif "groups" in json_data:
                                # 구형 데이터를 신규 폴더 구조로 변환하여 렌더링
                                converted_structure = []
                                for grp in json_data["groups"]:
                                    folder = { "name": grp.get("name", "Group"), "type": "folder", "children": [] }
                                    for node in grp.get("nodes", []):
                                        folder["children"].append({
                                            "name": node.get("label", "Unknown").replace("<br/>", " ").replace("\n", " "),
                                            "type": "file",
                                            "desc": node.get("desc", ""),
                                            "code": str(node.get("id", "")).replace("id_", "").replace("S", "")
                                        })
                                    converted_structure.append(folder)
                                render_tree_node(converted_structure)
                            else:
                                st.warning("지원되지 않는 데이터 형식입니다.")
                                st.json(json_data)
                                
                        except json.JSONDecodeError:
                            st.error("데이터가 올바른 JSON 형식이 아닙니다.")
                        except Exception as e:
                            st.error(f"렌더링 오류: {e}")

                        # 원본 데이터 확인용
                        with st.expander("🔍 원본 데이터 확인", expanded=False):
                            st.json(target_vc['json_data'])
                else:
                    st.info("선택된 문서가 삭제되었습니다.")
            else:
                st.info("👆 위 리스트에서 밸류체인을 선택하면 폴더 구조가 표시됩니다.")

        # ==========================================
        # [VIEW 2] ADD MODE
        # ==========================================
        elif st.session_state['vc_mode'] == 'add':
            st.subheader("📝 새 밸류체인 작성")
            vc_title = st.text_input("제목", placeholder="예: 2차전지 양극재 밸류체인")
            st.info("💡 Gems에게 '폴더형 계층 구조 JSON'을 요청하여 붙여넣으세요.")
            
            # Gems 프롬프트에 맞춘 기본 예시
            default_json = """{
  "title": "예시 밸류체인",
  "structure": [
    {
      "name": "상위 폴더",
      "type": "folder",
      "children": [
        {
          "name": "하위 폴더",
          "type": "folder",
          "children": [
            { "name": "기업 A", "type": "file", "desc": "설명...", "code": "005930" }
          ]
        },
        { "name": "기업 B", "type": "file", "desc": "설명..." }
      ]
    }
  ]
}"""
            vc_json = st.text_area("JSON 데이터 입력", value=default_json, height=400)
            
            b1, b2 = st.columns([1, 1])
            with b1:
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
                            time.sleep(0.5); st.rerun()
                        except json.JSONDecodeError:
                            st.error("JSON 형식이 올바르지 않습니다.")
