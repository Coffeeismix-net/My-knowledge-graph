"""
db_chain.py — Value Chain CRUD + AI 이미지 분석
"""
import streamlit as st
import google.generativeai as genai
import uuid
import logging
from utils.db_common import get_workbook, get_or_create_sheet, chunk_text, get_kst_now_str

logger = logging.getLogger(__name__)

# ==========================================
# AI HELPER (VISION)
# ==========================================
VALUECHAIN_PROMPT = """
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

def analyze_valuechain_image(image_bytes):
    """밸류체인 이미지 → JSON 구조 변환"""
    if "gemini" not in st.secrets:
        return {"success": False, "error": "API Key Missing"}
    genai.configure(api_key=st.secrets["gemini"]["api_key"])

    try:
        image_part = {"mime_type": "image/jpeg", "data": image_bytes}
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content([VALUECHAIN_PROMPT, image_part])
        text = response.text.replace('```json', '').replace('```', '').strip()
        return {"success": True, "json": text}
    except Exception as e:
        logger.error(f"analyze_valuechain_image failed: {e}")
        return {"success": False, "error": str(e)}

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

# ==========================================
# CRUD
# ==========================================
@st.cache_data(ttl=300)
def load_valuechains():
    """전체 밸류체인 로드"""
    wb = get_workbook()
    if not wb:
        return []
    try:
        ws_meta = get_or_create_sheet(wb, "valuechains", ["id", "title", "created_at"])
        meta_data = ws_meta.get_all_records()
        ws_json = get_or_create_sheet(wb, "valuechain_chunks", ["id", "index", "content"])
        ws_img = get_or_create_sheet(wb, "valuechain_images", ["id", "index", "content"])
        json_list = ws_json.get_all_records()
        img_list = ws_img.get_all_records()

        json_map = {}
        for r in json_list:
            json_map.setdefault(str(r['id']), []).append((int(r['index']), str(r['content'])))
        img_map = {}
        for r in img_list:
            img_map.setdefault(str(r['id']), []).append((int(r['index']), str(r['content'])))

        result = []
        for r in meta_data:
            did = str(r['id'])
            full_json = "".join([x[1] for x in sorted(json_map.get(did, []), key=lambda x: x[0])])
            full_img = "".join([x[1] for x in sorted(img_map.get(did, []), key=lambda x: x[0])])
            result.append({
                "id": did, "title": r['title'],
                "json_data": full_json, "image_data": full_img,
                "created_at": str(r['created_at'])
            })
        return result
    except Exception as e:
        logger.error(f"load_valuechains failed: {e}")
        return []

def clear_valuechains_cache():
    """밸류체인 캐시 초기화"""
    load_valuechains.clear()

def add_valuechain(title, json_str, image_base64=""):
    """밸류체인 추가"""
    wb = get_workbook()
    if not wb:
        return None
    try:
        new_id = str(uuid.uuid4())[:8]
        now_str = get_kst_now_str()

        ws_meta = get_or_create_sheet(wb, "valuechains", ["id", "title", "created_at"])
        ws_meta.append_row([new_id, title, now_str])

        ws_json = get_or_create_sheet(wb, "valuechain_chunks", ["id", "index", "content"])
        ws_json.append_rows([[new_id, i, c] for i, c in enumerate(chunk_text(json_str))])

        if image_base64:
            ws_img = get_or_create_sheet(wb, "valuechain_images", ["id", "index", "content"])
            ws_img.append_rows([[new_id, i, c] for i, c in enumerate(chunk_text(image_base64))])

        return {
            "id": new_id, "title": title,
            "json_data": json_str, "image_data": image_base64,
            "created_at": now_str
        }
    except Exception as e:
        logger.error(f"add_valuechain failed: {e}")
        return None

def delete_valuechain(doc_id):
    """밸류체인 삭제"""
    wb = get_workbook()
    if not wb:
        return
    try:
        ws_meta = wb.worksheet("valuechains")
        cell = ws_meta.find(str(doc_id))
        if cell:
            ws_meta.delete_rows(cell.row)
        _delete_chunks(wb, "valuechain_chunks", doc_id)
        _delete_chunks(wb, "valuechain_images", doc_id)
    except Exception as e:
        logger.error(f"delete_valuechain failed [{doc_id}]: {e}")
