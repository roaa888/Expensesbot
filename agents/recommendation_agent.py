"""
agents/recommendation_agent.py
════════════════════════════════
AGENT 2 — The Recommendation Agent

TRIGGERS (all 4 active):
  1. After every expense logged        → quick inline tip
  2. When user sends /report or /analyze → full deep report
  3. Automatically every Sunday        → weekly digest
  4. Automatically on 1st of month     → monthly summary

ANALYSIS COVERS:
  • Spending level  — 🔴 High / 🟡 Medium / 🟢 Good vs budget
  • Category breakdown — top spenders, budget breaches
  • Smart saving tips — data-driven actionable advice
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import logging
import json
from datetime import datetime

from utils.bedrock import invoke
from config import MONTHLY_BUDGET_JOD, CATEGORY_BUDGETS

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
#  SYSTEM PROMPT — Deep Report (used for /report, weekly, monthly)
# ─────────────────────────────────────────────────────────────────────
DEEP_REPORT_PROMPT = """
You are a warm, empathetic, and highly intelligent Bilingual Personal Finance Advisor.
You help users understand their spending and make better financial decisions.

You will receive a spending summary JSON and must produce a structured report.

━━━ ANALYSIS FRAMEWORK ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SECTION 1 — SPENDING LEVEL BADGE
Compute: (total_jod / monthly_budget) × 100
  • ≥ 100% → 🔴 HIGH — "مرتفع جداً" / "Too High"
  • 75–99% → 🟡 MEDIUM — "متوسط" / "Getting There"
  • 50–74% → 🟢 GOOD — "جيد" / "Good"
  • < 50%  → ✅ EXCELLENT — "ممتاز" / "Excellent"

SECTION 2 — CATEGORY BREAKDOWN
For each category in the data, show:
  • Amount spent vs its budget limit
  • Status: ✅ under | ⚠️ near (>80%) | 🚨 over budget
  • Sort by amount descending (biggest spender first)

SECTION 3 — SMART SAVING TIPS
Generate 3–5 specific tips based on the ACTUAL data:
  • If Food spending is high → suggest meal prep, cooking at home
  • If Electronics overspent → suggest waiting 48h before buying
  • If many small transactions in one category → suggest weekly batch
  • If good month → positively reinforce the behavior
  • Make tips SPECIFIC to the numbers, not generic

SECTION 4 — MOTIVATIONAL CLOSE
One personalized closing sentence based on their actual performance.

━━━ STRICT RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LANGUAGE: If user_language="ar" → ENTIRE response in Arabic. If "en" → English.
FORMAT: Telegram markdown — *bold*, use emojis generously
LENGTH: 250–400 words. Be insightful, not generic.
NO JSON: Return only the natural-language report.

CURRENT PERIOD: {period}
MONTHLY BUDGET: {budget} JOD
CATEGORY BUDGETS (JOD): {category_budgets}
"""

# ─────────────────────────────────────────────────────────────────────
#  SYSTEM PROMPT — After-Expense Quick Tip (inline, post-log)
# ─────────────────────────────────────────────────────────────────────
QUICK_TIP_PROMPT = """
You are Mia 💰 — a cheerful bilingual finance assistant. A user just logged an expense.
Give ONE short, warm, specific reaction — like a supportive friend would.

Rules:
- Maximum 2 sentences, conversational tone
- If over budget in this category → kind nudge, not a lecture
- If doing well → genuine celebration
- Feel personal, not robotic
- LANGUAGE: respond in {language}
- 1–2 emojis maximum
- Do NOT repeat the expense details

MONTHLY BUDGET: {budget} JOD
CATEGORY BUDGETS: {category_budgets}
"""

GENERAL_QUESTION_PROMPT = """
You are Mia 💰 — a warm, friendly, and knowledgeable bilingual personal finance assistant!
You love helping with anything finance-related AND you're great at general conversation too.

Your personality:
- Cheerful and encouraging 😊
- Knowledgeable about personal finance, budgeting, saving, and smart spending
- Fluent in Arabic and English — always respond in the same language the user wrote in
- You make finance feel approachable and fun, never scary or boring
- You can answer general questions, give advice, and have casual conversations

Keep responses concise but warm — like a knowledgeable friend texting back.
Use emojis naturally. Max 150 words unless the question genuinely needs more.

