import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils.style import get_common_style
# [DB API 연결]
from utils.db_api import load_stocks, add_stock, update_stock, move_stock_to_trash

try:
    from streamlit_quill import st_quill
except ImportError:
    st_quill = None

def init_stock_db():
    # [REAL DB] 예시 데이터 없이 DB에서 로드
    if 'stock_db' not in st.session_state:
        st.session_state['stock_db'] = load_stocks()
    if 'stock_trash_db' not in st.session_state:
        st.session_state['stock_trash_db'] = []

def move_to_trash(doc_id):
    target_doc = next((d for d in st.session_state['stock_db'] if d['id'] == doc_id), None)
    if target_doc:
        move_stock_to_trash(target_doc) # DB 삭제
        
        target_doc['deleted_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        st.session_state['stock_trash_db'].append(target_doc)
        st.session_state['stock_db'] = [d for d in st.session_state['stock_db'] if d['id'] != doc_id]
        
        if doc_id in st.session_state.get('selected_doc_ids', []):
            st.session_state['selected_doc_ids'].remove(doc_id)
        st.toast("🗑️ 휴지통으로 이동되었습니다.")
        time.sleep(0.5)
        st.rerun()

def delete_company_all(company_name):
    targets = [d for d in st.session_state['stock_db'] if d['company'] == company_name]
    if targets:
        for doc in targets:
            move_stock_to_trash(doc) # DB 삭제
            if doc['id'] in st.session_state.get('selected_doc_ids', []):
                st.session_state['selected_doc_ids'].remove(doc['id'])
        
        st.session_state['stock_db'] = [d for d in st.session_state['stock_db'] if d['company'] != company_name]
        st.toast(f"🗑️ '{company_name}' 관련 문서가 삭제되었습니다.")
    else:
        st.toast("삭제할 문서가 없습니다.")
    time.sleep(1.0)
    st.rerun()

def render_stock_page():
    init_stock_db()
    if 'selected_doc_ids' not in st.session_state: st.session_state['selected_doc_ids'] = []
    
    st.markdown(get_common_style(), unsafe_allow_html=True)
    st.markdown("""
    <style>
        .doc-tag { background-color: #222; color: #aaa; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; margin-right: 4px; border: 1px solid #444; white-space: nowrap; display: inline-block; }
        .date-label { color: #666; font-size: 0.75rem; margin-left: 8px; white-space: nowrap; }
        .stQuill { background-color: white; color: black; border-radius: 8px; padding: 5px; min-height: 400px; }
        div[data-testid="column"] button[kind="secondary"] { justify-content: flex-start !important; text-align: left !important; padding-left: 0px !important; border: none !important; }
        div[data-testid="column"] button[kind="secondary"] p { text-align: left !important; }
        div[data-testid="stPopover"] > button { border: none !important; background: transparent !important; color: #888 !important; }
        div[data-testid="stPopover"] > button:hover { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

    df = pd.DataFrame(st.session_state['stock_db'])
    all_companies = []
    all_keywords_set = set()
    grouped = pd.DataFrame()
    
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
        df['created_at'] = df['created_at'].fillna(pd.Timestamp.now())
        df = df.sort_values(by='created_at', ascending=False)
        
        if not st.session_state['selected_doc_ids'] and not st.session_state.get('doc_manually_closed', False):
            st.session_state['selected_doc_ids'] = [df.iloc[0]['id']]
        
        all_companies = sorted(list(df['company'].unique()))
        for kw_list in df['keywords']: all_keywords_set.update(kw_list)
        grouped = df.groupby('company').agg({'created_at': 'max', 'keywords': 'sum', 'id': 'count'}).reset_index()
        grouped = grouped.sort_values(by='created_at', ascending=False)
        grouped['keywords'] = grouped['keywords'].apply(lambda x: list(set(x))[:5])
    
    all_keywords_list = sorted(list(all_keywords_set))
    is_editor_mode = st.session_state.get('stock_view_mode') in ['add', 'edit']

    # --- [A] EDITOR MODE ---
    if is_editor_mode:
        target_id = st.session_state.get('edit_target_id')
        if target_id:
            edit_data = next((d for d in st.session_state['stock_db'] if d['id'] == target_id), None)
            if not edit_data: st.stop()
            def_comp, def_title = edit_data['company'], edit_data['title']
            def_kw_list, def_content = edit_data['keywords'], edit_data['content']
            mode_title = "기존 문서 수정"
        else:
            def_comp, def_title, def_kw_list, def_content = "", "", [], ""
            mode_title = "새 문서 작성"

        st.subheader(f"📝 {mode_title}")
        c1, c2 = st.columns([1, 2])
        with c1:
            comp_options = ["➕ 직접 입력"] + all_companies
            sel_idx = comp_options.index(def_comp) if def_comp in all_companies else 0
            sel_comp = st.selectbox("기업명", options=comp_options, index=sel_idx)
            final_comp = st.text_input("기업명 입력", value=def_comp if def_comp not in all_companies else "") if sel_comp == "➕ 직접 입력" else sel_comp
        with c2:
            st.text_input("제목", key="doc_title", value=def_title)

        c_k1, c_k2 = st.columns([2, 1])
        with c_k1: sel_kws = st.multiselect("키워드 선택", options=all_keywords_list, default=[k for k in def_kw_list if k in all_keywords_list])
        with c_k2: manual_kws = st.text_input("키워드 추가 (쉼표)", placeholder="태그 입력")
        
        st.markdown("###### 내용")
        toolbar = [['bold', 'italic', 'underline', 'strike'], ['blockquote', 'code-block'], [{'header': 1}, {'header': 2}], [{'list': 'ordered'}, {'list': 'bullet'}], [{'indent': '-1'}, {'indent': '+1'}], ['link', 'image'], ['clean']]
        if st_quill:
            in_content = st_quill(value=def_content or "", html=True, toolbar=toolbar, key=f"quill_{target_id or 'new'}")
        else:
            in_content = st.text_area("내용", value=def_content or "", height=500)

        if st.button("💾 저장하기", type="primary", use_container_width=True):
            if not final_comp or not st.session_state.doc_title: st.warning("기업명/제목 필수")
            else:
                m_kw = [k.strip() for k in manual_kws.split(',') if k.strip()]
                f_kw = list(set(sel_kws + m_kw))
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                if target_id:
                    update_stock(target_id, final_comp, st.session_state.doc_title, in_content, f_kw) # DB Update
                    for d in st.session_state['stock_db']:
                        if d['id'] == target_id: d.update({"company": final_comp, "title": st.session_state.doc_title, "content": in_content, "keywords": f_kw, "created_at": now_str})
                else:
                    new_data = add_stock(final_comp, st.session_state.doc_title, in_content, f_kw) # DB Add
                    if new_data: st.session_state['stock_db'].append(new_data)
                
                st.success("저장되었습니다!")
                st.session_state['stock_view_mode'] = 'list'
                st.session_state['edit_target_id'] = None
                if 'doc_manually_closed' in st.session_state: del st.session_state['doc_manually_closed']
                time.sleep(0.5); st.rerun()

    # --- [B] LIST & VIEWER MODE ---
    else:
        st.text_input("🔍 검색", placeholder="Search...", label_visibility="collapsed", key="stock_search_query")
        sq = st.session_state.get("stock_search_query", "")
        
        with st.container(height=280):
            if not grouped.empty:
                for _, co in grouped.iterrows():
                    if sq and (sq not in co['company']): continue
                    c_exp, c_del = st.columns([9.2, 0.8])
                    with c_exp:
                        with st.expander(f"🏢 {co['company']}", expanded=False):
                            st.markdown(f"Key: {' '.join([f'`{k}`' for k in co['keywords']])}")
                            st.markdown("<hr style='margin: 5px 0; border-color: #444;'>", unsafe_allow_html=True)
                            for _, doc in df[df['company']==co['company']].iterrows():
                                r1, r2, r3 = st.columns([5.5, 3.5, 1])
                                with r1:
                                    if st.button(f"📄 {doc['title']}", key=f"open_{doc['id']}", use_container_width=True):
                                        st.session_state['selected_doc_ids'] = [doc['id']]
                                        st.session_state['stock_view_mode'] = 'view'
                                        if 'doc_manually_closed' in st.session_state: del st.session_state['doc_manually_closed']
                                        st.rerun()
                                with r2:
                                    k_html = "".join([f"<span class='doc-tag'>#{k}</span>" for k in doc['keywords']])
                                    d_str = doc['created_at'].strftime('%y.%m.%d')
                                    st.markdown(f"<div style='text-align: right; padding-top: 5px;'>{k_html}<span class='date-label'>{d_str}</span></div>", unsafe_allow_html=True)
                                with r3:
                                    with st.popover("⋮", use_container_width=True):
                                        if st.button("Edit", key=f"e_{doc['id']}", use_container_width=True):
                                            st.session_state['stock_view_mode'] = 'edit'; st.session_state['edit_target_id'] = doc['id']; st.rerun()
                                        if st.button("Trash", key=f"d_{doc['id']}", use_container_width=True): move_to_trash(doc['id'])
                    with c_del:
                        if st.button("🗑️", key=f"del_co_{co['company']}", help="기업 삭제", use_container_width=True): delete_company_all(co['company'])
            else: st.caption("문서가 없습니다.")

        st.divider()
        sel_ids = st.session_state.get('selected_doc_ids', [])
        if sel_ids:
            for i, doc_id in enumerate(sel_ids):
                doc = next((d for d in st.session_state['stock_db'] if d['id'] == doc_id), None)
                if doc:
                    with st.container(border=True):
                        h1, h2, h3 = st.columns([9, 0.5, 0.5])
                        with h1: 
                            st.markdown(f"## {doc['title']}")
                            st.caption(f"{doc['created_at']} | {doc['company']}")
                        # [COPY BUTTON]
                        with h2:
                            with st.popover("📋", help="복사", use_container_width=True):
                                st.code(doc['content'], language='html')
                        with h3:
                            if st.button("✕", key=f"cl_{doc['id']}", help="닫기"):
                                st.session_state['selected_doc_ids'].remove(doc['id'])
                                st.session_state['doc_manually_closed'] = True
                                st.rerun()
                        
                        cols = st.columns(10)
                        for idx, kw in enumerate(doc['keywords']):
                            if idx < 10:
                                if cols[idx].button(f"#{kw}", key=f"k_{doc['id']}_{idx}"):
                                    st.session_state['menu_mode'] = "Knowledge Graph"; st.session_state['selected_keyword'] = kw; st.rerun()
                        st.divider()
                        st.markdown(doc['content'], unsafe_allow_html=True)
        else: st.info("문서를 선택하세요.")
