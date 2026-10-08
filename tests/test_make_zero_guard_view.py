"""guarded() changes exactly the ratio and the name, and refuses ambiguous DDL. Run: python3 tests/test_make_zero_guard_view.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from make_zero_guard_view import guarded, NEW  # noqa: E402

LOC = "DB.S"
ok = "create or replace semantic view DB.S.TRUST_DEMO_SV\n  metrics ( conversion_rate AS bookings.bookings / sessions.session_count )"
bad = 0
out = guarded(ok, LOC)
bad += "TRUST_DEMO_SV_ZG\n" not in out or NEW not in out or "/ sessions.session_count )" in out
for ddl in (ok.replace("bookings.bookings / sessions.session_count", "x"), ok + "\n" + "bookings.bookings / sessions.session_count"):
    try:
        guarded(ddl, LOC); bad += 1
    except ValueError:
        pass
print("PASS 3 / 3" if not bad else "FAILED"); sys.exit(1 if bad else 0)
