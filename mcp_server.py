"""
mcp_server.py — PKM 지식저장소 MCP 서버
Claude와 대화 중 지식 노드, 기업분석을 Google Sheets에 저장
"""
import os
import json
import uuid
import logging
import uvicorn

from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
SPREADSHEET_KEY = "1ryBvLf_iUwoFR7Cx9zjZEldV6WHe26Jngxu0fs-BZMc"
CHUNK_SIZE = 45000

_client = None
_wb = None

def get_workbook():
    global _client, _wb
    if _wb:
        return _wb
    try:
        sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        if not sa_json:
            raise ValueError("GCP_SERVICE_ACCOUNT_JSON 환경변수 없음")
        sa_info = json.loads(sa_json)
        creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        _client = gspread.authorize(creds)
        _wb = _client.open_by_key(SPREADSHEET_KEY)
        return _wb
    except Exception as e:
        logger.error(f"Workbook 연결 실패: {e}")
        return None

def get_or_create_sheet(wb, title, cols):
    try:
        return wb.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = wb.add_worksheet(title=title, rows=100, cols=max(len(cols), 1))
        if cols:
            ws.append_row(cols)
        return ws

def chunk_text(text):
    if not text:
        return [""]
    return [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

def get_kst_now_str():
    return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")

def new_id():
    return str(uuid.uuid4())[:8]

mcp = FastMCP(
    "pkm-knowledge-store",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    )
)

@mcp.tool()
def add_node(label: str, group: str, summary: str, keywords: str, content: str = "") -> str:
    """
    지식 노드를 PKM 홈피에 저장합니다.

    Args:
        label: 노드 제목 (예: "삼성전자 HBM 전략")
        group: 분류 그룹 (예: "반도체", "주식", "RF")
        summary: 3줄 이내 핵심 요약
        keywords: 쉼표로 구분된 키워드 (예: "HBM,반도체,AI")
        content: 본문 내용 (선택, 길어도 됨)
    """
    wb = get_workbook()
    if not wb:
        return "오류: DB 연결 실패"
    try:
        doc_id = new_id()
        now = get_kst_now_str()
        wb.sheet1.append_row([doc_id, label, group, summary, keywords, now])
        if content:
            ws_chunks = get_or_create_sheet(wb, "node_chunks", ["id", "index", "content"])
            ws_chunks.append_rows([[doc_id, i, c] for i, c in enumerate(chunk_text(content))])
        return f"저장 완료: [{group}] {label} (id: {doc_id})"
    except Exception as e:
        logger.error(f"add_node 실패: {e}")
        return f"오류: {e}"

@mcp.tool()
def add_stock(company: str, title: str, content: str, keywords: str) -> str:
    """
    기업 분석 내용을 PKM 홈피에 저장합니다.

    Args:
        company: 기업명 (예: "삼성전자", "POSCO홀딩스")
        title: 분석 제목 (예: "2026 HBM 수주 전망")
        content: 분석 본문 내용
        keywords: 쉼표로 구분된 키워드 (예: "HBM,AI반도체,수주")
    """
    wb = get_workbook()
    if not wb:
        return "오류: DB 연결 실패"
    try:
        doc_id = new_id()
        now = get_kst_now_str()
        ws_meta = get_or_create_sheet(wb, "stocks", ["id", "company", "title", "keywords", "created_at"])
        ws_meta.append_row([doc_id, company, title, keywords, now])
        ws_chunks = get_or_create_sheet(wb, "stock_chunks", ["id", "index", "content"])
        ws_chunks.append_rows([[doc_id, i, c] for i, c in enumerate(chunk_text(content))])
        return f"저장 완료: [{company}] {title} (id: {doc_id})"
    except Exception as e:
        logger.error(f"add_stock 실패: {e}")
        return f"오류: {e}"

# ==========================================
# ASGI 앱 + 실행
# ==========================================
import uvicorn

app = mcp.streamable_http_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
