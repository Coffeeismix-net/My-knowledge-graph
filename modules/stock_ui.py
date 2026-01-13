import streamlit as st
import pandas as pd
from datetime import datetime
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
            }
        ]

# [Helper] 문서 삭제
def delete_doc(doc_id):
    st.session_state['stock_db'] = [d for d in st.session_state['stock_db'] if d['id'] != doc_id]
    # 보고 있던 문서라면 닫기
    if doc_id in st.session_state.get('selected_doc_ids', []):
        st.session_state['selected_doc_ids'].remove(doc_id)
    st.toast("🗑️ 문서가 삭제되었습니다.")
    st.rerun()

def render_stock_page():
    init_stock_db()
    
    # 1. 스타일 적용
    st.markdown(get_common_style(), unsafe_allow_html=True)
    
    # [커스텀 CSS] 태그 및 리스트 스타일
    st.markdown("""
    <style>
        .doc-tag {
            background-color: #333; color: #ddd; padding: 2px 6px; 
            border-radius: 4px; font-size: 0.75rem; margin-right: 4px; border: 1px solid #555;
        }
        .company-header {
            font-size: 1.1rem; font-weight: bold; color: #00ADB5;
        }
        /* 에디터 스타일 */
        .stQuill { background-color: white; color: black; border-radius: 8px; padding: 5px; }
    </style>
    """, unsafe_allow_html=True)

    # 2. 데이터 준비
    df = pd.DataFrame(st.session_state['stock_db'])
    grouped = pd.DataFrame()
    
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'])
        df = df.sort_values(by='created_at', ascending=False)
        # 기업별 집계
        grouped = df.groupby('company').agg({
            'created_at': 'max',
            'keywords': 'sum',
            'id': 'count'
        }).reset_index()
        # 키워드 중복 제거 (기업 대표 키워드)
        grouped['keywords'] = grouped['keywords'].apply(lambda x: list(set(x))[:5])

    # 3. 상단 컨트롤 바
    c1, c2 = st.columns([6, 1])
    with c1:
        search_query = st.text_input("🔍 기업명/키워드 검색", placeholder="Search...", label_visibility="collapsed")
    with c2:
        if st.button("➕ 문서 추가", use_container_width=True):
            st.session_state['stock_view_mode'] = 'add'
            st.session_state['edit_target_id'] = None # 신규 작성
            st.rerun()

    st.divider()

    # 4. 뷰 모드 관리
    if 'selected_doc_ids' not in st.session_state: st.session_state['selected_doc_ids'] = []
    
    # 에디터 모드이거나 문서를 선택했으면 2단 분할
    is_editor_mode = st.session_state.get('stock_view_mode') in ['add', 'edit']
    is_viewer_open = len(st.session_state['selected_doc_ids']) > 0 or is_editor_mode
    
    if is_viewer_open:
        col_left, col_right = st.columns([1, 1.5]) # 좌측 리스트 좁게, 우측 넓게
    else:
        col_left = st.container()
        col_right = None

    # --- [좌측] 문서 리스트 ---
    with col_left:
        # 에디터 모드일 때 '목록으로' 버튼
        if is_editor_mode:
            if st.button("⬅️ 목록으로 돌아가기", use_container_width=True):
                st.session_state['stock_view_mode'] = 'list'
                st.rerun()
            st.divider()

        if not grouped.empty:
            for _, co_row in grouped.iterrows():
                # 검색 필터
                if search_query and (search_query not in co_row['company']):
                    continue

                # 기업 헤더 (기업명 + 대표 키워드)
                with st.expander(f"🏢 {co_row['company']}", expanded=True):
                    # 기업 대표 키워드 표시
                    st.markdown(f"Top Keywords: {' '.join([f'`{k}`' for k in co_row['keywords']])}")
                    st.markdown("<hr style='margin: 5px 0; border-color: #444;'>", unsafe_allow_html=True)

                    # 하위 문서 리스트
                    sub_docs = df[df['company'] == co_row['company']]
                    
                    for _, doc in sub_docs.iterrows():
                        # [레이아웃 개선] 제목/키워드(8) | 수정(1) | 삭제(1)
                        r_c1, r_c2, r_c3 = st.columns([8, 1.5, 1.5])
                        
                        with r_c1:
                            # 제목 버튼 (클릭 시 뷰어 열기)
                            if st.button(f"📄 {doc['title']}", key=f"open_{doc['id']}", use_container_width=True):
                                st.session_state['selected_doc_ids'] = [doc['id']] # 하나만 보기 (다중 원하면 append)
                                st.session_state['stock_view_mode'] = 'view'
                                st.rerun()
                            # 개별 문서 키워드 표시
                            kws_html = "".join([f"<span class='doc-tag'>#{k}</span>" for k in doc['keywords']])
                            st.caption(f"{doc['created_at'].strftime('%y-%m-%d')} | {doc['title']}", unsafe_allow_html=True)
                            st.markdown(kws_html, unsafe_allow_html=True)
                            st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)

                        with r_c2:
                            # 수정 버튼
                            if st.button("✏️", key=f"edit_{doc['id']}", help="수정"):
                                st.session_state['stock_view_mode'] = 'edit'
                                st.session_state['edit_target_id'] = doc['id']
                                st.rerun()
                        
                        with r_c3:
                            # 삭제 버튼
                            if st.button("🗑️", key=f"del_{doc['id']}", help="삭제"):
                                delete_doc(doc['id'])

    # --- [우측] 뷰어 & 에디터 ---
    if is_viewer_open and col_right:
        with col_right:
            
            # [A] 에디터 모드 (추가/수정) - st.form 제거 (에러 해결 핵심)
            if is_editor_mode:
                target_id = st.session_state.get('edit_target_id')
                # 수정일 경우 기존 데이터 로드
                if target_id:
                    edit_data = next((d for d in st.session_state['stock_db'] if d['id'] == target_id), None)
                    if not edit_data:
                        st.error("데이터를 찾을 수 없습니다.")
                        st.stop()
                    def_comp = edit_data['company']
                    def_title = edit_data['title']
                    def_kw = ", ".join(edit_data['keywords'])
                    def_content = edit_data['content']
                    mode_title = "문서 수정"
                else:
                    def_comp = ""
                    def_title = ""
                    def_kw = ""
                    def_content = ""
                    mode_title = "새 문서 작성"

                st.subheader(f"📝 {mode_title}")
                
                # 입력 폼 (st.form 없이 직접 배치)
                in_comp = st.text_input("기업명", value=def_comp, placeholder="예: 삼성전자")
                in_title = st.text_input("제목", value=def_title, placeholder="리포트 제목")
                in_kw = st.text_input("키워드 (쉼표 구분)", value=def_kw, placeholder="반도체, 실적, ...")
                
                st.markdown("##### 내용")
                # Quill 에디터 (st.form 밖에서 안전하게 실행)
                if st_quill:
                    in_content = st_quill(
                        value=def_content,
                        placeholder="내용을 작성하세요...",
                        html=True,
                        key="quill_editor_main",
                        min_height=500
                    )
                else:
                    in_content = st.text_area("내용", value=def_content, height=500)

                # 저장 버튼 (폼 없이 동작)
                if st.button("💾 저장하기", type="primary", use_container_width=True):
                    if not in_comp or not in_title:
                        st.warning("기업명과 제목은 필수입니다.")
                    else:
                        new_kws = [k.strip() for k in in_kw.split(',') if k.strip()]
                        
                        if target_id: # 수정 저장
                            for d in st.session_state['stock_db']:
                                if d['id'] == target_id:
                                    d.update({
                                        "company": in_comp, "title": in_title, 
                                        "content": in_content, "keywords": new_kws,
                                        "created_at": str(datetime.now()) # 수정 시간 갱신
                                    })
                        else: # 신규 저장
                            new_id = str(len(st.session_state['stock_db']) + 100) # Simple ID Gen
                            st.session_state['stock_db'].append({
                                "id": new_id, "company": in_comp, "title": in_title,
                                "content": in_content, "keywords": new_kws,
                                "created_at": str(datetime.now())
                            })
                        
                        st.success("저장되었습니다!")
                        st.session_state['stock_view_mode'] = 'list'
                        st.session_state['edit_target_id'] = None
                        time.sleep(0.5)
                        st.rerun()

            # [B] 뷰어 모드 (HTML 렌더링)
            else:
                sel_ids = st.session_state['selected_doc_ids']
                if not sel_ids:
                    st.info("좌측에서 문서를 선택하세요.")
                else:
                    # 탭으로 여러 문서 보기 지원 (또는 세로 스크롤)
                    # 여기서는 탭 인터페이스 사용
                    tabs = st.tabs([f"📄 Doc {i+1}" for i in range(len(sel_ids))])
                    
                    for i, doc_id in enumerate(sel_ids):
                        doc = next((d for d in st.session_state['stock_db'] if d['id'] == doc_id), None)
                        if doc:
                            with tabs[i]:
                                with st.container(border=True):
                                    # 헤더
                                    h1, h2 = st.columns([8, 2])
                                    h1.markdown(f"## {doc['title']}")
                                    h2.caption(f"{doc['created_at']}")
                                    st.markdown(f"**{doc['company']}**")
                                    
                                    # 키워드 (클릭 시 그래프 연동)
                                    kw_cols = st.columns(10) # 넉넉하게 잡음
                                    for k_idx, kw in enumerate(doc['keywords']):
                                        if k_idx < 10:
                                            if kw_cols[k_idx].button(f"#{kw}", key=f"v_kw_{doc['id']}_{k_idx}"):
                                                st.session_state['menu_mode'] = "Knowledge Graph"
                                                st.session_state['selected_keyword'] = kw
                                                st.rerun()
                                    
                                    st.divider()
                                    # HTML 내용 렌더링
                                    st.markdown(doc['content'], unsafe_allow_html=True)
                                    
                                    # 닫기
                                    if st.button("닫기", key=f"v_close_{doc['id']}", use_container_width=True):
                                        st.session_state['selected_doc_ids'].remove(doc['id'])
                                        st.rerun()
