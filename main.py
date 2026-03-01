"""
main.py — Entry Point
══════════════════════
Start the bot with:  python main.py
"""

import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def check_dependencies():
    missing = []
    packages = {
        "telegram":              "python-telegram-bot==20.7",
        "boto3":                 "boto3",
        "gspread":               "gspread",
        "google.auth":           "google-auth",
        "google_auth_oauthlib":  "google-auth-oauthlib",
    }
    for pkg, install_name in packages.items():
        try:
            __import__(pkg)
        except ImportError:
            missing.append(install_name)

    if missing:
        print("❌ Missing packages. Run:")
        print(f"   pip install {' '.join(missing)}")
        sys.exit(1)

    from config import OAUTH_CREDENTIALS_FILE, TOKEN_FILE, GOOGLE_SHEET_ID

    if not os.path.exists(OAUTH_CREDENTIALS_FILE):
        print(f"⚠️  WARNING: '{OAUTH_CREDENTIALS_FILE}' not found!")
        print("   Run:  python setup_oauth.py\n")

    if not os.path.exists(TOKEN_FILE):
        print(f"⚠️  WARNING: '{TOKEN_FILE}' not found!")
        print("   Run:  python setup_oauth.py\n")

    if GOOGLE_SHEET_ID == "YOUR_GOOGLE_SHEET_ID_HERE":
        print("⚠️  WARNING: GOOGLE_SHEET_ID not set in config.py!")
        print("   Run:  python setup_oauth.py\n")


def main():
    print("=" * 60)
    print("  💰 Bilingual Finance Bot — Starting")
    print("=" * 60)

    check_dependencies()
    print("[Main] ✅ Dependencies OK")

    # Ensure Google Sheet headers exist
    try:
        from agents.sheets_agent import ensure_headers
        ensure_headers()
        print("[Main] ✅ Google Sheets ready")
    except Exception as e:
        print(f"[Main] ⚠️  Google Sheets init failed: {e}")
        print("       Run:  python setup_oauth.py  to fix this\n")

    # Start Telegram bot
    from bot import build_app
    app = build_app()

    print("[Main] 🚀 Bot is running! Open Telegram and send a message.")
    print("[Main] 📌 Commands: /start /report /history /help")
    print("=" * 60)

    app.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()