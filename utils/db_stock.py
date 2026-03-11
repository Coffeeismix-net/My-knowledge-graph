"""
db_stock.py — Stock Analysis CRUD
"""
import streamlit as st
import uuid
import logging
from utils.db_common import get_workbook, get_or_create_sheet, chunk_text, get_kst_now_str, is_date_format

logger = logging.getLogger(__name__)

# ==========================================
# INTERNAL HELPERS
# ==========================================
def _delete_chunks(wb, sheet_name, doc_id):
    """특정 문서의 청크 데이터 삭제"""
    try:
        ws = wb.worksheet(sheet_name)
        all_vals = ws.get_all_values()
        if len(all_vals) > 1:
            kept = [r for r in all_vals[1:] if str(r[0]) != str(doc_id)]
            ws.clear()
            ws.append_row(all_vals[0])
            if kept:
                ws.append_rows(kept)
    except Exception as e:
        logger.warning(f"_delete_chunks failed [{sheet_name}/{doc_id}]: {e}")

def _parse_keywords_and_date(kw_raw, created_at):
    """키워드 문자열에서 날짜를 분리하고 순수 키워드만 반환"""
    real_kws = []
    if kw_raw:
        candidates = [k.strip() for k in kw_raw.split(',') if k.strip()]
        for cand in candidates:
            if not is_date_format(cand):
                real_kws.append(cand)
            elif not created_at or not is_date_format(created_at):
                created_at = cand
    return real_kws, created_at

# ==========================================
# CRUD
# ==========================================
def load_stocks():
    """전체 Stock 문서 로드"""
    wb = get_workbook()
    if not wb:
        return []
    try:
        ws_meta = get_or_create_sheet(wb, "stocks", ["id", "company", "title", "keywords", "created_at"])
        
        # content 컬럼이 남아있으면 제거 (마이그레이션 호환)
        headers = ws_meta.row_values(1)
        if "content" in headers:
            ws_meta.delete_columns(headers.index("content") + 1)

        raw_data = ws_meta.get_all_values()
        if not raw_data:
            return []
        data_rows = raw_data[1:]

        ws_chunks = get_or_create_sheet(wb, "stock_chunks", ["id", "index", "content"])
        chunk_data = ws_chunks.get_all_records()

        content_map = {}
        for row in chunk_data:
            doc_id = str(row['id'])
            content_map.setdefault(doc_id, []).append((int(row['index']), str(row['content'])))

        stocks = []
        for row in data_rows:
            doc_id = str(row[0]) if len(row) > 0 else ""
            company = row[1] if len(row) > 1 else ""
            title = row[2] if len(row) > 2 else ""
            kw_raw = str(row[3]) if len(row) > 3 else ""
            created_at = str(row[4]) if len(row) > 4 else ""

            real_kws, created_at = _parse_keywords_and_date(kw_raw, created_at)
            full_content = "".join([x[1] for x in sorted(content_map.get(doc_id, []), key=lambda x: x[0])])
            stocks.append({
                "id": doc_id, "company": company, "title": title,
                "content": full_content, "keywords": real_kws, "created_at": created_at
            })
        return stocks
    except Exception as e:
        logger.error(f"load_stocks failed: {e}")
        return []

def add_stock(company, title, content, keywords):
    """Stock 문서 추가"""
    wb = get_workbook()
    if not wb:
        return None
    try:
        new_id = str(uuid.uuid4())[:8]
        kw_str = ",".join(keywords)
        now_str = get_kst_now_str()

        ws_meta = get_or_create_sheet(wb, "stocks", ["id", "company", "title", "keywords", "created_at"])
        # content 컬럼 잔존 시 제거
        headers = ws_meta.row_values(1)
        if "content" in headers:
            ws_meta.delete_columns(headers.index("content") + 1)
        ws_meta.append_row([new_id, company, title, kw_str, now_str])

        ws_chunks = get_or_create_sheet(wb, "stock_chunks", ["id", "index", "content"])
        chunks = chunk_text(content)
        ws_chunks.append_rows([[new_id, i, c] for i, c in enumerate(chunks)])

        return {
            "id": new_id, "company": company, "title": title,
            "content": content, "keywords": keywords, "created_at": now_str
        }
    except Exception as e:
        logger.error(f"add_stock failed: {e}")
        return None

