#!/usr/bin/env python3
"""Set up a Cortex Agent that reviews this dbt repo (mission-os#1531 slice C). DEV only, never drops.

Creates, in MISSION_OS_DB.TRUST_DEMO_DEV:
  REPO_FILES          the repo's dbt files at one git ref (models, tests, pre-commit config, checkpoint report)
  REPO_REVIEW_SEARCH  a Cortex Search service over REPO_FILES.CONTENT (bills while it exists: long TARGET_LAG)
  REPO_REVIEW_AGENT   a Cortex Agent with that search service and the existing TRUST_DEMO_SV semantic view

Usage (dry run, prints the statements and the files it would load, opens no connection):
  python scripts/agent_review_setup.py --ref origin/demo/1531-planted-bug
Apply (needs Simon's go: it starts a recurring search refresh). The schema belongs to ACCOUNTADMIN and the
connection's default role is the read-only CLAUDE_DEMO_READER, so the owner runs it with --role:
  SNOWFLAKE_DEFAULT_CONNECTION_NAME=mission_os_dogfood uv run --with 'snowflake-connector-python[secure-local-storage]' \
    python scripts/agent_review_setup.py --ref origin/demo/1531-planted-bug --apply --role ACCOUNTADMIN
It then grants the reader role what it needs to ask the agent (same pattern as BOARD_LOCK_DEV), nothing more.
Every statement is IF NOT EXISTS and the table loads only when empty, so a re-run changes nothing.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

from sf import ROOT, fq, run

SCHEMA = "TRUST_DEMO_DEV"
WAREHOUSE = "MISSION_OS_WH"
TARGET_LAG = "7 days"
EMBEDDING_MODEL = "snowflake-arctic-embed-m-v1.5"
READER_ROLE = "CLAUDE_DEMO_READER"
# The files a reviewer needs: the dbt models and tests, the gate config, and the dbt-checkpoint report.
INCLUDE = re.compile(r"^((models|tests)/.*\.(sql|yml|yaml|md)|\.pre-commit-config\.yaml|dbt_project\.yml"
                     r"|evidence/checkpoint_[^/]+/report\.txt)$")

RESPONSE_INSTRUCTIONS = (
    "You review a dbt project for a data team lead who is not a dbt expert. "
    "Answer in plain words, at most 120 words. Name the exact file path of every problem you report. "
    "If a dbt-checkpoint report is present, say which hook failed and on which model, "
    "then explain in one or two sentences what could go wrong in the data because of it."
)
ORCHESTRATION_INSTRUCTIONS = (
    "For questions about the repository, its models, tests or checks, use repo_search: "
    "first search for the dbt-checkpoint report (FAIL lines), then search the YAML of the model it names. "
    "Use metrics_analyst only for questions about the numbers in the data. "
    "Never invent a file, hook or model that the search results do not show."
)


def repo_files(ref: str) -> list[tuple[str, str, str, str]]:
    names = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", ref],
                           check=True, capture_output=True, text=True).stdout.split()
    rows = []
    for path in sorted(n for n in names if INCLUDE.match(n)):
        content = subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:{path}"],
                                 check=True, capture_output=True, text=True).stdout
        kind = path.rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else "file"
        rows.append((path, kind, ref, content))
    return rows


def statements() -> list[str]:
    s = fq(SCHEMA)
    return [
        f"CREATE TABLE IF NOT EXISTS {s}.REPO_FILES "
        "(file_path VARCHAR, file_type VARCHAR, git_ref VARCHAR, content VARCHAR)",
        f"""CREATE CORTEX SEARCH SERVICE IF NOT EXISTS {s}.REPO_REVIEW_SEARCH
  ON content
  ATTRIBUTES file_type
  WAREHOUSE = {WAREHOUSE}
  TARGET_LAG = '{TARGET_LAG}'
  EMBEDDING_MODEL = '{EMBEDDING_MODEL}'
