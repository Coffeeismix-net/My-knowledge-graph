# utils/style.py

def get_common_style():
    """
    웹사이트 전체에 적용되는 공통 CSS 스타일을 반환합니다.
    """
    return """
    <style>
        /* [기본 앱 스타일] */
        .stApp { background-color: #000000 !important; color: #ffffff !important; }
        header { visibility: hidden; }
        .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
        
        /* [Iframe 스타일] */
        iframe { background-color: #000000 !important; border: 1px solid #444 !important; border-radius: 12px; }
        
        /* [입력 폼 스타일] */
        .stTextInput>div>div>input, .stTextArea>div>div>textarea { 
            background-color: #1a1a1a !important; color: white !important; border: 1px solid #333 !important; 
        }
        
        /* [멀티셀렉트 스타일] */
        .stMultiSelect div[data-baseweb="select"] > div { background-color: #111 !important; border-color: #333 !important; color: white !important; }
        .stMultiSelect div[data-baseweb="tag"] { background-color: #00ADB5 !important; color: black !important; }
        
        /* [고스트 버튼 스타일] */
        div.stButton > button { 
            background-color: transparent !important; 
            border: 1px solid transparent !important; 
            color: #fff !important; 
            width: 100%; 
            height: auto;
            min-height: 38px;
            min-width: 0px !important;
            padding: 0px !important;
            margin: 0px !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            line-height: 1 !important;
        }
        
        /* 버튼 내부 요소 정렬 */
        div.stButton > button p { width: 100% !important; text-align: center !important; margin: 0 !important; }
        div.stButton > button div { display: flex !important; justify-content: center !important; width: 100% !important; }

        /* Hover 효과 */
        div.stButton > button:hover { 
            background-color: #222 !important; 
            border: 1px solid #444 !important; 
            color: #00ADB5 !important; 
            border-radius: 8px;
        }
        
        /* Primary 버튼 스타일 */
        div.stButton > button[kind="primary"] { 
            background-color: #E03131 !important; 
            border: none !important; 
            color: white !important; 
        }
        div.stButton > button[kind="primary"]:hover { background-color: #c92a2a !important; }
        
        /* [헤더 스타일] */
        .tight-header { font-size: 1.5rem; font-weight: 600; margin-bottom: 0px !important; }
        .tight-hr { margin-top: 5px !important; margin-bottom: 15px !important; border: 0; border-top: 1px solid #333; }
    </style>
    """
