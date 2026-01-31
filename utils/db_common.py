import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, timedelta
import re
import base64
from io import BytesIO
from PIL import Image
import streamlit.components.v1 as components

# ==========================================
# GOOGLE SHEETS CONNECTION
# ==========================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CHUNK_SIZE = 45000

@st.cache_resource
def get_db_client():
    try:
        if "gcp_service_account" not in st.secrets: return None
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
        return gspread.authorize(creds)
    except: return None

def get_workbook():
    client = get_db_client()
    try:
        # [주의] 사용 중인 스프레드시트 Key 확인
        return client.open_by_key("1ryBvLf_iUwoFR7Cx9zjZEldV6WHe26Jngxu0fs-BZMc") if client else None
    except: return None

def get_or_create_sheet(wb, title, cols):
    try: return wb.worksheet(title)
    except:
        ws = wb.add_worksheet(title=title, rows=100, cols=len(cols))
        ws.append_row(cols)
        return ws

# ==========================================
# COMMON UTILS
# ==========================================
def get_kst_now_str():
    return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")

def chunk_text(text):
    if not text: return [""]
    return [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

def copy_to_clipboard(text):
    escaped_text = json.dumps(text)
    js_code = f"""
    <script>
        function copyToClipboard(text) {{
            if (navigator.clipboard && window.isSecureContext) {{ navigator.clipboard.writeText(text); }} 
            else {{
                let textArea = document.createElement("textarea");
                textArea.value = text;
                textArea.style.position = "fixed";
                textArea.style.left = "-9999px";
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                try {{ document.execCommand('copy'); }} catch (err) {{}}
                document.body.removeChild(textArea);
            }}
        }}
        copyToClipboard({escaped_text});
    </script>
    """
    components.html(js_code, height=0)

def strip_html(html_content):
    if not html_content: return ""
    return re.sub(re.compile('<.*?>'), '', html_content)

def is_date_format(text):
    return bool(re.search(r'\d{2,4}[-.]\d{1,2}[-.]\d{1,2}', str(text)))

# ==========================================
# IMAGE TOOLS
# ==========================================
def compress_image(image_file):
    try:
        img = Image.open(image_file)
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        max_size = 1024
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        return buffer.getvalue()
    except: return image_file.getvalue()

def image_to_base64(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')

# ==========================================
# SETTINGS
# ==========================================
def save_setting_to_db(key, value):
    wb = get_workbook()
    if not wb: return
    try:
        try: ws = wb.worksheet("settings")
        except: 
            ws = wb.add_worksheet(title="settings", rows=20, cols=2)
            ws.append_row(["key", "value"])
        cell = ws.find(key)
        if cell: ws.update_cell(cell.row, 2, str(value))
        else: ws.append_row([key, str(value)])
    except: pass
