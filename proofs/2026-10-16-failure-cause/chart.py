"""Bar chart of questions per failure_cause, from the 'Causes:' line that check.sh prints.

Usage: bash check.sh | uvx --with matplotlib python chart.py OUT.png
"""
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

line = next((l for l in sys.stdin if l.startswith("Causes:")), None)
if line is None:
    sys.exit("FAIL: no 'Causes:' line on stdin")
counts = {k: int(v) for v, k in re.findall(r"(\d+) (none|definition|filter|join|model)", line)}
order = ["definition", "filter", "join", "model", "none"]
vals = [counts.get(k, 0) for k in order]
fig, ax = plt.subplots(figsize=(6, 3.2), dpi=150)
bars = ax.bar(order, vals, color=["#c2410c", "#c2410c", "#c2410c", "#c2410c", "#9ca3af"])
ax.bar_label(bars, padding=2)
ax.set_ylabel("questions")
ax.set_title("Cortex Analyst run 2026-10-08: questions per failure cause", fontsize=10)
ax.spines[["top", "right"]].set_visible(False)
ax.set_ylim(0, max(vals) + 1)
fig.tight_layout()
fig.savefig(sys.argv[1])
print("wrote", sys.argv[1], dict(zip(order, vals)))
