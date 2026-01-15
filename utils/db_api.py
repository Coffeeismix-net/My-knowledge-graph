import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import json
import hashlib
from datetime import datetime
import uuid

# ==========================================
# GOOGLE SHEETS & DRIVE
# ==========================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_db_client():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets에 'gcp_service_account' 정보가 없습니다.")
            return None
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"DB 연결 실패: {e}")
        return None

def get_workbook():
    client = get_db_client()
    # [주의] 스프레드시트 Key가 정확한지 확인하세요!
    try:
        return client.open_by_key("1ryBvLf_iUwoFR7Cx9zjZEldV6WHe26Jngxu0fs-BZMc") if client else None
    except Exception as e:
        st.error(f"스프레드시트를 찾을 수 없습니다: {e}")
        return None

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
    except Exception as e: print(f"Setting Save Error: {e}")

# ==========================================
# NODE CRUD
# ==========================================
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
    except Exception as e:
        st.error(f"노드 불러오기 실패: {e}")
        return []

def add_node(label, group, summary, keywords):
    wb = get_workbook()
    if not wb: return None
    try:
        new_id = str(uuid.uuid4())[:8]
        kw_str = ",".join(keywords)
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        wb.sheet1.append_row([new_id, label, group, summary, kw_str, now_ts])
        return {"id": new_id, "label": label, "group": group, "summary": summary, "keywords": keywords, "timestamp": now_ts}
    except Exception as e:
        st.error(f"노드 추가 실패: {e}")
        return None

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
    except Exception as e: st.error(f"노드 수정 실패: {e}")

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
    except Exception as e: st.error(f"삭제 실패: {e}")

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

# ==========================================
# [STOCK CRUD] (에러 출력 추가)
# ==========================================
def load_stocks():
    wb = get_workbook()
    if not wb: return []
    try:
        try: ws = wb.worksheet("stocks")
        except:
            ws = wb.add_worksheet(title="stocks", rows=100, cols=6)
            ws.append_row(["id", "company", "title", "content", "keywords", "created_at"])
            return []
        
        data = ws.get_all_records()
        stocks = []
        for row in data:
            k_str = str(row.get('keywords', ''))
            kws = [k.strip() for k in k_str.split(',')] if k_str else []
            stocks.append({
                "id": str(row['id']),
                "company": row['company'],
                "title": row['title'],
                "content": row['content'],
                "keywords": kws,
                "created_at": str(row['created_at'])
            })
        return stocks
    except Exception as e:
        st.error(f"Stock 목록 로드 실패: {e}")
        return []

def add_stock(company, title, content, keywords):
    wb = get_workbook()
    if not wb: return None
    try:
        new_id = str(uuid.uuid4())[:8]
        kw_str = ",".join(keywords)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        ws = wb.worksheet("stocks")
        ws.append_row([new_id, company, title, content, kw_str, now_str])
        
        return {
            "id": new_id, "company": company, "title": title, 
            "content": content, "keywords": keywords, "created_at": now_str
        }
    except Exception as e:
        st.error(f"Stock 추가 실패: {e}")
        return None

def update_stock(doc_id, company, title, content, keywords):
    wb = get_workbook()
    if not wb: return
    try:
        ws = wb.worksheet("stocks")
        cell = ws.find(str(doc_id))
        if cell:
            r = cell.row
            ws.update_cell(r, 2, company)
            ws.update_cell(r, 3, title)
            ws.update_cell(r, 4, content)
            ws.update_cell(r, 5, ",".join(keywords))
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            ws.update_cell(r, 6, now_str)
    except Exception as e: st.error(f"Stock 수정 실패: {e}")

def move_stock_to_trash(doc_data):
    wb = get_workbook()
    if not wb: return
    try:
        try: trash_sheet = wb.worksheet("stock_trash")
        except: 
            trash_sheet = wb.add_worksheet(title="stock_trash", rows=100, cols=7)
            trash_sheet.append_row(["id", "company", "title", "content", "keywords", "created_at", "deleted_at"])
        
        del_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        k_str = ",".join(doc_data['keywords'])
        
        trash_sheet.append_row([
            doc_data['id'], doc_data['company'], doc_data['title'], 
            doc_data['content'], k_str, doc_data['created_at'], del_time
        ])
        
        ws = wb.worksheet("stocks")
        cell = ws.find(str(doc_data['id']))
        if cell: ws.delete_rows(cell.row)
    except Exception as e: st.error(f"Stock 삭제 실패: {e}")

# ==========================================
# AI Helper
# ==========================================
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

# ==========================================
# COLORS
# ==========================================
FIXED_COLORS = { "Antenna": "#FF0055", "Stock": "#00FFC2", "Tech": "#00ADB5", "Space": "#9D00FF", "Chip": "#FFE600", "Economy": "#FF8800", "General": "#888" }
COLOR_PALETTE = ["#FF0055", "#00FFC2", "#00ADB5", "#9D00FF", "#FFE600", "#FF8800", "#FF3333", "#33FF33", "#3333FF", "#FF33FF", "#33FFFF", "#FFFF33"]

def get_group_color(group_name):
    if group_name in FIXED_COLORS: return FIXED_COLORS[group_name]
    hash_val = int(hashlib.sha256(group_name.encode('utf-8')).hexdigest(), 16)
    return COLOR_PALETTE[hash_val % len(COLOR_PALETTE)]
