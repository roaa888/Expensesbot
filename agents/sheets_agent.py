"""
agents/sheets_agent.py
══════════════════════
Google Sheets Integration Layer — OAuth 2.0 Authentication

No service account key needed. Uses OAuth so you authorize with
your own Google account via a one-time browser popup.

First run:  prints a URL → open it → click Allow → done forever.
Token saved in token.json — subsequent runs are fully automatic.

Sheet columns (Expenses tab):
  A: Row ID  |  B: Date  |  C: Day  |  D: Time  |  E: Category
  F: Item Name (original language)  |  G: Amount  |  H: Currency
  I: Note  |  J: Language  |  K: User ID  |  L: Username
  M: Logged At (UTC)

Dependencies:
  pip install gspread google-auth google-auth-oauthlib
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import os
import logging
from datetime import datetime

import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from config import OAUTH_CREDENTIALS_FILE, TOKEN_FILE, GOOGLE_SHEET_ID, \
                   EXPENSES_WORKSHEET, SUMMARY_WORKSHEET

logger = logging.getLogger(__name__)

# Scopes needed by the bot
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

EXPENSE_HEADERS = [
    "Row ID", "Date", "Day of Week", "Time",
    "Category", "Item Name", "Amount", "Currency",
    "Note", "Language", "User ID", "Username", "Logged At (UTC)"
]

_gc = None   # gspread client singleton


def _get_client():
    """
    Authenticate via OAuth 2.0.

    Flow:
      1. If token.json exists and is valid → use it silently
      2. If token.json is expired → auto-refresh it silently
      3. If no token.json → print auth URL → user opens in browser → saves token
    """
    global _gc
    if _gc is not None:
        return _gc

    creds = None

    # ── Load saved token ──────────────────────────────────────
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        logger.info("[Sheets] Loaded token from token.json")

    # ── Refresh or authorize ──────────────────────────────────
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("[Sheets] Token expired — refreshing automatically…")
            creds.refresh(Request())
        else:
            # First-time auth
            if not os.path.exists(OAUTH_CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"\n\n❌  '{OAUTH_CREDENTIALS_FILE}' not found!\n"
                    f"    Follow the setup guide to download your OAuth credentials.\n"
                    f"    Run:  python setup_oauth.py  for step-by-step instructions.\n"
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                OAUTH_CREDENTIALS_FILE, SCOPES
            )

            print("\n" + "="*60)
            print("  🔑 GOOGLE SHEETS — ONE-TIME AUTHORIZATION")
            print("="*60)
            print("\nOpening your browser for Google authorization...")
            print("If browser doesn't open, copy the URL printed below.\n")

            try:
                # Try to open browser automatically
                creds = flow.run_local_server(
                    port=8080,
                    prompt="consent",
                    open_browser=True,
                )
            except Exception:
                # Fallback: print URL for manual copy-paste
                flow2 = InstalledAppFlow.from_client_secrets_file(
                    OAUTH_CREDENTIALS_FILE, SCOPES,
                    redirect_uri="urn:ietf:wg:oauth:2.0:oob"
                )
                auth_url, _ = flow2.authorization_url(prompt="consent")
                print(f"\n👉 Open this URL in your browser:\n\n{auth_url}\n")
                code = input("Paste the authorization code here: ").strip()
                flow2.fetch_token(code=code)
                creds = flow2.credentials

            print("\n✅ Authorization successful! Token saved.\n")

        # ── Save refreshed / new token ────────────────────────
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        logger.info(f"[Sheets] ✅ Token saved to {TOKEN_FILE}")

    _gc = gspread.authorize(creds)
    logger.info("[Sheets] ✅ Google Sheets client ready (OAuth)")
    return _gc


def _get_sheet(worksheet_name: str):
    """Open the spreadsheet and return the named worksheet, creating it if needed."""
    gc = _get_client()
    spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
    try:
        ws = spreadsheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
        logger.info(f"[Sheets] Created new worksheet: {worksheet_name}")
    return ws


def ensure_headers():
    """
    Make sure the Expenses sheet has the correct header row.
    Safe to call on every startup.
    """
    ws = _get_sheet(EXPENSES_WORKSHEET)
    existing = ws.row_values(1)
    if existing != EXPENSE_HEADERS:
        ws.insert_row(EXPENSE_HEADERS, index=1)
        # Style the header row bold
        try:
            ws.format("A1:M1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.2, "green": 0.5, "blue": 0.8}
            })
        except Exception:
            pass  # Formatting is cosmetic, don't fail if it doesn't work
        logger.info("[Sheets] ✅ Headers written to Expenses sheet")


def log_expense(parsed: dict, user_id: int, username: str) -> int:
    """
    Write one expense row to Google Sheets.
    Returns the new row number (acts as expense ID).

    `parsed` is the dict produced by Agent 1 (parsing_agent.py).
    """
    ws = _get_sheet(EXPENSES_WORKSHEET)

    # Determine next row ID
    all_rows = ws.get_all_values()
    row_id = max(len(all_rows), 1)  # header is row 1

    now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    row = [
        row_id,                              # A: Row ID
        parsed.get("expense_date", ""),      # B: Date
        parsed.get("day_of_week", ""),       # C: Day of Week
        parsed.get("time_of_day", ""),       # D: Time
        parsed.get("category", "Other"),     # E: Category
        parsed.get("item_name", ""),         # F: Item Name
        parsed.get("amount", 0),             # G: Amount
        parsed.get("currency", "JOD"),       # H: Currency
        parsed.get("note", ""),              # I: Note
        parsed.get("language", "en"),        # J: Language
        user_id,                             # K: User ID
        username,                            # L: Username
        now_utc,                             # M: Logged At
    ]

    ws.append_row(row, value_input_option="USER_ENTERED")
    logger.info(f"[Sheets] ✅ Row {row_id} written: {parsed.get('item_name')} {parsed.get('amount')} {parsed.get('currency')}")
    return row_id


def get_expenses_this_month(user_id: int = None) -> list[dict]:
    """
    Read all expenses for the current month.
    If user_id is given, filter to that user only.
    Returns list of dicts keyed by EXPENSE_HEADERS.
    """
    ws = _get_sheet(EXPENSES_WORKSHEET)
    month_prefix = datetime.utcnow().strftime("%Y-%m")

    all_rows = ws.get_all_values()
    if not all_rows or len(all_rows) < 2:
        return []

    headers = all_rows[0]
    rows = []
    for row in all_rows[1:]:
        if len(row) < len(headers):
            row += [""] * (len(headers) - len(row))
        d = dict(zip(headers, row))
        # Filter by month
        if not d.get("Date", "").startswith(month_prefix):
            continue
        # Filter by user if requested
        if user_id and str(d.get("User ID", "")) != str(user_id):
            continue
        rows.append(d)
    return rows


def get_all_expenses(user_id: int = None) -> list[dict]:
    """Read ALL expenses (optionally filtered by user_id)."""
    ws = _get_sheet(EXPENSES_WORKSHEET)
    all_rows = ws.get_all_values()
    if not all_rows or len(all_rows) < 2:
        return []
    headers = all_rows[0]
    rows = []
    for row in all_rows[1:]:
        if len(row) < len(headers):
            row += [""] * (len(headers) - len(row))
        d = dict(zip(headers, row))
        if user_id and str(d.get("User ID", "")) != str(user_id):
            continue
        rows.append(d)
    return rows


def compute_monthly_summary(expenses: list[dict]) -> dict:
    """
    Aggregate expenses by category for the Recommendation Agent.
    Returns dict with totals, category breakdown, daily averages, etc.
    """
    if not expenses:
        return {"total": 0, "by_category": {}, "by_day": {}, "by_currency": {}, "count": 0}

    by_category: dict = {}
    by_day: dict = {}
    by_currency: dict = {}
    total_jod = 0.0

    for row in expenses:
        try:
            amount = float(row.get("Amount", 0) or 0)
        except (ValueError, TypeError):
            amount = 0.0

        cat = row.get("Category", "Other") or "Other"
        day = row.get("Date", "") or ""
        cur = row.get("Currency", "JOD") or "JOD"

        # By category
        by_category.setdefault(cat, {"total": 0.0, "count": 0, "currency": cur})
        by_category[cat]["total"] = round(by_category[cat]["total"] + amount, 2)
        by_category[cat]["count"] += 1

        # By day
        by_day.setdefault(day, 0.0)
        by_day[day] = round(by_day[day] + amount, 2)

        # By currency
        by_currency.setdefault(cur, 0.0)
        by_currency[cur] = round(by_currency[cur] + amount, 2)

        if cur == "JOD":
            total_jod += amount

    # Sort categories by total spending descending
    sorted_cats = dict(
        sorted(by_category.items(), key=lambda x: x[1]["total"], reverse=True)
    )

    return {
        "count": len(expenses),
        "total_jod": round(total_jod, 2),
        "by_category": sorted_cats,
        "by_day": by_day,
        "by_currency": by_currency,
        "month": datetime.utcnow().strftime("%B %Y"),
    }


def update_summary_sheet(summary: dict, user_id: int, username: str):
    """Write/overwrite the Monthly Summary worksheet with latest data."""
    try:
        ws = _get_sheet(SUMMARY_WORKSHEET)
        ws.clear()

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        header = [
            [f"📊 Monthly Summary — {summary.get('month', '')}"],
            [f"Generated: {now}  |  User: {username}  |  Total Transactions: {summary.get('count', 0)}"],
            [],
            ["Category", "Total (JOD)", "Transactions"],
        ]
        for row in header:
            ws.append_row(row)

        for cat, data in summary.get("by_category", {}).items():
            ws.append_row([cat, data["total"], data["count"]])

        ws.append_row([])
        ws.append_row(["💰 TOTAL JOD", summary.get("total_jod", 0), ""])
        logger.info("[Sheets] ✅ Summary sheet updated")
    except Exception as e:
        logger.warning(f"[Sheets] Could not update summary sheet: {e}")


def delete_all_expenses(user_id: int) -> int:
    """
    Delete ALL expense rows for a specific user.
    Keeps the header row intact.
    Returns number of rows deleted.
    """
    ws = _get_sheet(EXPENSES_WORKSHEET)
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return 0

    # Find all row indices (1-based) belonging to this user, in reverse order
    # so deleting doesn't shift indices
    to_delete = []
    for i, row in enumerate(all_rows[1:], start=2):  # start=2 skips header
        # User ID is column K (index 10)
        if len(row) > 10 and str(row[10]) == str(user_id):
            to_delete.append(i)

    # Delete in reverse order to preserve indices
    for row_idx in reversed(to_delete):
        ws.delete_rows(row_idx)

    logger.info(f"[Sheets] ✅ Deleted {len(to_delete)} rows for user {user_id}")
    return len(to_delete)


def delete_last_expense(user_id: int) -> dict | None:
    """
    Delete the most recent expense row for a specific user.
    Returns the deleted row as a dict, or None if nothing found.
    """
    ws = _get_sheet(EXPENSES_WORKSHEET)
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return None

    headers = all_rows[0]

    # Find the last row belonging to this user
    for i in range(len(all_rows) - 1, 0, -1):
        row = all_rows[i]
        if len(row) > 10 and str(row[10]) == str(user_id):
            # Build dict for confirmation message
            if len(row) < len(headers):
                row += [""] * (len(headers) - len(row))
            deleted = dict(zip(headers, row))
            ws.delete_rows(i + 1)  # +1 because all_rows is 0-indexed
            logger.info(f"[Sheets] ✅ Deleted last row for user {user_id}: {deleted.get('Item Name')}")
            return deleted

    return None