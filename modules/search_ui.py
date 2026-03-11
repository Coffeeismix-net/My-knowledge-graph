"""
search_ui.py — 글로벌 통합 검색
Node / Stock / Value Chain 전체를 대상으로 검색하고 도메인 태그와 함께 결과를 표시한다.
"""
import streamlit as st
import pandas as pd
import json
from utils.db_common import highlight_text, strip_html, copy_to_clipboard


# ==========================================
# SEARCH ENGINE
# ==========================================
def _search_nodes(query):
    """Node에서 검색 → list of result dicts"""
    results = []
    q = query.lower()
    for node in st.session_state.get('nodes_db', []):
        searchable = (
            node.get('label', '') + ' ' +
            node.get('summary', '') + ' ' +
            ' '.join(node.get('keywords', [])) + ' ' +
            strip_html(node.get('content', ''))
        ).lower()
        if q in searchable:
            # 매칭 우선순위 점수
            score = 0
            if q in node.get('label', '').lower():
                score += 100
            if q in ' '.join(node.get('keywords', [])).lower():
                score += 50
            if q in node.get('summary', '').lower():
                score += 20
            results.append({
                'domain': 'Node',
                'domain_icon': '🧠',
                'id': node['id'],
                'title': node['label'],
                'subtitle': ', '.join(node.get('keywords', [])),
                'preview': node.get('summary', '')[:200],
                'timestamp': node.get('timestamp', ''),
                'score': score,
                'raw': node,
            })
    return results


def _search_stocks(query):
    """Stock에서 검색 → list of result dicts"""
    results = []
    q = query.lower()
    for doc in st.session_state.get('stock_db', []):
        searchable = (
            doc.get('company', '') + ' ' +
            doc.get('title', '') + ' ' +
            ' '.join(doc.get('keywords', [])) + ' ' +
            strip_html(doc.get('content', ''))
        ).lower()
        if q in searchable:
            score = 0
            if q in doc.get('company', '').lower():
                score += 100
            if q in doc.get('title', '').lower():
                score += 80
            if q in ' '.join(doc.get('keywords', [])).lower():
                score += 50
            results.append({
                'domain': 'Stock',
                'domain_icon': '📊',
                'id': doc['id'],
                'title': f"[{doc['company']}] {doc['title']}",
                'subtitle': ', '.join(doc.get('keywords', [])),
                'preview': strip_html(doc.get('content', ''))[:200],
                'timestamp': str(doc.get('created_at', '')),
                'score': score,
                'raw': doc,
            })
    return results


def _search_valuechains(query):
    """ValueChain에서 검색 → list of result dicts"""
    results = []
    q = query.lower()
    for vc in st.session_state.get('vc_list', []):
        searchable = (
            vc.get('title', '') + ' ' +
            vc.get('json_data', '')
        ).lower()
        if q in searchable:
            score = 0
            if q in vc.get('title', '').lower():
                score += 100

            # JSON 내 매칭 컨텍스트 추출
            preview = vc.get('title', '')
            try:
                jd = json.loads(vc.get('json_data', '{}'))
                flat_text = json.dumps(jd, ensure_ascii=False)
                idx = flat_text.lower().find(q)
                if idx >= 0:
                    start = max(0, idx - 40)
                    end = min(len(flat_text), idx + len(query) + 80)
                    preview = "..." + flat_text[start:end] + "..."
            except Exception:
                pass

            results.append({
                'domain': 'Chain',
                'domain_icon': '🔗',
                'id': vc['id'],
                'title': vc['title'],
                'subtitle': '',
                'preview': preview[:200],
                'timestamp': vc.get('created_at', '')[:16],
                'score': score,
                'raw': vc,
            })
    return results


# ==========================================
# TAG-BASED SEARCH
# ==========================================
def _search_by_tag(tag):
    """특정 태그를 가진 Node/Stock 항목 수집"""
    results = []
    t = tag.strip().lower()

    for node in st.session_state.get('nodes_db', []):
        node_tags = [k.strip().lower() for k in node.get('keywords', [])]
        if t in node_tags:
            results.append({
                'domain': 'Node',
                'domain_icon': '🧠',
                'id': node['id'],
                'title': node['label'],
                'subtitle': ', '.join(node.get('keywords', [])),
                'preview': node.get('summary', '')[:200],
                'timestamp': node.get('timestamp', ''),
                'score': 50,
                'raw': node,
            })

    for doc in st.session_state.get('stock_db', []):
        doc_tags = [k.strip().lower() for k in doc.get('keywords', [])]
        if t in doc_tags:
            results.append({
                'domain': 'Stock',
                'domain_icon': '📊',
                'id': doc['id'],
                'title': f"[{doc['company']}] {doc['title']}",
                'subtitle': ', '.join(doc.get('keywords', [])),
                'preview': strip_html(doc.get('content', ''))[:200],
                'timestamp': str(doc.get('created_at', '')),
                'score': 50,
                'raw': doc,
            })

    return results


# ==========================================
# NAVIGATION HELPERS
# ==========================================
def _navigate_to_result(result):
    """검색 결과 클릭 시 해당 페이지로 이동"""
    domain = result['domain']
    rid = result['id']

    if domain == 'Node':
        st.session_state['menu_mode'] = "List View"
        # card_stack에 추가
        raw = result['raw']
        if rid not in [n['id'] for n in st.session_state.get('card_stack', [])]:
            st.session_state['card_stack'].append(raw)
        st.rerun()

    elif domain == 'Stock':
        st.session_state['menu_mode'] = "Stock Analysis"
        st.session_state['stock_view_mode'] = 'list'
        st.session_state['selected_doc_ids'] = [rid]
        st.session_state.pop('doc_manually_closed', None)
        st.rerun()

    elif domain == 'Chain':
        st.session_state['menu_mode'] = "Value Chain"
        st.session_state['vc_mode'] = 'list'
        st.session_state['selected_vc_id'] = rid
        st.rerun()


