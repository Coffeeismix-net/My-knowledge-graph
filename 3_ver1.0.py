import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config

st.set_page_config(layout="wide")
st.title("🧪 Physics Engine Diagnostic Test")

# 사이드바에서 모드 선택
mode = st.sidebar.radio(
    "물리 엔진 모드 선택",
    ("1. Default (기본값)", "2. Extreme Jelly (극단적 젤리 모드)")
)

# 테스트용 더미 데이터
nodes = [
    Node(id="1", label="Center", size=40, color="#ff0055"),
    Node(id="2", label="Sat 1", size=20, color="#00ffc2"),
    Node(id="3", label="Sat 2", size=20, color="#00adb5"),
    Node(id="4", label="Sat 3", size=20, color="#ffe600"),
]
edges = [
    Edge(source="1", target="2"),
    Edge(source="1", target="3"),
    Edge(source="1", target="4"),
    Edge(source="2", target="3"),
]

if mode == "1. Default (기본값)":
    # 비교군: 아무 설정 없는 기본 상태
    config = Config(
        width="100%",
        height=500,
        directed=False,
        nodeHighlightBehavior=True,
        highlightColor="#F7A7A6",
        collapsible=True,
        node={'labelProperty': 'label'},
        link={'labelProperty': 'label', 'renderLabel': True}
    )
    st.info("ℹ️ 기본 설정입니다. 노드가 뻣뻣하게 움직이거나 바로 멈추면 정상입니다.")

else:
    # 실험군: 물리 법칙을 극단적으로 적용
    config = Config(
        width="100%",
        height=500,
        directed=False,
        # [핵심 진단 포인트]
        physics={
            "enabled": True,
            # Solver를 바꿔봅니다. forceAtlas2Based가 안 먹힐 경우를 대비해 barnesHut 등 다른 것도 테스트 가능
            "solver": "forceAtlas2Based", 
            "forceAtlas2Based": {
                "gravitationalConstant": -50,
                "centralGravity": 0.005,
                "springLength": 100,
                "springConstant": 0.01, # 극도로 낮음 -> 흐물거려야 함
                "damping": 0.05         # 0에 가까움 -> 멈추지 않고 계속 미끄러져야 함
            },
            "stabilization": {
                "enabled": False,       # False면 로딩되자마자 막 움직여야 함
            },
            "minVelocity": 0.01         # 아주 작은 움직임도 허용
        }
    )
    st.warning("⚠️ 젤리 모드입니다. 노드가 미친듯이 흐물거리거나 계속 움직여야 정상입니다.")

# 그래프 렌더링
st.write(f"### Current Mode: {mode}")
return_value = agraph(nodes=nodes, edges=edges, config=config)
