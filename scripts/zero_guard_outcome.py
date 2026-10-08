"""Classify one Cortex Analyst run on a zero-denominator question (mission-os #1377).
  number           SQL returned a number
  empty            SQL returned no rows, and the text does not say there is no data
  empty_explained  SQL returned no rows, and the text says there is no data for that slice
  null             SQL returned NULL, text silent
  null_explained   SQL returned NULL, text says there is no data
  error            the returned SQL raised when executed (e.g. Division by zero)
  declined         no SQL at all (suggestions or text only)"""
from __future__ import annotations
import re

NO_DATA = re.compile(r"\bno (partner )?(sessions?|data|records?|rows?|bookings?)\b|\bwere no\b|\bwas no\b|\bundefined\b|\bnot available\b", re.I)


def outcome(row: dict) -> str:
    if row["kind"] != "sql":
        return "declined"
    v = row["value"].strip()
    if v.startswith("ERR"):
        return "error"
    explained = bool(NO_DATA.search(row.get("text", "")))
    if v == "EMPTY":
        return "empty_explained" if explained else "empty"
    if re.fullmatch(r"\((None,?\s*)+\)", v):
        return "null_explained" if explained else "null"
    return "number" if re.search(r"\d", v) else "empty"
