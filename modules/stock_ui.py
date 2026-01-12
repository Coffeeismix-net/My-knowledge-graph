# 주식 분석 페이지 UI

import streamlit as st
from utils.style import get_common_style

def render_stock_page():
    """
    기업 분석(Stock Analysis) 페이지의 메인 UI를 렌더링합니다.
    """
    # 1. 공통 스타일 적용 (기존 테마 유지)
    st.markdown(get_common_style(), unsafe_allow_html=True)

    # 2. 페이지 헤더
    st.markdown("## 📈 기업 스터디 (Stock Analysis)")
    st.caption("기업 분석 리포트와 주식 스터디를 위한 전용 공간입니다.")
    st.markdown("<hr class='tight-hr'>", unsafe_allow_html=True)

    # 3. 3단 레이아웃 구성 (좌측: 리스트 / 중앙: 문서 / 우측: 뷰어)
    # 비율: 1 (기업목록) : 1.2 (문서목록) : 2.8 (에디터/뷰어)
    col_list, col_docs, col_viewer = st.columns([1, 1.2, 2.8])

    # --- [1열] 좌측: 기업 리스트 ---
    with col_list:
        st.markdown("### 🏢 기업 목록")
        # 검색창
        search_ticker = st.text_input("기업명/티커 검색", placeholder="ex) 삼성전자, AAPL", key="stock_search")
        
        # (임시 데이터) 실제로는 DB에서 불러올 예정
        dummy_stocks = ["삼성전자", "SK하이닉스", "Tesla (TSLA)", "NVIDIA (NVDA)", "Apple (AAPL)"]
        
        # 리스트 표시
        st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
        for stock in dummy_stocks:
            if search_ticker and search_ticker not in stock:
                continue
            if st.button(f"📊 {stock}", key=f"btn_{stock}", use_container_width=True):
                st.session_state['selected_stock'] = stock
                st.rerun()

    # --- [2열] 중앙: 하위 문서 리스트 ---
    with col_docs:
        st.markdown("### 📄 관련 리포트")
        
        if 'selected_stock' in st.session_state and st.session_state['selected_stock']:
            current_stock = st.session_state['selected_stock']
            st.info(f"선택됨: {current_stock}")
            
            # (임시 데이터)
            dummy_docs = [
                f"{current_stock} 24년 4분기 실적발표",
                f"{current_stock} 산업 동향 분석",
                f"{current_stock} 경쟁사 비교"
            ]
            
            for doc in dummy_docs:
                if st.button(doc, key=f"doc_{doc}", use_container_width=True):
                    st.session_state['selected_doc'] = doc
        else:
            st.warning("👈 좌측에서 기업을 선택해주세요.")

    # --- [3열] 우측: 뷰어 & 에디터 ---
    with col_viewer:
        st.markdown("### 📝 노트 & 분석")
        
        # 탭 구성 (읽기 / 쓰기 / 그래프)
        tab_view, tab_edit, tab_graph = st.tabs(["👁️ 뷰어", "✏️ 에디터", "🕸️ 그래프"])
        
        with tab_view:
            if 'selected_doc' in st.session_state:
                st.markdown(f"#### {st.session_state['selected_doc']}")
                st.write("여기에 마크다운 형식의 본문 내용이 표시됩니다. 키워드는 자동으로 하이라이팅됩니다.")
                st.divider()
                st.caption("Last updated: 2024-05-20")
            else:
                st.info("문서를 선택하면 내용이 표시됩니다.")

        with tab_edit:
            st.text_area("내용 입력 (Markdown)", height=500, placeholder="# 여기에 분석 내용을 작성하세요.\n이미지를 붙여넣으면 구글 드라이브에 자동 업로드됩니다.")
            if st.button("저장 (Save to Drive)", type="primary"):
                st.toast("저장 기능은 아직 연결되지 않았습니다.")

        with tab_graph:
            st.info("이 기업과 관련된 지식 그래프가 여기에 표시됩니다.")
