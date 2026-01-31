import streamlit as st
import pandas as pd
import json
import time
import re
import streamlit.components.v1 as components
from utils.db_chain import load_valuechains, add_valuechain, delete_valuechain, analyze_valuechain_image
from utils.db_common import get_kst_now_str, copy_to_clipboard, compress_image, image_to_base64

# ==========================================
# HELPERS
# ==========================================
def highlight_text(text, query):
    if not query or not text: return text
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(lambda m: f"<span style='background-color: #ffd700; color: black; padding: 0 2px; border-radius: 2px;'>{m.group(0)}</span>", str(text))

def check_json_contains_keyword(json_str, query):
    if not query: return True
    if not json_str: return False
    return query.lower() in json_str.lower()

# ==========================================
# RENDER TREE
# ==========================================
def render_tree_node(nodes, level=0, search_query=""):
    if not nodes: return

    for node in nodes:
        name = node.get('name', 'Unknown')
        code = node.get('code', '')
        desc = node.get('desc', '')
        
        if node.get('type') == 'folder':
            display_name = highlight_text(name, search_query)
            # 검색어가 있으면 해당 내용이 포함된 폴더는 자동 확장
            should_expand = bool(search_query) # 검색 중이면 다 펼치는게 속 편함
            
            with st.expander(f"📂 {name}", expanded=should_expand or True):
                if 'children' in node and node['children']:
                    render_tree_node(node['children'], level + 1, search_query)
                else:
                    st.caption("(비어있음)")
        else:
            h_name = highlight_text(name, search_query)
            h_code = highlight_text(code, search_query)
            h_desc = highlight_text(desc, search_query)
            
            c1, c2 = st.columns([4, 6])
            with c1:
                if code: st.markdown(f"📄 **{h_name}** <span style='color:#888; font-size:0.8em;'>({h_code})</span>", unsafe_allow_html=True)
                else: st.markdown(f"📄 **{h_name}**", unsafe_allow_html=True)
            with c2:
                if desc: st.markdown(f"<span style='color:#bbb;'>{h_desc}</span>", unsafe_allow_html=True)
            st.markdown("<hr style='margin: 5px 0; border-top: 1px solid #333;'>", unsafe_allow_html=True)

