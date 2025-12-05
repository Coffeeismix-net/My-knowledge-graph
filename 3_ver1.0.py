import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
import random

st.set_page_config(layout="wide", page_title="Physics Test V3", page_icon="🧪")

# ==========================================
# 1. 테스트용 데이터 생성
# ==========================================
nodes = []
edges = []
nodes.append(Node(id="center", label="Center", size=40, color="#FF0055"))

# 뭉침 현상 확인을 위해 노드 20개 생성
for i in range(1, 20):
    nodes.append(Node(id=f"node_{i}", label=f"Node_{i}", size=20, color="#00ADB5"))
    edges.append(Edge(source="center", target=f"node_{i}", color="#555"))
    # 서로 얽히게 만듦
    if i > 1:
        edges.append(Edge(source=f"node_{i}", target=f"node_{i-1}", color="#333"))

# ==========================================
# 2. 물리 엔진 튜닝 패널 (사이드바)
# ==========================================
st.sidebar.header("🧪 물리 엔진 실험실 V3")

# [1] 점성 (Damping): 높을수록(0.9) 물속처럼 묵직함
damping = st.sidebar.slider("점성 (Damping)", 0.1, 1.0, 0.9, 0.1)

# [2] 척력 (Repulsion): 절대값이 클수록(-1000) 서로 강하게 밀어냄
repulsion = st.sidebar.slider("척력 (Gravity)", -2000, -50, -100, 50)

# [3] 연결선 길이
spring_len = st.sidebar.slider("간격 (Spring Length)", 50, 500, 200, 50)

# [4] 겹침 방지
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
    node={
        'labelProperty': 'label', 
        'renderLabel': True, 
        'font': {'color': 'white'}
    },
    physics={
        "enabled": True,
        # 유기적인 움직임에 최적화된 Solver 사용
        "solver": "forceAtlas2Based",
        "forceAtlas2Based": {
            "theta": 0.5,
            "gravitationalConstant": repulsion, # [척력] 슬라이더 값
            "centralGravity": 0.01,             # [중력] 중앙 유지
            "springConstant": 0.08,             # [탄성] 끈의 당김
            "springLength": spring_len,         # [간격] 슬라이더 값
            "damping": damping,                 # [점성] 슬라이더 값 (핵심!)
            "avoidOverlap": 1 if overlap else 0 # [겹침 방지]
        },
        "stabilization": {
            # [핵심] True로 설정해야 계산 후 딱 멈춥니다!
            "enabled": True,    
            "iterations": 1000, 
            "updateInterval": 50,
            "onlyDynamicEdges": False,
            "fit": True
        }
    },
    backgroundColor="#000000"
)

# ==========================================
# 4. 렌더링 (key 파라미터 삭제됨)
# ==========================================
st.markdown("### 🧪 Physics Simulation Test")
st.info("값이 바뀌면 그래프가 새로고침됩니다. (초기 계산 후 멈춤)")

# 에러가 났던 key 파라미터를 제거했습니다.
agraph(nodes=nodes, edges=edges, config=config)
