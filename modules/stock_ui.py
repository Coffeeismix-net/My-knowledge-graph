import streamlit as st
import pandas as pd
from datetime import datetime
from utils.style import get_common_style

# [Mock DB] 데이터베이스가 없을 경우를 대비한 초기 더미 데이터
def init_stock_db():
    if 'stock_db' not in st.session_state:
        st.session_state['stock_db'] = [
            # 예시 데이터 구조
            {
                "id": "1", "company": "삼성전자", "title": "24년 4분기 잠정실적 분석", 
                "content": "메모리 반도체 업황 회복으로 인한 어닝 서프라이즈...", 
                "keywords": ["반도체", "HBM", "실적발표"], "created_at": "2024-05-20 10:00"
            },
            {
                "id": "2", "company": "삼성전자", "title": "HBM3E 공급 전망", 
                "content": "엔비디아 향 HBM3E 공급 테스트 통과 가능성이 높아지며...", 
                "keywords": ["HBM", "엔비디아", "공급망"], "created_at": "2024-05-18 14:30"
            },
            {
                "id": "3", "company": "에코프로비엠", "title": "양극재 수출입 데이터 분석", 
                "content": "전기차 수요 둔화로 인한 양극재 판가 하락...", 
                "keywords": ["2차전지", "양극재", "수출입"], "created_at": "2024-05-19 09:00"
            }
        ]