AS
  SELECT file_path, file_type, content FROM {s}.REPO_FILES""",
        f"""CREATE AGENT IF NOT EXISTS {s}.REPO_REVIEW_AGENT
  COMMENT = 'Reviews the trust-sprint-demo dbt repo (mission-os#1531). DEV only.'
  PROFILE = '{{"display_name": "dbt repo reviewer"}}'
  FROM SPECIFICATION
  $$
  models:
    orchestration: auto
  orchestration:
    budget:
      seconds: 60
      tokens: 16000
  instructions:
    response: "{RESPONSE_INSTRUCTIONS}"
    orchestration: "{ORCHESTRATION_INSTRUCTIONS}"
  tools:
    - tool_spec:
        type: "cortex_search"
        name: "repo_search"
        description: "Searches the dbt repository files: model SQL, model YAML with tests and descriptions, singular tests, the pre-commit config and the dbt-checkpoint report."
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "metrics_analyst"
        description: "Answers questions about bookings, sessions and users data through the TRUST_DEMO_SV semantic view."
  tool_resources:
    repo_search:
      search_service: "{s}.REPO_REVIEW_SEARCH"
      max_results: 6
      title_column: "FILE_PATH"
      id_column: "FILE_PATH"
    metrics_analyst:
      semantic_view: "{s}.TRUST_DEMO_SV"
      execution_environment:
        type: "warehouse"
        warehouse: "{WAREHOUSE}"
        query_timeout: 60
  $$""",
    ]


def grants() -> list[str]:
    s, r = fq(SCHEMA), READER_ROLE
    return [
        f"GRANT USAGE ON SCHEMA {s} TO ROLE {r}",
        f"GRANT SELECT ON TABLE {s}.REPO_FILES TO ROLE {r}",
        f"GRANT USAGE ON CORTEX SEARCH SERVICE {s}.REPO_REVIEW_SEARCH TO ROLE {r}",
        f"GRANT SELECT ON SEMANTIC VIEW {s}.TRUST_DEMO_SV TO ROLE {r}",
        f"GRANT USAGE ON AGENT {s}.REPO_REVIEW_AGENT TO ROLE {r}",
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ref", required=True, help="git ref whose files are loaded, e.g. origin/demo/1531-planted-bug")
    ap.add_argument("--apply", action="store_true", help="execute on Snowflake (default: dry run)")
    ap.add_argument("--role", help="role to run as, e.g. ACCOUNTADMIN (the schema owner)")
    a = ap.parse_args()

    rows = repo_files(a.ref)
    if not rows:
        print(f"refused: no files match at {a.ref}", file=sys.stderr)
        return 1
    stmts = statements() + grants()
    print(f"{len(rows)} files at {a.ref}:")
    for path, _, _, content in rows:
        print(f"  {path} ({len(content)} chars)")
    for st in stmts:
        print(f"\n{st};")
    if not a.apply:
        print("\ndry run: nothing executed (pass --apply)")
        return 0

    from sf import connect
    cur = connect().cursor()
    if a.role:
        if not re.fullmatch(r"[A-Z_]+", a.role):
            print(f"refused: role {a.role!r}", file=sys.stderr)
            return 1
        run(cur, f"USE ROLE {a.role}")
    run(cur, f"USE WAREHOUSE {WAREHOUSE}")
    run(cur, stmts[0])
    n = run(cur, f"SELECT COUNT(*) FROM {fq(SCHEMA)}.REPO_FILES").fetchone()[0]
    if n == 0:
        cur.executemany(f"INSERT INTO {fq(SCHEMA)}.REPO_FILES VALUES (%s, %s, %s, %s)", rows)
        print(f"loaded REPO_FILES: {len(rows)} rows")
    else:
        print(f"REPO_FILES already holds {n} rows, left alone")
    for st in stmts[1:]:
        run(cur, st)
    print("ready:", f"{fq(SCHEMA)}.REPO_REVIEW_SEARCH", f"{fq(SCHEMA)}.REPO_REVIEW_AGENT", "granted to", READER_ROLE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