def update_stock(doc_id, company, title, content, keywords):
    """Stock 문서 수정"""
    wb = get_workbook()
    if not wb:
        return
    try:
        ws_meta = wb.worksheet("stocks")
        cell = ws_meta.find(str(doc_id))
        if cell:
            r = cell.row
            ws_meta.update_cell(r, 2, company)
            ws_meta.update_cell(r, 3, title)
            ws_meta.update_cell(r, 4, ",".join(keywords))
            ws_meta.update_cell(r, 5, get_kst_now_str())

        # 청크 교체
        ws_chunks = wb.worksheet("stock_chunks")
        all_chunks = ws_chunks.get_all_values()
        if len(all_chunks) > 1:
            header = all_chunks[0]
            new_data = [row for row in all_chunks[1:] if str(row[0]) != str(doc_id)]
            for i, c in enumerate(chunk_text(content)):
                new_data.append([str(doc_id), i, c])
            ws_chunks.clear()
            ws_chunks.append_row(header)
            if new_data:
                ws_chunks.append_rows(new_data)
    except Exception as e:
        logger.error(f"update_stock failed [{doc_id}]: {e}")

def move_stock_to_trash(doc_data):
    """Stock 문서를 휴지통으로 이동"""
    wb = get_workbook()
    if not wb:
        return
    try:
        ws_trash_meta = get_or_create_sheet(wb, "stock_trash",
            ["id", "company", "title", "keywords", "created_at", "deleted_at"])
        ws_trash_chunks = get_or_create_sheet(wb, "stock_trash_chunks", ["id", "index", "content"])

        del_time = get_kst_now_str()
        kw_str = ",".join(doc_data['keywords'])
        ws_trash_meta.append_row([
            doc_data['id'], doc_data['company'], doc_data['title'],
            kw_str, doc_data['created_at'], del_time
        ])

        # 컨텐츠 청크를 휴지통 시트로 복사
        chunks = chunk_text(doc_data['content'])
        ws_trash_chunks.append_rows([[doc_data['id'], i, chunk] for i, chunk in enumerate(chunks)])

        # 원본 삭제
        ws_meta = wb.worksheet("stocks")
        cell = ws_meta.find(str(doc_data['id']))
        if cell:
            ws_meta.delete_rows(cell.row)
        _delete_chunks(wb, "stock_chunks", doc_data['id'])
    except Exception as e:
        logger.error(f"move_stock_to_trash failed [{doc_data.get('id')}]: {e}")

def load_stock_trash():
    """Stock 휴지통 목록"""
    wb = get_workbook()
    if not wb:
        return []
    try:
        ws_meta = get_or_create_sheet(wb, "stock_trash",
            ["id", "company", "title", "keywords", "created_at", "deleted_at"])
        ws_chunks = get_or_create_sheet(wb, "stock_trash_chunks", ["id", "index", "content"])
        meta_data = ws_meta.get_all_records()
        chunk_data = ws_chunks.get_all_records()

        content_map = {}
        for row in chunk_data:
            doc_id = str(row['id'])
            content_map.setdefault(doc_id, []).append(str(row['content']))

        trash_list = []
        for row in meta_data:
            doc_id = str(row['id'])
            k_str = str(row.get('keywords', ''))
            kws = [k.strip() for k in k_str.split(',') if k.strip()] if k_str else []
            trash_list.append({
                "id": doc_id, "company": row['company'], "title": row['title'],
                "content": "".join(content_map.get(doc_id, [])),
                "keywords": kws, "created_at": str(row['created_at']),
                "deleted_at": str(row['deleted_at'])
            })
        return trash_list
    except Exception as e:
        logger.error(f"load_stock_trash failed: {e}")
        return []

def restore_stock(stock_row):
    """Stock 휴지통에서 복구"""
    wb = get_workbook()
    if not wb:
        return
    try:
        add_stock(stock_row['company'], stock_row['title'], stock_row['content'], stock_row['keywords'])
        permanent_delete_stock(stock_row['id'])
    except Exception as e:
        logger.error(f"restore_stock failed [{stock_row.get('id')}]: {e}")

def permanent_delete_stock(doc_id):
    """Stock 휴지통에서 영구 삭제"""
    wb = get_workbook()
    if not wb:
        return
    try:
        ws_trash = wb.worksheet("stock_trash")
        cell = ws_trash.find(str(doc_id))
        if cell:
            ws_trash.delete_rows(cell.row)
        _delete_chunks(wb, "stock_trash_chunks", doc_id)
    except Exception as e:
        logger.error(f"permanent_delete_stock failed [{doc_id}]: {e}")
