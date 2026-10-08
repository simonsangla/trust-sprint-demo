"""One classifier for a Cortex Analyst run, shared by the evidence page, the post renderer and the images.
  declined        no SQL returned (Cortex declined or asked)
  sql_refusal     SQL returned only a refusal message, no number
  said_no_number  the answer text says it cannot be computed, and the SQL computed a number
  number          answered with a number"""
from __future__ import annotations
import re

REFUSE = re.compile(r"cannot be (?:\w+ )?(computed|calculated)|not defined|unable|cannot calculate|unanswerable", re.I)
OUTCOMES = ("declined", "sql_refusal", "said_no_number", "number")


def outcome(row: dict) -> str:
    if row["kind"] != "sql":
        return "declined"
    v = row["value"]
    if REFUSE.search(v):
        return "sql_refusal"
    if not re.search(r"\d", v) or v.startswith(("EMPTY", "ERR")):
        return "declined"
    return "said_no_number" if REFUSE.search(row["text"]) else "number"


def gave_number(o: str) -> bool:
    return o in ("said_no_number", "number")
