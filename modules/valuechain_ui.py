import streamlit as st
import pandas as pd
import json
import time
import re
import streamlit.components.v1 as components
from utils.db_api import load_valuechains, add_valuechain, delete_valuechain, get_kst_now_str, copy_to_clipboard

# ==========================================
# [HELPER] 검색어 하이라이팅 & 매칭 로직
# ==========================================
def highlight_text(text, query):
    """텍스트 내에 검색어(query)가 있으면 노란색 배경으로 강조"""
    if not query or not text:
        return text
    # 대소문자 구분 없이 매칭하기 위해 정규식 사용
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(lambda m: f"<span style='background-color: #ffd700; color: black; padding: 0 2px; border-radius: 2px;'>{m.group(0)}</span>", str(text))

def check_json_contains_keyword(json_str, query):
    """JSON 문자열 자체에서 검색어가 포함되어 있는지 아주 빠르게 확인"""
    if not query: return True
    if not json_str: return False
    return query.lower() in json_str.lower()

# ==========================================
# [CORE] 재귀적 트리 렌더러 (하이라이트 기능 추가)
# ==========================================
def render_tree_node(nodes, level=0, search_query=""):
    """
    JSON의 'children'을 순회하며 폴더(Expander)와 파일(Text/Button)을 그립니다.
    search_query가 있으면 해당 텍스트를 하이라이팅합니다.
    """
    if not nodes: return

    for node in nodes:
        # 데이터 추출
        name = node.get('name', 'Unknown')
        code = node.get('code', '')
        desc = node.get('desc', '')
        
        # 검색어가 있을 때, 이 노드가 검색어와 관련 있는지 확인
        # (관련 없어도 부모 폴더는 보여야 하므로 렌더링은 하되, 하이라이트만 적용)
        
        # [CASE 1] 폴더 (Folder)
        if node.get('type') == 'folder':
            # 폴더 이름에 검색어가 있으면 강조
            display_name = highlight_text(name, search_query)
            folder_label = f"📂 {display_name}"
            
            # 검색어가 있으면 관련 폴더를 기본적으로 펼쳐줌 (UX 향상)
            should_expand = bool(search_query and check_json_contains_keyword(json.dumps(node), search_query))
            
            # Expander 렌더링
            # 주의: Streamlit Expander 라벨에는 HTML 적용이 제한적이므로, 
            # 검색어가 매칭되어도 라벨 자체 색상은 안 바뀔 수 있음. (내용물은 확실함)
            with st.expander(f"📂 {name}", expanded=True): # 검색 시 구조 파악 위해 기본 펼침 권장
                if 'children' in node and node['children']:
                    render_tree_node(node['children'], level + 1, search_query)
                else:
                    st.caption("(비어있음)")

        # [CASE 2] 파일 (File/Item)
        else:
            # 텍스트 하이라이팅 적용
            h_name = highlight_text(name, search_query)
            h_code = highlight_text(code, search_query)
            h_desc = highlight_text(desc, search_query)
            
            c1, c2 = st.columns([4, 6])
            
            with c1:
                if code:
                    st.markdown(f"📄 **{h_name}** <span style='color:#888; font-size:0.8em;'>({h_code})</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"📄 **{h_name}**", unsafe_allow_html=True)
            
            with c2:
                if desc:
                    st.markdown(f"<span style='color:#bbb;'>{h_desc}</span>", unsafe_allow_html=True)

            st.markdown("<hr style='margin: 5px 0; border-top: 1px solid #333;'>", unsafe_allow_html=True)

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
            st.text_input("🔍 밸류체인 검색 (내용 포함)", placeholder="기업명, 부품명, 코드 등...", label_visibility="collapsed", key="vc_search_query")
            search_query = st.session_state.get("vc_search_query", "")
            
            with st.container(height=280):
                if not st.session_state['vc_list']:
                    st.caption("등록된 밸류체인이 없습니다. 상단 메뉴 Chain > Add를 이용하세요.")
                else:
                    sorted_list = sorted(st.session_state['vc_list'], key=lambda x: x['created_at'], reverse=True)
                    
                    found_count = 0
                    for vc in sorted_list:
                        # [검색 로직 강화] 제목 또는 JSON 데이터 안에 검색어가 있는지 확인 (Deep Search)
                        is_match = False
                        if not search_query:
                            is_match = True
                        else:
                            # 1. 제목 검색
                            if search_query.lower() in vc['title'].lower():
                                is_match = True
                            # 2. 내용(JSON) 검색
                            elif check_json_contains_keyword(vc['json_data'], search_query):
                                is_match = True
                        
                        if not is_match:
                            continue
                        
                        found_count += 1
                        r1, r2, r3 = st.columns([6, 3, 1])
                        with r1:
                            # 제목에도 검색어 하이라이팅 표시
                            display_title = highlight_text(vc['title'], search_query)
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
                    
                    if search_query and found_count == 0:
                        st.caption(f"'{search_query}'에 대한 검색 결과가 없습니다.")

            st.divider()

            # [VIEWER] 검색어 전달
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
                        
                        try:
                            json_data = json.loads(target_vc['json_data'])
                            # [핵심] search_query를 렌더러에 전달하여 하이라이팅 적용
                            if "structure" in json_data:
                                render_tree_node(json_data["structure"], search_query=search_query)
                            elif "groups" in json_data:
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
                                render_tree_node(converted_structure, search_query=search_query)
                            else:
                                st.warning("지원되지 않는 데이터 형식입니다.")
                                st.json(json_data)
                                
                        except json.JSONDecodeError:
                            st.error("데이터가 올바른 JSON 형식이 아닙니다.")
                        except Exception as e:
                            st.error(f"렌더링 오류: {e}")

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
