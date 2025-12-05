import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
import random

st.set_page_config(layout="wide", page_title="Physics Test V2", page_icon="🧪")

# ==========================================
# 1. 사이드바 설정 (값 변경 시 그래프 강제 새로고침)
# ==========================================
st.sidebar.header("🧪 물리 엔진 실험실 V2")
st.sidebar.caption("이제 값이 즉시 적용됩니다.")

# [1] 점성 (Damping)
# 값이 클수록(1.0) 물엿처럼 끈적하고, 작을수록(0.1) 공기처럼 가볍습니다.
damping = st.sidebar.slider("점성 (Damping)", 0.0, 1.0, 0.90, 0.05)

# [2] 척력 (Repulsion)
# 절대값이 클수록(-1000) 서로 강하게 밀어냅니다. (겹침 방지 핵심)
repulsion = st.sidebar.slider("척력 (Repulsion)", -2000, -100, -1000, 100)

# [3] 연결선 길이 (Spring Length)
spring_len = st.sidebar.slider("노드 간격 (Length)", 50, 500, 200, 10)

# [4] 겹침 방지
overlap = st.sidebar.checkbox("겹침 방지 (Avoid Overlap)", value=True)

# ==========================================
# 2. 데이터 생성 (고정된 데이터)
# ==========================================
nodes = []
edges = []
nodes.append(Node(id="center", label="Center", size=40, color="#FF0055"))

# 뭉침 현상을 확인하기 위해 일부러 빽빽하게 생성
for i in range(1, 20):
    nodes.append(Node(id=f"node_{i}", label=f"Node_{i}", size=20, color="#00ADB5"))
    edges.append(Edge(source="center", target=f"node_{i}", color="#555"))
    # 노드끼리도 연결해서 복잡도 증가
    if i > 1:
        edges.append(Edge(source=f"node_{i}", target=f"node_{i-1}", color="#333"))

# ==========================================
# 3. 그래프 설정
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
        # 'forceAtlas2Based'는 유기적인 움직임에 좋지만 설정이 까다로울 수 있어,
        # 가장 강력한 'barnesHut' 솔버로 변경하여 테스트합니다.
        "solver": "barnesHut",
        "barnesHut": {
            "gravitationalConstant": repulsion, # 슬라이더 값 적용
            "centralGravity": 0.1,
            "springLength": spring_len,         # 슬라이더 값 적용
            "springConstant": 0.04,
            "damping": damping,                 # 슬라이더 값 적용
            "avoidOverlap": 1 if overlap else 0 # 슬라이더 값 적용
        },
        "stabilization": {
            "enabled": False, # [테스트용] 움직임을 보기 위해 끕니다.
        }
    },
    backgroundColor="#000000"
)

# ==========================================
# 4. 렌더링 (Key 부여로 강제 리프레시)
# ==========================================
st.markdown("### 🧪 Physics Simulation Test V2")
st.info("슬라이더를 움직이면 그래프가 새로고침되며 적용됩니다.")

# key에 설정값을 넣어서, 값이 바뀔 때마다 컴포넌트를 새로 만듭니다.
unique_key = f"graph_{damping}_{repulsion}_{spring_len}_{overlap}"
agraph(nodes=nodes, edges=edges, config=config, key=unique_key)
