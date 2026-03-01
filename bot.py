"""
bot.py — Telegram Bot Handlers + Scheduled Jobs
══════════════════════════════════════════════════
RECOMMENDATION TRIGGERS (all 4 active):
  1. After every expense  → inline quick tip from Agent 2
  2. /report or /analyze  → full deep report on demand
  3. Every Sunday 20:00   → weekly digest (auto)
  4. 1st of each month    → monthly summary (auto)
"""

import logging
from datetime import datetime, time as dtime

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode, ChatAction

import pipeline
from agents.sheets_agent import (
    get_expenses_this_month, get_all_expenses,
    compute_monthly_summary, update_summary_sheet,
)
from agents.recommendation_agent import (
    generate_full_report,
    generate_weekly_digest,
    generate_monthly_summary,
)
from utils.voice import transcribe_voice_message, detect_language
from config import TELEGRAM_TOKEN, WHISPER_MODEL

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
#  Active user registry for scheduled messages
#  Production: persist this to Sheets or a file
# ──────────────────────────────────────────────────────────────────────
ACTIVE_USERS: dict = {}   # {user_id: {username, lang, chat_id}}


def _register_user(user_id: int, username: str, chat_id: int, lang: str = "en"):
    ACTIVE_USERS[user_id] = {
        "username": username,
        "chat_id":  chat_id,
        "lang":     lang,
    }


# ════════════════════════════════════════════════════════════════════════
#  COMMANDS
# ════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    _register_user(user.id, user.username or user.first_name,
                   update.effective_chat.id)
    msg = (
        f"👋 *مرحباً {user.first_name}!*\n\n"
        "أنا مساعدك المالي الذكي 💰\n"
        "أتحدث العربية والإنجليزية وأفهم الرسائل الصوتية!\n\n"
        "*أمثلة:*\n"
        "• `اشتريت غداء ب 5 دينار`\n"
        "• `spent 12 USD on groceries`\n"
        "• `دفعنا 90 دينار على العشاء، نصيبي الثلث`\n"
        "• أرسل رسالة صوتية 🎙️\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 *Hello {user.first_name}!*\n\n"
        "I'm your bilingual finance assistant 💰\n\n"
        "*Commands:*\n"
        "/report   — 📊 Full AI spending report\n"
        "/analyze  — 📊 Same as /report\n"
        "/history  — 📋 Last 10 transactions\n"
        "/budget   — 🎯 View your budget limits\n"
        "/help     — 🆘 Usage guide\n\n"
        "📅 *Auto-reports sent to you:*\n"
        "• Every Sunday evening — weekly digest\n"
        "• 1st of each month — monthly summary"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🆘 *دليل الاستخدام / Usage Guide*\n\n"
        "*🇯🇴 أمثلة عربية:*\n"
        "• `اشتريت بقالة ب 25 دينار`\n"
        "• `دفعت 50 دينار مبارح على مطعم`\n"
        "• `اشتريت charger ب 10 JOD`\n"
        "• `دفعنا 90 دينار على العشاء، نصيبي الثلث`\n"
        "• `كيف مصاريفي هذا الشهر؟`\n\n"
        "*🇺🇸 English Examples:*\n"
        "• `spent 12 USD on groceries today`\n"
        "• `paid 15 JOD for petrol yesterday`\n"
        "• `we paid 60 JOD for dinner, my share is 1/3`\n"
        "• `how are my expenses this month?`\n\n"
        "🎙 *Voice notes fully supported!*\n\n"
        "*📅 Automatic reports:*\n"
        "• 🗓 Every Sunday → weekly spending digest\n"
        "• 📆 1st of month → full monthly analysis"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ────────────────────────────────────────────
#  TRIGGER 2 — /report and /analyze commands
# ────────────────────────────────────────────
async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    _register_user(user_id, username, update.effective_chat.id)

    await update.message.chat.send_action(ChatAction.TYPING)

    monthly = get_expenses_this_month(user_id)
    if not monthly:
        await update.message.reply_text(
            "📭 لا توجد مصاريف مسجلة هذا الشهر.\n"
            "📭 No expenses recorded this month yet.\n\n"
            "Log your first expense and I'll start tracking! 💪"
        )
        return

    lang = _detect_user_lang(monthly)
    thinking = (
        "⏳ *جاري تحليل مصاريفك…*\n"
        "_Agent 2 يقرأ بياناتك من Google Sheets…_"
        if lang == "ar" else
        "⏳ *Analyzing your expenses…*\n"
        "_Agent 2 is reading your data from Google Sheets…_"
    )
    await update.message.reply_text(thinking, parse_mode=ParseMode.MARKDOWN)
    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        summary = compute_monthly_summary(monthly)
        update_summary_sheet(summary, user_id, username)
        report  = generate_full_report(summary, lang)
        await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"[Bot] /report error: {e}")
        await update.message.reply_text(
            "⚠️ فشل إنشاء التقرير. تحقق من إعدادات Google Sheets.\n"
            "⚠️ Report failed. Check Google Sheets config."
        )


