#!/usr/bin/env python3
"""Ask REPO_REVIEW_AGENT one question over the Cortex Agents REST API and save the answer (mission-os#1531 slice C).

Usage:
  SNOWFLAKE_DEFAULT_CONNECTION_NAME=mission_os_dogfood uv run --with 'snowflake-connector-python[secure-local-storage]' \
    python scripts/ask_review_agent.py --out evidence/agent_review_2026-10-16 "What is wrong with this repo?"
Each call is one billed agent turn. The programmatic access token is read from SF_PAT_FILE
(default ~/.snowflake/verif_pat) and never printed or written; a response that contains it is refused.
Writes <out>/raw.sse (the stream as received) and <out>/answer.md (question, tools used, answer text).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from sf import DB, connect

SCHEMA = "TRUST_DEMO_DEV"
AGENT = "REPO_REVIEW_AGENT"
WAREHOUSE = "MISSION_OS_WH"


def host() -> str:
    cur = connect().cursor()
    org, acc = cur.execute("SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME()").fetchone()
    return f"{org}-{acc}".lower().replace("_", "-") + ".snowflakecomputing.com"


def parse_sse(raw: str) -> list[tuple[str, dict]]:
    events, name, data = [], None, []
    for line in raw.splitlines() + [""]:
        if line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].strip())
        elif not line and data:
            try:
                events.append((name or "", json.loads("\n".join(data))))
            except json.JSONDecodeError:
                events.append((name or "", {"raw": "\n".join(data)}))
            name, data = None, []
    return events


def summarize(events: list[tuple[str, dict]]) -> tuple[str, list[str]]:
    text = "".join(d.get("text", "") for e, d in events if e == "response.text.delta")
    tools = [d.get("name") or d.get("type", "?") for e, d in events if e == "response.tool_use"]
    if not text:
        for e, d in events:
            if e == "response":
                text = "".join(c.get("text", "") for c in d.get("content", []) if c.get("type") == "text")
    return text.strip(), tools


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("question")
    ap.add_argument("--out", required=True, help="directory for raw.sse and answer.md")
    a = ap.parse_args()

    token = Path(os.environ.get("SF_PAT_FILE", "~/.snowflake/verif_pat")).expanduser().read_text().strip()
    url = f"https://{host()}/api/v2/databases/{DB}/schemas/{SCHEMA}/agents/{AGENT}:run"
    body = {"messages": [{"role": "user", "content": [{"type": "text", "text": a.question}]}], "stream": True}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "Accept": "text/event-stream",
        "Authorization": f"Bearer {token}",
        "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
        "X-Snowflake-Warehouse": WAREHOUSE,
        "X-Snowflake-Role": "CLAUDE_DEMO_READER",
    })
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            status, raw = resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        if token in detail:
            detail = "(withheld: contains the token)"
        print(f"HTTP {e.code}: {detail[:500]}", file=sys.stderr)
        return 1
    if token in raw:
        print("refused: the token appears in the response; nothing written", file=sys.stderr)
        return 1

    events = parse_sse(raw)
    errors = [d for e, d in events if e == "error"]
    text, tools = summarize(events)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "raw.sse").write_text(raw)
    (out / "answer.md").write_text(
        f"# {AGENT} on {DB}.{SCHEMA}\n\n"
        f"**Question:** {a.question}\n\n"
        f"**Tools called:** {', '.join(t for t in tools if t) or 'none'}\n\n"
        f"**Answer:**\n\n{text or '(no text)'}\n")
    print(f"HTTP {status}, {len(events)} events, tools: {tools}")
    if errors:
        print("agent error:", json.dumps(errors[0])[:500], file=sys.stderr)
        return 1
    print(text)
    return 0 if text else 1


if __name__ == "__main__":
    sys.exit(main())
