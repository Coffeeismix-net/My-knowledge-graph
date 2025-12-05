import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
import random

st.set_page_config(layout="wide", page_title="Physics Tuning", page_icon="🧪")

# 1. 화면 구성
st.title("🧪 물리 엔진 튜닝 실험실")
st.info("좌측 사이드바의 값을 조절하면 그래프가 실시간으로 반응합니다.")

# 2. 사이드바 설정 (여기가 핵심 컨트롤러)
st.sidebar.header("⚙️ 물리 엔진 설정")

# [A] Solver 선택 (움직임의 방식 결정)
# forceAtlas2Based: 유기적이고 부드러움 (물방울 느낌 추천)
# barnesHut: 기본값, 빠르고 안정적
solver_type = st.sidebar.selectbox("알고리즘 (Solver)", ["forceAtlas2Based", "barnesHut"], index=0)

# [B] 물리 변수 조절
st.sidebar.subheader("🌊 물방울 느낌 조절")

# 1. 점성 (Damping): 높을수록 꿀물처럼 끈적하게 움직임
damping = st.sidebar.slider("점성 (Damping)", 0.0, 1.0, 0.90, 0.01, help="1.0에 가까울수록 저항이 커져 묵직하게 움직입니다.")

# 2. 척력 (Gravity Constant): 서로 밀어내는 힘
# forceAtlas2Based는 값이 크고, barnesHut은 값이 매우 큽니다.
if solver_type == "forceAtlas2Based":
    gravity = st.sidebar.slider("척력 (Repulsion)", -200, -10, -50, 10)
else:
    gravity = st.sidebar.slider("척력 (Repulsion)", -50000, -1000, -2000, 500)

# 3. 스프링 길이 (Spring Length): 노드 간격
spring_len = st.sidebar.slider("노드 간격 (Spring Length)", 50, 300, 100, 10)

# 4. 겹침 방지 (Avoid Overlap)
overlap = st.sidebar.checkbox("겹침 방지 (Avoid Overlap)", value=True)


# 3. 데이터 생성 (테스트용 랜덤 데이터)
nodes = []
edges = []
nodes.append(Node(id="center", label="Center", size=30, color="#FF0055"))

# 노드 15개 생성
for i in range(1, 16):
    nodes.append(Node(id=f"node_{i}", label=f"N_{i}", size=random.randint(15, 20), color="#00ADB5"))
    edges.append(Edge(source="center", target=f"node_{i}", color="#555"))
    # 서로 얽히게 연결 추가
    if i % 3 == 0:
        edges.append(Edge(source=f"node_{i}", target=f"node_{i-1}", color="#333"))


# 4. 그래프 설정 (Config)
# 핵심: stabilization을 False로 설정해야 실시간 움직임이 보임!
physics_options = {
    "enabled": True,
    "solver": solver_type,
    "stabilization": {
        "enabled": False,  # <--- [매우 중요] 이걸 꺼야 계속 움직입니다!
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

config = Config(
    width="100%",
    height=600,
    directed=False,
    nodeHighlightBehavior=True,
    highlightColor="#F7A7A6",
    collapsible=False,
    node={'labelProperty': 'label', 'renderLabel': True, 'font': {'color': 'white'}},
    physics=physics_options, # 위에서 만든 설정 적용
    backgroundColor="#000000"
)

# 5. 그리기
agraph(nodes=nodes, edges=edges, config=config)
