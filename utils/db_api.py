import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import json
import hashlib
from datetime import datetime
import uuid
import re
import pandas as pd
import streamlit.components.v1 as components

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
# CLIPBOARD HELPER
# ==========================================
def copy_to_clipboard(text):
    escaped_text = json.dumps(text)
    js_code = f"""
    <script>
        function copyToClipboard(text) {{
            if (navigator.clipboard && window.isSecureContext) {{
                navigator.clipboard.writeText(text);
            }} else {{
                let textArea = document.createElement("textarea");
                textArea.value = text;
                textArea.style.position = "fixed";
                textArea.style.left = "-9999px";
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                try {{ document.execCommand('copy'); }} catch (err) {{ console.error('Fallback error', err); }}
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

# ==========================================
# STOCK CRUD (자동 복구 로직 포함)
# ==========================================
def load_stocks():
    wb = get_workbook()
    if not wb: return []
    try:
        # 1. 메타데이터 시트 확인
        ws_meta = get_or_create_sheet(wb, "stocks", ["id", "company", "title", "keywords", "created_at"])
        
        # [AUTO-FIX] 레거시 컬럼('content') 감지 및 삭제 로직
        headers = ws_meta.row_values(1)
        if "content" in headers:
            # content 컬럼 인덱스 찾기 (1부터 시작)
            col_idx = headers.index("content") + 1
            ws_meta.delete_columns(col_idx)
            # st.toast("🔄 DB 스키마가 최신 버전으로 자동 업데이트되었습니다.")
            # 삭제 후 헤더 다시 로드 불필요 (다음 호출부터 정상화)
        
        meta_data = ws_meta.get_all_records()
        
        # 2. 청크 로드 및 조립
        ws_chunks = get_or_create_sheet(wb, "stock_chunks", ["id", "index", "content"])
        chunk_data = ws_chunks.get_all_records()
        
        content_map = {}
        sorted_chunks = sorted(chunk_data, key=lambda x: (str(x['id']), int(x['index'])))
        for row in sorted_chunks:
            doc_id = str(row['id'])
            if doc_id not in content_map: content_map[doc_id] = []
            content_map[doc_id].append(row['content'])
            
        stocks = []
        for row in meta_data:
            doc_id = str(row['id'])
            full_content = "".join(content_map.get(doc_id, []))
            
            k_str = str(row.get('keywords', ''))
            kws = [k.strip() for k in k_str.split(',')] if k_str else []
            
            stocks.append({
                "id": doc_id,
                "company": row['company'],
                "title": row['title'],
                "content": full_content,
                "keywords": kws,
                "created_at": str(row['created_at'])
            })
        return stocks
    except Exception as e:
        st.error(f"데이터 로드 중 오류: {e}")
        return []

def add_stock(company, title, content, keywords):
    wb = get_workbook()
    if not wb: return None
    try:
        new_id = str(uuid.uuid4())[:8]
        kw_str = ",".join(keywords)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        ws_meta = get_or_create_sheet(wb, "stocks", ["id", "company", "title", "keywords", "created_at"])
        # 혹시 모를 레거시 컬럼 체크 (안전장치)
        if "content" in ws_meta.row_values(1):
             col_idx = ws_meta.row_values(1).index("content") + 1
             ws_meta.delete_columns(col_idx)

        ws_meta.append_row([new_id, company, title, kw_str, now_str])
        
        ws_chunks = get_or_create_sheet(wb, "stock_chunks", ["id", "index", "content"])
        chunks = chunk_text(content)
        chunk_rows = [[new_id, i, chunk] for i, chunk in enumerate(chunks)]
        ws_chunks.append_rows(chunk_rows)
        
        return {"id": new_id, "company": company, "title": title, "content": content, "keywords": keywords, "created_at": now_str}
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return None

def update_stock(doc_id, company, title, content, keywords):
    wb = get_workbook()
    if not wb: return
    try:
        ws_meta = wb.worksheet("stocks")
        cell = ws_meta.find(str(doc_id))
        if cell:
            r = cell.row
            ws_meta.update_cell(r, 2, company)
            ws_meta.update_cell(r, 3, title)
            ws_meta.update_cell(r, 4, ",".join(keywords))
            ws_meta.update_cell(r, 5, datetime.now().strftime("%Y-%m-%d %H:%M"))
            
        ws_chunks = wb.worksheet("stock_chunks")
        all_chunks = ws_chunks.get_all_values()
        if len(all_chunks) > 1:
            header = all_chunks[0]
            data = all_chunks[1:]
            new_data = [row for row in data if str(row[0]) != str(doc_id)]
            chunks = chunk_text(content)
            for i, chunk in enumerate(chunks):
                new_data.append([str(doc_id), i, chunk])
            ws_chunks.clear()
            ws_chunks.append_row(header)
            if new_data: ws_chunks.append_rows(new_data)
    except Exception as e: st.error(f"수정 실패: {e}")

def move_stock_to_trash(doc_data):
    wb = get_workbook()
    if not wb: return
    try:
        ws_trash_meta = get_or_create_sheet(wb, "stock_trash", ["id", "company", "title", "keywords", "created_at", "deleted_at"])
        ws_trash_chunks = get_or_create_sheet(wb, "stock_trash_chunks", ["id", "index", "content"])
        
        del_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        kw_str = ",".join(doc_data['keywords'])
        
        ws_trash_meta.append_row([doc_data['id'], doc_data['company'], doc_data['title'], kw_str, doc_data['created_at'], del_time])
        
        chunks = chunk_text(doc_data['content'])
        chunk_rows = [[doc_data['id'], i, chunk] for i, chunk in enumerate(chunks)]
        ws_trash_chunks.append_rows(chunk_rows)
        
        ws_meta = wb.worksheet("stocks")
        cell = ws_meta.find(str(doc_data['id']))
        if cell: ws_meta.delete_rows(cell.row)
        
        ws_chunks = wb.worksheet("stock_chunks")
        all_vals = ws_chunks.get_all_values()
        if len(all_vals) > 1:
            header = all_vals[0]
            rows = all_vals[1:]
            kept_rows = [r for r in rows if str(r[0]) != str(doc_data['id'])]
            ws_chunks.clear()
            ws_chunks.append_row(header)
            if kept_rows: ws_chunks.append_rows(kept_rows)
    except Exception as e: st.error(f"삭제 실패: {e}")

def load_stock_trash():
    wb = get_workbook()
    if not wb: return []
    try:
        ws_meta = get_or_create_sheet(wb, "stock_trash", [])
        ws_chunks = get_or_create_sheet(wb, "stock_trash_chunks", [])
        
        meta_data = ws_meta.get_all_records()
        chunk_data = ws_chunks.get_all_records()
        
        content_map = {}
        sorted_chunks = sorted(chunk_data, key=lambda x: (str(x['id']), int(x['index'])))
        for row in sorted_chunks:
            doc_id = str(row['id'])
            if doc_id not in content_map: content_map[doc_id] = []
            content_map[doc_id].append(row['content'])
            
        trash_list = []
        for row in meta_data:
            doc_id = str(row['id'])
            k_str = str(row.get('keywords', ''))
            kws = [k.strip() for k in k_str.split(',')] if k_str else []
            trash_list.append({
                "id": doc_id,
                "company": row['company'],
                "title": row['title'],
                "content": "".join(content_map.get(doc_id, [])),
                "keywords": kws,
                "created_at": str(row['created_at']),
                "deleted_at": str(row['deleted_at'])
            })
        return trash_list
    except: return []

def restore_stock(stock_row):
    wb = get_workbook()
    if not wb: return
    try:
        add_stock(stock_row['company'], stock_row['title'], stock_row['content'], stock_row['keywords'])
        permanent_delete_stock(stock_row['id'])
    except: pass

def permanent_delete_stock(doc_id):
    wb = get_workbook()
    if not wb: return
    try:
        ws_trash = wb.worksheet("stock_trash")
        cell = ws_trash.find(str(doc_id))
        if cell: ws_trash.delete_rows(cell.row)
        
        ws_chunks = wb.worksheet("stock_trash_chunks")
        all_vals = ws_chunks.get_all_values()
        if len(all_vals) > 1:
            kept = [r for r in all_vals[1:] if str(r[0]) != str(doc_id)]
            ws_chunks.clear()
            ws_chunks.append_row(all_vals[0])
            if kept: ws_chunks.append_rows(kept)
    except: pass

# ==========================================
# SETTINGS & NODE & AI & UTILS
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

def load_nodes():
    wb = get_workbook()
    if not wb: return []
    try:
        data = wb.sheet1.get_all_records()
        nodes = []
        for row in data:
            k_str = str(row.get('keywords', ''))
            kws = [k.strip() for k in k_str.split(',')] if k_str else []
            ts = row.get('timestamp') or "25-01-01 00:00"
            nodes.append({
                "id": str(row['id']), "label": row['label'], "group": row['group_name'],
                "summary": row['summary'], "keywords": kws, "timestamp": ts
            })
        return nodes
    except: return []

def add_node(label, group, summary, keywords):
    wb = get_workbook()
    if not wb: return None
    try:
        new_id = str(uuid.uuid4())[:8]
        kw_str = ",".join(keywords)
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        wb.sheet1.append_row([new_id, label, group, summary, kw_str, now_ts])
        return {"id": new_id, "label": label, "group": group, "summary": summary, "keywords": keywords, "timestamp": now_ts}
    except: return None

def update_node(node_id, label, summary, keywords):
    wb = get_workbook()
    if not wb: return
    try:
        sheet = wb.sheet1
        cell = sheet.find(str(node_id))
        if cell:
            r = cell.row
            sheet.update_cell(r, 2, label)
            sheet.update_cell(r, 3, keywords[0] if keywords else "General")
            sheet.update_cell(r, 4, summary)
            sheet.update_cell(r, 5, ",".join(keywords))
    except: pass

def move_to_trash(node_id, node_data):
    wb = get_workbook()
    if not wb: return
    try:
        try: trash_sheet = wb.worksheet("trash")
        except: 
            trash_sheet = wb.add_worksheet(title="trash", rows=100, cols=7)
            trash_sheet.append_row(["id", "label", "group", "summary", "keywords", "created_at", "deleted_at"])
        del_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        k_str = ",".join(node_data['keywords'])
        trash_sheet.append_row([node_data['id'], node_data['label'], node_data['group'], node_data['summary'], k_str, node_data['timestamp'], del_time])
        main_sheet = wb.sheet1
        cell = main_sheet.find(str(node_id))
        if cell: main_sheet.delete_rows(cell.row)
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
    try:
        trash_sheet = wb.worksheet("trash")
        cell = trash_sheet.find(str(node_id))
        if cell: trash_sheet.delete_rows(cell.row)
    except: pass

def ai_process(text):
    if "gemini" not in st.secrets: return {"success": False, "error": "Secrets Error"}
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        prompt = f"Analyze:\n{text}\n\nOutput JSON: {{'summary': 'Korean summary (max 2 sentences)', 'keywords': '3-5 keywords (comma separated)'}}"
        res = model.generate_content(prompt)
        data = json.loads(res.text.replace('```json','').replace('```','').strip())
        return {"success": True, "summary": data.get('summary',''), "keywords": data.get('keywords',''), "error": None}
    except Exception as e: return {"success": False, "error": str(e)}

def strip_html(html_content):
    if not html_content: return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', html_content)

COLOR_PALETTE = ["#FF0055", "#00FFC2", "#00ADB5", "#9D00FF", "#FFE600", "#FF8800", "#FF3333", "#33FF33", "#3333FF", "#FF33FF", "#33FFFF", "#FFFF33", "#FF5733", "#33FF57", "#3357FF", "#A0522D", "#8A2BE2", "#5F9EA0", "#D2691E", "#FF7F50"]

def get_group_color(group_name):
    if not group_name: return "#888888"
    hash_val = int(hashlib.sha256(group_name.encode('utf-8')).hexdigest(), 16)
    return COLOR_PALETTE[hash_val % len(COLOR_PALETTE)]
