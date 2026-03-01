"""
setup_oauth.py
══════════════
Run this ONCE before starting the bot.
It walks you through getting your OAuth credentials and authorizes
the bot to access your Google Sheet — no service account key needed.

Usage:
  python setup_oauth.py
"""

import os
import sys
import webbrowser

# ─────────────────────────────────────────────────────────────
#  ASCII art header
# ─────────────────────────────────────────────────────────────
HEADER = """
╔══════════════════════════════════════════════════════════╗
║   🔑  Google Sheets OAuth Setup — Finance Bot           ║
║   No service account key needed!                        ║
╚══════════════════════════════════════════════════════════╝
"""

def pause(msg="Press Enter to continue..."):
    input(f"\n  {msg}")

def section(title):
    print(f"\n{'─'*58}")
    print(f"  {title}")
    print(f"{'─'*58}")

def step(n, text):
    print(f"\n  [{n}] {text}")

def ok(text):
    print(f"  ✅  {text}")

def warn(text):
    print(f"  ⚠️   {text}")

def info(text):
    print(f"  ℹ️   {text}")


# ─────────────────────────────────────────────────────────────
#  PART 1 — Guide user to download OAuth credentials from GCP
# ─────────────────────────────────────────────────────────────
def guide_download_credentials():
    print(HEADER)
    print("  This script will help you set up Google Sheets in 3 stages:")
    print("  1. Download OAuth credentials from Google Cloud (guided)")
    print("  2. Place the file in the right location")
    print("  3. Authorize the bot with your Google account (one click)")
    pause("Press Enter to start...")

    section("STAGE 1 — Download OAuth Credentials from Google Cloud")

    print("""
  We need to create an "OAuth 2.0 Client ID" in Google Cloud.
  This is different from a service account — it lets the bot
  act on YOUR behalf, using YOUR Google account. No keys needed.
    """)

    step(1, "Open Google Cloud Console")
    info("URL: https://console.cloud.google.com/")
    info("Sign in with your personal Gmail account")

    open_browser = input("\n  Open it in your browser now? (y/n): ").strip().lower()
    if open_browser == 'y':
        webbrowser.open("https://console.cloud.google.com/")
    pause()

    step(2, "Make sure the right project is selected")
    info("Look at the top bar — it should show your 'finance-bot' project")
    info("If not, click the dropdown and select or create it")
    pause()

    step(3, "Enable required APIs (if not done yet)")
    info("Go to:  APIs & Services  →  Library")
    info("Search and Enable:  'Google Sheets API'")
    info("Search and Enable:  'Google Drive API'")

    open_browser = input("\n  Open API Library now? (y/n): ").strip().lower()
    if open_browser == 'y':
        webbrowser.open("https://console.cloud.google.com/apis/library")
    pause("Press Enter once both APIs are enabled...")

    step(4, "Configure the OAuth Consent Screen (one-time)")
    info("Go to:  APIs & Services  →  OAuth consent screen")
    info("Select:  'External'  →  click Create")
    info("Fill in:")
    info("  • App name:        Finance Bot")
    info("  • User support email:   (your Gmail)")
    info("  • Developer email:      (your Gmail)")
    info("Click  'Save and Continue'  through all steps")
    info("On 'Test users' page → Add your own Gmail as a test user")
    info("Click  'Save and Continue'  →  'Back to Dashboard'")

    open_browser = input("\n  Open OAuth consent screen now? (y/n): ").strip().lower()
    if open_browser == 'y':
        webbrowser.open("https://console.cloud.google.com/apis/credentials/consent")
    pause("Press Enter once the consent screen is configured...")

    step(5, "Create the OAuth 2.0 Client ID")
    info("Go to:  APIs & Services  →  Credentials")
    info("Click:  + Create Credentials  →  OAuth client ID")
    info("Application type:  'Desktop app'")
    info("Name:  'Finance Bot Desktop'")
    info("Click:  Create")

    open_browser = input("\n  Open Credentials page now? (y/n): ").strip().lower()
    if open_browser == 'y':
        webbrowser.open("https://console.cloud.google.com/apis/credentials")
    pause("Press Enter once you've created the OAuth client ID...")

    step(6, "Download the JSON file")
    info("A dialog will appear — click  'Download JSON'")
    info("A file like  client_secret_XXXXX.json  will download")
    pause("Press Enter once the file is downloaded...")

    step(7, "Rename and move the file")
    print(f"""
  Rename the downloaded file to:
    oauth_credentials.json

  Move it to this folder:
    {os.path.abspath('.')}

  So the path is:
    {os.path.abspath('oauth_credentials.json')}
    """)
    pause("Press Enter once you've placed the file here...")


