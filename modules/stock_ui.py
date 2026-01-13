import streamlit as st
import pandas as pd
from datetime import datetime
from utils.style import get_common_style

# [NEW] 리치 텍스트 에디터 라이브러리
try:
    from streamlit_quill import st_quill
except ImportError:
    st.error("라이브러리가 설치되지 않았습니다. 터미널에 'pip install streamlit-quill'을 입력하세요.")
    st_quill = st.text_area  # fallback

# [Mock DB] 초기 데이터
def init_stock_db():
    if 'stock_db' not in st.session_state:
        st.session_state['stock_db'] = [
            {
                "id": "1", "company": "삼성전자", "title": "24년 4분기 잠정실적 분석", 
                "content": "<p><strong>1. 실적 요약</strong></p><ul><li>매출: 67조원</li><li>영업이익: 2.8조원</li></ul><p>메모리 반도체 업황 회복으로...</p>", 
                "keywords": ["반도체", "HBM", "실적발표"], "created_at": "2024-05-20 10:00"
            }
        ]

def render_stock_page():
    init_stock_db()
    
    # 1. 스타일 및 헤더
    st.markdown(get_common_style(), unsafe_allow_html=True)
    
    # [CSS 추가] 에디터 스타일링 (검은 배경에 맞게 조정)
    st.markdown("""
    <style>
        .stock-row { 
            display: flex; align-items: center; padding: 10px; 
            border-bottom: 1px solid #333; transition: background 0.2s;
        }
        .stock-row:hover { background-color: #222; cursor: pointer; }
        
        /* Quill 에디터 배경색 조정 (가독성 확보) */
        .stQuill { background-color: white; color: black; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

    # 2. 데이터 준비
    df = pd.DataFrame(st.session_state['stock_db'])
    
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'])
        df = df.sort_values(by='created_at', ascending=False)
        grouped = df.groupby('company').agg({
            'created_at': 'max',
            'keywords': 'sum',
            'id': 'count'
        }).reset_index()
        grouped['keywords'] = grouped['keywords'].apply(lambda x: list(set(x))[:5])
    else:
        grouped = pd.DataFrame()

    # 3. 상단 컨트롤 바
    c1, c2 = st.columns([6, 2])
    with c1:
        search_query = st.text_input("🔍 기업명/키워드 검색", placeholder="Search...", label_visibility="collapsed")
    with c2:
        if st.button("➕ 문서 추가", use_container_width=True):
            st.session_state['stock_view_mode'] = 'add'
            st.rerun()

    st.divider()

    # 4. 레이아웃 분기
    if 'selected_doc_ids' not in st.session_state: st.session_state['selected_doc_ids'] = []
    
    is_viewer_open = len(st.session_state['selected_doc_ids']) > 0 or st.session_state.get('stock_view_mode') == 'add'
    
    if is_viewer_open:
        col_left, col_right = st.columns([1, 2])
    else:
        col_left = st.container()
        col_right = None

    # --- [좌측] 리스트 ---
    with col_left:
        if st.session_state.get('stock_view_mode') == 'add':
            if st.button("⬅️ 목록으로", use_container_width=True):
                st.session_state['stock_view_mode'] = 'list'
                st.session_state['selected_doc_ids'] = []
                st.rerun()
        
        if not grouped.empty:
            for _, company_row in grouped.iterrows():
                if search_query and (search_query not in company_row['company']):
                    continue

                with st.expander(f"🏢 {company_row['company']} ({company_row['id']} docs)", expanded=False):
                    sub_docs = df[df['company'] == company_row['company']]
                    st.markdown(f"🏷️ {' '.join([f'`{k}`' for k in company_row['keywords']])}")
                    
                    for _, doc in sub_docs.iterrows():
                        sc1, sc2, sc3 = st.columns([0.5, 4, 1.5])
                        
                        is_checked = doc['id'] in st.session_state['selected_doc_ids']
                        if sc1.checkbox("", key=f"chk_{doc['id']}", value=is_checked):
                            if doc['id'] not in st.session_state['selected_doc_ids']:
                                if len(st.session_state['selected_doc_ids']) < 2:
                                    st.session_state['selected_doc_ids'].append(doc['id'])
                                    st.rerun()
                                else:
                                    st.toast("최대 2개까지만 비교 가능합니다.")
                        else:
                            if doc['id'] in st.session_state['selected_doc_ids']:
                                st.session_state['selected_doc_ids'].remove(doc['id'])
                                st.rerun()

                        if sc2.button(doc['title'], key=f"btn_title_{doc['id']}"):
                            st.session_state['selected_doc_ids'] = [doc['id']]
                            st.session_state['stock_view_mode'] = 'view'
                            st.rerun()
                            
                        sc3.caption(doc['created_at'].strftime('%y-%m-%d'))

    # --- [우측] 뷰어 & 에디터 ---
    if is_viewer_open and col_right:
        with col_right:
            # A. 문서 추가 모드 (Rich Text Editor 적용)
            if st.session_state.get('stock_view_mode') == 'add':
                with st.form("add_stock_doc"):
                    st.subheader("새로운 기업 분석 작성")
                    new_comp = st.text_input("기업명", placeholder="삼성전자")
                    new_title = st.text_input("제목", placeholder="24년 전망 보고서")
                    
                    c_date, c_kw = st.columns([1, 2])
                    new_date = c_date.date_input("작성일", value=datetime.now())
                    new_kw = c_kw.text_input("키워드 (쉼표 구분)", placeholder="반도체, AI, 실적")
                    
                    st.markdown("### 내용 작성")
                    st.caption("💡 웹페이지나 워드의 표/글머리 기호를 그대로 붙여넣을 수 있습니다.")
                    
                    # [핵심 변경] st.text_area -> st_quill (위지윅 에디터)
                    new_content = st_quill(
                        placeholder="여기에 내용을 작성하거나 붙여넣으세요...",
                        html=True,  # HTML 형식으로 저장
                        key="quill_editor",
                        min_height=400
                    )
                    
                    if st.form_submit_button("저장", type="primary", use_container_width=True):
                        new_doc = {
                            "id": str(len(st.session_state['stock_db']) + 1),
                            "company": new_comp, "title": new_title, 
                            "content": new_content,  # HTML 태그가 포함된 내용 저장
                            "keywords": [k.strip() for k in new_kw.split(',')],
                            "created_at": str(new_date)
                        }
                        st.session_state['stock_db'].append(new_doc)
                        st.session_state['stock_view_mode'] = 'list'
                        st.success("저장되었습니다!")
                        time.sleep(0.5)
                        st.rerun()

            # B. 문서 보기 모드 (HTML 렌더링)
            else:
                sel_ids = st.session_state['selected_doc_ids']
                view_cols = st.columns(len(sel_ids))
                
                for idx, doc_id in enumerate(sel_ids):
                    doc_data = next((item for item in st.session_state['stock_db'] if item["id"] == doc_id), None)
                    
                    if doc_data:
                        with view_cols[idx]:
                            with st.container(border=True):
                                h1, h2 = st.columns([8, 2])
                                h1.markdown(f"### {doc_data['title']}")
                                h2.caption(f"{doc_data['created_at']}")
                                
                                st.markdown(f"**{doc_data['company']}**")
                                
                                kw_cols = st.columns(len(doc_data['keywords']) + 1)
                                for k_i, kw in enumerate(doc_data['keywords']):
                                    if kw_cols[k_i].button(f"#{kw}", key=f"kw_{doc_id}_{k_i}"):
                                        st.session_state['menu_mode'] = "Knowledge Graph"
                                        st.session_state['selected_keyword'] = kw
                                        st.rerun()
                                
                                st.divider()
                                
                                # [핵심 변경] 저장된 HTML 내용을 서식 그대로 렌더링
                                st.markdown(doc_data['content'], unsafe_allow_html=True)
                                
                                if st.button("닫기", key=f"close_{doc_id}", use_container_width=True):
                                    st.session_state['selected_doc_ids'].remove(doc_id)
                                    st.rerun()
