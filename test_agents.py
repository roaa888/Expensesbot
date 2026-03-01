
"""
test_agents.py — Tests for Agent 1 (Parser) & Agent 2 (Recommender)
Run with:  python3 test_agents.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from agents.parsing_agent import parse

PASS = "✅ PASS"
FAIL = "❌ FAIL"

TEST_CASES = [
    # (label, input, expected_intent, expected_lang, expected_amount, expected_currency)
    ("Arabic expense — Eastern numerals",
     "اشتريت إلكترونيات ب ٢٠٠ دينار",
     "log_expense", "ar", 200, "JOD"),

    ("English expense",
     "spent 25 USD on groceries today",
     "log_expense", "en", 25, "USD"),

    ("Arabizi — mixed language with English tech term",
     "اشتريت charger ب 10 JOD",
     "log_expense", "ar", 10, "JOD"),

    ("Arabic bill split — calculates 90÷3=30",
     "دفعنا ٩٠ دينار على العشاء، نصيبي الثلث",
     "split_bill", "ar", 30, "JOD"),

    ("English bill split — 60÷3=20",
     "We paid 60 JOD for dinner, my share is 1/3",
     "split_bill", "en", 20, "JOD"),

    ("Arabic summary query",
     "كيف كانت مصاريفي هذا الشهر؟",
     "query_report", "ar", None, None),

    ("Relative date — yesterday (مبارح)",
     "اشتريت قهوة ب 3 دينار مبارح",
     "log_expense", "ar", 3, "JOD"),

    ("English with time context",
     "paid 45 JOD for electricity bill this morning",
     "log_expense", "en", 45, "JOD"),
]


def run():
    print("=" * 65)
    print("  🧪 Agent 1 (Parser) Test Suite")
    print("=" * 65)

    passed = 0
    for i, (label, text, exp_intent, exp_lang, exp_amount, exp_cur) in enumerate(TEST_CASES, 1):
        print(f"\n[{i}] {label}")
        print(f"    Input: {text!r}")
        try:
            result = parse(text)
            ok = True
            notes = []

            if result.get("intent") != exp_intent:
                notes.append(f"intent: {result.get('intent')!r} ≠ {exp_intent!r}")
                ok = False
            if result.get("language") != exp_lang:
                notes.append(f"lang: {result.get('language')!r} ≠ {exp_lang!r}")
                ok = False
            if exp_amount is not None:
                got_amount = result.get("amount")
                if not got_amount:
                    split = result.get("split_info") or {}
                    got_amount = split.get("user_share")
                if got_amount != exp_amount:
                    notes.append(f"amount: {got_amount!r} ≠ {exp_amount!r}")
                    ok = False
            if exp_cur and result.get("currency") != exp_cur:
                notes.append(f"currency: {result.get('currency')!r} ≠ {exp_cur!r}")
                ok = False

            status = PASS if ok else FAIL
            if ok:
                passed += 1
            print(f"    {status}")
            if notes:
                for n in notes:
                    print(f"    ⚠️  {n}")
            print(f"    → intent={result.get('intent')}, amount={result.get('amount')}, "
                  f"currency={result.get('currency')}, lang={result.get('language')}, "
                  f"date={result.get('expense_date')}")
            if result.get("split_info"):
                print(f"    → split={result.get('split_info')}")
            print(f"    → category={result.get('category')}, item={result.get('item_name')!r}")

        except Exception as e:
            print(f"    {FAIL} — Exception: {e}")

    print("\n" + "=" * 65)
    print(f"  Results: {passed}/{len(TEST_CASES)} passed")
    if passed == len(TEST_CASES):
        print("  🎉 All tests passed! Agent 1 is working correctly.")
    else:
        print(f"  ⚠️  {len(TEST_CASES)-passed} tests failed.")
    print("=" * 65)

    # Quick Agent 2 smoke test
    print("\n\n" + "=" * 65)
    print("  🧪 Agent 2 (Recommender) Smoke Test")
    print("=" * 65)
    from agents.recommendation_agent import generate

    mock_summary = {
        "count": 15,
        "total_jod": 420.5,
        "by_category": {
            "Food & Dining":      {"total": 150.0, "count": 8, "currency": "JOD"},
            "Groceries":          {"total": 95.0,  "count": 4, "currency": "JOD"},
            "Transportation":     {"total": 75.5,  "count": 2, "currency": "JOD"},
            "Entertainment":      {"total": 60.0,  "count": 1, "currency": "JOD"},
            "Personal Care":      {"total": 40.0,  "count": 1, "currency": "JOD"},
        },
        "by_currency": {"JOD": 420.5},
        "month": "February 2026"
    }

    for lang in ("en", "ar"):
        print(f"\n  Testing language: {lang.upper()}")
        try:
            rec = generate(mock_summary, lang)
            preview = rec[:300].replace("\n", " ") + "…"
            print(f"  ✅ Generated ({len(rec)} chars)")
            print(f"  Preview: {preview}")
        except Exception as e:
            print(f"  ❌ Failed: {e}")

    print("\n" + "=" * 65)
    print("  Done! If all tests pass, run:  python3 main.py")
    print("=" * 65)


if __name__ == "__main__":
    run()
