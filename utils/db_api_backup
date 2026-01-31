import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import json
import hashlib
from datetime import datetime, timedelta
import uuid
import re
import pandas as pd
import streamlit.components.v1 as components
import base64
from io import BytesIO
from PIL import Image

# ==========================================
# GOOGLE SHEETS & DRIVE
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
        return client.open_by_key("1ryBvLf_iUwoFR7Cx9zjZEldV6WHe26Jngxu0fs-BZMc") if client else None
    except: return None

# ==========================================
# UTILS
# ==========================================
def get_kst_now_str():
    return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")

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

def chunk_text(text):
    if not text: return [""]
    return [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

def get_or_create_sheet(wb, title, cols):
    try: return wb.worksheet(title)
    except:
        ws = wb.add_worksheet(title=title, rows=100, cols=len(cols))
        ws.append_row(cols)
        return ws

def strip_html(html_content):
    if not html_content: return ""
    return re.sub(re.compile('<.*?>'), '', html_content)

def is_date_format(text):
    return bool(re.search(r'\d{2,4}[-.]\d{1,2}[-.]\d{1,2}', str(text)))

# ==========================================
# [REPAIRED] AI ANALYSIS (프롬프트 복구)
# ==========================================
def analyze_valuechain_image(image_bytes):
    if "gemini" not in st.secrets: return {"success": False, "error": "API Key Missing"}
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    
    try:
        image_part = {"mime_type": "image/jpeg", "data": image_bytes}
        
        # [복구된 강력한 프롬프트]
        prompt = """
        당신은 산업 분석 전문가입니다. 제공된 밸류체인 이미지를 분석하여 '폴더형 계층 구조 JSON'으로 변환해주세요.
        
        [요청사항]
        1. 이미지에 있는 업체명을 검색하거나 추론하여 정확한 한국 주식 종목코드(6자리)를 'code' 필드에 입력하세요.
        2. 이미지에 있는 모든 기업을 포함해야 하며, 가상의 데이터를 넣지 마세요.
        
        [JSON 구조 및 규칙]
        1. Root는 "title"과 "structure" 리스트를 가집니다.
        2. "structure" 내부 요소는 "type": "folder" 또는 "file"입니다.
        3. "folder": "name"(카테고리명), "children"(하위 리스트), "id"(유니크값)를 가집니다.
        4. "file": "name"(기업명), "desc"(설명/역할), "code"(종목코드 6자리 숫자), "type": "file"을 가집니다.
        5. "id" 규칙: 숫자로 시작하면 안 됩니다. 기업 ID는 'S' + 종목코드 형식을 권장합니다. (예: "id": "S005930")
        
        [출력 예시]
        {
          "title": "2차전지 밸류체인",
          "structure": [
            {
              "name": "양극재",
              "type": "folder",
              "id": "cat_cathode",
              "children": [
                { "name": "에코프로비엠", "type": "file", "desc": "하이니켈 양극재", "code": "247540", "id": "S247540" }
              ]
            }
          ]
        }
        
        오직 JSON 코드만 출력하세요. Markdown 표시는 하지 마세요.
        """
        
        model = genai.GenerativeModel('gemini-flash-latest') 
        response = model.generate_content([prompt, image_part])
        
        text = response.text.replace('```json','').replace('```','').strip()
        return {"success": True, "json": text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def ai_process(text):
    if "gemini" not in st.secrets: return {"success": False, "error": "Secrets Error"}
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        res = model.generate_content(f"Analyze:\n{text}\n\nOutput JSON: {{'summary': 'Korean summary (max 3 sentences)', 'keywords': '3-5 keywords'}}")
        data = json.loads(res.text.replace('```json','').replace('```','').strip())
        return {"success": True, "summary": data.get('summary',''), "keywords": data.get('keywords',''), "error": None}
    except Exception as e: return {"success": False, "error": str(e)}

# ==========================================
# NODE CRUD
# ==========================================
def load_nodes():
    wb = get_workbook()
    if not wb: return []
    try:
        ws = wb.sheet1
        data = ws.get_all_records()
        
        ws_chunks = get_or_create_sheet(wb, "node_chunks", ["id", "index", "content"])
        chunk_data = ws_chunks.get_all_records()
        
        content_map = {}
        for row in chunk_data:
            doc_id = str(row['id'])
            if doc_id not in content_map: content_map[doc_id] = []
            content_map[doc_id].append((int(row['index']), str(row['content'])))
            
        nodes = []
        for row in data:
            doc_id = str(row['id'])
            sorted_chunks = sorted(content_map.get(doc_id, []), key=lambda x: x[0])
            full_content = "".join([x[1] for x in sorted_chunks])
            k_str = str(row.get('keywords', ''))
            kws = [k.strip() for k in k_str.split(',')] if k_str else []
            ts = row.get('timestamp') or "25-01-01 00:00"
            nodes.append({"id": doc_id, "label": row['label'], "group": row['group_name'], "summary": row['summary'], "content": full_content, "keywords": kws, "timestamp": ts})
        return nodes
    except: return []

def add_node(label, group, summary, keywords, content=""):
    wb = get_workbook()
    if not wb: return None
    try:
        new_id = str(uuid.uuid4())[:8]
        kw_str = ",".join(keywords)
        now_ts = get_kst_now_str()
        wb.sheet1.append_row([new_id, label, group, summary, kw_str, now_ts])
        if content:
            ws_chunks = get_or_create_sheet(wb, "node_chunks", ["id", "index", "content"])
            chunks = chunk_text(content)
            ws_chunks.append_rows([[new_id, i, c] for i, c in enumerate(chunks)])
        return {"id": new_id, "label": label, "group": group, "summary": summary, "content": content, "keywords": keywords, "timestamp": now_ts}
    except: return None

def update_node(node_id, label, summary, keywords, content=""):
    wb = get_workbook()
    if not wb: return
    try:
        sheet = wb.sheet1
        cell = sheet.find(str(node_id))
        if cell:
            r = cell.row
            sheet.update_cell(r, 2, label)
            sheet.update_cell(r, 4, summary)
            sheet.update_cell(r, 5, ",".join(keywords))
        if content:
            ws_chunks = wb.worksheet("node_chunks")
            all_vals = ws_chunks.get_all_values()
            if len(all_vals) > 1:
                header = all_vals[0]
                new_data = [row for row in all_vals[1:] if str(row[0]) != str(node_id)]
                chunks = chunk_text(content)
                for i, c in enumerate(chunks): new_data.append([str(node_id), i, c])
                ws_chunks.clear()
                ws_chunks.append_row(header)
                if new_data: ws_chunks.append_rows(new_data)
    except: pass

def move_to_trash(node_id, node_data):
    wb = get_workbook()
    if not wb: return
    try:
        try: trash_sheet = wb.worksheet("trash")
        except: trash_sheet = wb.add_worksheet(title="trash", rows=100, cols=7); trash_sheet.append_row(["id","label","group","summary","keywords","created_at","deleted_at"])
        del_time = get_kst_now_str()
        k_str = ",".join(node_data['keywords'])
        trash_sheet.append_row([node_data['id'], node_data['label'], node_data['group'], node_data['summary'], k_str, node_data['timestamp'], del_time])
        main_sheet = wb.sheet1
        cell = main_sheet.find(str(node_id))
        if cell: main_sheet.delete_rows(cell.row)
        try:
            ws_chunks = wb.worksheet("node_chunks")
            all_vals = ws_chunks.get_all_values()
            if len(all_vals) > 1:
                kept = [r for r in all_vals[1:] if str(r[0]) != str(node_id)]
                ws_chunks.clear()
                ws_chunks.append_row(all_vals[0])
                if kept: ws_chunks.append_rows(kept)
        except: pass
    except: pass

def load_trash():
    wb = get_workbook()
    if not wb: return []
    try: return wb.worksheet("trash").get_all_records()
    except: return []

def restore_node(node_row):
    wb = get_workbook()
    if not wb: return
    try:
        wb.sheet1.append_row([node_row['id'], node_row['label'], node_row['group'], node_row['summary'], node_row['keywords'], node_row['created_at']])
        permanent_delete(node_row['id'])
    except: pass

def permanent_delete(node_id):
    wb = get_workbook()
    if not wb: return
    try: wb.worksheet("trash").delete_rows(wb.worksheet("trash").find(str(node_id)).row)
    except: pass

# ==========================================
# VALUE CHAIN CRUD
# ==========================================
def load_valuechains():
    wb = get_workbook()
    if not wb: return []
    try:
        ws_meta = get_or_create_sheet(wb, "valuechains", ["id", "title", "created_at"])
        meta_data = ws_meta.get_all_records()
        ws_json = get_or_create_sheet(wb, "valuechain_chunks", ["id", "index", "content"])
        ws_img = get_or_create_sheet(wb, "valuechain_images", ["id", "index", "content"])
        json_list = ws_json.get_all_records()
        img_list = ws_img.get_all_records()
        
        json_map = {}
        for r in json_list:
            if str(r['id']) not in json_map: json_map[str(r['id'])] = []
            json_map[str(r['id'])].append((int(r['index']), str(r['content'])))
        img_map = {}
        for r in img_list:
            if str(r['id']) not in img_map: img_map[str(r['id'])] = []
            img_map[str(r['id'])].append((int(r['index']), str(r['content'])))
            
        result = []
        for r in meta_data:
            did = str(r['id'])
            full_json = "".join([x[1] for x in sorted(json_map.get(did, []), key=lambda x:x[0])])
            full_img = "".join([x[1] for x in sorted(img_map.get(did, []), key=lambda x:x[0])])
            result.append({"id": did, "title": r['title'], "json_data": full_json, "image_data": full_img, "created_at": str(r['created_at'])})
        return result
    except: return []

def add_valuechain(title, json_str, image_base64=""):
    wb = get_workbook()
    if not wb: return None
    try:
        new_id = str(uuid.uuid4())[:8]; now_str = get_kst_now_str()
        ws_meta = get_or_create_sheet(wb, "valuechains", ["id", "title", "created_at"])
        ws_meta.append_row([new_id, title, now_str])
        ws_json = get_or_create_sheet(wb, "valuechain_chunks", ["id", "index", "content"])
        ws_json.append_rows([[new_id, i, c] for i, c in enumerate(chunk_text(json_str))])
        if image_base64:
            ws_img = get_or_create_sheet(wb, "valuechain_images", ["id", "index", "content"])
            ws_img.append_rows([[new_id, i, c] for i, c in enumerate(chunk_text(image_base64))])
        return {"id": new_id, "title": title, "json_data": json_str, "image_data": image_base64, "created_at": now_str}
    except: return None

def delete_valuechain(doc_id):
    wb = get_workbook()
    if not wb: return
    try:
        ws_meta = wb.worksheet("valuechains")
        cell = ws_meta.find(str(doc_id))
        if cell: ws_meta.delete_rows(cell.row)
        ws_json = wb.worksheet("valuechain_chunks")
        all_j = ws_json.get_all_values()
        if len(all_j) > 1:
            kept = [r for r in all_j[1:] if str(r[0]) != str(doc_id)]
            ws_json.clear(); ws_json.append_row(all_j[0])
            if kept: ws_json.append_rows(kept)
        try:
            ws_img = wb.worksheet("valuechain_images")
            all_i = ws_img.get_all_values()
            if len(all_i) > 1:
                kept = [r for r in all_i[1:] if str(r[0]) != str(doc_id)]
                ws_img.clear(); ws_img.append_row(all_i[0])
                if kept: ws_img.append_rows(kept)
        except: pass
    except: pass

# ==========================================
# STOCK CRUD
# ==========================================
def load_stocks():
    wb = get_workbook()
    if not wb: return []
    try:
        ws_meta = get_or_create_sheet(wb, "stocks", ["id", "company", "title", "keywords", "created_at"])
        headers = ws_meta.row_values(1)
        if "content" in headers: ws_meta.delete_columns(headers.index("content") + 1)
        raw_data = ws_meta.get_all_values()
        if not raw_data: return []
        data_rows = raw_data[1:]
        ws_chunks = get_or_create_sheet(wb, "stock_chunks", ["id", "index", "content"])
        chunk_data = ws_chunks.get_all_records()
        content_map = {}
        for row in chunk_data:
            doc_id = str(row['id'])
            if doc_id not in content_map: content_map[doc_id] = []
            content_map[doc_id].append((int(row['index']), str(row['content'])))
        stocks = []
        for row in data_rows:
            doc_id = str(row[0]) if len(row) > 0 else ""
            company = row[1] if len(row) > 1 else ""
            title = row[2] if len(row) > 2 else ""
            kw_raw = str(row[3]) if len(row) > 3 else ""
            created_at = str(row[4]) if len(row) > 4 else ""
            real_kws = []
            if kw_raw:
                candidates = [k.strip() for k in kw_raw.split(',') if k.strip()]
                for cand in candidates:
                    if not is_date_format(cand): real_kws.append(cand)
                    else:
                        if not created_at or not is_date_format(created_at): created_at = cand
            full_content = "".join([x[1] for x in sorted(content_map.get(doc_id, []), key=lambda x: x[0])])
            stocks.append({"id": doc_id, "company": company, "title": title, "content": full_content, "keywords": real_kws, "created_at": created_at})
        return stocks
    except: return []

def add_stock(company, title, content, keywords):
    wb = get_workbook()
    if not wb: return None
    try:
        new_id = str(uuid.uuid4())[:8]; kw_str = ",".join(keywords); now_str = get_kst_now_str()
        ws_meta = get_or_create_sheet(wb, "stocks", ["id", "company", "title", "keywords", "created_at"])
        if "content" in ws_meta.row_values(1): ws_meta.delete_columns(ws_meta.row_values(1).index("content") + 1)
        ws_meta.append_row([new_id, company, title, kw_str, now_str])
        ws_chunks = get_or_create_sheet(wb, "stock_chunks", ["id", "index", "content"])
        ws_chunks.append_rows([[new_id, i, c] for i, c in enumerate(chunk_text(content))])
        return {"id": new_id, "company": company, "title": title, "content": content, "keywords": keywords, "created_at": now_str}
    except: return None

def update_stock(doc_id, company, title, content, keywords):
    wb = get_workbook()
    if not wb: return
    try:
        ws_meta = wb.worksheet("stocks")
        cell = ws_meta.find(str(doc_id))
        if cell:
            r = cell.row
            ws_meta.update_cell(r, 2, company); ws_meta.update_cell(r, 3, title); ws_meta.update_cell(r, 4, ",".join(keywords)); ws_meta.update_cell(r, 5, get_kst_now_str())
        ws_chunks = wb.worksheet("stock_chunks")
        all_chunks = ws_chunks.get_all_values()
        if len(all_chunks) > 1:
            header = all_chunks[0]; new_data = [row for row in all_chunks[1:] if str(row[0]) != str(doc_id)]
            for i, c in enumerate(chunk_text(content)): new_data.append([str(doc_id), i, c])
            ws_chunks.clear(); ws_chunks.append_row(header)
            if new_data: ws_chunks.append_rows(new_data)
    except: pass

def move_stock_to_trash(doc_data):
    wb = get_workbook()
    if not wb: return
    try:
        ws_trash_meta = get_or_create_sheet(wb, "stock_trash", ["id", "company", "title", "keywords", "created_at", "deleted_at"])
        ws_trash_chunks = get_or_create_sheet(wb, "stock_trash_chunks", ["id", "index", "content"])
        del_time = get_kst_now_str()
        kw_str = ",".join(doc_data['keywords'])
        ws_trash_meta.append_row([doc_data['id'], doc_data['company'], doc_data['title'], kw_str, doc_data['created_at'], del_time])
        ws_trash_chunks.append_rows([[doc_data['id'], i, c] for i, c in enumerate(chunk_text(doc_data['content']))])
        ws_meta = wb.worksheet("stocks"); cell = ws_meta.find(str(doc_data['id'])); 
        if cell: ws_meta.delete_rows(cell.row)
        ws_chunks = wb.worksheet("stock_chunks"); all_vals = ws_chunks.get_all_values()
        if len(all_vals) > 1:
            kept = [r for r in all_vals[1:] if str(r[0]) != str(doc_data['id'])]
            ws_chunks.clear(); ws_chunks.append_row(all_vals[0])
            if kept: ws_chunks.append_rows(kept)
    except: pass

def load_stock_trash():
    wb = get_workbook()
    if not wb: return []
    try:
        ws_meta = get_or_create_sheet(wb, "stock_trash", []); ws_chunks = get_or_create_sheet(wb, "stock_trash_chunks", [])
        meta_data = ws_meta.get_all_records(); chunk_data = ws_chunks.get_all_records()
        content_map = {}
        for row in chunk_data:
            doc_id = str(row['id'])
            if doc_id not in content_map: content_map[doc_id] = []
            content_map[doc_id].append(str(row['content']))
        trash_list = []
        for row in meta_data:
            doc_id = str(row['id']); k_str = str(row.get('keywords', '')); kws = [k.strip() for k in k_str.split(',')] if k_str else []
            trash_list.append({"id": doc_id, "company": row['company'], "title": row['title'], "content": "".join(content_map.get(doc_id, [])), "keywords": kws, "created_at": str(row['created_at']), "deleted_at": str(row['deleted_at'])})
        return trash_list
    except: return []

def restore_stock(stock_row):
    wb = get_workbook()
    if not wb: return
    try: add_stock(stock_row['company'], stock_row['title'], stock_row['content'], stock_row['keywords']); permanent_delete_stock(stock_row['id'])
    except: pass

def permanent_delete_stock(doc_id):
    wb = get_workbook()
    if not wb: return
    try:
        ws_trash = wb.worksheet("stock_trash"); cell = ws_trash.find(str(doc_id))
        if cell: ws_trash.delete_rows(cell.row)
        ws_chunks = wb.worksheet("stock_trash_chunks"); all_vals = ws_chunks.get_all_values()
        if len(all_vals) > 1:
            kept = [r for r in all_vals[1:] if str(r[0]) != str(doc_id)]
            ws_chunks.clear(); ws_chunks.append_row(all_vals[0])
            if kept: ws_chunks.append_rows(kept)
    except: pass

def save_setting_to_db(key, value):
    wb = get_workbook(); 
    if not wb: return
    try:
        try: ws = wb.worksheet("settings")
        except: ws = wb.add_worksheet(title="settings", rows=20, cols=2); ws.append_row(["key", "value"])
        cell = ws.find(key)
        if cell: ws.update_cell(cell.row, 2, str(value))
        else: ws.append_row([key, str(value)])
    except: pass

def get_group_color(group_name):
    COLOR_PALETTE = ["#FF0055", "#00FFC2", "#00ADB5", "#9D00FF", "#FFE600", "#FF8800", "#FF3333", "#33FF33", "#3333FF", "#FF33FF", "#33FFFF", "#FFFF33", "#FF5733", "#33FF57", "#3357FF", "#A0522D", "#8A2BE2", "#5F9EA0", "#D2691E", "#FF7F50"]
    if not group_name: return "#888888"
    hash_val = int(hashlib.sha256(group_name.encode('utf-8')).hexdigest(), 16)
    return COLOR_PALETTE[hash_val % len(COLOR_PALETTE)]