async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_report(update, ctx)


async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.chat.send_action(ChatAction.TYPING)
    rows = get_all_expenses(user_id)
    rows = rows[-10:]
    if not rows:
        await update.message.reply_text("📭 No records yet. Start logging expenses!")
        return
    lang  = rows[-1].get("Language", "en")
    title = "📋 *آخر المعاملات:*\n" if lang == "ar" else "📋 *Recent Transactions:*\n"
    lines = [title]
    for r in reversed(rows):
        lines.append(
            f"• `{r.get('Date','')}` | *{r.get('Item Name','')}* "
            f"— {r.get('Amount','')} {r.get('Currency','')} "
            f"[{r.get('Category','')}]"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_budget(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from config import CATEGORY_BUDGETS, MONTHLY_BUDGET_JOD
    lines = [
        f"🎯 *Monthly Budget Limits*\n",
        f"💰 *Total budget:* {MONTHLY_BUDGET_JOD} JOD\n",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    for cat, limit in CATEGORY_BUDGETS.items():
        lines.append(f"• {cat}: *{limit} JOD*")
    lines.append("\n_Edit these in `config.py` → CATEGORY\\_BUDGETS_")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════════════════════
#  TEXT MESSAGE HANDLER
# ════════════════════════════════════════════════════════════════════════

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user     = update.effective_user
    text     = update.message.text.strip()
    user_id  = user.id
    username = user.username or user.first_name
    _register_user(user_id, username, update.effective_chat.id)

    logger.info(f"[Bot] Text from {user_id}: {text!r}")
    await update.message.chat.send_action(ChatAction.TYPING)

    # Run full pipeline — Trigger 1 (quick tip) fires inside pipeline.run()
    result = pipeline.run(
        raw_text=text,
        user_id=user_id,
        username=username,
        with_recommendation=False,
    )

    if result.reply_text:
        await update.message.reply_text(
            result.reply_text, parse_mode=ParseMode.MARKDOWN
        )

    if result.language:
        ACTIVE_USERS.setdefault(user_id, {})["lang"] = result.language


# ════════════════════════════════════════════════════════════════════════
#  VOICE MESSAGE HANDLER
# ════════════════════════════════════════════════════════════════════════

async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user     = update.effective_user
    user_id  = user.id
    username = user.username or user.first_name
    voice    = update.message.voice or update.message.audio
    _register_user(user_id, username, update.effective_chat.id)

    await update.message.reply_text(
        "🎙 *جاري تحليل رسالتك الصوتية…*\n_Transcribing with Whisper…_",
        parse_mode=ParseMode.MARKDOWN
    )
    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        transcript = await transcribe_voice_message(
            ctx.bot, voice.file_id, model_size=WHISPER_MODEL
        )
    except RuntimeError as e:
        await update.message.reply_text(
            f"❌ فشل تحليل الصوت:\n`{e}`\n\n"
            "Install: `pip install openai-whisper pydub` and `apt install ffmpeg`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if not transcript:
        await update.message.reply_text(
            "❌ لم أسمع شيئاً واضحاً. حاول مجدداً.\n❌ Could not transcribe."
        )
        return

    lang = detect_language(transcript)
    await update.message.reply_text(
        f"📝 *{'فهمت' if lang == 'ar' else 'Heard'}:*\n_{transcript}_",
        parse_mode=ParseMode.MARKDOWN
    )
    await update.message.chat.send_action(ChatAction.TYPING)

    result = pipeline.run(
        raw_text=transcript,
        user_id=user_id,
        username=username,
        with_recommendation=False,
    )

    if result.language:
        ACTIVE_USERS.setdefault(user_id, {})["lang"] = result.language

    if result.reply_text:
        await update.message.reply_text(
            result.reply_text, parse_mode=ParseMode.MARKDOWN
        )


# ════════════════════════════════════════════════════════════════════════
#  TRIGGER 3 — Weekly digest (every Sunday 20:00 UTC)
# ════════════════════════════════════════════════════════════════════════

async def _send_weekly_digest(context: ContextTypes.DEFAULT_TYPE):
    logger.info("[Scheduler] 🗓 Sending weekly digest to all users…")
    if not ACTIVE_USERS:
        return

    for user_id, info in list(ACTIVE_USERS.items()):
        try:
            monthly = get_expenses_this_month(user_id)
            if not monthly:
                continue
            lang    = info.get("lang", "en")
            summary = compute_monthly_summary(monthly)
            report  = generate_weekly_digest(summary, lang)
            await context.bot.send_message(
                chat_id=info["chat_id"],
                text=report,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"[Scheduler] ✅ Weekly digest sent → user {user_id}")
        except Exception as e:
            logger.error(f"[Scheduler] Weekly digest failed for {user_id}: {e}")


# ════════════════════════════════════════════════════════════════════════
#  TRIGGER 4 — Monthly summary (1st of each month 09:00 UTC)
# ════════════════════════════════════════════════════════════════════════

async def _send_monthly_summary(context: ContextTypes.DEFAULT_TYPE):
    if datetime.utcnow().day != 1:
        return   # Job runs daily, only fires on the 1st

    logger.info("[Scheduler] 📆 Sending monthly summary to all users…")
    if not ACTIVE_USERS:
        return

    from calendar import month_name
    now        = datetime.utcnow()
    last_month = (now.month - 2) % 12 + 1
    last_year  = now.year if now.month > 1 else now.year - 1
    period     = f"{month_name[last_month]} {last_year}"

    for user_id, info in list(ACTIVE_USERS.items()):
        try:
            monthly = get_expenses_this_month(user_id)
            if not monthly:
                continue
            lang    = info.get("lang", "en")
            summary = compute_monthly_summary(monthly)
            update_summary_sheet(summary, user_id, info["username"])
            report  = generate_monthly_summary(summary, lang, month_label=period)
            await context.bot.send_message(
                chat_id=info["chat_id"],
                text=report,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"[Scheduler] ✅ Monthly summary sent → user {user_id}")
        except Exception as e:
            logger.error(f"[Scheduler] Monthly summary failed for {user_id}: {e}")


# ════════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════════

def _detect_user_lang(rows: list) -> str:
    ar = sum(1 for r in rows[-5:] if r.get("Language") == "ar")
    return "ar" if ar >= 3 else "en"


# ════════════════════════════════════════════════════════════════════════
#  APPLICATION BUILDER
# ════════════════════════════════════════════════════════════════════════

def build_app() -> Application:
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("report",  cmd_report))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("budget",  cmd_budget))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO,   handle_voice))

    # Scheduled jobs
    app.job_queue.run_daily(
        _send_weekly_digest,
        time=dtime(hour=20, minute=0),
        days=(6,),              # Sunday
        name="weekly_digest",
    )
    app.job_queue.run_daily(
        _send_monthly_summary,
        time=dtime(hour=9, minute=0),
        name="monthly_summary",
    )

    logger.info("[Bot] ✅ Handlers + schedulers registered")
    logger.info("[Bot]    Trigger 1 → after every expense (quick tip)")
    logger.info("[Bot]    Trigger 2 → /report or /analyze command")
    logger.info("[Bot]    Trigger 3 → every Sunday 20:00 UTC (weekly)")
    logger.info("[Bot]    Trigger 4 → 1st of month 09:00 UTC (monthly)")
    return app
