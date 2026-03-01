"""
pipeline.py
═══════════
THE MAIN PIPELINE ORCHESTRATOR

This is the brain that connects all components in order.

FULL FLOW:
                                            ┌─────────────────────────────┐
  User Input (Telegram)                     │                             │
       │                                    │   AGENT 1: PARSING AGENT    │
       ├─ Text message ──────────────────►  │   (parsing_agent.py)        │
       │                                    │                             │
       └─ Voice note ──► Whisper STT ─────► │   text → structured JSON   │
                          (voice.py)        │                             │
                                            └──────────────┬──────────────┘
                                                           │
                                                           │ structured JSON
                                                           ▼
                                            ┌─────────────────────────────┐
                                            │   GOOGLE SHEETS WRITER      │
                                            │   (sheets_agent.py)         │
                                            │                             │
                                            │   JSON → row in sheet       │
                                            └──────────────┬──────────────┘
                                                           │
                                                           │ monthly summary
                                                           ▼
                                            ┌─────────────────────────────┐
                                            │   AGENT 2: RECOMMENDER      │
                                            │   (recommendation_agent.py) │
                                            │                             │
                                            │   summary → advice message  │
                                            └──────────────┬──────────────┘
                                                           │
                                                           ▼
                                               Reply to user (Telegram)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from datetime import datetime

from agents.parsing_agent      import parse as agent1_parse
from agents.sheets_agent       import (log_expense, get_expenses_this_month,
                                        compute_monthly_summary,
                                        update_summary_sheet,
                                        delete_all_expenses,
                                        delete_last_expense)
from agents.recommendation_agent import (
    generate_full_report,
    generate_quick_tip,
    budget_status_line,
    answer_general_question,
)

logger = logging.getLogger(__name__)


class PipelineResult:
    """Returned by run() to tell bot.py exactly what to send back."""
    def __init__(self):
        self.success       = False
        self.intent        = "unknown"
        self.parsed        = {}
        self.row_id        = None
        self.language      = "en"
        self.reply_text    = ""
        self.recommendation = ""
        self.error         = ""


def run(raw_text: str, user_id: int, username: str,
        with_recommendation: bool = False) -> PipelineResult:
    """
    Full pipeline execution.

    Parameters:
      raw_text            — the user's text (from message or Whisper transcript)
      user_id             — Telegram user_id
      username            — Telegram username or first_name
      with_recommendation — if True, always run Agent 2 after logging

    Returns:
      PipelineResult with all data needed to compose the Telegram reply
    """
    result = PipelineResult()

    # ──────────────────────────────────────────────────────────────
    # STEP 1  →  AGENT 1: Parse text into structured JSON
    # ──────────────────────────────────────────────────────────────
    try:
        logger.info(f"[Pipeline] ▶ Step 1 — Parsing: {raw_text!r}")
        parsed = agent1_parse(raw_text)
        result.parsed   = parsed
        result.intent   = parsed.get("intent", "unknown")
        result.language = parsed.get("language", "en")
        logger.info(f"[Pipeline] ✅ Parsed intent={result.intent}, "
                    f"amount={parsed.get('amount')}, currency={parsed.get('currency')}")
    except Exception as e:
        logger.error(f"[Pipeline] ❌ Agent 1 failed: {e}")
        result.error = str(e)
        result.reply_text = _error_msg("en")
        return result

    lang = result.language

    # ──────────────────────────────────────────────────────────────
    # STEP 2  →  Route by intent
    # ──────────────────────────────────────────────────────────────

    # ── A) Log an expense ──────────────────────────────────────────
    if result.intent in ("log_expense", "split_bill"):

        if not parsed.get("amount"):
            result.reply_text = (
                "⚠️ لم أتمكن من تحديد المبلغ. أعد المحاولة مثل:\n"
                "`اشتريت غداء ب 5 دينار`"
                if lang == "ar" else
                "⚠️ Could not detect the amount. Try:\n"
                "`spent 5 JOD on lunch`"
            )
            return result

        # STEP 2A → Write to Google Sheets
        try:
            logger.info("[Pipeline] ▶ Step 2 — Writing to Google Sheets…")
            logger.info(f"[Pipeline] parsed={parsed}")
            row_id = log_expense(parsed, user_id, username)
            result.row_id   = row_id
            result.success  = True
            logger.info(f"[Pipeline] ✅ Logged as row #{row_id}")
        except Exception as e:
            import traceback
            logger.error(f"[Pipeline] ❌ Sheets write failed: {e}")
            logger.error(traceback.format_exc())
            result.error = str(e)
            result.reply_text = _sheets_error_msg(lang)
            return result

        # STEP 2B → Build the confirmation card
        result.reply_text = _build_expense_card(parsed, row_id, lang)

        # STEP 2C → Budget status bar (always shown)
        try:
            monthly = get_expenses_this_month(user_id)
            summary = compute_monthly_summary(monthly)
            result.reply_text += budget_status_line(summary, lang)
        except Exception as e:
            logger.warning(f"[Pipeline] Could not get budget status: {e}")
            summary = None

        # STEP 2D → Quick AI tip (always shown after every expense)
        if summary:
            try:
                logger.info("[Pipeline] ▶ Step 3 — Generating quick tip…")
                tip = generate_quick_tip(summary, parsed, lang)
                if tip:
                    result.reply_text += f"\n\n💡 _{tip}_"
            except Exception as e:
                logger.warning(f"[Pipeline] Quick tip failed: {e}")

        # STEP 2E → Full recommendation if explicitly requested
        if with_recommendation:
            try:
                logger.info("[Pipeline] ▶ Full report requested — running Agent 2…")
                if not summary:
                    monthly = get_expenses_this_month(user_id)
                    summary = compute_monthly_summary(monthly)
                update_summary_sheet(summary, user_id, username)
                result.recommendation = generate_full_report(summary, lang)
            except Exception as e:
                logger.warning(f"[Pipeline] Full recommendation failed: {e}")

    # ── B) User explicitly asks for report ─────────────────────────
    elif result.intent == "query_report":
        try:
            logger.info("[Pipeline] ▶ Report request — querying Sheets + Agent 2…")
            monthly = get_expenses_this_month(user_id)
            summary = compute_monthly_summary(monthly)
            update_summary_sheet(summary, user_id, username)
            result.recommendation = generate_full_report(summary, lang)
            result.reply_text = result.recommendation
            result.success = True
        except Exception as e:
            logger.error(f"[Pipeline] ❌ Report generation failed: {e}")
            result.error = str(e)
            result.reply_text = _error_msg(lang)

    # ── C) Delete expenses ───────────────────────────────────────────────
    elif result.intent == "delete_expenses":
        scope = (parsed.get("note") or "all").lower()
        try:
            if "last" in scope:
                deleted = delete_last_expense(user_id)
                if deleted:
                    item = deleted.get("Item Name", "")
                    amount = deleted.get("Amount", "")
                    currency = deleted.get("Currency", "JOD")
                    date = deleted.get("Date", "")
                    result.reply_text = (
                        f"🗑 *تم حذف آخر مصروف:*\n• {item} — {amount} {currency} ({date})"
                        if lang == "ar" else
                        f"🗑 *Last expense deleted:*\n• {item} — {amount} {currency} ({date})"
                    )
                else:
                    result.reply_text = (
                        "📭 لا يوجد مصاريف لحذفها." if lang == "ar"
                        else "📭 No expenses found to delete."
                    )
            else:
                count = delete_all_expenses(user_id)
                if count > 0:
                    result.reply_text = (
                        f"🗑 *تم حذف جميع مصاريفك!*\n_{count} سجل تم مسحه._\n\nابدأ من جديد 💪"
                        if lang == "ar" else
                        f"🗑 *All expenses deleted!*\n_{count} records cleared._\n\nFresh start! 💪"
                    )
                else:
                    result.reply_text = (
                        "📭 لا يوجد مصاريف لحذفها." if lang == "ar"
                        else "📭 No expenses found to delete."
                    )
            result.success = True
        except Exception as e:
            logger.error(f"[Pipeline] ❌ Delete failed: {e}")
            result.reply_text = _error_msg(lang)

    # ── D) History / last transactions ────────────────────────────
    elif result.intent == "query_history":
        result.reply_text = (
            "📋 استخدم /history لرؤية آخر المعاملات."
            if lang == "ar" else
            "📋 Use /history to see recent transactions."
        )
        result.success = True

    # ── D) General question / chat ─────────────────────────────
    elif result.intent == "general_question":
        try:
            answer = answer_general_question(raw_text, lang)
            result.reply_text = answer
            result.success = True
        except Exception as e:
            logger.error(f"[Pipeline] General question failed: {e}")
            result.reply_text = (
                "عذراً، حدث خطأ. حاول مجدداً! 😊" if lang == "ar"
                else "Oops, something went wrong. Try again! 😊"
            )

    # ── F) Unknown — route through Mia instead of cold error message ──
    else:
        try:
            answer = answer_general_question(raw_text, lang)
            result.reply_text = answer
            result.success = True
        except Exception:
            result.reply_text = (
                "مرحبا! 😊 جرب أن تقول مثلاً:\n`اشتريت غداء ب 5 دينار`\nأو أرسل `/help`"
                if lang == "ar" else
                "Hey! 😊 Try something like:\n`spent 5 JOD on lunch`\nor send `/help`"
            )

    return result


# ──────────────────────────────────────────────────────────────────────────────
#  Formatting helpers
# ──────────────────────────────────────────────────────────────────────────────

def _build_expense_card(parsed: dict, row_id: int, lang: str) -> str:
    amount   = parsed.get("amount")
    currency = parsed.get("currency", "JOD")
    category = parsed.get("category", "Other")
    item     = parsed.get("item_name", "")
    date     = parsed.get("expense_date", datetime.utcnow().strftime("%Y-%m-%d"))
    day      = parsed.get("day_of_week", "")
    time_val = parsed.get("time_of_day", "")
    note     = parsed.get("note", "")
    split    = parsed.get("split_info")

    if lang == "ar":
        header = f"✅ تم تسجيل المصروف!"
        lines = [
            header, "",
            f"🗂 *الرقم:* #{row_id}",
            f"🛒 *الصنف:* {item}",
            f"💰 *المبلغ:* {amount} {currency}",
            f"📂 *الفئة:* {category}",
            f"📅 *التاريخ:* {date}  ({day})",
        ]
        if time_val:
            lines.append(f"🕐 *الوقت:* {time_val}")
        if note:
            lines.append(f"📝 *ملاحظة:* {note}")
        if split:
            lines += [
                "",
                f"👥 *تقسيم الفاتورة:*",
                f"   الإجمالي: {split.get('total_bill')} {currency}",
                f"   عدد الأشخاص: {split.get('number_of_people')}",
                f"   نصيبك: *{split.get('user_share')} {currency}*",
            ]
    else:
        header = f"✅ Expense logged!"
        lines = [
            header, "",
            f"🗂 *ID:* #{row_id}",
            f"🛒 *Item:* {item}",
            f"💰 *Amount:* {amount} {currency}",
            f"📂 *Category:* {category}",
            f"📅 *Date:* {date}  ({day})",
        ]
        if time_val:
            lines.append(f"🕐 *Time:* {time_val}")
        if note:
            lines.append(f"📝 *Note:* {note}")
        if split:
            lines += [
                "",
                f"👥 *Bill Split:*",
                f"   Total: {split.get('total_bill')} {currency}",
                f"   People: {split.get('number_of_people')}",
                f"   Your share: *{split.get('user_share')} {currency}*",
            ]

    return "\n".join(lines)


def _error_msg(lang: str) -> str:
    if lang == "ar":
        return "⚠️ حدث خطأ أثناء المعالجة. حاول مجدداً."
    return "⚠️ A processing error occurred. Please try again."


def _sheets_error_msg(lang: str) -> str:
    if lang == "ar":
        return (
            "❌ فشل الحفظ في Google Sheets.\n"
            "تأكد من:\n"
            "• ملف `google_credentials.json` موجود\n"
            "• تم مشاركة الـ Sheet مع حساب الخدمة\n"
            "• `GOOGLE_SHEET_ID` صحيح في `config.py`"
        )
    return (
        "❌ Failed to save to Google Sheets.\n"
        "Please check:\n"
        "• `google_credentials.json` file exists\n"
        "• The Sheet is shared with your service account email\n"
        "• `GOOGLE_SHEET_ID` is correct in `config.py`"
    )