"""
stock_ui.py — Stock Analysis UI (List / Editor / Viewer)
"""
import streamlit as st
import pandas as pd
import time
from utils.db_stock import load_stocks, add_stock, update_stock, move_stock_to_trash
from utils.db_common import (
    copy_to_clipboard, strip_html, get_kst_now_str, highlight_text
)
from utils.style import QUILL_TOOLBAR

try:
    from streamlit_quill import st_quill
except ImportError:
    st_quill = None

# ==========================================
# HELPERS
# ==========================================
def _init_stock_db():
    """Stock DB 세션 초기화"""
    if 'stock_db' not in st.session_state:
        st.session_state['stock_db'] = load_stocks()

def _move_to_trash(doc_id):
    """Stock 문서를 휴지통으로 이동"""
    target_doc = next((d for d in st.session_state['stock_db'] if d['id'] == doc_id), None)
    if target_doc:
        move_stock_to_trash(target_doc)
        target_doc['deleted_at'] = get_kst_now_str()
        st.session_state['stock_db'] = [d for d in st.session_state['stock_db'] if d['id'] != doc_id]
        sel_ids = st.session_state.get('selected_doc_ids', [])
        if doc_id in sel_ids:
            sel_ids.remove(doc_id)
        st.toast("🗑️ 휴지통으로 이동되었습니다.")
        time.sleep(0.5)
        st.rerun()

def _delete_company_all(company_name):
    """기업 전체 문서 휴지통 이동"""
    targets = [d for d in st.session_state['stock_db'] if d['company'] == company_name]
    if targets:
        for doc in targets:
            move_stock_to_trash(doc)
            sel_ids = st.session_state.get('selected_doc_ids', [])
            if doc['id'] in sel_ids:
                sel_ids.remove(doc['id'])
        st.session_state['stock_db'] = [d for d in st.session_state['stock_db'] if d['company'] != company_name]
        st.toast(f"🗑️ '{company_name}' 전체가 휴지통으로 이동되었습니다.")
    else:
        st.toast("삭제할 문서가 없습니다.")
    time.sleep(1.0)
    st.rerun()

# ==========================================
# MAIN RENDER
# ==========================================
def render_stock_page():
    _init_stock_db()
    if 'selected_doc_ids' not in st.session_state:
        st.session_state['selected_doc_ids'] = []

    df = pd.DataFrame(st.session_state['stock_db'])
    all_companies, all_keywords_set = [], set()
    grouped = pd.DataFrame()

    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
        df['created_at'] = df['created_at'].fillna(pd.Timestamp.now())
        df = df.sort_values(by='created_at', ascending=False)

        if not st.session_state['selected_doc_ids'] and not st.session_state.get('doc_manually_closed', False):
            st.session_state['selected_doc_ids'] = [df.iloc[0]['id']]

        all_companies = sorted(list(df['company'].unique()))
        for kw_list in df['keywords']:
            all_keywords_set.update(kw_list)
        grouped = df.groupby('company').agg({'created_at': 'max', 'keywords': 'sum', 'id': 'count'}).reset_index()
        grouped = grouped.sort_values(by='created_at', ascending=False)
        grouped['keywords'] = grouped['keywords'].apply(lambda x: list(set(x))[:5])

    all_keywords_list = sorted(list(all_keywords_set))
    is_editor_mode = st.session_state.get('stock_view_mode') in ['add', 'edit']

    if is_editor_mode:
        _render_editor(all_companies, all_keywords_list)
    else:
        _render_list_and_viewer(df, grouped, all_keywords_list)

# ==========================================
# EDITOR MODE
# ==========================================
def _render_editor(all_companies, all_keywords_list):
    target_id = st.session_state.get('edit_target_id')
    if target_id:
        edit_data = next((d for d in st.session_state['stock_db'] if d['id'] == target_id), None)
        if not edit_data:
            st.stop()
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
    with c_k1:
        sel_kws = st.multiselect("키워드 선택", options=all_keywords_list, default=[k for k in def_kw_list if k in all_keywords_list])
    with c_k2:
        manual_kws = st.text_input("키워드 추가 (쉼표)", placeholder="태그 입력")

    st.markdown("###### 내용")
    if st_quill:
        in_content = st_quill(value=def_content or "", html=True, toolbar=QUILL_TOOLBAR, key=f"quill_{target_id or 'new'}")
    else:
        in_content = st.text_area("내용", value=def_content or "", height=500)

    if st.button("💾 저장하기", type="primary", use_container_width=True):
        if not final_comp or not st.session_state.doc_title:
            st.warning("기업명/제목 필수")
        else:
            m_kw = [k.strip() for k in manual_kws.split(',') if k.strip()]
            f_kw = list(set(sel_kws + m_kw))

            if target_id:
                update_stock(target_id, final_comp, st.session_state.doc_title, in_content, f_kw)
                st.session_state['stock_db'] = load_stocks()
                st.success("수정되었습니다!")
            else:
                new_data = add_stock(final_comp, st.session_state.doc_title, in_content, f_kw)
                if new_data:
                    st.session_state['stock_db'] = load_stocks()
                    st.success("저장되었습니다!")
                else:
                    st.error("저장 실패.")
                    st.stop()

            st.session_state['stock_view_mode'] = 'list'
            st.session_state['edit_target_id'] = None
            st.session_state.pop('doc_manually_closed', None)
            time.sleep(0.5)
            st.rerun()

