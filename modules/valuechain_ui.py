"""
valuechain_ui.py — Value Chain List / Viewer / Add UI
"""
import streamlit as st
import json
import time
from utils.db_chain import load_valuechains, add_valuechain, delete_valuechain, analyze_valuechain_image, clear_valuechains_cache
from utils.db_common import (
    get_kst_now_str, copy_to_clipboard, compress_image,
    image_to_base64, highlight_text
)

# ==========================================
# HELPERS
# ==========================================
def _json_contains_keyword(json_str, query):
    """JSON 문자열 내 검색어 포함 여부"""
    if not query:
        return True
    if not json_str:
        return False
    return query.lower() in json_str.lower()

# ==========================================
# TREE RENDERER
# ==========================================
def _render_tree_node(nodes, level=0, search_query=""):
    """재귀적 트리 구조 렌더링"""
    if not nodes:
        return

    for node in nodes:
        name = node.get('name', 'Unknown')
        code = node.get('code', '')
        desc = node.get('desc', '')

        if node.get('type') == 'folder':
            should_expand = bool(search_query) or True
            with st.expander(f"📂 {name}", expanded=should_expand):
                if 'children' in node and node['children']:
                    _render_tree_node(node['children'], level + 1, search_query)
                else:
                    st.caption("(비어있음)")
        else:
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

def _convert_legacy_groups(json_data):
    """구형 groups 포맷을 structure 포맷으로 변환"""
    converted = []
    for grp in json_data.get("groups", []):
        folder = {"name": grp.get("name", "Group"), "type": "folder", "children": []}
        for node in grp.get("nodes", []):
            folder["children"].append({
                "name": node.get("label", "Unknown").replace("<br/>", " ").replace("\n", " "),
                "type": "file",
                "desc": node.get("desc", ""),
                "code": str(node.get("id", "")).replace("id_", "").replace("S", "")
            })
        converted.append(folder)
    return converted

# ==========================================
# MAIN RENDER
# ==========================================
def render_valuechain_page(main_col):
    if not st.session_state.get('vc_list'):
        st.session_state['vc_list'] = load_valuechains()
    if 'selected_vc_id' not in st.session_state:
        st.session_state['selected_vc_id'] = None
    if 'show_original_img' not in st.session_state:
        st.session_state['show_original_img'] = False

    with main_col:
        if st.session_state['vc_mode'] == 'list':
            _render_list_view()
        elif st.session_state['vc_mode'] == 'add':
            _render_add_view()

