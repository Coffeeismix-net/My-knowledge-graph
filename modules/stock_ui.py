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

# [Helper] 문서 삭제
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
    st.markdown(get_common_style(), unsafe_allow_html=True)
    
    # [스타일 정의]
    st.markdown("""
    <style>
        .doc-tag { background-color: #222; color: #aaa; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; margin-right: 4px; border: 1px solid #444; }
        .stQuill { background-color: white; color: black; border-radius: 8px; padding: 5px; min-height: 400px; }
        div[data-testid="column"] button[kind="secondary"] p { text-align: left !important; padding-left: 0px !important; }
        div[data-testid="stPopover"] > button { border: none !important; background: transparent !important; color: #888 !important; }
        div[data-testid="stPopover"] > button:hover { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

    # 1. 데이터 준비 (DB 로드 및 정렬)
    df = pd.DataFrame(st.session_state['stock_db'])
    
    # [Data for Auto-complete] 자동완성을 위한 고유 리스트 추출
    all_companies = []
    all_keywords_set = set()
    
    grouped = pd.DataFrame()
    
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
        df['created_at'] = df['created_at'].fillna(pd.Timestamp.now())
        df = df.sort_values(by='created_at', ascending=False)
        
        # 자동완성용 데이터 추출
        all_companies = sorted(list(df['company'].unique()))
        for kw_list in df['keywords']:
            all_keywords_set.update(kw_list)
            
        grouped = df.groupby('company').agg({
            'created_at': 'max', 'keywords': 'sum', 'id': 'count'
        }).reset_index()
        grouped = grouped.sort_values(by='created_at', ascending=False)
        grouped['keywords'] = grouped['keywords'].apply(lambda x: list(set(x))[:5])
    
    all_keywords_list = sorted(list(all_keywords_set))

    # 2. 모드 확인 (작성 모드 vs 리스트 모드)
    # stock_view_mode: 'list', 'view', 'add', 'edit'
    current_mode = st.session_state.get('stock_view_mode', 'list')
    is_editor_mode = current_mode in ['add', 'edit']

    # ==========================================
    # [CASE A] 에디터 모드 (Add / Edit) - 전체 화면 사용
    # ==========================================
    if is_editor_mode:
        # [뒤로가기 버튼]
        if st.button("⬅️ 목록으로 돌아가기", use_container_width=True):
            st.session_state['stock_view_mode'] = 'list'
            st.rerun()
        
        st.divider()

        # 데이터 로드 (수정 모드일 경우)
        target_id = st.session_state.get('edit_target_id')
        if target_id:
            edit_data = next((d for d in st.session_state['stock_db'] if d['id'] == target_id), None)
            if not edit_data: 
                st.error("데이터를 찾을 수 없습니다."); st.stop()
            def_comp, def_title = edit_data['company'], edit_data['title']
            def_kw_list, def_content = edit_data['keywords'], edit_data['content']
            mode_title = "기존 문서 수정"
        else:
            def_comp, def_title, def_kw_list, def_content = "", "", [], ""
            mode_title = "새 문서 작성"

        st.subheader(f"📝 {mode_title}")
        
        # --- [자동완성 입력 폼] ---
        c_input1, c_input2 = st.columns([1, 2])
        
        with c_input1:
            # 1. 기업명 (Selectbox + 직접 입력)
            # 리스트에 없는 새 기업을 입력할 수 있도록 '➕ 직접 입력' 옵션 추가
            comp_options = ["➕ 직접 입력"] + all_companies
            
            # 기존 기업명이 옵션에 있으면 그걸 기본값으로, 없으면 '직접 입력'으로
            if def_comp in all_companies:
                sel_index = comp_options.index(def_comp)
            else:
                sel_index = 0 # 직접 입력
                
            selected_comp = st.selectbox("기업명 선택", options=comp_options, index=sel_index)
            
            if selected_comp == "➕ 직접 입력":
                final_comp = st.text_input("기업명 입력", value=def_comp if def_comp not in all_companies else "", placeholder="새로운 기업명 입력")
            else:
                final_comp = selected_comp

        with c_input2:
            st.text_input("제목", key="doc_title", value=def_title, placeholder="리포트 제목을 입력하세요")

        # 2. 키워드 (Multiselect + 추가 입력)
        st.markdown("###### 키워드 (Tags)")
        c_kw1, c_kw2 = st.columns([2, 1])
        with c_kw1:
            # 기존 키워드들 중에서 선택 (자동완성 효과)
            selected_kws = st.multiselect("기존 키워드 선택", options=all_keywords_list, default=[k for k in def_kw_list if k in all_keywords_list], placeholder="키워드 검색 및 선택...")
        with c_kw2:
            # 리스트에 없는 새로운 키워드 입력
            manual_kws = st.text_input("신규 키워드 추가 (쉼표 구분)", placeholder="예: 성장주, 어닝서프라이즈")
            
        st.markdown("###### 내용")
        if st_quill:
            in_content = st_quill(
                value=def_content or "",
                placeholder="내용을 작성하거나 붙여넣으세요...",
                html=True,
                key=f"quill_{target_id or 'new'}"
            )
        else:
            in_content = st.text_area("내용", value=def_content or "", height=500)

        # [저장 로직]
        if st.button("💾 저장하기", type="primary", use_container_width=True):
            if not final_comp or not st.session_state.doc_title:
                st.warning("기업명과 제목은 필수입니다.")
            else:
                # 키워드 합치기 (선택된 것 + 직접 입력한 것)
                manual_kw_list = [k.strip() for k in manual_kws.split(',') if k.strip()]
                final_kw_list = list(set(selected_kws + manual_kw_list)) # 중복 제거
                
                # 기존 문서 수정 시 보존해야 할 키워드가 있다면 로직 추가 가능 (현재는 덮어쓰기)
                # 만약 사용자가 Multiselect에서 뺐다면 삭제 의도로 간주

                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                if target_id:
                    for d in st.session_state['stock_db']:
                        if d['id'] == target_id:
                            d.update({
                                "company": final_comp, 
                                "title": st.session_state.doc_title, 
                                "content": in_content, 
                                "keywords": final_kw_list,
                                "created_at": now_str
                            })
                else:
                    new_id = str(len(st.session_state['stock_db']) + 100)
                    st.session_state['stock_db'].append({
                        "id": new_id, 
                        "company": final_comp, 
                        "title": st.session_state.doc_title,
                        "content": in_content, 
                        "keywords": final_kw_list,
                        "created_at": now_str
                    })
                
                st.success("저장되었습니다!")
                st.session_state['stock_view_mode'] = 'list'
                st.session_state['edit_target_id'] = None
                time.sleep(0.5)
                st.rerun()

    # ==========================================
    # [CASE B] 리스트 / 뷰어 모드 (기존 레이아웃)
    # ==========================================
    else:
        # 상단 검색바
        st.text_input("🔍 기업명/키워드 검색", placeholder="Search...", label_visibility="collapsed", key="stock_search_query")
        search_query = st.session_state.get("stock_search_query", "")
        st.divider()

        is_viewer_open = len(st.session_state['selected_doc_ids']) > 0
        
        if is_viewer_open:
            col_left, col_right = st.columns([1, 2.5]) 
        else:
            col_left = st.container()
            col_right = None

        # [좌측] 리스트
        with col_left:
            if not grouped.empty:
                for _, co_row in grouped.iterrows():
                    if search_query and (search_query not in co_row['company']):
                        continue

                    with st.expander(f"🏢 {co_row['company']}", expanded=False):
                        st.markdown(f"Key: {' '.join([f'`{k}`' for k in co_row['keywords']])}")
                        st.markdown("<hr style='margin: 5px 0; border-color: #444;'>", unsafe_allow_html=True)

                        sub_docs = df[df['company'] == co_row['company']]
                        for _, doc in sub_docs.iterrows():
                            r_c1, r_c2 = st.columns([0.9, 0.1])
                            with r_c1:
                                doc_title = f"📄 {doc['title']}"
                                if st.button(doc_title, key=f"open_{doc['id']}", use_container_width=True):
                                    st.session_state['selected_doc_ids'] = [doc['id']]
                                    st.session_state['stock_view_mode'] = 'view'
                                    st.rerun()
                                date_str = doc['created_at'].strftime('%y.%m.%d')
                                kws_html = "".join([f"<span class='doc-tag'>#{k}</span>" for k in doc['keywords']])
                                st.caption(f"{date_str} | {kws_html}", unsafe_allow_html=True)
                                st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)

                            with r_c2:
                                with st.popover("⋮", use_container_width=True):
                                    if st.button("Edit", key=f"edit_{doc['id']}", use_container_width=True):
                                        st.session_state['stock_view_mode'] = 'edit'
                                        st.session_state['edit_target_id'] = doc['id']
                                        st.rerun()
                                    if st.button("Trash", key=f"del_{doc['id']}", use_container_width=True):
                                        move_to_trash(doc['id'])

        # [우측] 뷰어
        if is_viewer_open and col_right:
            with col_right:
                sel_ids = st.session_state['selected_doc_ids']
                if not sel_ids:
                    st.info("문서를 선택하세요.")
                else:
                    tabs = st.tabs([f"📄 Doc {i+1}" for i in range(len(sel_ids))])
                    for i, doc_id in enumerate(sel_ids):
                        doc = next((d for d in st.session_state['stock_db'] if d['id'] == doc_id), None)
                        if doc:
                            with tabs[i]:
                                with st.container(border=True):
                                    h1, h2 = st.columns([9.5, 0.5])
                                    with h1:
                                        st.markdown(f"## {doc['title']}")
                                        st.caption(f"{doc['created_at']} | {doc['company']}")
                                    with h2:
                                        if st.button("✕", key=f"v_close_{doc['id']}", help="닫기"):
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