def render_stock_page():
    init_stock_db()
    
    # 1. 스타일 및 헤더
    st.markdown(get_common_style(), unsafe_allow_html=True)
    
    # [CSS 추가] 리스트 아이템 스타일링
    st.markdown("""
    <style>
        .stock-row { 
            display: flex; align-items: center; padding: 10px; 
            border-bottom: 1px solid #333; transition: background 0.2s;
        }
        .stock-row:hover { background-color: #222; cursor: pointer; }
        .tag {
            background-color: #00ADB5; color: black; padding: 2px 8px; 
            border-radius: 12px; font-size: 0.75rem; margin-right: 5px;
        }
    </style>
    """, unsafe_allow_html=True)

    # 2. 데이터 준비 (Aggregation)
    df = pd.DataFrame(st.session_state['stock_db'])
    
    # 기업별로 데이터 묶기 (Grouping)
    if not df.empty:
        # 최신순 정렬
        df['created_at'] = pd.to_datetime(df['created_at'])
        df = df.sort_values(by='created_at', ascending=False)
        
        # 기업별 집계 (최신 업데이트일, 키워드 통합)
        grouped = df.groupby('company').agg({
            'created_at': 'max',
            'keywords': 'sum',  # 리스트 합치기
            'id': 'count'       # 문서 개수
        }).reset_index()
        
        # 키워드 중복 제거
        grouped['keywords'] = grouped['keywords'].apply(lambda x: list(set(x))[:5]) # 최대 5개만 표시
    else:
        grouped = pd.DataFrame()

    # 3. 상단 컨트롤 바 (검색 & 추가)
    c1, c2 = st.columns([6, 2])
    with c1:
        search_query = st.text_input("🔍 기업명/키워드 검색", placeholder="Search...", label_visibility="collapsed")
    with c2:
        # 문서 추가 버튼 (모달/폼 열기)
        if st.button("➕ 문서 추가", use_container_width=True):
            st.session_state['stock_view_mode'] = 'add'
            st.rerun()

    st.divider()

    # 4. 레이아웃 분기 (리스트 모드 vs 뷰어 모드)
    # 선택된 문서가 있으면 뷰어 모드(좌측 리스트, 우측 내용), 없으면 전체 리스트
    if 'selected_doc_ids' not in st.session_state: st.session_state['selected_doc_ids'] = []
    
    is_viewer_open = len(st.session_state['selected_doc_ids']) > 0 or st.session_state.get('stock_view_mode') == 'add'
    
    # 화면 비율 설정 (뷰어 열리면 1:2, 아니면 1)
    if is_viewer_open:
        col_left, col_right = st.columns([1, 2])
    else:
        col_left = st.container()
        col_right = None

    # --- [좌측] 기업 및 문서 리스트 ---
    with col_left:
        # [모드] 문서 추가 폼인 경우 Back 버튼 표시
        if st.session_state.get('stock_view_mode') == 'add':
            if st.button("⬅️ 목록으로", use_container_width=True):
                st.session_state['stock_view_mode'] = 'list'
                st.session_state['selected_doc_ids'] = []
                st.rerun()
        
        # 리스트 렌더링
        if not grouped.empty:
            for _, company_row in grouped.iterrows():
                # 검색 필터링
                if search_query and (search_query not in company_row['company']):
                    continue

                # 기업 정보 표시 (Expandable)
                with st.expander(f"🏢 {company_row['company']} ({company_row['id']} docs)", expanded=False):
                    # 해당 기업의 하위 문서들
                    sub_docs = df[df['company'] == company_row['company']]
                    
                    # 상위 키워드 배너
                    st.markdown(f"🏷️ {' '.join([f'`{k}`' for k in company_row['keywords']])}")
                    
                    for _, doc in sub_docs.iterrows():
                        # 문서 행 (체크박스 + 제목 + 날짜)
                        sc1, sc2, sc3 = st.columns([0.5, 4, 1.5])
                        
                        # 체크박스 (다중 선택용)
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

                        # 제목 버튼 (클릭 시 단독 보기)
                        if sc2.button(doc['title'], key=f"btn_title_{doc['id']}"):
                            st.session_state['selected_doc_ids'] = [doc['id']]
                            st.session_state['stock_view_mode'] = 'view'
                            st.rerun()
                            
                        sc3.caption(doc['created_at'].strftime('%y-%m-%d'))

    # --- [우측] 뷰어 & 에디터 ---
    if is_viewer_open and col_right:
        with col_right:
            # A. 문서 추가 모드
            if st.session_state.get('stock_view_mode') == 'add':
                with st.form("add_stock_doc"):
                    st.subheader("새로운 기업 분석 작성")
                    new_comp = st.text_input("기업명", placeholder="삼성전자")
                    new_title = st.text_input("제목", placeholder="24년 전망 보고서")
                    new_date = st.date_input("작성일", value=datetime.now())
                    new_kw = st.text_input("키워드 (쉼표 구분)", placeholder="반도체, AI, 실적")
                    new_content = st.text_area("내용 (Markdown)", height=400)
                    
                    if st.form_submit_button("저장", type="primary", use_container_width=True):
                        # 저장 로직 (Mock)
                        new_doc = {
                            "id": str(len(st.session_state['stock_db']) + 1),
                            "company": new_comp, "title": new_title, "content": new_content,
                            "keywords": [k.strip() for k in new_kw.split(',')],
                            "created_at": str(new_date)
                        }
                        st.session_state['stock_db'].append(new_doc)
                        st.session_state['stock_view_mode'] = 'list'
                        st.success("저장되었습니다!")
                        time.sleep(0.5)
                        st.rerun()

            # B. 문서 보기 모드 (1개 또는 2개 비교)
            else:
                sel_ids = st.session_state['selected_doc_ids']
                view_cols = st.columns(len(sel_ids))
                
                for idx, doc_id in enumerate(sel_ids):
                    # DB에서 데이터 찾기
                    doc_data = next((item for item in st.session_state['stock_db'] if item["id"] == doc_id), None)
                    
                    if doc_data:
                        with view_cols[idx]:
                            with st.container(border=True):
                                # 헤더 (수정/삭제 버튼 포함)
                                h1, h2 = st.columns([8, 2])
                                h1.markdown(f"### {doc_data['title']}")
                                h2.caption(f"{doc_data['created_at']}")
                                
                                st.markdown(f"**{doc_data['company']}**")
                                
                                # 키워드 (클릭 시 그래프 뷰 연동)
                                kw_cols = st.columns(len(doc_data['keywords']) + 1)
                                for k_i, kw in enumerate(doc_data['keywords']):
                                    # [핵심 기능] 키워드 클릭 시 그래프 뷰로 이동
                                    if kw_cols[k_i].button(f"#{kw}", key=f"kw_{doc_id}_{k_i}"):
                                        st.session_state['menu_mode'] = "Knowledge Graph"
                                        st.session_state['selected_keyword'] = kw
                                        st.rerun()
                                
                                st.divider()
                                st.markdown(doc_data['content'])
                                
                                # 닫기 버튼
                                if st.button("닫기", key=f"close_{doc_id}", use_container_width=True):
                                    st.session_state['selected_doc_ids'].remove(doc_id)
                                    st.rerun()
