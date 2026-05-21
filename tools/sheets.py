"""
Google Sheets writer for kessan-reports.
Based on the original kessan-app/sheets.py with two changes:
  1. httplib2 explicit ca_certs (cloud sandbox SSL inspection)
  2. GitHub upload removed (Claude Code commits via git directly)
"""
import os
import re
import json
import httplib2
from typing import Optional
from google.oauth2 import service_account
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build

GITHUB_PAGES_BASE = "https://kyon4166.github.io/kessan-reports"
SPREADSHEET_ID = "12jLfVOv8IvVtEU254OBIeO-SgajGkOoRo-YJo_JU7MU"

SHEET_NAME = "決算情報"
HEADER_ROW = 7
DATA_START_ROW = 8

COL = {
    "code": 0, "name": 1,
    "quarter": 3, "revenue_yoy": 4, "profit_yoy": 5,
    "dividend_change": 6, "forecast_revision": 7,
    "payout_ratio": 8, "equity_ratio": 9, "equity_ratio_change": 10,
    "next_dividend": 11, "next_dividend_chg": 12,
    "next_eps": 13, "next_eps_chg": 14,
    "summary": 15,
}
ANNUAL_ONLY_COLS = {"next_dividend", "next_dividend_chg", "next_eps", "next_eps_chg"}

CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt")


def _get_service():
    creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE")
    if creds_file:
        creds = service_account.Credentials.from_service_account_file(
            creds_file,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
    else:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS")
        if not creds_json:
            raise EnvironmentError("GOOGLE_CREDENTIALS_FILE または GOOGLE_CREDENTIALS が必要です")
        creds = service_account.Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
    http = httplib2.Http(ca_certs=CA_BUNDLE)
    authed = AuthorizedHttp(creds, http=http)
    return build("sheets", "v4", http=authed, cache_discovery=False)


def _read_data(service) -> list:
    res = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A{DATA_START_ROW}:Q",
    ).execute()
    return res.get("values", [])


def _find_row(rows: list, code: str) -> Optional[int]:
    for i, row in enumerate(rows):
        if row and str(row[0]).strip() == code:
            return i
    return None


def _cell(row: list, col_idx: int) -> str:
    return str(row[col_idx]).strip() if col_idx < len(row) else ""


def _safe_text(v) -> str:
    """テキスト列の値を文字列化（書込は RAW を使用するため数式 escape は不要）。"""
    if v is None:
        return ""
    return str(v).strip()


def _get_quarter_label(data: dict) -> str:
    if data.get("is_annual"):
        return "年度末"
    fiscal = str(data.get("fiscal_period", ""))
    if "第1四半期" in fiscal or "1Q" in fiscal: return "1Q"
    if "第2四半期" in fiscal or "2Q" in fiscal: return "2Q"
    if "第3四半期" in fiscal or "3Q" in fiscal: return "3Q"
    return ""


def _build_row_values(data: dict, existing_row: Optional[list]) -> list:
    is_annual = data.get("is_annual", False)

    def resolve(key, col_idx):
        v = data.get(key)
        if v is None or str(v).strip() == "":
            return _cell(existing_row, col_idx) if existing_row else ""
        return str(v)

    def resolve_pct(key, col_idx):
        v = data.get(key)
        if v is None or str(v).strip() == "":
            return _cell(existing_row, col_idx) if existing_row else ""
        try:
            return round(float(str(v).replace("+", "")) / 100, 6)
        except ValueError:
            return str(v)

    def resolve_annual(key, col_idx):
        return resolve(key, col_idx) if is_annual else (_cell(existing_row, col_idx) if existing_row else "")

    def resolve_annual_pct(key, col_idx):
        return resolve_pct(key, col_idx) if is_annual else (_cell(existing_row, col_idx) if existing_row else "")

    row = [""] * 16
    row[0]  = str(data.get("company_code", ""))
    row[1]  = resolve("company_name", 1)
    row[2]  = ""  # C列 ArrayFormula 保護
    row[3]  = _get_quarter_label(data)
    row[4]  = resolve_pct("revenue_yoy", 4)
    row[5]  = resolve_pct("operating_profit_yoy", 5)
    row[6]  = _safe_text(resolve("dividend_change", 6))
    row[7]  = _safe_text(resolve("forecast_revision", 7))
    row[8]  = resolve_pct("payout_ratio", 8)
    row[9]  = resolve_pct("equity_ratio", 9)
    row[10] = resolve_pct("equity_ratio_change", 10)
    row[11] = resolve_annual("next_dividend_forecast", 11)
    row[12] = _safe_text(resolve_annual("next_dividend_change", 12))
    row[13] = resolve_annual("next_eps_forecast", 13)
    row[14] = resolve_annual_pct("next_eps_change_pct", 14)
    row[15] = _safe_text(resolve("summary", 15))
    return row


def _write_row_skip_c(service, sheet_row: int, new_row: list):
    # 数値列（E,F,I,J,K,O）は USER_ENTERED で % として書く
    # テキスト列（D,G,H,L,M,N,P）は RAW で書く（"+46円" 等が数式扱いされるのを防止）
    user_entered_data = [
        {"range": f"{SHEET_NAME}!A{sheet_row}:B{sheet_row}", "values": [new_row[0:2]]},
        {"range": f"{SHEET_NAME}!E{sheet_row}:F{sheet_row}", "values": [new_row[4:6]]},
        {"range": f"{SHEET_NAME}!I{sheet_row}:K{sheet_row}", "values": [new_row[8:11]]},
        {"range": f"{SHEET_NAME}!O{sheet_row}", "values": [[new_row[14]]]},
    ]
    raw_data = [
        {"range": f"{SHEET_NAME}!D{sheet_row}", "values": [[new_row[3]]]},
        {"range": f"{SHEET_NAME}!G{sheet_row}:H{sheet_row}", "values": [new_row[6:8]]},
        {"range": f"{SHEET_NAME}!L{sheet_row}:N{sheet_row}", "values": [new_row[11:14]]},
        {"range": f"{SHEET_NAME}!P{sheet_row}", "values": [[new_row[15]]]},
    ]
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"valueInputOption": "USER_ENTERED", "data": user_entered_data},
    ).execute()
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"valueInputOption": "RAW", "data": raw_data},
    ).execute()


