"""Turn one question of seeds/question_pack.csv into DuckDB SQL using the METRICS block of
snowflake/semantic_view.sql as written in the tree under test. Stdlib only; offline.
Usage: python3 -I svsql.py TREE QUESTION_ID  -> prints SQL, or exits 3 if the question's metric is not in the view.
       python3 -I svsql.py --scope VIEW_SQL PACK_CSV -> prints the ids of the questions whose metric VIEW_SQL defines.
Only the metric EXPRESSIONS come from the view. The anchoring and the filters are fixed here, not read from the view:
a base metric filters its own table on its own date column (and the session channel); a derived metric (a.x / b.y)
anchors bookings to the sessions in the slice (the owner's definition, see 2026-10-09-semantic-view-still-wrong)."""
import csv, re, sys


def parse_metrics(sv):
    block = re.search(r"\n  METRICS \((.*?)\n  \)\n", sv, re.S)
    if not block:
        sys.exit("FAIL: no METRICS block in snowflake/semantic_view.sql")
    body = block.group(1)
    metrics = {}
    for m in re.finditer(r"^    (?:(\w+)\.)?(\w+) AS (.+?)\n      COMMENT", body, re.M | re.S):
        metrics[m.group(2)] = (m.group(1), m.group(3).strip())
    # independent counts: every entry has one "<name> AS" head and one COMMENT; a format drift the parser
    # skipped must fail here, not silently shrink the set of replayed questions
    heads = len(re.findall(r"^\s*(?:\w+\.)?\w+\s+AS\s", body, re.M))
    comments = len(re.findall(r"\bCOMMENT\s*=", body))
    if not metrics or heads != len(metrics) or comments != len(metrics):
        sys.exit("FAIL: METRICS block parsed %d metrics but has %d AS entries and %d COMMENTs"
                 % (len(metrics), heads, comments))
    return metrics


if sys.argv[1] == "--scope":
    metrics = parse_metrics(open(sys.argv[2], encoding="utf-8").read())
    print(" ".join(r["question_id"] for r in csv.DictReader(open(sys.argv[3])) if r["metric_key"] in metrics))
    sys.exit(0)
tree, qid = sys.argv[1], sys.argv[2]
metrics = parse_metrics(open(tree + "/snowflake/semantic_view.sql", encoding="utf-8").read())
q = [r for r in csv.DictReader(open(tree + "/seeds/question_pack.csv")) if r["question_id"] == qid][0]
key = q["metric_key"]
if key not in metrics:
    sys.exit(3)
d0, d1, ch = q["date_from"], q["date_to"], q["channel"]
derived = metrics[key][0] is None
chs = f"and s.channel = '{ch}'" if ch else ""
sess = f"(select * from {{{{ ref('sessions') }}}} s where s.session_date between date '{d0}' and date '{d1}' {chs})"
if derived:
    book = f"(select b.* from {{{{ ref('bookings') }}}} b join {sess} s2 on b.session_id = s2.session_id)"
else:
    book = (f"(select b.* from {{{{ ref('bookings') }}}} b left join {{{{ ref('sessions') }}}} s on b.session_id = s.session_id "
            f"where b.booking_date between date '{d0}' and date '{d1}' {chs})")
src = {"sessions": sess, "bookings": book}
def scalar(name):
    tbl, expr = metrics[name]
    return f"(select {expr} from {src[tbl]} as {tbl})"
tbl, expr = metrics[key]
if derived:
    expr = re.sub(r"\b(sessions|bookings)\.(\w+)\b", lambda m: "cast(" + scalar(m.group(2)) + " as double)", expr)
    print(f"select cast(round({expr}, 4) as varchar) as v")
else:
    print(f"select cast(round({scalar(key)}, 4) as varchar) as v")
