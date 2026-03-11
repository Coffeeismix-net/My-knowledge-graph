"""
dashboard_ui.py — 대시보드 홈 화면
로그인 직후 표시. 도메인별 통계, 최근 항목, 크로스-도메인 태그 클라우드.
"""
import streamlit as st
import pandas as pd
from collections import Counter


# ==========================================
# HELPERS
# ==========================================
def _collect_all_tags():
    """Node + Stock 키워드를 합산하여 {tag: {domain: count}} 형태로 반환"""
    tag_counter = Counter()
    tag_domain = {}  # tag -> set of domains

    # Node keywords
    for node in st.session_state.get('nodes_db', []):
        for kw in node.get('keywords', []):
            kw = kw.strip()
            if kw:
                tag_counter[kw] += 1
                tag_domain.setdefault(kw, set()).add("Node")

    # Stock keywords
    for doc in st.session_state.get('stock_db', []):
        for kw in doc.get('keywords', []):
            kw = kw.strip()
            if kw:
                tag_counter[kw] += 1
                tag_domain.setdefault(kw, set()).add("Stock")

    return tag_counter, tag_domain


def _get_recent_nodes(n=5):
    """최근 수정된 노드 n개"""
    nodes = st.session_state.get('nodes_db', [])
    if not nodes:
        return []
    df = pd.DataFrame(nodes)
    if df.empty:
        return []
    try:
        df['sort_dt'] = pd.to_datetime(df['timestamp'], format="%y-%m-%d %H:%M", errors='coerce')
        df['sort_dt'] = df['sort_dt'].fillna(pd.Timestamp.min)
        df = df.sort_values('sort_dt', ascending=False)
    except Exception:
        pass
    return df.head(n).to_dict('records')


def _get_recent_stocks(n=5):
    """최근 수정된 Stock 문서 n개"""
    stocks = st.session_state.get('stock_db', [])
    if not stocks:
        return []
    df = pd.DataFrame(stocks)
    if df.empty:
        return []
    try:
        df['sort_dt'] = pd.to_datetime(df['created_at'], errors='coerce')
        df['sort_dt'] = df['sort_dt'].fillna(pd.Timestamp.min)
        df = df.sort_values('sort_dt', ascending=False)
    except Exception:
        pass
    return df.head(n).to_dict('records')


def _get_recent_chains(n=5):
    """최근 밸류체인 n개"""
    chains = st.session_state.get('vc_list', [])
    if not chains:
        return []
    sorted_list = sorted(chains, key=lambda x: x.get('created_at', ''), reverse=True)
    return sorted_list[:n]


# ==========================================
# MAIN RENDER
# ==========================================
def render_dashboard():
    """대시보드 메인 렌더링"""

    # --- 1) 도메인별 통계 카드 ---
    node_count = len(st.session_state.get('nodes_db', []))
    stock_count = len(st.session_state.get('stock_db', []))
    chain_count = len(st.session_state.get('vc_list', []))

    tag_counter, tag_domain = _collect_all_tags()
    total_tags = len(tag_counter)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""<div class='dash-card'>
                <div class='dash-card-icon'>🧠</div>
                <div class='dash-card-num'>{node_count}</div>
                <div class='dash-card-label'>Knowledge Nodes</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""<div class='dash-card'>
                <div class='dash-card-icon'>📊</div>
                <div class='dash-card-num'>{stock_count}</div>
                <div class='dash-card-label'>Stock Documents</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""<div class='dash-card'>
                <div class='dash-card-icon'>🔗</div>
                <div class='dash-card-num'>{chain_count}</div>
                <div class='dash-card-label'>Value Chains</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"""<div class='dash-card'>
                <div class='dash-card-icon'>🏷️</div>
                <div class='dash-card-num'>{total_tags}</div>
                <div class='dash-card-label'>Unique Tags</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 2) 최근 항목 ---
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("#### 🕒 최근 Knowledge Nodes")
        recent_nodes = _get_recent_nodes(5)
        if recent_nodes:
            for node in recent_nodes:
                with st.container(border=True):
                    r1, r2 = st.columns([7, 3])
                    with r1:
                        st.markdown(f"**{node['label']}**")
                        kw_html = " ".join([f"`{k}`" for k in node.get('keywords', [])])
                        st.markdown(f"{kw_html}", unsafe_allow_html=True)
                    with r2:
                        st.caption(f"🕒 {node.get('timestamp', '')}")
                        if st.button("Open", key=f"dash_n_{node['id']}", use_container_width=True):
                            st.session_state['menu_mode'] = "List View"
                            st.rerun()
        else:
            st.caption("등록된 노드가 없습니다.")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 🔗 최근 Value Chains")
        recent_chains = _get_recent_chains(5)
        if recent_chains:
            for vc in recent_chains:
                with st.container(border=True):
                    r1, r2 = st.columns([7, 3])
                    with r1:
                        st.markdown(f"**{vc['title']}**")
                    with r2:
                        st.caption(f"🕒 {vc.get('created_at', '')[:16]}")
                        if st.button("Open", key=f"dash_vc_{vc['id']}", use_container_width=True):
                            st.session_state['menu_mode'] = "Value Chain"
                            st.session_state['vc_mode'] = 'list'
                            st.session_state['selected_vc_id'] = vc['id']
                            st.rerun()
        else:
            st.caption("등록된 밸류체인이 없습니다.")

    with col_right:
        st.markdown("#### 📊 최근 Stock Documents")
        recent_stocks = _get_recent_stocks(5)
        if recent_stocks:
            for doc in recent_stocks:
                with st.container(border=True):
                    r1, r2 = st.columns([7, 3])
                    with r1:
                        st.markdown(f"**[{doc['company']}] {doc['title']}**")
                        kw_html = " ".join([f"`{k}`" for k in doc.get('keywords', [])])
                        st.markdown(f"{kw_html}", unsafe_allow_html=True)
                    with r2:
                        st.caption(f"🕒 {str(doc.get('created_at', ''))[:16]}")
                        if st.button("Open", key=f"dash_s_{doc['id']}", use_container_width=True):
                            st.session_state['menu_mode'] = "Stock Analysis"
                            st.session_state['stock_view_mode'] = 'list'
                            st.session_state['selected_doc_ids'] = [doc['id']]
                            st.rerun()
        else:
            st.caption("등록된 문서가 없습니다.")

        # --- 3) 크로스 도메인 태그 클라우드 ---
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 🏷️ Tag Cloud (Top 30)")

        if tag_counter:
            top_tags = tag_counter.most_common(30)
            tag_html_parts = []
            for tag, count in top_tags:
                domains = tag_domain.get(tag, set())
                # 도메인별 색상: Node=cyan, Stock=yellow, 둘 다=green
                if domains == {"Node"}:
                    color = "#00ADB5"
                elif domains == {"Stock"}:
                    color = "#FFE600"
                else:
                    color = "#00FF88"

                # 크기: count에 비례
                size = min(0.7 + count * 0.08, 1.4)
                tag_html_parts.append(
                    f"<span class='tag-cloud-item' style='font-size:{size}rem; "
                    f"border-color:{color}; color:{color};'>"
                    f"{tag} <sup style='font-size:0.6em;'>{count}</sup></span>"
                )

            tag_cloud_html = " ".join(tag_html_parts)
            st.markdown(
                f"<div class='tag-cloud-wrap'>{tag_cloud_html}</div>",
                unsafe_allow_html=True,
            )
            st.caption("🟦 Node only  🟨 Stock only  🟩 Both")
        else:
            st.caption("태그가 없습니다.")
