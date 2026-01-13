import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils.style import get_common_style

# [라이브러리 로드]
try:
    from streamlit_quill import st_quill
except ImportError:
    st_quill = None

# [Mock DB] 초기 데이터
def init_stock_db():
    if 'stock_db' not in st.session_state:
        st.session_state['stock_db'] = [
            {
                "id": "1", "company": "삼성전자", "title": "24년 4분기 잠정실적 분석", 
                "content": "<p><strong>1. 실적 요약</strong></p><ul><li>매출: 67조원</li><li>영업이익: 2.8조원</li></ul>", 
                "keywords": ["반도체", "HBM", "실적발표"], "created_at": "2024-05-20 10:00"
            },
            {
                "id": "2", "company": "에코프로비엠", "title": "양극재 수출입 데이터", 
                "content": "<p>수출입 데이터 분석 결과...</p>", 
                "keywords": ["2차전지", "양극재"], "created_at": "2024-05-19 14:00"
            },
            {
                "id": "3", "company": "리브스메드", "title": "상세 분석 리포트", 
                "content": "<p>다관절 복강경 수술 기구...</p>", 
                "keywords": ["로봇", "의료", "다빈치"], "created_at": "2026-01-13 14:47"
            }
        ]
    
    if 'stock_trash_db' not in st.session_state:
        st.session_state['stock_trash_db'] = []

