import streamlit as st
import pandas as pd
from datetime import datetime

# ==========================================
# 
# ==========================================

def render_stock_page():
    """
    기업 분석 페이지 메인 렌더링 함수
    """
    st.title("📈 기업 분석 리포트 관리")

    # ------------------------------------------------------------------
    # 1. 사이드바: 기업 목록 (최신 수정순 정렬)
    # ------------------------------------------------------------------
    st.sidebar.header("기업 목록")

    # [TODO] 실제 DB에서 기업 목록을 가져오는 함수로 교체하세요.
    # stocks_data = get_all_stocks() 
    # 임시 데이터 예시 (실제 연결 시 삭제)
    if 'stocks_data' not in st.session_state:
        st.session_state['stocks_data'] = [
            {'id': 1, 'name': '리브스메드', 'created_at': '2025-01-10'},
            {'id': 2, 'name': '로킷헬스케어', 'created_at': '2025-01-12'}
        ]
    
    # DataFrame 변환
    stocks_df = pd.DataFrame(st.session_state['stocks_data'])

    if not stocks_df.empty:
        # 날짜 변환 (에러 방지: errors='coerce')
        if 'created_at' in stocks_df.columns:
            stocks_df['created_at'] = pd.to_datetime(stocks_df['created_at'], errors='coerce')
            # [요청사항] 기업 리스트 최신순 정렬
            stocks_df = stocks_df.sort_values(by='created_at', ascending=False)

        # 사이드바 선택창
        stock_names = stocks_df['name'].tolist()
        selected_stock_name = st.sidebar.selectbox("기업 선택", stock_names)
        
        # 선택된 기업 ID 찾기
        selected_stock_row = stocks_df[stocks_df['name'] == selected_stock_name].iloc[0]
        current_stock_id = selected_stock_row['id']
    else:
        st.sidebar.warning("등록된 기업이 없습니다.")
        return

    # ------------------------------------------------------------------
    # 2. 메인 화면: 선택된 기업 정보 및 문서 리스트
    # ------------------------------------------------------------------
    st.subheader(f"🏢 {selected_stock_name}")

    # (여기서 종목 분석 요청 입력창 등이 있을 수 있음 - 기존 코드 유지)
    with st.expander("새로운 분석 요청하기", expanded=False):
        query = st.text_input("분석하고 싶은 내용을 입력하세요 (예: 최근 실적 분석해줘)")
        if st.button("분석 시작"):
            st.info("분석 기능은 메인 로직(LLM)과 연결되어야 합니다.")

    st.divider()

    # ------------------------------------------------------------------
    # 3. 문서 리스트 출력 (핵심 수정 구간)
    # ------------------------------------------------------------------
    st.markdown("### 📑 저장된 분석 문서")

    # [TODO] 실제 DB에서 해당 기업의 문서를 가져오는 함수로 교체하세요.
    # documents = get_documents(stock_id=current_stock_id)
    
    # 임시 데이터 (테스트용)
    if 'documents_data' not in st.session_state:
        st.session_state['documents_data'] = [
            {'id': 101, 'stock_id': 1, 'title': '리브스메드 상세 분석', 'keywords': '로봇, 의료, 다빈치', 'created_at': '2025-01-13 14:00:00'},
            {'id': 102, 'stock_id': 1, 'title': '경쟁사 비교 분석', 'keywords': '시장점유율, 경쟁사', 'created_at': None}, # 날짜 없는 케이스 테스트
        ]
    
    # 현재 선택된 기업의 문서만 필터링 (DB 연동 시 쿼리에서 해결될 부분)
    documents = [d for d in st.session_state['documents_data'] if d['stock_id'] == current_stock_id]
    
    df_docs = pd.DataFrame(documents)

    if not df_docs.empty:
        # [에러 해결 1] 날짜 컬럼을 Datetime 객체로 변환 (실패 시 NaT 처리)
        if 'created_at' in df_docs.columns:
            df_docs['created_at'] = pd.to_datetime(df_docs['created_at'], errors='coerce')
            
            # [요청사항] 문서 최신순 정렬 (내림차순)
            df_docs = df_docs.sort_values(by='created_at', ascending=False)

        # 리스트 출력 루프
        for index, row in df_docs.iterrows():
            # 카드 형태의 디자인을 위해 컨테이너 사용
            with st.container():
                # [요청사항] 레이아웃 4분할: 제목(5) / 키워드&날짜(3) / 수정(1) / 삭제(1)
                col1, col2, col3, col4 = st.columns([5, 3, 1, 1])

                # 1. 문서 제목 (왼쪽 정렬)
                with col1:
                    st.markdown(f"📄 **{row['title']}**")

                # 2. 키워드 및 작성일 표기
                with col2:
                    # [에러 해결 2] NaT(날짜 없음) 체크 후 문자열 변환
                    if 'created_at' in row and pd.notnull(row['created_at']):
                        date_str = row['created_at'].strftime('%y-%m-%d')
                    else:
                        date_str = "-"
                    
                    keywords = row.get('keywords', '')
                    # 키워드가 있으면 함께, 없으면 날짜만 표시
                    if keywords:
                        st.caption(f"{keywords} | {date_str}")
                    else:
                        st.caption(f"{date_str}")

                # 3. 수정 버튼
                with col3:
                    if st.button("수정", key=f"edit_{row.get('id', index)}"):
                        st.session_state['edit_doc_id'] = row.get('id')
                        st.toast(f"수정 모드로 진입합니다. (ID: {row.get('id')})")
                        # 여기에 수정 페이지로 이동하거나 모달을 띄우는 로직 추가
                        st.rerun()

                # 4. 삭제 버튼
                with col4:
                    if st.button("삭제", key=f"del_{row.get('id', index)}"):
                        # [TODO] 실제 DB 삭제 함수 호출
                        # delete_document(row['id'])
                        
                        # (임시 삭제 로직)
                        st.session_state['documents_data'] = [
                            d for d in st.session_state['documents_data'] if d['id'] != row['id']
                        ]
                        st.success("문서가 삭제되었습니다.")
                        st.rerun()
            
            # 항목 간 구분선
            st.markdown("---")
            
    else:
        st.info("저장된 분석 문서가 없습니다.")

# 이 파일이 직접 실행될 때를 위한 코드 (테스트용)
if __name__ == "__main__":
    render_stock_page()