Bot features you can tell users about:
- Log expenses by typing or sending a voice note 🎙️
- Supports Arabic, English, and Arabizi
- Splits bills automatically
- Tracks spending in Google Sheets
- Weekly & monthly AI spending reports
- Commands: /report, /analyze, /history, /budget, /help
"""


# ─────────────────────────────────────────────────────────────────────
#  PUBLIC FUNCTIONS
# ─────────────────────────────────────────────────────────────────────

def answer_general_question(question: str, language: str = "en") -> str:
    """
    Agent 2 answers general questions and casual conversation.
    Used when intent = "general_question".
    High temperature for natural, varied responses.
    """
    logger.info(f"[Agent2] Answering general question (lang={language})")
    response = invoke(GENERAL_QUESTION_PROMPT, question, max_tokens=400, temperature=1.0)
    logger.info("[Agent2] ✅ General answer generated")
    return response


def generate_full_report(summary: dict, language: str = "en",
                         period_label: str = None) -> str:
    """
    Full deep report — used for:
      • /report command
      • /analyze command
      • Weekly auto-digest
      • Monthly auto-summary

    Returns a Telegram-formatted string.
    """
    if not period_label:
        period_label = datetime.utcnow().strftime("%B %Y")

    system = (
        DEEP_REPORT_PROMPT
        .replace("{period}", period_label)
        .replace("{budget}", str(MONTHLY_BUDGET_JOD))
        .replace("{category_budgets}", json.dumps(CATEGORY_BUDGETS, ensure_ascii=False))
    )

    user_msg = (
        f"User language: {language}\n\n"
        f"Spending summary for {period_label}:\n"
        f"{json.dumps(summary, indent=2, ensure_ascii=False)}\n\n"
        f"Produce a full spending report with all 4 sections."
    )

    logger.info(f"[Agent2] Generating FULL report (lang={language}, period={period_label})")
    text = invoke(system, user_msg, max_tokens=1800, temperature=0.9)
    logger.info("[Agent2] ✅ Full report generated")
    return text


def generate_quick_tip(summary: dict, last_expense: dict,
                       language: str = "en") -> str:
    """
    Short 1–2 sentence tip shown inline after every logged expense.

    Parameters:
      summary      — current month summary dict
      last_expense — the parsed dict of the expense just logged
      language     — "ar" or "en"
    """
    system = (
        QUICK_TIP_PROMPT
        .replace("{language}", "Arabic" if language == "ar" else "English")
        .replace("{budget}", str(MONTHLY_BUDGET_JOD))
        .replace("{category_budgets}", json.dumps(CATEGORY_BUDGETS, ensure_ascii=False))
    )

    cat_total = 0.0
    cat_budget = CATEGORY_BUDGETS.get(last_expense.get("category", "Other"), 999)
    for cat, data in summary.get("by_category", {}).items():
        if cat == last_expense.get("category"):
            cat_total = data.get("total", 0)
            break

    user_msg = (
        f"User language: {language}\n"
        f"Just logged: {last_expense.get('amount')} {last_expense.get('currency')} "
        f"on {last_expense.get('category')} (item: {last_expense.get('item_name')})\n"
        f"This category total this month: {cat_total} JOD / budget: {cat_budget} JOD\n"
        f"Overall month total: {summary.get('total_jod', 0)} JOD / {MONTHLY_BUDGET_JOD} JOD\n\n"
        f"Give one short specific tip."
    )

    logger.info(f"[Agent2] Generating quick tip (lang={language})")
    try:
        text = invoke(system, user_msg, max_tokens=120)
        logger.info(f"[Agent2] ✅ Quick tip: {text[:80]}")
        return text
    except Exception as e:
        logger.warning(f"[Agent2] Quick tip failed: {e}")
        return ""


def generate_weekly_digest(summary: dict, language: str = "en",
                           week_label: str = None) -> str:
    """Auto-sent every Sunday — wraps generate_full_report with week framing."""
    if not week_label:
        week_label = f"Week of {datetime.utcnow().strftime('%d %B %Y')}"

    header_ar = f"📅 *ملخص أسبوعي — {week_label}*\n\n"
    header_en = f"📅 *Weekly Digest — {week_label}*\n\n"

    report = generate_full_report(summary, language, period_label=week_label)
    return (header_ar if language == "ar" else header_en) + report


def generate_monthly_summary(summary: dict, language: str = "en",
                              month_label: str = None) -> str:
    """Auto-sent on 1st of each month for the previous month."""
    if not month_label:
        month_label = datetime.utcnow().strftime("%B %Y")

    header_ar = f"🗓 *تقرير نهاية الشهر — {month_label}*\n\n"
    header_en = f"🗓 *End-of-Month Report — {month_label}*\n\n"

    report = generate_full_report(summary, language, period_label=month_label)
    return (header_ar if language == "ar" else header_en) + report


# ─────────────────────────────────────────────────────────────────────
#  BUDGET STATUS HELPER  (used by pipeline for the inline status bar)
# ─────────────────────────────────────────────────────────────────────

def budget_status_line(summary: dict, language: str = "en") -> str:
    """
    Returns a single status line shown after every logged expense.
    e.g.  🟡 This month: 380 JOD / 500 JOD (76%) — Approaching limit
    """
    total  = summary.get("total_jod", 0)
    budget = MONTHLY_BUDGET_JOD
    pct    = round((total / budget) * 100, 1) if budget else 0

    if pct >= 100:
        emoji, ar, en = "🔴", "تجاوزت الميزانية", "Over budget"
    elif pct >= 75:
        emoji, ar, en = "🟡", "قريب من الحد", "Approaching limit"
    elif pct >= 50:
        emoji, ar, en = "🟢", "جيد", "Good"
    else:
        emoji, ar, en = "✅", "ممتاز", "Excellent"

    label = ar if language == "ar" else en
    if language == "ar":
        return (f"\n\n{emoji} *هذا الشهر:* {total} JOD من {budget} JOD "
                f"({pct}%) — {label}")
    return (f"\n\n{emoji} *This month:* {total} JOD / {budget} JOD "
            f"({pct}%) — {label}")