# ==========================================
# MAIN RENDERER
# ==========================================
def render_valuechain_page(main_col):
    if 'vc_list' not in st.session_state:
        st.session_state['vc_list'] = load_valuechains()
    if 'vc_mode' not in st.session_state:
        st.session_state['vc_mode'] = 'list'
    if 'selected_vc_id' not in st.session_state:
        st.session_state['selected_vc_id'] = None
    if 'show_original_img' not in st.session_state:
        st.session_state['show_original_img'] = False

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
        # [LIST VIEW]
        if st.session_state['vc_mode'] == 'list':
            st.text_input("🔍 밸류체인 검색 (내용 포함)", placeholder="Search...", label_visibility="collapsed", key="vc_search_query")
            search_query = st.session_state.get("vc_search_query", "")
            
            with st.container(height=280):
                if not st.session_state['vc_list']:
                    st.caption("등록된 밸류체인이 없습니다.")
                else:
                    sorted_list = sorted(st.session_state['vc_list'], key=lambda x: x['created_at'], reverse=True)
                    for vc in sorted_list:
                        # Deep Search
                        is_match = False
                        if not search_query: is_match = True
                        else:
                            if search_query.lower() in vc['title'].lower(): is_match = True
                            elif check_json_contains_keyword(vc['json_data'], search_query): is_match = True
                        
                        if not is_match: continue
                        
                        r1, r2, r3 = st.columns([6, 3, 1])
                        with r1:
                            display_title = highlight_text(vc['title'], search_query)
                            if st.button(f"🗂️ {vc['title']}", key=f"open_vc_{vc['id']}", use_container_width=True):
                                st.session_state['selected_vc_id'] = vc['id']
                                st.session_state['show_original_img'] = False # 초기화
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

            # [VIEWER]
            if st.session_state['selected_vc_id']:
                target_vc = next((item for item in st.session_state['vc_list'] if item['id'] == st.session_state['selected_vc_id']), None)
                if target_vc:
                    with st.container(border=True):
                        # Header: Title | Original Toggle | Copy | Close
                        h1, h2, h3, h4 = st.columns([7, 1.5, 0.8, 0.7])
                        with h1:
                            st.markdown(f"### {target_vc['title']}")
                            st.caption(f"Created: {target_vc['created_at']}")
                        
                        # [NEW] 원본 보기 토글 (이미지 데이터가 있을 때만 활성화)
                        has_image = bool(target_vc.get('image_data'))
                        with h2:
                            if has_image:
                                icon = "📂 닫기" if st.session_state['show_original_img'] else "👁️ 원본"
                                if st.button(icon, key="toggle_orig_img", use_container_width=True):
                                    st.session_state['show_original_img'] = not st.session_state['show_original_img']
                                    st.rerun()
                            else:
                                st.button("🚫 없음", disabled=True, use_container_width=True)

                        with h3:
                            if st.button("📋", key="cp_vc_json", help="JSON 복사", use_container_width=True):
                                copy_to_clipboard(target_vc['json_data'])
                                st.toast("복사됨")
                        with h4:
                            if st.button("✕", key="close_vc_viewer", help="닫기", use_container_width=True):
                                st.session_state['selected_vc_id'] = None
                                st.rerun()
                        
                        st.divider()
                        
                        # [VIEW] 원본 이미지 모드 vs 트리 뷰 모드
                        if st.session_state['show_original_img'] and has_image:
                            st.image(f"data:image/jpeg;base64,{target_vc['image_data']}", use_column_width=True)
                        else:
                            try:
                                json_data = json.loads(target_vc['json_data'])
                                if "structure" in json_data:
                                    render_tree_node(json_data["structure"], search_query=search_query)
                                elif "groups" in json_data:
                                    # 구형 데이터 호환
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
                                    st.error("JSON 포맷을 인식할 수 없습니다.")
                                    st.json(json_data)
                            except json.JSONDecodeError:
                                st.error("데이터 손상됨 (JSON Parse Error)")
                else:
                    st.info("문서가 존재하지 않습니다.")
            else:
                st.info("👆 리스트에서 항목을 선택하세요.")

        # [ADD MODE]
        elif st.session_state['vc_mode'] == 'add':
            st.subheader("📝 새 밸류체인 작성 (AI Auto)")
            
            c_input1, c_input2 = st.columns([1, 1])
            with c_input1:
                vc_title = st.text_input("제목", placeholder="예: 2차전지 밸류체인")
            
            # [NEW] 이미지 업로더 (Drag & Drop)
            uploaded_file = st.file_uploader("이미지를 업로드하면 AI가 자동으로 구조화합니다.", type=['png', 'jpg', 'jpeg', 'webp'])
            
            # 분석 상태 저장소
            if 'analyzed_json' not in st.session_state: st.session_state['analyzed_json'] = ""
            if 'analyzed_img_b64' not in st.session_state: st.session_state['analyzed_img_b64'] = ""

            # 이미지 분석 로직
            if uploaded_file:
                # 이미지가 변경되면 다시 분석
                if st.button("🚀 AI 분석 시작", type="primary", use_container_width=True):
                    with st.spinner("이미지를 분석하고 있습니다... (약 5~10초 소요)"):
                        # 1. 이미지 압축
                        compressed_bytes = compress_image(uploaded_file)
                        st.session_state['analyzed_img_b64'] = image_to_base64(compressed_bytes)
                        
                        # 2. AI 분석
                        res = analyze_valuechain_image(compressed_bytes)
                        if res['success']:
                            st.session_state['analyzed_json'] = res['json']
                            st.success("분석 완료! 아래 JSON을 확인하고 저장하세요.")
                        else:
                            st.error(f"분석 실패: {res['error']}")

            # JSON 편집창 (AI 결과가 있으면 채워넣음)
            default_text = st.session_state['analyzed_json'] if st.session_state['analyzed_json'] else "{}"
            vc_json = st.text_area("JSON 데이터 (자동 생성됨, 수정 가능)", value=default_text, height=400)
            
            b1, b2 = st.columns([1, 1])
            with b1:
                if st.button("취소", use_container_width=True):
                    st.session_state['vc_mode'] = 'list'
                    st.session_state['analyzed_json'] = "" # 초기화
                    st.session_state['analyzed_img_b64'] = ""
                    st.rerun()
            with b2:
                if st.button("💾 저장하기", type="primary", use_container_width=True):
                    if not vc_title:
                        st.warning("제목을 입력해주세요.")
                    else:
                        try:
                            json.loads(vc_json) # 유효성 검사
                            # 원본 이미지(Base64)와 함께 저장
                            add_valuechain(vc_title, vc_json, st.session_state['analyzed_img_b64'])
                            
                            st.success("저장되었습니다!")
                            st.session_state['vc_list'] = load_valuechains()
                            st.session_state['vc_mode'] = 'list'
                            # 상태 초기화
                            st.session_state['analyzed_json'] = ""
                            st.session_state['analyzed_img_b64'] = ""
                            time.sleep(0.5); st.rerun()
                        except json.JSONDecodeError:
                            st.error("JSON 형식이 올바르지 않습니다.")