def _reconstruct_q_formula(code: str, q_str: str) -> str:
    if q_str.startswith("="):
        return q_str
    parts = q_str.strip().split()
    if len(parts) == 2 and re.match(r"^\d{4}$", parts[0]) and re.match(r"^Q[1-4]$", parts[1]):
        year, qtr = parts
        filename = f"{code}_{year}_{qtr}.html"
        url = f"{GITHUB_PAGES_BASE}/{filename}"
        return f'=HYPERLINK("{url}","{q_str}")'
    return q_str


def _sort_data(service):
    formula_rows = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A{DATA_START_ROW}:Q",
        valueRenderOption="FORMULA",
    ).execute().get("values", [])

    code_to_q = {}
    for row in formula_rows:
        if row and str(row[0]).strip():
            code = str(row[0]).strip()
            q_val = row[16] if len(row) > 16 else ""
            q_str = str(q_val).strip()
            if q_str:
                code_to_q[code] = _reconstruct_q_formula(code, q_str)

    rows = _read_data(service)
    non_empty = [r for r in rows if r and str(r[0]).strip()]
    if not non_empty:
        return

    def sort_key(row):
        try: return int(str(row[0]).strip())
        except ValueError: return str(row[0]).strip()

    sorted_rows = sorted(non_empty, key=sort_key)
    end_row = DATA_START_ROW + len(sorted_rows) - 1

    def col(idx):
        return [[(list(r)+[""]*17)[idx]] for r in sorted_rows]
    def cols(start, end):  # inclusive start, exclusive end
        return [(list(r)+[""]*17)[start:end] for r in sorted_rows]

    # 数値列（E,F,I,J,K,O）は USER_ENTERED、テキスト列（D,G,H,L,M,N,P）は RAW、
    # Q列はHYPERLINK数式の再構築なので USER_ENTERED で書き込む
    ab = [[(list(r)+["",""])[0], (list(r)+["",""])[1]] for r in sorted_rows]
    q = [[code_to_q.get(str(r[0]).strip(), "")] for r in sorted_rows]

    user_entered_data = [
        {"range": f"{SHEET_NAME}!A{DATA_START_ROW}:B{end_row}", "values": ab},
        {"range": f"{SHEET_NAME}!E{DATA_START_ROW}:F{end_row}", "values": cols(4, 6)},
        {"range": f"{SHEET_NAME}!I{DATA_START_ROW}:K{end_row}", "values": cols(8, 11)},
        {"range": f"{SHEET_NAME}!O{DATA_START_ROW}:O{end_row}", "values": col(14)},
        {"range": f"{SHEET_NAME}!Q{DATA_START_ROW}:Q{end_row}", "values": q},
    ]
    raw_data = [
        {"range": f"{SHEET_NAME}!D{DATA_START_ROW}:D{end_row}", "values": col(3)},
        {"range": f"{SHEET_NAME}!G{DATA_START_ROW}:H{end_row}", "values": cols(6, 8)},
        {"range": f"{SHEET_NAME}!L{DATA_START_ROW}:N{end_row}", "values": cols(11, 14)},
        {"range": f"{SHEET_NAME}!P{DATA_START_ROW}:P{end_row}", "values": col(15)},
    ]
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"valueInputOption": "USER_ENTERED", "data": user_entered_data},
    ).execute()
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"valueInputOption": "RAW", "data": raw_data},
    ).execute()


def _parse_filename(filename: str) -> tuple:
    try:
        parts = filename.replace(".html", "").split("_")
        if len(parts) >= 3:
            return parts[1], parts[2]
    except Exception:
        pass
    return "", ""


def write_data(data: dict, html_filename: Optional[str] = None) -> dict:
    """
    決算情報シートへ書き込み。
    html_filename を渡すと、GitHub Pages URLからQ列HYPERLINKを構築。
    """
    service = _get_service()
    rows = _read_data(service)
    code = str(data.get("company_code", "")).strip()
    if not code:
        raise ValueError("証券コードが抽出できませんでした")

    row_idx = _find_row(rows, code)
    if row_idx is not None:
        sheet_row = DATA_START_ROW + row_idx
        new_row = _build_row_values(data, rows[row_idx])
        _write_row_skip_c(service, sheet_row, new_row)
        action = "上書き更新"
    else:
        new_row = _build_row_values(data, None)
        next_row = DATA_START_ROW + len(rows)
        _write_row_skip_c(service, next_row, new_row)
        _sort_data(service)
        updated = _read_data(service)
        idx2 = _find_row(updated, code)
        sheet_row = DATA_START_ROW + idx2 if idx2 is not None else next_row
        action = "新規追加"

    link_status = None
    if html_filename:
        year, qtr = _parse_filename(html_filename)
        label = f"{year} {qtr}".strip() if year else html_filename
        url = f"{GITHUB_PAGES_BASE}/{html_filename}"
        formula = f'=HYPERLINK("{url}","{label}")'
        try:
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!Q{sheet_row}",
                valueInputOption="USER_ENTERED",
                body={"values": [[formula]]},
            ).execute()
            link_status = f"written:Q{sheet_row}"
        except Exception as e:
            link_status = f"error:{e}"

    return {"action": action, "code": code,
            "name": data.get("company_name", ""),
            "link_status": link_status}
