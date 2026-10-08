"""Fixture tests for scripts/zero_guard_outcome.py (mission-os #1377). Run: python3 tests/test_zero_guard_outcome.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from zero_guard_outcome import outcome  # noqa: E402

CASES = [
    ({"kind": "sql", "value": "(Decimal('0.062500'),)", "text": "This is our interpretation"}, "number"),
    ({"kind": "sql", "value": "EMPTY", "text": "This is our interpretation of your question"}, "empty"),
    ({"kind": "sql", "value": "(None,)", "text": "conversion rate"}, "null"),
    ({"kind": "sql", "value": "ERR 100051 (22012): Division by zero", "text": "x"}, "error"),
    ({"kind": "suggestions", "value": "", "text": "I'm sorry, there is no partner data"}, "declined"),
    ({"kind": "sql", "value": "EMPTY", "text": "There were no partner sessions in January 2026, so the rate is undefined."}, "empty_explained"),
    ({"kind": "sql", "value": "(None,)", "text": "No sessions were recorded for the partner channel in that period."}, "null_explained"),
    ({"kind": "text_only", "value": "", "text": "no data"}, "declined"),
]


def main() -> int:
    bad = 0
    for row, want in CASES:
        got = outcome(row)
        if got != want:
            print("FAIL", row["value"][:30], "|", row["text"][:40], "got", got, "want", want); bad += 1
    print("PASS" if not bad else "FAILED", len(CASES) - bad, "/", len(CASES))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
