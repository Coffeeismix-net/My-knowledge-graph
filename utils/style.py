"""
style.py — 전체 앱 공통 CSS
모든 CSS를 여기서 관리하여 중복을 제거한다.
"""

# 메인 앱 전역 스타일 (app.py에서 한 번만 주입)
GLOBAL_CSS = """
<style>
    /* 기본 앱 */
    .stApp { background-color: #000000 !important; color: #ffffff !important; }
    header { visibility: hidden; }
    .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
    
    /* Iframe (그래프) */
    iframe { background-color: #000000 !important; border: 1px solid #444 !important; border-radius: 12px; }
    
    /* 입력 폼 */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { 
        background-color: #1a1a1a !important; color: white !important; border: 1px solid #333 !important; 
    }
    
    /* 멀티셀렉트 */
    .stMultiSelect div[data-baseweb="select"] > div { background-color: #111 !important; border-color: #333 !important; color: white !important; }
    .stMultiSelect div[data-baseweb="tag"] { background-color: #00ADB5 !important; color: black !important; }
    
    /* 고스트 버튼 */
    div.stButton > button { 
        background-color: transparent !important; border: 1px solid transparent !important; 
        color: #fff !important; width: 100%; height: auto; min-height: 38px;
        min-width: 0px !important; padding: 0px !important; margin: 0px !important;
        display: flex !important; justify-content: center !important; align-items: center !important; line-height: 1 !important;
    }
    div.stButton > button p { width: 100% !important; text-align: center !important; margin: 0 !important; color: #ffffff !important; }
    div.stButton > button:hover { background-color: #222 !important; border: 1px solid #444 !important; color: #00ADB5 !important; border-radius: 8px; }
    div.stButton > button:hover p { color: #00ADB5 !important; }
    
    /* Primary 버튼 */
    div.stButton > button[kind="primary"] { background-color: #E03131 !important; border: none !important; color: white !important; }
    div.stButton > button[kind="primary"]:hover { background-color: #c92a2a !important; }
    
    /* 리스트 헤더/행 */
    .list-header-row { display: flex; align-items: center; height: 35px; font-weight: bold; color: #888; font-size: 0.85rem; }
    .list-content-row { display: flex; align-items: center; height: 46px; }
    .col-center { justify-content: center; width: 100%; display: flex; }
    
    /* 타이트 헤더 */
    .tight-header { font-size: 1.5rem; font-weight: 600; margin-bottom: 0px !important; padding-bottom: 0px !important; }
    .tight-hr { margin-top: 5px !important; margin-bottom: 15px !important; border: 0; border-top: 1px solid #333; }
    
    /* Popover */
    div[data-testid="stPopover"] > button { background-color: transparent !important; border: 1px solid transparent !important; color: white !important; }
    
    /* Stock/Chain 공통 태그 */
    .doc-tag { background-color: #222; color: #aaa; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; margin-right: 4px; border: 1px solid #444; white-space: nowrap; display: inline-block; }
    .date-label { color: #666; font-size: 0.75rem; margin-left: 8px; white-space: nowrap; }
    
    /* Quill 에디터 */
    .stQuill { background-color: white; color: black; border-radius: 8px; padding: 5px; min-height: 400px; }
    
    /* Expander */
    .streamlit-expanderHeader { font-size: 1rem; font-weight: 600; color: #e0e0e0; background-color: #222; border-radius: 5px; }
    div[data-testid="stExpander"] { border: none; box-shadow: none; background-color: transparent; }
    div[data-testid="stExpanderDetails"] { border-left: 2px solid #444; margin-left: 10px; padding-left: 15px; }
    
    /* 좌정렬 버튼 (Stock/Chain 리스트용) */
    div[data-testid="column"] button[kind="secondary"] { justify-content: flex-start !important; text-align: left !important; padding-left: 0px !important; border: none !important; }
    div[data-testid="column"] button[kind="secondary"] p { text-align: left !important; }
    div[data-testid="stPopover"] > button { border: none !important; background: transparent !important; color: #888 !important; }
    div[data-testid="stPopover"] > button:hover { color: white !important; }
</style>
"""

# Quill 에디터 툴바 설정
QUILL_TOOLBAR = [
    ['bold', 'italic', 'underline', 'strike'],
    ['blockquote', 'code-block'],
    [{'header': 1}, {'header': 2}],
    [{'list': 'ordered'}, {'list': 'bullet'}],
    [{'indent': '-1'}, {'indent': '+1'}],
    ['link', 'image'],
    ['clean']
]