# ==========================================
# MAIN RENDER
# ==========================================
def render_global_search():
    """글로벌 검색 페이지 렌더링"""

    # --- 검색 바 ---
    search_col, filter_col = st.columns([7, 3])
    with search_col:
        query = st.text_input(
            "🔍 통합 검색",
            placeholder="모든 도메인에서 검색 (제목, 내용, 태그)...",
            label_visibility="collapsed",
            key="global_search_query",
        )
    with filter_col:
        domain_filter = st.multiselect(
            "도메인 필터",
            options=["Node", "Stock", "Chain"],
            default=["Node", "Stock", "Chain"],
            label_visibility="collapsed",
            key="global_search_filter",
        )

    # --- 태그 기반 검색 ---
    all_tags = set()
    for node in st.session_state.get('nodes_db', []):
        for kw in node.get('keywords', []):
            if kw.strip():
                all_tags.add(kw.strip())
    for doc in st.session_state.get('stock_db', []):
        for kw in doc.get('keywords', []):
            if kw.strip():
                all_tags.add(kw.strip())

    sorted_tags = sorted(all_tags)
    selected_tag = st.selectbox(
        "🏷️ 태그 필터",
        options=[""] + sorted_tags,
        index=0,
        format_func=lambda x: "태그 선택 (선택사항)..." if x == "" else f"#{x}",
        label_visibility="collapsed",
        key="global_tag_filter",
    )

    if not query and not selected_tag:
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("검색어를 입력하거나 태그를 선택하세요. 모든 도메인(Node, Stock, Value Chain)을 통합 검색합니다.")
        return

    # --- 검색 실행 ---
    all_results = []

    if selected_tag and not query:
        # 태그 전용 검색
        all_results = _search_by_tag(selected_tag)
        # 도메인 필터 적용
        all_results = [r for r in all_results if r['domain'] in domain_filter]
    elif query:
        # 텍스트 검색
        if "Node" in domain_filter:
            all_results.extend(_search_nodes(query))
        if "Stock" in domain_filter:
            all_results.extend(_search_stocks(query))
        if "Chain" in domain_filter:
            all_results.extend(_search_valuechains(query))

        # 태그 필터 추가 적용
        if selected_tag:
            tag_ids = {r['id'] for r in _search_by_tag(selected_tag)}
            all_results = [r for r in all_results if r['id'] in tag_ids]

    # 점수 기준 정렬
    all_results.sort(key=lambda x: x['score'], reverse=True)

    # --- 결과 표시 ---
    domain_counts = {}
    for r in all_results:
        domain_counts[r['domain']] = domain_counts.get(r['domain'], 0) + 1

    count_parts = []
    for d in ["Node", "Stock", "Chain"]:
        if d in domain_counts:
            icon = {"Node": "🧠", "Stock": "📊", "Chain": "🔗"}[d]
            count_parts.append(f"{icon} {d}: {domain_counts[d]}")

    result_label = f"**{len(all_results)}건** 발견"
    if count_parts:
        result_label += f"  ({' · '.join(count_parts)})"
    st.markdown(result_label)
    st.markdown("<hr class='tight-hr'>", unsafe_allow_html=True)

    if not all_results:
        st.caption("검색 결과가 없습니다.")
        return

    # 결과 리스트
    for i, result in enumerate(all_results):
        with st.container(border=True):
            r1, r2, r3 = st.columns([0.8, 8, 1.2])
            with r1:
                # 도메인 뱃지
                badge_colors = {"Node": "#00ADB5", "Stock": "#FFE600", "Chain": "#FF8800"}
                badge_color = badge_colors.get(result['domain'], "#888")
                st.markdown(
                    f"<div style='text-align:center;'>"
                    f"<span style='font-size:1.5rem;'>{result['domain_icon']}</span><br>"
                    f"<span class='search-domain-badge' style='background:{badge_color};'>"
                    f"{result['domain']}</span></div>",
                    unsafe_allow_html=True,
                )

            with r2:
                display_query = query if query else selected_tag
                h_title = highlight_text(result['title'], display_query)
                h_preview = highlight_text(result['preview'], display_query)
                h_subtitle = highlight_text(result['subtitle'], display_query) if result['subtitle'] else ""

                st.markdown(f"**{h_title}**", unsafe_allow_html=True)
                if h_subtitle:
                    tags_html = " ".join([
                        f"<span class='doc-tag'>#{highlight_text(t.strip(), display_query)}</span>"
                        for t in result['subtitle'].split(',') if t.strip()
                    ])
                    st.markdown(tags_html, unsafe_allow_html=True)
                st.markdown(
                    f"<span style='color:#999; font-size:0.85rem;'>{h_preview}</span>",
                    unsafe_allow_html=True,
                )
                st.caption(f"🕒 {result['timestamp']}")

            with r3:
                if st.button("Open →", key=f"gs_open_{result['domain']}_{result['id']}_{i}", use_container_width=True):
                    _navigate_to_result(result)
                if st.button("📋", key=f"gs_cp_{result['domain']}_{result['id']}_{i}", use_container_width=True):
                    copy_to_clipboard(f"{result['title']}\n{result['preview']}")
                    st.toast("복사됨")