# ==========================================
# LIST VIEW
# ==========================================
def _render_list_view():
    st.text_input("🔍 밸류체인 검색 (내용 포함)", placeholder="Search...", label_visibility="collapsed", key="vc_search_query")
    search_query = st.session_state.get("vc_search_query", "")

    with st.container(height=280):
        if not st.session_state['vc_list']:
            st.caption("등록된 밸류체인이 없습니다.")
        else:
            sorted_list = sorted(st.session_state['vc_list'], key=lambda x: x['created_at'], reverse=True)
            for vc in sorted_list:
                is_match = False
                if not search_query:
                    is_match = True
                elif search_query.lower() in vc['title'].lower():
                    is_match = True
                elif _json_contains_keyword(vc['json_data'], search_query):
                    is_match = True

                if not is_match:
                    continue

                r1, r2, r3 = st.columns([6, 3, 1])
                with r1:
                    if st.button(f"🗂️ {vc['title']}", key=f"open_vc_{vc['id']}", use_container_width=True):
                        st.session_state['selected_vc_id'] = vc['id']
                        st.session_state['show_original_img'] = False
                        st.rerun()
                with r2:
                    d_str = vc['created_at'][:16]
                    st.markdown(f"<div style='text-align: right; padding-top: 5px;'><span class='date-label'>{d_str}</span></div>", unsafe_allow_html=True)
                with r3:
                    with st.popover("⋮", use_container_width=True):
                        if st.button("Trash", key=f"del_vc_{vc['id']}", use_container_width=True):
                            delete_valuechain(vc['id'])
                            clear_valuechains_cache()
                            st.session_state['vc_list'] = load_valuechains()
                            if st.session_state['selected_vc_id'] == vc['id']:
                                st.session_state['selected_vc_id'] = None
                            st.toast("삭제되었습니다.")
                            time.sleep(0.5)
                            st.rerun()

    st.divider()

    # Viewer
    if st.session_state['selected_vc_id']:
        target_vc = next((item for item in st.session_state['vc_list'] if item['id'] == st.session_state['selected_vc_id']), None)
        if target_vc:
            with st.container(border=True):
                h1, h2, h3, h4 = st.columns([7, 1.5, 0.8, 0.7])
                with h1:
                    st.markdown(f"### {target_vc['title']}")
                    st.caption(f"Created: {target_vc['created_at']}")

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

                # 원본 이미지 vs 트리 뷰
                if st.session_state['show_original_img'] and has_image:
                    st.image(f"data:image/jpeg;base64,{target_vc['image_data']}", use_column_width=True)
                else:
                    try:
                        json_data = json.loads(target_vc['json_data'])
                        if "structure" in json_data:
                            _render_tree_node(json_data["structure"], search_query=search_query)
                        elif "groups" in json_data:
                            converted = _convert_legacy_groups(json_data)
                            _render_tree_node(converted, search_query=search_query)
                        else:
                            st.error("JSON 포맷을 인식할 수 없습니다.")
                            st.json(json_data)
                    except json.JSONDecodeError:
                        st.error("데이터 손상됨 (JSON Parse Error)")
        else:
            st.info("문서가 존재하지 않습니다.")
    else:
        st.info("👆 리스트에서 항목을 선택하세요.")

# ==========================================
# ADD MODE
# ==========================================
def _render_add_view():
    st.subheader("📝 새 밸류체인 작성 (AI Auto)")

    vc_title = st.text_input("제목", placeholder="예: 2차전지 밸류체인")
    uploaded_file = st.file_uploader("이미지를 업로드하면 AI가 자동으로 구조화합니다.", type=['png', 'jpg', 'jpeg', 'webp'])

    if 'analyzed_json' not in st.session_state:
        st.session_state['analyzed_json'] = ""
    if 'analyzed_img_b64' not in st.session_state:
        st.session_state['analyzed_img_b64'] = ""

    if uploaded_file:
        if st.button("🚀 AI 분석 시작", type="primary", use_container_width=True):
            with st.spinner("이미지를 분석하고 있습니다... (약 5~10초 소요)"):
                compressed_bytes = compress_image(uploaded_file)
                st.session_state['analyzed_img_b64'] = image_to_base64(compressed_bytes)
                res = analyze_valuechain_image(compressed_bytes)
                if res['success']:
                    st.session_state['analyzed_json'] = res['json']
                    st.success("분석 완료!")
                else:
                    st.error(f"분석 실패: {res['error']}")

    default_text = st.session_state['analyzed_json'] if st.session_state['analyzed_json'] else "{}"
    vc_json = st.text_area("JSON 데이터 (자동 생성됨, 수정 가능)", value=default_text, height=400)

    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("취소", use_container_width=True):
            st.session_state['vc_mode'] = 'list'
            st.session_state['analyzed_json'] = ""
            st.session_state['analyzed_img_b64'] = ""
            st.rerun()
    with b2:
        if st.button("💾 저장하기", type="primary", use_container_width=True):
            if not vc_title:
                st.warning("제목을 입력해주세요.")
            else:
                try:
                    json.loads(vc_json)  # 유효성 검사
                    add_valuechain(vc_title, vc_json, st.session_state['analyzed_img_b64'])
                    clear_valuechains_cache()
                    st.success("저장되었습니다!")
                    st.session_state['vc_list'] = load_valuechains()
                    st.session_state['vc_mode'] = 'list'
                    st.session_state['analyzed_json'] = ""
                    st.session_state['analyzed_img_b64'] = ""
                    time.sleep(0.5)
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("JSON 형식이 올바르지 않습니다.")