# [Helper] 문서 삭제 (휴지통 이동)
def move_to_trash(doc_id):
    target_doc = next((d for d in st.session_state['stock_db'] if d['id'] == doc_id), None)
    if target_doc:
        target_doc['deleted_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        st.session_state['stock_trash_db'].append(target_doc)
        st.session_state['stock_db'] = [d for d in st.session_state['stock_db'] if d['id'] != doc_id]
        
        if doc_id in st.session_state.get('selected_doc_ids', []):
            st.session_state['selected_doc_ids'].remove(doc_id)
            
        st.toast("🗑️ 휴지통으로 이동되었습니다.")
        time.sleep(0.5)
        st.rerun()

def render_stock_page():
    init_stock_db()
    
    # 1. 스타일 적용
    st.markdown(get_common_style(), unsafe_allow_html=True)
    
    # [커스텀 CSS] 
    st.markdown("""
    <style>
        /* 태그 스타일 */
        .doc-tag {
            background-color: #222; color: #aaa; padding: 2px 6px; 
            border-radius: 4px; font-size: 0.7rem; margin-right: 4px; border: 1px solid #444;
        }
        .date-label {
            color: #666; font-size: 0.75rem; margin-left: 5px;
        }
        .stQuill { 
            background-color: white; color: black; border-radius: 8px; padding: 5px; min-height: 400px;
        }
        /* 버튼 스타일 정교화 */
        button[kind="secondary"] p {
            text-align: left !important;
            padding-left: 5px !important;
        }
        div[data-testid="column"] button[kind="secondary"] {
            padding: 0px 5px !important;
            min-width: 0px !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # 2. 데이터 준비
    df = pd.DataFrame(st.session_state['stock_db'])
    grouped = pd.DataFrame()
    
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
        df['created_at'] = df['created_at'].fillna(pd.Timestamp.now())
        df = df.sort_values(by='created_at', ascending=False)
        
        grouped = df.groupby('company').agg({
            'created_at': 'max', 
            'keywords': 'sum',
            'id': 'count'
        }).reset_index()
        
        grouped = grouped.sort_values(by='created_at', ascending=False)
        grouped['keywords'] = grouped['keywords'].apply(lambda x: list(set(x))[:5])

    # 3. 상단 컨트롤 바
    # [수정] 문서 추가 버튼을 삭제하고 검색창을 넓게 씀
    st.text_input("🔍 기업명/키워드 검색", placeholder="Search...", label_visibility="collapsed", key="stock_search_query")
    search_query = st.session_state.get("stock_search_query", "")

    st.divider()

    # 4. 뷰 모드 관리
    if 'selected_doc_ids' not in st.session_state: st.session_state['selected_doc_ids'] = []
    
    # [핵심] 메인 메뉴에서 stock_view_mode를 'add'로 설정하면 에디터가 열림
    is_editor_mode = st.session_state.get('stock_view_mode') in ['add', 'edit']
    is_viewer_open = len(st.session_state['selected_doc_ids']) > 0 or is_editor_mode
    
    if is_viewer_open:
        col_left, col_right = st.columns([1, 2.2]) 
    else:
        col_left = st.container()
        col_right = None

    # --- [좌측] 문서 리스트 ---
    with col_left:
        if is_editor_mode:
            if st.button("⬅️ 목록으로", use_container_width=True):
                st.session_state['stock_view_mode'] = 'list'
                st.rerun()
            st.divider()

        if not grouped.empty:
            for _, co_row in grouped.iterrows():
                if search_query and (search_query not in co_row['company']):
                    continue

                with st.expander(f"🏢 {co_row['company']}", expanded=True):
                    st.markdown(f"Key: {' '.join([f'`{k}`' for k in co_row['keywords']])}")
                    st.markdown("<hr style='margin: 5px 0; border-color: #444;'>", unsafe_allow_html=True)

                    sub_docs = df[df['company'] == co_row['company']]
                    
                    for _, doc in sub_docs.iterrows():
                        r_c1, r_c2, r_c3, r_c4 = st.columns([4.5, 3.5, 0.6, 0.6])
                        
                        with r_c1:
                            if st.button(f"📄 {doc['title']}", key=f"open_{doc['id']}", use_container_width=True):
                                st.session_state['selected_doc_ids'] = [doc['id']]
                                st.session_state['stock_view_mode'] = 'view'
                                st.rerun()
                        
                        with r_c2:
                            kws_html = "".join([f"<span class='doc-tag'>#{k}</span>" for k in doc['keywords']])
                            date_str = doc['created_at'].strftime('%y.%m.%d')
                            st.markdown(f"{kws_html} <span class='date-label'>{date_str}</span>", unsafe_allow_html=True)

                        with r_c3:
                            if st.button("✏️", key=f"edit_{doc['id']}", help="수정", use_container_width=True):
                                st.session_state['stock_view_mode'] = 'edit'
                                st.session_state['edit_target_id'] = doc['id']
                                st.rerun()
                        
                        with r_c4:
                            if st.button("🗑️", key=f"del_{doc['id']}", help="삭제", use_container_width=True):
                                move_to_trash(doc['id'])

    # --- [우측] 뷰어 & 에디터 ---
    if is_viewer_open and col_right:
        with col_right:
            
            # [A] 에디터 모드
            if is_editor_mode:
                target_id = st.session_state.get('edit_target_id')
                if target_id:
                    edit_data = next((d for d in st.session_state['stock_db'] if d['id'] == target_id), None)
                    if not edit_data: st.stop()
                    def_comp, def_title = edit_data['company'], edit_data['title']
                    def_kw, def_content = ", ".join(edit_data['keywords']), edit_data['content']
                    mode_title = "문서 수정"
                else:
                    def_comp, def_title, def_kw, def_content = "", "", "", ""
                    mode_title = "새 문서 작성"

                st.subheader(f"📝 {mode_title}")
                
                in_comp = st.text_input("기업명", value=def_comp, placeholder="예: 삼성전자")
                in_title = st.text_input("제목", value=def_title, placeholder="리포트 제목")
                in_kw = st.text_input("키워드 (쉼표 구분)", value=def_kw, placeholder="반도체, 실적, ...")
                
                st.markdown("##### 내용")
                
                if st_quill:
                    in_content = st_quill(
                        value=def_content or "",
                        placeholder="내용을 작성하세요...",
                        html=True,
                        key=f"quill_{target_id or 'new'}"
                    )
                else:
                    in_content = st.text_area("내용", value=def_content or "", height=500)

                if st.button("💾 저장하기", type="primary", use_container_width=True):
                    if not in_comp or not in_title:
                        st.warning("기업명과 제목은 필수입니다.")
                    else:
                        new_kws = [k.strip() for k in in_kw.split(',') if k.strip()]
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                        
                        if target_id:
                            for d in st.session_state['stock_db']:
                                if d['id'] == target_id:
                                    d.update({
                                        "company": in_comp, "title": in_title, 
                                        "content": in_content, "keywords": new_kws,
                                        "created_at": now_str
                                    })
                        else:
                            new_id = str(len(st.session_state['stock_db']) + 100)
                            st.session_state['stock_db'].append({
                                "id": new_id, "company": in_comp, "title": in_title,
                                "content": in_content, "keywords": new_kws,
                                "created_at": now_str
                            })
                        st.success("저장되었습니다!")
                        st.session_state['stock_view_mode'] = 'list'
                        st.session_state['edit_target_id'] = None
                        time.sleep(0.5)
                        st.rerun()

            # [B] 뷰어 모드
            else:
                sel_ids = st.session_state['selected_doc_ids']
                if not sel_ids:
                    st.info("좌측에서 문서를 선택하세요.")
                else:
                    tabs = st.tabs([f"📄 Doc {i+1}" for i in range(len(sel_ids))])
                    for i, doc_id in enumerate(sel_ids):
                        doc = next((d for d in st.session_state['stock_db'] if d['id'] == doc_id), None)
                        if doc:
                            with tabs[i]:
                                with st.container(border=True):
                                    h1, h2 = st.columns([9, 1])
                                    with h1:
                                        st.markdown(f"## {doc['title']}")
                                        st.caption(f"{doc['created_at']} | {doc['company']}")
                                    with h2:
                                        if st.button("✖️", key=f"v_close_{doc['id']}", help="닫기"):
                                            st.session_state['selected_doc_ids'].remove(doc['id'])
                                            st.rerun()
                                    
                                    kw_cols = st.columns(10)
                                    for k_idx, kw in enumerate(doc['keywords']):
                                        if k_idx < 10:
                                            if kw_cols[k_idx].button(f"#{kw}", key=f"v_kw_{doc['id']}_{k_idx}"):
                                                st.session_state['menu_mode'] = "Knowledge Graph"
                                                st.session_state['selected_keyword'] = kw
                                                st.rerun()
                                    st.divider()
                                    st.markdown(doc['content'], unsafe_allow_html=True)
