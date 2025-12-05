import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
import random

st.set_page_config(layout="wide", page_title="Physics Test V4", page_icon="🧪")

st.markdown("### 🧪 물리 엔진 실험실 V4")
st.info("이제 그래프가 멈추지 않고 계속 움직입니다. 슬라이더를 조절해 보세요.")

# ==========================================
# 1. 사이드바 설정 (범위 수정)
# ==========================================
st.sidebar.header("설정 조절")

# [1] 점성 (Damping): 물 vs 공기
# 0.9 이상이면 물속처럼 아주 묵직해집니다.
damping = st.sidebar.slider("1. 점성 (Damping/묵직함)", 0.1, 1.0, 0.9, 0.05)

# [2] 척력 (Repulsion): 서로 밀어내는 힘
# -500보다 더 낮추면(-1000) 서로 강하게 밀어내서 겹침이 사라집니다.
repulsion = st.sidebar.slider("2. 척력 (밀어내는 힘)", -2000, -100, -1000, 100)

# [3] 연결선 길이 (Length)
spring_len = st.sidebar.slider("3. 노드 간격 (길이)", 50, 400, 200, 10)

# [4] 겹침 방지
overlap = st.sidebar.checkbox("4. 겹침 방지 켜기", value=True)

# ==========================================
# 2. 데이터 생성
# ==========================================
nodes = []
edges = []
nodes.append(Node(id="center", label="Center", size=40, color="#FF0055"))

for i in range(1, 15):
    nodes.append(Node(id=f"node_{i}", label=f"Node_{i}", size=20, color="#00ADB5"))
    edges.append(Edge(source="center", target=f"node_{i}", color="#555"))
    # 얽히고 설킨 구조를 만들어 물리 엔진 테스트
    if i % 3 == 0:
        edges.append(Edge(source=f"node_{i}", target=f"node_{i-1}", color="#333"))

# ==========================================
# 3. 그래프 설정 (움직임 활성화)
# ==========================================
config = Config(
    width="100%",
    height=600,
    directed=False,
    nodeHighlightBehavior=True,
    highlightColor="#F7A7A6",
    collapsible=False,
    node={'labelProperty': 'label', 'renderLabel': True, 'font': {'color': 'white'}},
    physics={
        "enabled": True,
        "solver": "forceAtlas2Based",
        "forceAtlas2Based": {
            "theta": 0.5,
            "gravitationalConstant": repulsion, # 슬라이더 값
            "centralGravity": 0.01,
            "springConstant": 0.08,
            "springLength": spring_len,         # 슬라이더 값
            "damping": damping,                 # 슬라이더 값
            "avoidOverlap": 1 if overlap else 0 # 슬라이더 값
        },
        "stabilization": {
            "enabled": False, # [핵심] 테스트 중에는 끄기! (계속 움직여야 확인 가능)
            "iterations": 1000
        }
    },
    backgroundColor="#000000"
)

# ==========================================
# 4. 렌더링
# ==========================================
# key 파라미터 없이 호출 (에러 방지)
agraph(nodes=nodes, edges=edges, config=config)