# ==========================================
# LIST & VIEWER MODE
# ==========================================
def _render_list_and_viewer(df, grouped, all_keywords_list):
    st.text_input("🔍 기업명/제목/내용 검색", placeholder="Search...", label_visibility="collapsed", key="stock_search_query")
    sq = st.session_state.get("stock_search_query", "")

    # Company List
    with st.container(height=280):
        if not grouped.empty:
            for _, co_row in grouped.iterrows():
                sub_docs = df[df['company'] == co_row['company']]

                # Deep Search: 기업명 or 하위 문서에서 검색어 매칭
                company_match = False
                if not sq:
                    company_match = True
                elif sq.lower() in co_row['company'].lower():
                    company_match = True
                else:
                    for _, d in sub_docs.iterrows():
                        if sq.lower() in (d['title'] + str(d['keywords']) + d['content']).lower():
                            company_match = True
                            break

                if not company_match:
                    continue

                c_exp, c_del = st.columns([9.2, 0.8])

                with c_exp:
                    with st.expander(f"🏢 {co_row['company']}", expanded=bool(sq)):
                        st.markdown(f"Key: {' '.join([f'`{k}`' for k in co_row['keywords']])}")
                        st.markdown("<hr style='margin: 5px 0; border-color: #444;'>", unsafe_allow_html=True)

                        for _, doc in sub_docs.iterrows():
                            if sq:
                                content_match = sq.lower() in (doc['title'] + str(doc['keywords']) + doc['content']).lower()
                                if not content_match and sq.lower() not in co_row['company'].lower():
                                    continue

                            r1, r2, r3 = st.columns([5.5, 3.5, 1])
                            with r1:
                                if st.button(f"📄 {doc['title']}", key=f"open_{doc['id']}", use_container_width=True):
                                    st.session_state['selected_doc_ids'] = [doc['id']]
                                    st.session_state['stock_view_mode'] = 'view'
                                    st.session_state.pop('doc_manually_closed', None)
                                    st.rerun()
                            with r2:
                                k_html = "".join([f"<span class='doc-tag'>#{k}</span>" for k in doc['keywords']])
                                try:
                                    d_str = doc['created_at'].strftime('%y.%m.%d')
                                except Exception:
                                    d_str = str(doc['created_at'])[:10]
                                st.markdown(f"<div style='text-align: right; padding-top: 5px;'>{k_html}<span class='date-label'>{d_str}</span></div>", unsafe_allow_html=True)
                            with r3:
                                with st.popover("⋮", use_container_width=True):
                                    if st.button("Edit", key=f"e_{doc['id']}", use_container_width=True):
                                        st.session_state['stock_view_mode'] = 'edit'
                                        st.session_state['edit_target_id'] = doc['id']
                                        st.rerun()
                                    if st.button("Trash", key=f"d_{doc['id']}", use_container_width=True):
                                        _move_to_trash(doc['id'])

                with c_del:
                    if st.button("🗑️", key=f"del_co_{co_row['company']}", help="기업 전체 휴지통 이동", use_container_width=True):
                        _delete_company_all(co_row['company'])
        else:
            st.caption("문서가 없습니다.")

    st.divider()

    # Document Viewer
    sel_ids = st.session_state.get('selected_doc_ids', [])
    if sel_ids:
        for doc_id in sel_ids:
            doc = next((d for d in st.session_state['stock_db'] if d['id'] == doc_id), None)
            if doc:
                with st.container(border=True):
                    h1, h2, h3 = st.columns([8, 1, 1])
                    with h1:
                        h_title = highlight_text(doc['title'], sq)
                        h_comp = highlight_text(doc['company'], sq)
                        keywords_html = "".join([f"<span class='doc-tag'>#{highlight_text(k, sq)}</span>" for k in doc['keywords']])
                        title_html = f"""
                        <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 10px;">
                            <h2 style="margin: 0; padding: 0;">{h_title}</h2>
                            <span style="color: #888; font-size: 0.9rem; white-space: nowrap;">{h_comp} | {doc['created_at']}</span>
                            <span style="margin-left: 5px;">{keywords_html}</span>
                        </div>
                        """
                        st.markdown(title_html, unsafe_allow_html=True)
                    with h2:
                        if st.button("📋", key=f"cp_doc_{doc['id']}", help="복사", use_container_width=True):
                            full_text = f"[{doc['company']}] {doc['title']}\n키워드: {', '.join(doc['keywords'])}\n작성일: {doc['created_at']}\n\n{strip_html(doc['content'])}"
                            copy_to_clipboard(full_text)
                            st.toast("클립보드에 복사되었습니다!")
                    with h3:
                        if st.button("✕", key=f"cl_{doc['id']}", help="닫기", use_container_width=True):
                            st.session_state['selected_doc_ids'].remove(doc['id'])
                            st.session_state['doc_manually_closed'] = True
                            st.rerun()

                    st.divider()
                    st.markdown(doc['content'], unsafe_allow_html=True)
    else:
        st.info("문서를 선택하세요.")