# ─────────────────────────────────────────────────────────────
#  PART 2 — Validate file exists
# ─────────────────────────────────────────────────────────────
def validate_credentials_file():
    section("STAGE 2 — Verifying Credentials File")

    from config import OAUTH_CREDENTIALS_FILE

    if not os.path.exists(OAUTH_CREDENTIALS_FILE):
        warn(f"'{OAUTH_CREDENTIALS_FILE}' not found in current directory!")
        print(f"\n  Expected location: {os.path.abspath(OAUTH_CREDENTIALS_FILE)}")
        print(f"  Files in this folder: {', '.join(os.listdir('.'))}")
        sys.exit(1)

    # Quick content check
    import json
    try:
        with open(OAUTH_CREDENTIALS_FILE) as f:
            data = json.load(f)
        if "installed" not in data and "web" not in data:
            warn("File doesn't look like an OAuth client secrets file.")
            warn("Make sure you downloaded 'OAuth 2.0 Client ID', not a service account key.")
            sys.exit(1)
        ok(f"'{OAUTH_CREDENTIALS_FILE}' found and valid!")
    except json.JSONDecodeError:
        warn(f"'{OAUTH_CREDENTIALS_FILE}' is not valid JSON. Re-download it.")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────
#  PART 3 — Get Sheet ID
# ─────────────────────────────────────────────────────────────
def get_sheet_id():
    section("STAGE 3 — Your Google Sheet ID")
    from config import GOOGLE_SHEET_ID

    if GOOGLE_SHEET_ID != "YOUR_GOOGLE_SHEET_ID_HERE":
        ok(f"Sheet ID already set: {GOOGLE_SHEET_ID}")
        return

    print("""
  You need a Google Sheet to store your expenses.
  
  If you haven't created one yet:
    1. Go to https://sheets.google.com
    2. Click  '+ Blank spreadsheet'
    3. Name it  'Finance Bot — Expenses'
    """)

    open_browser = input("  Open Google Sheets now? (y/n): ").strip().lower()
    if open_browser == 'y':
        webbrowser.open("https://sheets.google.com")

    print("""
  Now copy the Sheet ID from the URL bar.
  The URL looks like:
  
  https://docs.google.com/spreadsheets/d/ [SHEET_ID_HERE] /edit
                                            ↑ copy this part ↑
    """)

    sheet_id = input("  Paste your Sheet ID here: ").strip()
    if not sheet_id or len(sheet_id) < 20:
        warn("That doesn't look right — Sheet IDs are usually ~44 characters.")
        sheet_id = input("  Try again: ").strip()

    # Patch config.py automatically
    config_path = os.path.join(os.path.dirname(__file__), "config.py")
    with open(config_path, "r") as f:
        content = f.read()
    content = content.replace(
        'GOOGLE_SHEET_ID = "YOUR_GOOGLE_SHEET_ID_HERE"',
        f'GOOGLE_SHEET_ID = "{sheet_id}"'
    )
    with open(config_path, "w") as f:
        f.write(content)

    ok(f"Sheet ID saved to config.py: {sheet_id}")


