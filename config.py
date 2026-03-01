"""Application configuration.

Secrets are loaded from environment variables so they are not committed to Git.
"""

import os

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# AWS Bedrock
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")

# Google Sheets OAuth
OAUTH_CREDENTIALS_FILE = os.getenv("OAUTH_CREDENTIALS_FILE", "oauth_credentials.json")
TOKEN_FILE = os.getenv("TOKEN_FILE", "token.json")

# Google Sheet
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1Uqq7I0l7zx3uDXig7d3oeIKdNRMzTsCKAnPRgGr-cgU")
EXPENSES_WORKSHEET = os.getenv("EXPENSES_WORKSHEET", "Expenses")
SUMMARY_WORKSHEET = os.getenv("SUMMARY_WORKSHEET", "Monthly Summary")

# Voice
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# Budget settings
MONTHLY_BUDGET_JOD = int(os.getenv("MONTHLY_BUDGET_JOD", "500"))

CATEGORY_BUDGETS = {
    "Food & Dining": 80,
    "Groceries": 100,
    "Transportation": 60,
    "Electronics": 50,
    "Clothing & Fashion": 50,
    "Health & Medical": 40,
    "Entertainment": 30,
    "Education": 50,
    "Housing & Rent": 200,
    "Utilities": 50,
    "Subscriptions": 20,
    "Travel": 100,
    "Personal Care": 25,
    "Gifts": 30,
    "Other": 40,
}

DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "JOD")
CATEGORIES = list(CATEGORY_BUDGETS.keys())
