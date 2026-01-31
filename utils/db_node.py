import streamlit as st
import google.generativeai as genai
import json
import hashlib
import uuid
from utils.db_common import get_workbook, get_or_create_sheet, chunk_text, get_kst_now_str

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
# AI HELPER (TEXT)
# ==========================================
def ai_process(text):
    if "gemini" not in st.secrets: return {"success": False, "error": "Secrets Error"}
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        res = model.generate_content(f"Analyze:\n{text}\n\nOutput JSON: {{'summary': 'Korean summary (max 3 sentences)', 'keywords': '3-5 keywords'}}")
        data = json.loads(res.text.replace('```json','').replace('```','').strip())
        return {"success": True, "summary": data.get('summary',''), "keywords": data.get('keywords',''), "error": None}
    except Exception as e: return {"success": False, "error": str(e)}

def get_group_color(group_name):
    COLOR_PALETTE = ["#FF0055", "#00FFC2", "#00ADB5", "#9D00FF", "#FFE600", "#FF8800", "#FF3333", "#33FF33", "#3333FF", "#FF33FF", "#33FFFF", "#FFFF33", "#FF5733", "#33FF57", "#3357FF", "#A0522D", "#8A2BE2", "#5F9EA0", "#D2691E", "#FF7F50"]
    if not group_name: return "#888888"
    hash_val = int(hashlib.sha256(group_name.encode('utf-8')).hexdigest(), 16)
    return COLOR_PALETTE[hash_val % len(COLOR_PALETTE)]