# ─────────────────────────────────────────────────────────────
#  PART 4 — Run the OAuth authorization flow
# ─────────────────────────────────────────────────────────────
def run_oauth_flow():
    section("STAGE 4 — Authorizing with Your Google Account")

    print("""
  Now we'll authorize the bot to access your Google Sheet.
  
  What happens next:
    • Your browser will open a Google authorization page
    • Sign in with the same Gmail you used for GCP
    • Click  'Allow'
    • Come back here — done!
    """)
    pause("Press Enter to open the authorization page...")

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from config import OAUTH_CREDENTIALS_FILE, TOKEN_FILE

        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        flow = InstalledAppFlow.from_client_secrets_file(
            OAUTH_CREDENTIALS_FILE, SCOPES
        )

        print("\n  Opening browser...")
        try:
            creds = flow.run_local_server(port=8080, prompt="consent", open_browser=True)
        except Exception:
            # Fallback for headless / remote servers
            flow2 = InstalledAppFlow.from_client_secrets_file(
                OAUTH_CREDENTIALS_FILE, SCOPES,
                redirect_uri="urn:ietf:wg:oauth:2.0:oob"
            )
            auth_url, _ = flow2.authorization_url(prompt="consent")
            print(f"\n  ⚠️  Could not open browser automatically.")
            print(f"  👉 Copy and open this URL:\n\n  {auth_url}\n")
            code = input("  Paste the authorization code from Google: ").strip()
            flow2.fetch_token(code=code)
            creds = flow2.credentials

        # Save token
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

        ok(f"Token saved to {TOKEN_FILE}")

    except Exception as e:
        print(f"\n  ❌ Authorization failed: {e}")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────
#  PART 5 — Test the connection
# ─────────────────────────────────────────────────────────────
def test_connection():
    section("STAGE 5 — Testing Google Sheets Connection")

    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from agents.sheets_agent import ensure_headers, _get_sheet
        from config import EXPENSES_WORKSHEET

        print("  Connecting to Google Sheets...")
        ensure_headers()
        ok("Connected and headers verified!")

        # Write a quick test row
        import gspread
        ws = _get_sheet(EXPENSES_WORKSHEET)
        ws.append_row(["TEST", "2000-01-01", "Saturday", "", "Other",
                        "TEST_DELETE_ME", 0.01, "JOD", "setup test",
                        "en", 0, "setup", ""])
        ok("Test row written successfully!")

        # Clean it up
        cells = ws.findall("TEST_DELETE_ME")
        for cell in cells:
            ws.delete_rows(cell.row)
        ok("Test row cleaned up!")

    except Exception as e:
        print(f"\n  ❌ Connection test failed: {e}")
        print("  Common fixes:")
        print("  • Make sure GOOGLE_SHEET_ID is correct in config.py")
        print("  • Make sure the Sheet is not restricted")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────
def main():
    # Check if already set up
    from config import TOKEN_FILE, OAUTH_CREDENTIALS_FILE, GOOGLE_SHEET_ID

    already_has_token = os.path.exists(TOKEN_FILE)
    already_has_creds = os.path.exists(OAUTH_CREDENTIALS_FILE)
    already_has_sheet = GOOGLE_SHEET_ID != "YOUR_GOOGLE_SHEET_ID_HERE"

    if already_has_token and already_has_creds and already_has_sheet:
        print(HEADER)
        print("  ✅ Already set up! Running connection test...\n")
        test_connection()
    else:
        if not already_has_creds:
            guide_download_credentials()
        validate_credentials_file()
        get_sheet_id()
        run_oauth_flow()
        test_connection()

    # Final summary
    print(f"""
{'═'*58}
  🎉  SETUP COMPLETE!

  Files created:
  ✅  oauth_credentials.json   (your OAuth client secrets)
  ✅  token.json               (your access token — auto-refreshes)

  Next steps:
  ─────────────────────────────────────────────────
  1.  python test_agents.py    ← test AI agents
  2.  python main.py           ← launch the bot!
{'═'*58}
    """)


if __name__ == "__main__":
    main()