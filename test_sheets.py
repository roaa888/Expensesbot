"""
test_sheets.py — Google Sheets Connection Test (OAuth)
Run with:  python test_sheets.py
"""
import sys
import os
from datetime import datetime

# Fix path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_sheets():
    print("=" * 55)
    print("  🧪 Google Sheets Connection Test (OAuth)")
    print("=" * 55)

    from config import OAUTH_CREDENTIALS_FILE, TOKEN_FILE, GOOGLE_SHEET_ID

    # 1. Check files exist
    if not os.path.exists(OAUTH_CREDENTIALS_FILE):
        print(f"❌ '{OAUTH_CREDENTIALS_FILE}' not found!")
        print("   Run:  python setup_oauth.py")
        return False
    print(f"✅ OAuth credentials file found: {OAUTH_CREDENTIALS_FILE}")

    if not os.path.exists(TOKEN_FILE):
        print(f"❌ token.json not found! Run:  python setup_oauth.py")
        return False
    print(f"✅ Token file found: {TOKEN_FILE}")

    if GOOGLE_SHEET_ID == "YOUR_GOOGLE_SHEET_ID_HERE":
        print("❌ GOOGLE_SHEET_ID not set in config.py!")
        return False
    print(f"✅ Sheet ID: {GOOGLE_SHEET_ID}")

    # 2. Authenticate
    try:
        import gspread
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = Credentials.from_authorized_user_file(TOKEN_FILE)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        gc = gspread.authorize(creds)
        print("✅ Google Sheets client authenticated (OAuth)")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        print("   Run:  python setup_oauth.py  to re-authorize")
        return False

    # 3. Open spreadsheet
    try:
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        print(f"✅ Spreadsheet opened: '{spreadsheet.title}'")
    except Exception as e:
        print(f"❌ Cannot open sheet: {e}")
        return False

    # 4. Create/verify Expenses worksheet and headers
    try:
        try:
            ws = spreadsheet.worksheet("Expenses")
        except Exception:
            ws = spreadsheet.add_worksheet(title="Expenses", rows=1000, cols=20)
            print("✅ Created 'Expenses' worksheet")

        headers = [
            "Row ID", "Date", "Day of Week", "Time", "Category",
            "Item Name", "Amount", "Currency", "Note", "Language",
            "User ID", "Username", "Logged At (UTC)"
        ]
        existing = ws.row_values(1)
        if existing != headers:
            ws.insert_row(headers, index=1)
        print("✅ Headers written to Expenses sheet")
    except Exception as e:
        print(f"❌ Header write failed: {e}")
        return False

    # 5. Write a test row
    try:
        ws.append_row([
            1, "2000-01-01", "Saturday", "", "Other",
            "TEST_ROW_DELETE_ME", 0.01, "JOD", "automated test",
            "en", 0, "test_bot",
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        ])
        print("✅ Test row written successfully")
    except Exception as e:
        print(f"❌ Write test failed: {e}")
        return False

    # 6. Clean up test row
    try:
        cells = ws.findall("TEST_ROW_DELETE_ME")
        for cell in cells:
            ws.delete_rows(cell.row)
        print("✅ Test row cleaned up")
    except Exception as e:
        print(f"⚠️  Could not clean up test row: {e}")

    print("\n" + "=" * 55)
    print("  🎉 Google Sheets is ready!")
    print("  Run:  python main.py  to start the bot!")
    print("=" * 55)
    return True


if __name__ == "__main__":
    success = test_sheets()
    sys.exit(0 if success else 1)