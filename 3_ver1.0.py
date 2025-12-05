import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
import random

st.set_page_config(layout="wide", page_title="Physics Test", page_icon="🧪")

# ==========================================
# 1. 테스트용 데이터 생성 (랜덤 노드 15개)
# ==========================================
nodes = []
edges = []

# 중앙 노드
nodes.append(Node(id="center", label="중심", size=30, color="#FF0055"))

# 주변 노드들
for i in range(1, 15):
    nodes.append(Node(id=f"node_{i}", label=f"노드_{i}", size=random.randint(15, 25), color="#00ADB5"))
    # 중심과 연결
    edges.append(Edge(source="center", target=f"node_{i}", color="#555"))
    # 가끔 서로 연결 (뭉침 현상 테스트용)
    if i > 1 and random.random() > 0.7:
        edges.append(Edge(source=f"node_{i}", target=f"node_{i-1}", color="#555"))

# ==========================================
# 2. 물리 엔진 튜닝 패널 (사이드바)
# ==========================================
st.sidebar.header("🧪 물리 엔진 실험실")
st.sidebar.info("값을 조절해서 원하는 '물방울 느낌'을 찾아보세요.")

# [1] 점성 (Damping): 물 vs 공기
damping = st.sidebar.slider("점성 (Damping)", 0.0, 1.0, 0.90, 0.01, help="1.0에 가까울수록 물속처럼 묵직해집니다.")

# [2] 척력 (Repulsion): 서로 밀어내는 힘
repulsion = st.sidebar.slider("척력 (Gravitational Constant)", -500, -10, -150, 10, help="절대값이 클수록 서로 멀리 밀어냅니다.")

# [3] 연결선 길이 (Spring Length)
spring_len = st.sidebar.slider("노드 간격 (Spring Length)", 50, 300, 150, 10)

# [4] 겹침 방지 (Avoid Overlap)
overlap = st.sidebar.checkbox("겹침 방지 (Avoid Overlap)", value=True)

# ==========================================
# 3. 그래프 설정 (Config)
# ==========================================
config = Config(
    width="100%",
    height=600,
    directed=False,
    nodeHighlightBehavior=True,
    highlightColor="#F7A7A6",
    collapsible=False,
    node={'labelProperty': 'label', 'renderLabel': True, 'font': {'color': 'white'}},
    
    # [핵심] 물리 엔진 설정
    physics={
        "enabled": True,
        "solver": "forceAtlas2Based", # 유기적인 움직임에 가장 적합한 솔버
        "forceAtlas2Based": {
            "theta": 0.5,
            "gravitationalConstant": repulsion, # [척력] 서로 밀어냄
            "centralGravity": 0.01,             # [중력] 화면 밖으로 안 나가게 살짝 잡음
            "springConstant": 0.08,             # [인력] 연결된 끈의 탄성
            "springLength": spring_len,         # [간격] 끈의 길이
            "damping": damping,                 # [점성] 물속 저항감 (가장 중요!)
            "avoidOverlap": 1 if overlap else 0 # [겹침 방지] 1이면 절대 안 겹침
        },
