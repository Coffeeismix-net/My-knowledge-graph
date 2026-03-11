"""
db_common.py — 공통 DB 연결, 유틸리티 함수 모음
모든 모듈이 공유하는 기능을 여기에 집중시킨다.
"""
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import re
import base64
import logging
from io import BytesIO
from datetime import datetime, timedelta
from PIL import Image
import streamlit.components.v1 as components

# ==========================================
# LOGGING
# ==========================================
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# ==========================================
# CONSTANTS
# ==========================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CHUNK_SIZE = 45000
SPREADSHEET_KEY = "1ryBvLf_iUwoFR7Cx9zjZEldV6WHe26Jngxu0fs-BZMc"

# ==========================================
# GOOGLE SHEETS CONNECTION
# ==========================================
@st.cache_resource
def get_db_client():
    """Google Sheets 클라이언트 생성 (캐싱)"""
    try:
        if "gcp_service_account" not in st.secrets:
            logger.error("gcp_service_account not found in secrets")
            return None
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        logger.error(f"DB client creation failed: {e}")
        return None

def get_workbook():
    """스프레드시트 워크북 반환"""
    client = get_db_client()
    if not client:
        return None
    try:
        return client.open_by_key(SPREADSHEET_KEY)
    except Exception as e:
        logger.error(f"Workbook open failed: {e}")
        return None

def get_or_create_sheet(wb, title, cols):
    """워크시트를 가져오거나 생성"""
    try:
        return wb.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = wb.add_worksheet(title=title, rows=100, cols=max(len(cols), 1))
        if cols:
            ws.append_row(cols)
        return ws
    except Exception as e:
        logger.error(f"Sheet '{title}' access failed: {e}")
        raise

# ==========================================
# TIME
# ==========================================
def get_kst_now_str():
    """KST 기준 현재 시각 문자열"""
    return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")

# ==========================================
# TEXT UTILS
# ==========================================
def chunk_text(text):
    """긴 텍스트를 Google Sheets 셀 크기 제한에 맞춰 분할"""
    if not text:
        return [""]
    return [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

def strip_html(html_content):
    """HTML 태그 제거"""
    if not html_content:
        return ""
    return re.sub(re.compile('<.*?>'), '', html_content)

def is_date_format(text):
    """날짜 형식 여부 판별"""
    return bool(re.search(r'\d{2,4}[-.]\d{1,2}[-.]\d{1,2}', str(text)))

def highlight_text(text, query):
    """검색어 하이라이팅 (HTML)"""
    if not query or not text:
        return text
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(
        lambda m: f"<span style='background-color:#ffd700;color:black;padding:0 2px;border-radius:2px;'>{m.group(0)}</span>",
        str(text)
    )

# ==========================================
# CLIPBOARD
# ==========================================
def copy_to_clipboard(text):
    """클립보드에 텍스트 복사 (JS injection)"""
    escaped_text = json.dumps(text)
    js_code = f"""
    <script>
        (function() {{
            var text = {escaped_text};
            if (navigator.clipboard && window.isSecureContext) {{
                navigator.clipboard.writeText(text);
            }} else {{
                var ta = document.createElement("textarea");
                ta.value = text;
                ta.style.position = "fixed";
                ta.style.left = "-9999px";
                document.body.appendChild(ta);
                ta.focus();
                ta.select();
                try {{ document.execCommand('copy'); }} catch(e) {{}}
                document.body.removeChild(ta);
            }}
        }})();
    </script>
    """
    components.html(js_code, height=0)

# ==========================================
# IMAGE TOOLS
# ==========================================
def compress_image(image_file, max_size=1024, quality=70):
    """이미지 압축 (JPEG 변환)"""
    try:
        img = Image.open(image_file)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        return buffer.getvalue()
    except Exception as e:
        logger.warning(f"Image compression failed, returning raw bytes: {e}")
        return image_file.getvalue()

def image_to_base64(image_bytes):
    """바이트 → Base64 인코딩"""
    return base64.b64encode(image_bytes).decode('utf-8')

# ==========================================
# SETTINGS
# ==========================================
def save_setting_to_db(key, value):
    """설정값 DB 저장"""
    wb = get_workbook()
    if not wb:
        return
    try:
        ws = get_or_create_sheet(wb, "settings", ["key", "value"])
        cell = ws.find(key)
        if cell:
            ws.update_cell(cell.row, 2, str(value))
        else:
            ws.append_row([key, str(value)])
    except Exception as e:
        logger.error(f"Setting save failed [{key}]: {e}")

def load_settings_from_db():
    """설정값 DB에서 로드 → session_state 반영"""
    if st.session_state.get('settings_loaded'):
        return
    wb = get_workbook()
    if not wb:
        return
    try:
        ws = get_or_create_sheet(wb, "settings", ["key", "value"])
        records = ws.get_all_records()
        settings_map = {str(r['key']): str(r['value']) for r in records}

        type_map = {
            'phy_active': lambda v: v.strip().lower() == 'true',
            'phy_damping': float,
            'phy_repulsion': int,
            'phy_len': int,
            'phy_overlap': lambda v: v.strip().lower() == 'true',
        }
        for key, converter in type_map.items():
            if key in settings_map:
                try:
                    st.session_state[key] = converter(settings_map[key])
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Setting parse failed [{key}]: {e}")

        st.session_state['settings_loaded'] = True
    except Exception as e:
        logger.error(f"Settings load failed: {e}")
