# ExpensesBot

Bilingual (Arabic + English) Telegram expense tracker powered by:
- Telegram Bot API for chat interface
- AWS Bedrock (Claude) for intent parsing and financial advice
- Google Sheets (OAuth) as the expense database
- Whisper for voice-note transcription

It supports text and voice input, logs expenses to Google Sheets, and generates AI-powered quick tips plus full reports.

## Features

- Log expenses from free-form text (`Arabic`, `English`, `Arabizi`)
- Voice note support (`.ogg/.audio` -> Whisper -> structured expense)
- Bill splitting (extracts your share)
- Monthly budget tracking with per-category limits
- Google Sheets logging and monthly summary sheet generation
- AI recommendations:
  - quick tip after each logged expense
  - on-demand full report (`/report`, `/analyze`)
  - scheduled weekly digest
  - scheduled monthly summary
- Expense deletion commands (all entries or last entry) via parsed intent

## Project Structure

- `main.py`: App entrypoint. Validates dependencies/config presence, ensures sheet headers, starts Telegram polling.
- `bot.py`: Telegram handlers, commands, message routing, voice flow, and scheduled jobs.
- `pipeline.py`: Core orchestrator that chains parse -> sheet write/query -> recommendation response.
- `config.py`: Runtime settings and secrets via environment variables (Telegram, AWS, Sheets, budgets).
- `requirements.txt`: Python dependencies (telegram, boto3, gspread, whisper, etc.).
- `Setup_oauth.py`: Interactive CLI wizard for Google OAuth setup and connection validation.
- `GOOGLE_SHEETS_SETUP.html`: Visual HTML guide for Google Sheets OAuth setup steps.
- `test_sheets.py`: End-to-end Google Sheets OAuth/connectivity test.
- `test_agents.py`: Parser/recommender tests (note: recommender import is currently outdated).

### `agents/`

- `agents/parsing_agent.py`: Agent 1 prompt + parser. Uses Bedrock to convert raw text into structured JSON (`intent`, `amount`, `currency`, `category`, `date`, etc.).
- `agents/sheets_agent.py`: Google Sheets layer (OAuth auth, worksheet creation, header management, CRUD-like ops, summary aggregation).
- `agents/recommendation_agent.py`: Agent 2 prompt + generation logic for quick tips, full reports, weekly/monthly narrative outputs, and budget status line.
- `agents/__init__.py`: Package marker.

### `utils/`

- `utils/bedrock.py`: Shared Bedrock client wrapper and helper methods (`invoke`, `invoke_json`).
- `utils/voice.py`: Whisper transcription pipeline + simple Arabic/English language detection.
- `utils/__init__.py`: Package marker.

## Runtime Flow

1. User sends text or voice message in Telegram.
2. For voice: `utils/voice.py` downloads audio, converts with ffmpeg, transcribes with Whisper.
3. `pipeline.py` calls `agents/parsing_agent.py` to extract structured intent and expense fields.
4. For logging intents: `agents/sheets_agent.py` writes a row to Google Sheets.
5. Pipeline computes monthly summary and appends budget status.
6. `agents/recommendation_agent.py` generates quick tip or full report when requested.
7. `bot.py` sends formatted response back to user.

## Setup

## 1) Create and activate virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate   # Windows PowerShell
```

## 2) Install dependencies

```bash
pip install -r requirements.txt
```

Install ffmpeg separately (required for voice conversion):
- Ubuntu/Debian: `sudo apt install ffmpeg`
- macOS: `brew install ffmpeg`
- Windows: install from ffmpeg.org and add to PATH

## 3) Configure environment variables

Required:

- `TELEGRAM_TOKEN`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

Optional / commonly needed:

- `AWS_SESSION_TOKEN` (if using temporary credentials)
- `AWS_REGION` (default: `us-east-1`)
- `BEDROCK_MODEL_ID` (default in `config.py`)
- `GOOGLE_SHEET_ID`
- `OAUTH_CREDENTIALS_FILE` (default: `oauth_credentials.json`)
- `TOKEN_FILE` (default: `token.json`)
- `MONTHLY_BUDGET_JOD` (default: `500`)

Example (PowerShell):

```powershell
$env:TELEGRAM_TOKEN="<your_token>"
$env:AWS_ACCESS_KEY_ID="<your_access_key>"
$env:AWS_SECRET_ACCESS_KEY="<your_secret_key>"
$env:AWS_SESSION_TOKEN="<your_session_token>"  # optional
$env:GOOGLE_SHEET_ID="<your_sheet_id>"
```

## 4) Run Google OAuth setup once

```bash
python Setup_oauth.py
```

This creates/refreshes `token.json` and validates sheet access.

## 5) Start the bot

```bash
python main.py
```

## Telegram Commands

- `/start` -> welcome + examples
- `/help` -> usage examples (Arabic + English)
- `/report` -> full AI spending report
- `/analyze` -> alias of `/report`
- `/history` -> last 10 transactions
- `/budget` -> monthly + category budget limits

## Scheduled Jobs

Registered in `bot.py`:
- Weekly digest: Sunday 20:00 UTC
- Monthly summary: daily check at 09:00 UTC, sends only on day 1

## Testing

- Google Sheets integration:

```bash
python test_sheets.py
```

- Agent tests:

```bash
python test_agents.py
```

Note: `test_agents.py` currently imports `generate` from `recommendation_agent`, but the module now exposes `generate_full_report` / `generate_quick_tip`. Update this test before relying on Agent 2 test results.

## Security Notes

- Never commit secrets (Telegram token, AWS keys, OAuth tokens).
- Keep `oauth_credentials.json` and `token.json` out of version control.
- Rotate any key/token immediately if leaked.

## Troubleshooting

- `Repository rule violations / secret scanning` on push:
  - remove secrets from files and commit history before pushing.
- Google Sheets auth errors:
  - rerun `python Setup_oauth.py`
  - verify OAuth client JSON is valid and sheet ID is correct.
- Voice transcription failures:
  - ensure `openai-whisper`, `pydub`, and `ffmpeg` are installed.
