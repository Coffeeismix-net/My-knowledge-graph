import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
import random

st.set_page_config(layout="wide", page_title="Physics Final Test", page_icon="🧪")

st.title("🧪 물리 엔진 최종 테스트")
st.info("좌측 슬라이더를 움직이면 그래프가 즉시 반응합니다.")

# ==========================================
# 1. 사이드바 설정 (물리 엔진 튜닝)
# ==========================================
st.sidebar.header("⚙️ 물방울 효과 조절")

# Solver 선택 (물방울 느낌은 forceAtlas2Based 추천)
solver_type = st.sidebar.selectbox("알고리즘 (Solver)", ["forceAtlas2Based", "barnesHut"], index=0)

# [점성] 물속 저항 (0.9 추천)
damping = st.sidebar.slider("점성 (Damping)", 0.1, 1.0, 0.9, 0.05)

# [척력] 서로 밀어내는 힘 (-100 추천)
gravity = st.sidebar.slider("척력 (Repulsion)", -200, -10, -100, 10)

# [간격] 노드 사이 거리 (100 추천)
spring_len = st.sidebar.slider("간격 (Spring Length)", 50, 300, 100, 10)

# [겹침 방지]
overlap = st.sidebar.checkbox("겹침 방지 (Avoid Overlap)", value=True)


# ==========================================
# 2. 데이터 생성
# ==========================================
nodes = []
edges = []
nodes.append(Node(id="center", label="Center", size=40, color="#FF0055"))

for i in range(1, 15):
    nodes.append(Node(id=f"node_{i}", label=f"N_{i}", size=random.randint(15, 25), color="#00ADB5"))
    edges.append(Edge(source="center", target=f"node_{i}", color="#555"))
    if i % 3 == 0:
        edges.append(Edge(source=f"node_{i}", target=f"node_{i-1}", color="#333"))


# ==========================================
# 3. 그래프 설정 (강제 주입 방식)
# ==========================================
# 1단계: 기본 Config 생성 (여기서는 physics를 일단 비워둡니다)
config = Config(
    width="100%",
    height=600,
    directed=False,
    nodeHighlightBehavior=True,
    highlightColor="#F7A7A6",
    collapsible=False,
    node={'labelProperty': 'label', 'renderLabel': True, 'font': {'color': 'white'}},
    backgroundColor="#000000"
)

# 2단계: 물리 엔진 설정 딕셔너리 생성
physics_config = {
    "enabled": True,
    "solver": solver_type,
    "stabilization": {
        "enabled": False,  # [핵심] False여야 계속 움직임 (테스트용)
        "iterations": 1000
    },
    # 선택한 Solver에 따른 세부 설정
    solver_type: {
        "gravitationalConstant": gravity,
        "centralGravity": 0.01,
        "springLength": spring_len,
        "springConstant": 0.08,
        "damping": damping,
        "avoidOverlap": 1 if overlap else 0
    }
}

# 3단계: [핵심] 설정을 강제로 덮어씌움 (이래야 적용됨!)
config.physics = physics_config


# ==========================================
# 4. 렌더링
# ==========================================
# 디버깅용: 설정이 잘 들어갔는지 화면에 표시
with st.expander("🔧 적용된 물리 설정 확인 (Debug)"):
    st.json(config.physics)

agraph(nodes=nodes, edges=edges, config=config)
