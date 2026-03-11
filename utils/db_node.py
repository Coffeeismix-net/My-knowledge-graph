"""
db_node.py — Knowledge Node CRUD + AI 분석
"""
import streamlit as st
import google.generativeai as genai
import json
import hashlib
import uuid
import logging
from utils.db_common import get_workbook, get_or_create_sheet, chunk_text, get_kst_now_str

logger = logging.getLogger(__name__)

# ==========================================
# COLOR
# ==========================================
COLOR_PALETTE = [
    "#FF0055", "#00FFC2", "#00ADB5", "#9D00FF", "#FFE600", "#FF8800",
    "#FF3333", "#33FF33", "#3333FF", "#FF33FF", "#33FFFF", "#FFFF33",
    "#FF5733", "#33FF57", "#3357FF", "#A0522D", "#8A2BE2", "#5F9EA0",
    "#D2691E", "#FF7F50"
]

def get_group_color(group_name):
    """그룹명 기반 해시 컬러"""
    if not group_name:
        return "#888888"
    hash_val = int(hashlib.sha256(group_name.encode('utf-8')).hexdigest(), 16)
    return COLOR_PALETTE[hash_val % len(COLOR_PALETTE)]

# ==========================================
# CRUD
# ==========================================
def load_nodes():
    """메인 시트 + node_chunks에서 전체 노드 로드"""
    wb = get_workbook()
    if not wb:
        return []
    try:
        ws = wb.sheet1
        data = ws.get_all_records()

        ws_chunks = get_or_create_sheet(wb, "node_chunks", ["id", "index", "content"])
        chunk_data = ws_chunks.get_all_records()

        content_map = {}
        for row in chunk_data:
            doc_id = str(row['id'])
            content_map.setdefault(doc_id, []).append((int(row['index']), str(row['content'])))

        nodes = []
        for row in data:
            doc_id = str(row['id'])
            sorted_chunks = sorted(content_map.get(doc_id, []), key=lambda x: x[0])
            full_content = "".join([x[1] for x in sorted_chunks])
            k_str = str(row.get('keywords', ''))
            kws = [k.strip() for k in k_str.split(',') if k.strip()] if k_str else []
            ts = row.get('timestamp') or "25-01-01 00:00"
            nodes.append({
                "id": doc_id, "label": row['label'], "group": row['group_name'],
                "summary": row['summary'], "content": full_content,
                "keywords": kws, "timestamp": ts
            })
        return nodes
    except Exception as e:
        logger.error(f"load_nodes failed: {e}")
        return []

def add_node(label, group, summary, keywords, content=""):
    """노드 추가"""
    wb = get_workbook()
    if not wb:
        return None
    try:
        new_id = str(uuid.uuid4())[:8]
        kw_str = ",".join(keywords)
        now_ts = get_kst_now_str()
        wb.sheet1.append_row([new_id, label, group, summary, kw_str, now_ts])

        if content:
            ws_chunks = get_or_create_sheet(wb, "node_chunks", ["id", "index", "content"])
            chunks = chunk_text(content)
            ws_chunks.append_rows([[new_id, i, c] for i, c in enumerate(chunks)])

        return {
            "id": new_id, "label": label, "group": group,
            "summary": summary, "content": content,
            "keywords": keywords, "timestamp": now_ts
        }
    except Exception as e:
        logger.error(f"add_node failed: {e}")
        return None

def update_node(node_id, label, summary, keywords, content=""):
    """노드 수정"""
    wb = get_workbook()
    if not wb:
        return
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
                for i, c in enumerate(chunk_text(content)):
                    new_data.append([str(node_id), i, c])
                ws_chunks.clear()
                ws_chunks.append_row(header)
                if new_data:
                    ws_chunks.append_rows(new_data)
    except Exception as e:
        logger.error(f"update_node failed [{node_id}]: {e}")

def move_to_trash(node_id, node_data):
    """노드를 휴지통으로 이동"""
    wb = get_workbook()
    if not wb:
        return
    try:
        trash_sheet = get_or_create_sheet(wb, "trash",
            ["id", "label", "group", "summary", "keywords", "created_at", "deleted_at"])
        del_time = get_kst_now_str()
        k_str = ",".join(node_data['keywords'])
        trash_sheet.append_row([
            node_data['id'], node_data['label'], node_data['group'],
            node_data['summary'], k_str, node_data['timestamp'], del_time
        ])

        # 메인 시트에서 삭제
        main_sheet = wb.sheet1
        cell = main_sheet.find(str(node_id))
        if cell:
            main_sheet.delete_rows(cell.row)

        # 청크 데이터 삭제
        _delete_chunks(wb, "node_chunks", node_id)
    except Exception as e:
        logger.error(f"move_to_trash failed [{node_id}]: {e}")

def load_trash():
    """휴지통 노드 목록"""
    wb = get_workbook()
    if not wb:
        return []
    try:
        return wb.worksheet("trash").get_all_records()
    except Exception as e:
        logger.warning(f"load_trash failed: {e}")
        return []

def restore_node(node_row):
    """휴지통에서 노드 복구"""
    wb = get_workbook()
    if not wb:
        return
    try:
        wb.sheet1.append_row([
            node_row['id'], node_row['label'], node_row['group'],
            node_row['summary'], node_row['keywords'], node_row['created_at']
        ])
        permanent_delete(node_row['id'])
    except Exception as e:
        logger.error(f"restore_node failed [{node_row.get('id')}]: {e}")

def permanent_delete(node_id):
    """휴지통에서 영구 삭제"""
    wb = get_workbook()
    if not wb:
        return
    try:
        trash_sheet = wb.worksheet("trash")
        cell = trash_sheet.find(str(node_id))
        if cell:
            trash_sheet.delete_rows(cell.row)
    except Exception as e:
        logger.error(f"permanent_delete failed [{node_id}]: {e}")

# ==========================================
# AI HELPER
# ==========================================
def ai_process(text):
    """Gemini AI 텍스트 분석 (요약 + 키워드)"""
    if "gemini" not in st.secrets:
        return {"success": False, "error": "Gemini API key not configured"}
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        prompt = (
            f"Analyze:\n{text}\n\n"
            f"Output JSON: {{'summary': 'Korean summary (max 3 sentences)', 'keywords': '3-5 keywords'}}"
        )
        res = model.generate_content(prompt)
        data = json.loads(res.text.replace('```json', '').replace('```', '').strip())
        return {"success": True, "summary": data.get('summary', ''), "keywords": data.get('keywords', ''), "error": None}
    except Exception as e:
        logger.error(f"ai_process failed: {e}")
        return {"success": False, "error": str(e)}

# ==========================================
# INTERNAL HELPER
# ==========================================
def _delete_chunks(wb, sheet_name, doc_id):
    """특정 문서의 청크 데이터 삭제"""
    try:
        ws_chunks = wb.worksheet(sheet_name)
        all_vals = ws_chunks.get_all_values()
        if len(all_vals) > 1:
            kept = [r for r in all_vals[1:] if str(r[0]) != str(doc_id)]
            ws_chunks.clear()
            ws_chunks.append_row(all_vals[0])
            if kept:
                ws_chunks.append_rows(kept)
    except Exception as e:
        logger.warning(f"_delete_chunks failed [{sheet_name}/{doc_id}]: {e}")
