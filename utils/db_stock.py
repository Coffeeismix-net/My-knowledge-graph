import streamlit as st
from utils.db_common import get_workbook, get_or_create_sheet, chunk_text, get_kst_now_str, is_date_format
import uuid

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
        new_id = str(uuid.uuid4())[:8]
        kw_str = ",".join(keywords)
        now_str = get_kst_now_str()
        
        ws_meta = get_or_create_sheet(wb, "stocks", ["id", "company", "title", "keywords", "created_at"])
        if "content" in ws_meta.row_values(1): ws_meta.delete_columns(ws_meta.row_values(1).index("content") + 1)
        ws_meta.append_row([new_id, company, title, kw_str, now_str])
        
        ws_chunks = get_or_create_sheet(wb, "stock_chunks", ["id", "index", "content"])
        chunks = chunk_text(content)
        ws_chunks.append_rows([[new_id, i, c] for i, c in enumerate(chunks)])
        
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
            ws_meta.update_cell(r, 2, company)
            ws_meta.update_cell(r, 3, title)
            ws_meta.update_cell(r, 4, ",".join(keywords))
            ws_meta.update_cell(r, 5, get_kst_now_str())
            
        ws_chunks = wb.worksheet("stock_chunks")
        all_chunks = ws_chunks.get_all_values()
        if len(all_chunks) > 1:
            header = all_chunks[0]
            new_data = [row for row in all_chunks[1:] if str(row[0]) != str(doc_id)]
            chunks = chunk_text(content)
            for i, c in enumerate(chunks): new_data.append([str(doc_id), i, c])
            ws_chunks.clear()
            ws_chunks.append_row(header)
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
        chunks = chunk_text(doc_data['content'])
        ws_trash_chunks.append_rows([[doc_data['id'], i, chunk] for i, chunk in enumerate(chunks)])
        ws_meta = wb.worksheet("stocks")
        cell = ws_meta.find(str(doc_data['id']))
        if cell: ws_meta.delete_rows(cell.row)
        ws_chunks = wb.worksheet("stock_chunks")
        all_vals = ws_chunks.get_all_values()
        if len(all_vals) > 1:
            header = all_vals[0]
            kept = [r for r in all_vals[1:] if str(r[0]) != str(doc_data['id'])]
            ws_chunks.clear()
            ws_chunks.append_row(header)
            if kept: ws_chunks.append_rows(kept)
    except: pass

def load_stock_trash():
    wb = get_workbook()
    if not wb: return []
    try:
        ws_meta = get_or_create_sheet(wb, "stock_trash", [])
        ws_chunks = get_or_create_sheet(wb, "stock_trash_chunks", [])
        meta_data = ws_meta.get_all_records()
        chunk_data = ws_chunks.get_all_records()
        content_map = {}
        for row in chunk_data:
            doc_id = str(row['id'])
            if doc_id not in content_map: content_map[doc_id] = []
            content_map[doc_id].append(str(row['content']))
        trash_list = []
        for row in meta_data:
            doc_id = str(row['id'])
            k_str = str(row.get('keywords', ''))
            kws = [k.strip() for k in k_str.split(',')] if k_str else []
            trash_list.append({"id": doc_id, "company": row['company'], "title": row['title'], "content": "".join(content_map.get(doc_id, [])), "keywords": kws, "created_at": str(row['created_at']), "deleted_at": str(row['deleted_at'])})
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
