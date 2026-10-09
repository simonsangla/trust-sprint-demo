#!/usr/bin/env python3
"""Build site/refusal/index.html: the public evidence page for the Cortex Analyst refusal finding (mission-os #1362).
Every run shown is a row of evidence/refusal_runs_2026-10-08/batch20.csv; nothing on the page is typed by hand.
    python3 scripts/build_refusal_page.py [--csv PATH]"""
from __future__ import annotations
import argparse, csv, html, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from refusal_outcome import outcome, gave_number  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "evidence" / "refusal_runs_2026-10-08" / "batch20.csv"
OUT = ROOT / "site" / "refusal" / "index.html"
REPO = "https://github.com/simonsangla/trust-sprint-demo"
PROOF_ID = "proof_2026_10_09_refusal_text_is_not_a_refusal"  # exposure name in models/proofs/_proofs.yml, shown on the home page too
CAL = "https://cal.com/simon-sangla/trust-sprint-scoping-call?ref=refusal"
EDITS = [("E0", "Edit 0", "No verified queries"),
         ("E1", "Edit 1", "One verified query added, about paying customers"),
         ("E2", "Edit 2", "Custom instructions: do not approximate undefined metrics"),
         ("E3", "Edit 3", "Rule moved to question categorization only: unanswerable, reject")]


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--csv", default=str(CSV)); a = ap.parse_args()
    rows = list(csv.DictReader(open(a.csv)))
    if not rows:
        sys.exit("no rows")
    def pack(r):
        return {"run": int(r["run"]), "o": outcome(r), "text": r["text"], "sql": r["sql"], "value": r["value"],
                "rid": r["request_id"], "ts": r["ts"]}
    data = {"edits": [], "typo": [], "control": []}
    for e, lab, sub in EDITS:
        rs = sorted((r for r in rows if r["cell"] == "churn" and r["edit"] == e), key=lambda r: int(r["run"]))
        data["edits"].append({"id": e, "label": lab, "sub": sub, "runs": [pack(r) for r in rs]})
    convs = {}
    for r in rows:
        if r["cell"] == "typo_followup":
            convs.setdefault(int(r["run"]), {})[r["turn"]] = r
    for i in sorted(convs):
        if "2" in convs[i]:
            p = pack(convs[i]["2"]); p["first"] = outcome(convs[i]["1"]) if "1" in convs[i] else ""
            data["typo"].append(p)
    ctrl = [r for r in rows if r["cell"] == "control"]
    data["control"] = {"ok": sum("6983" in r["value"] for r in ctrl), "n": len(ctrl)}
    data["batch"] = rows[0]["batch_id"]; data["sha"] = rows[0]["script_sha"]
    data["first_ts"] = min(r["ts"] for r in rows); data["last_ts"] = max(r["ts"] for r in rows); data["rows"] = len(rows)
    summ = []
    for ed in data["edits"]:
        n = len(ed["runs"]); num = sum(gave_number(x["o"]) for x in ed["runs"])
        summ.append((ed["label"], n, num))
    e1 = data["edits"][1]["runs"]; e2 = data["edits"][2]["runs"]
    lede = (f'{html.escape(data["edits"][0]["label"])}: no number in {summ[0][1]-summ[0][2]} of {summ[0][1]} runs. '
            f'After one unrelated verified query: a number in {summ[1][2]} of {summ[1][1]}. '
            f'Told not to approximate: the answer said no in {sum(x["o"] in ("declined","sql_refusal","said_no_number") for x in e2)} of {len(e2)}, '
            f'while the SQL computed a number in {summ[2][2]}.')
    # Proof line, all figures recomputed here from the CSV (the proof's check.sh recounts them independently).
    e1v = {re.findall(r"-?\d+\.\d+", r["value"])[-1] for r in rows if r["cell"] == "churn" and r["edit"] == "E1"
           and gave_number(outcome(r)) and re.findall(r"-?\d+\.\d+", r["value"])}
    if len(e1v) != 1:
        sys.exit("edit 1 answers are not one value: %s" % sorted(e1v))
    proof = (f'Proof <code>{PROOF_ID}</code>: recounted offline from the {len(rows)} Cortex calls of this batch, no Snowflake call. '
             f'After the verified query (edit 1) the answer was {100 * float(next(iter(e1v))):.1f}% in {summ[1][2]} of {summ[1][1]} runs; '
             f'edit 2 said no in {sum(x["o"] in ("declined","sql_refusal","said_no_number") for x in e2)} of {len(e2)} and its SQL computed a number in {summ[2][2]}. '
             f'Re-run: <code>bash proofs/2026-10-09-refusal-text-is-not-a-refusal/check.sh</code> · '
             f'<a href="{REPO}/tree/main/proofs/2026-10-09-refusal-text-is-not-a-refusal">proof folder</a>')
    page = TEMPLATE.replace("__DATA__", json.dumps(data).replace("</", "<\\/")).replace("__LEDE__", lede).replace("__PROOF__", proof) \
        .replace("__REPO__", REPO).replace("__CAL__", CAL)
    OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(page, encoding="utf-8")
    print("wrote", OUT, "rows", len(rows), "|", summ, "| control", data["control"])
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cortex refusal test</title>
<meta name="description" content="Fictional data, real Cortex Analyst runs: the same undefined-metric question asked 20 times after each semantic view edit. Every run, its text, its SQL and its result.">
<meta name="color-scheme" content="light">
<meta property="og:type" content="website">
<meta property="og:title" content="One verified query was enough to make Cortex Analyst answer a question it should decline">
<meta property="og:description" content="Fictional data, real Cortex Analyst runs: 20 runs per semantic view edit. What it said vs what the SQL did, run by run.">
<meta property="og:url" content="https://trustsprint.simonsangla.com/refusal/">
<meta property="og:image" content="https://trustsprint.simonsangla.com/refusal/og.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:,">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
/* Ledger (simonsangla.com, mission-os #1283): paper surface, deep navy ink, numbers first. Green = holds, brick = risk/refusal.
   Ink is the single CTA fill. Light only, by design (same as the site). Chart marks use #23845c (dataviz validator pass). */
:root{color-scheme:light;
  --paper:#ffffff;--ink:#101c2b;--muted:#4a5768;--tint:#f2f5f8;--hair:#d9e0e8;--green:#2f6b4f;--brick:#9e3b2e;--mark-green:#23845c;
  --sans:"IBM Plex Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;--mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;--r:.5rem}
*{box-sizing:border-box}html{background:var(--paper)}
body{margin:0;background:var(--paper);color:var(--ink);font:400 1rem/1.6 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--ink);text-underline-offset:3px}:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.top{border-bottom:1px solid var(--hair);position:sticky;top:env(safe-area-inset-top,0px);background:var(--paper);z-index:5}
.bar,.wrap{max-width:880px;margin:0 auto;padding-inline:16px}
.bar{display:flex;justify-content:space-between;align-items:center;gap:12px;min-height:52px}
.brand{font:500 .8rem var(--mono);letter-spacing:.14em;text-transform:uppercase;text-decoration:none}
.btn{display:inline-block;background:var(--ink);color:var(--paper);text-decoration:none;font:500 .72rem var(--mono);letter-spacing:.12em;text-transform:uppercase;padding:10px 16px;border-radius:var(--r);white-space:nowrap}
.btn.big{font:600 .95rem var(--sans);letter-spacing:0;text-transform:none;padding:12px 18px}
.wrap{padding-block:56px 72px;display:grid;gap:64px}
.eyebrow{font:500 .66rem var(--mono);letter-spacing:.2em;text-transform:uppercase;color:var(--muted)}
.sec{border-top:1px solid var(--hair);padding-top:28px;display:grid;gap:16px;min-width:0}
.num{font:500 .72rem var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
h1,h2{font-weight:500;letter-spacing:-.02em;line-height:1.15;margin:0;text-wrap:balance}
h1{font-size:clamp(1.9rem,5vw,2.75rem)}h2{font-size:clamp(1.35rem,3vw,1.75rem)}
p{margin:0}.lede{color:var(--muted);max-width:62ch}
.recap{display:grid;gap:8px;border-left:2px solid var(--hair);padding-left:16px}
.ledger{font:400 clamp(1.15rem,3.6vw,1.55rem)/1.4 var(--mono);letter-spacing:-.02em;font-variant-numeric:tabular-nums;margin:0}
.ledger .g{color:var(--green)}.ledger .b{color:var(--brick)}.ledger small{font-size:.42em;color:var(--muted);letter-spacing:.02em;margin-left:.6em}
.tag{justify-self:start;font:500 .66rem var(--mono);letter-spacing:.14em;text-transform:uppercase;border:1px solid var(--hair);background:var(--tint);color:var(--muted);padding:4px 10px;border-radius:4px}
.stats{display:flex;flex-wrap:wrap;gap:20px 48px;border-top:1px solid var(--ink);padding-top:14px;max-width:560px}
.stats div{display:grid}.stats b{font:400 1.4rem var(--mono);font-variant-numeric:tabular-nums}.stats span{font-size:.75rem;color:var(--muted)}
.leg{display:flex;flex-wrap:wrap;gap:8px 22px;font-size:.85rem;color:var(--muted)}.leg span{display:flex;align-items:center;gap:8px}
.edit{display:grid;gap:10px;padding-block:16px;border-top:1px solid var(--hair)}
.eh{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:baseline}.eh b{font-weight:600}.eh span{color:var(--muted)}
.eh em{font-style:normal;margin-left:auto;font:500 .8rem var(--mono);font-variant-numeric:tabular-nums}
.dots{display:flex;flex-wrap:wrap;gap:7px}
.d{width:24px;height:24px;border-radius:50%;border:0;padding:0;cursor:pointer;background:transparent}
.d.declined{background:var(--mark-green)}.d.sql_refusal{box-shadow:inset 0 0 0 5px var(--mark-green)}
.d.said_no_number{box-shadow:inset 0 0 0 5px var(--brick)}.d.number{background:var(--brick)}
.d[aria-pressed=true]{outline:3px solid var(--ink);outline-offset:2px}.leg .d{width:16px;height:16px;cursor:default}
.panel{border:1px solid var(--hair);border-radius:var(--r);padding:18px;display:grid;gap:12px;min-width:0}
.panel h3{margin:0;font:600 1rem var(--sans)}.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:680px){.two{grid-template-columns:1fr}}
.box{min-width:0;display:grid;gap:6px;align-content:start}.said{font-size:.92rem}
pre{margin:0;background:var(--tint);border:1px solid var(--hair);color:var(--ink);padding:12px;border-radius:6px;font:.78rem/1.5 var(--mono);overflow-x:auto;white-space:pre-wrap;overflow-wrap:anywhere}
.meta{font:.72rem/1.6 var(--mono);color:var(--muted);overflow-wrap:anywhere}
ol{margin:0;padding-left:22px;display:grid;gap:8px;max-width:62ch}
.cta{border:1px solid var(--ink);border-radius:var(--r);padding:24px;display:grid;gap:12px}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style>
</head>
<body>
<header class="top"><div class="bar"><a class="brand" href="https://simonsangla.com">Simon Sangla</a><a class="btn" href="__CAL__">Book a 20-min scoping call</a></div></header>
<main class="wrap">
<section style="display:grid;gap:22px">
  <div class="eyebrow">Snowflake · Cortex Analyst · refusal test</div>
  <span class="tag">Fictional demo data · 20 runs per edit</span>
  <h1>One verified query was enough to make Cortex Analyst answer a question it should decline.</h1>
  <p class="lede">I asked "What is our customer churn rate?" after each edit to a semantic view where churn is not defined. __LEDE__</p>
  <div class="recap"><div class="eyebrow">Recap · runs that returned a number, out of 20</div><p class="ledger" id="ledger"></p></div>
  <div><a class="btn big" href="__CAL__">Book a 20-min scoping call</a></div>
  <div class="stats" id="stats"></div>
</section>

<section class="sec" aria-labelledby="h-runs">
  <div class="num">01 / Every run</div>
  <h2 id="h-runs">Click a dot: what Cortex said, and what its SQL returned</h2>
  <div class="leg" aria-label="Legend">
    <span><i class="d declined"></i>declined, no SQL</span><span><i class="d sql_refusal"></i>SQL returned a refusal message</span>
    <span><i class="d said_no_number"></i>said no, SQL computed a number</span><span><i class="d number"></i>answered with a number</span>
  </div>
  <div id="edits"></div>
  <div class="panel" id="panel" aria-live="polite"></div>
</section>

<section class="sec" aria-labelledby="h-why">
  <div class="num">02 / Why it matters</div>
  <h2 id="h-why">The sentence says no. The table under it is what ends up in a slide.</h2>
  <p class="lede">In most apps the SQL runs and its table is shown under the answer. A refusal that only lives in the text is not a refusal.</p>
  <p class="lede" id="ctrl"></p>
</section>

<section class="sec" aria-labelledby="h-how">
  <div class="num">03 / Test your own assistant</div>
  <h2 id="h-how">Three steps</h2>
  <ol>
    <li>List the questions it must decline: undefined metrics, forecasts, actions, opinions, and questions with no data behind them.</li>
    <li>For each run, grade two things: what the answer says, and what the SQL returns when executed.</li>
    <li>Rerun the set on every semantic view edit: new verified queries, edited instructions, new tables.</li>
  </ol>
</section>

<section class="cta" aria-labelledby="h-cta">
  <div class="num">04 / Offer</div>
  <h2 id="h-cta">Run this on your semantic view</h2>
  <p class="lede" style="color:var(--ink)">AI Analytics Trust Sprint: 5 days, fixed scope, from EUR 4,500. Your questions, your semantic view, a written pass and fail report.</p>
  <div><a class="btn big" href="__CAL__">Book a 20-min scoping call</a></div>
</section>

<p class="meta" id="proof">__PROOF__</p>
<footer class="meta" id="foot"></footer>
</main>
<script>
const D=__DATA__;
const NAMES={declined:"declined, no SQL",sql_refusal:"SQL returned a refusal message",said_no_number:"said no, SQL computed a number",number:"answered with a number"};
const gave=o=>o==="said_no_number"||o==="number";
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const host=document.getElementById("edits"),panel=document.getElementById("panel");
let first=null;
document.getElementById("ledger").innerHTML=D.edits.map(e=>{const n=e.runs.length,k=e.runs.filter(r=>gave(r.o)).length;
  return `<span class="${k?"b":"g"}">${esc(e.label)} ${String(k).padStart(2," ")}/${n}.</span><small>${k?"number given":"no number"}</small>`}).join("<br>");
const e2=D.edits[2].runs,said=e2.filter(r=>r.o!=="number").length;
document.getElementById("stats").innerHTML=`<div><b>${D.rows}</b><span>Cortex calls, one batch</span></div><div><b>${said}/${e2.length}</b><span>Edit 2 answers said no</span></div><div><b>${D.control.ok}/${D.control.n}</b><span>control answered correctly</span></div>`;
function row(label,sub,runs,key){
  const n=runs.length,num=runs.filter(r=>gave(r.o)).length;
  const el=document.createElement("div");el.className="edit";
  el.innerHTML=`<div class="eh"><b>${esc(label)}</b><span>${esc(sub)}</span><em>number in ${num}/${n}</em></div><div class="dots"></div>`;
  const dots=el.querySelector(".dots");
  runs.forEach(r=>{const b=document.createElement("button");b.type="button";b.className="d "+r.o;b.setAttribute("aria-pressed","false");
    b.setAttribute("aria-label",`${label}, run ${r.run}: ${NAMES[r.o]}`);b.onclick=()=>show(label,r,b);dots.appendChild(b);
    if(key&&!first&&r.o==="said_no_number")first=[label,r,b];});
  host.appendChild(el);
}
function show(label,r,b){
  document.querySelectorAll(".d[aria-pressed]").forEach(x=>x.setAttribute("aria-pressed","false"));b.setAttribute("aria-pressed","true");
  panel.innerHTML=`<h3>${esc(label)} · run ${r.run} · ${esc(NAMES[r.o])}</h3>
  <div class="two"><div class="box"><span class="eyebrow">What Cortex said</span><p class="said">${esc(r.text||"(no text)")}</p></div>
  <div class="box"><span class="eyebrow">SQL it returned, and the result when executed</span><pre>${esc(r.sql||"(no SQL)")}</pre><p class="meta">Result: ${esc(r.value||"none")}</p></div></div>
  <p class="meta">request_id ${esc(r.rid)} · ${esc(r.ts)}${r.first!==undefined?" · first turn: "+esc(NAMES[r.first]||r.first):""}</p>`;
}
D.edits.forEach((e,i)=>row(e.label,e.sub,e.runs,i===2));
if(D.typo.length)row("Edit 2, follow-up",'"chrun rate" asked next in the same conversation',D.typo,false);
if(!first){const b=document.querySelector("#edits .d");if(b)b.click();}else show(...first);
document.getElementById("ctrl").textContent=`Control: on the same four views, "What was total revenue in Q1 2026?" came back as 6983.00, the correct value, in ${D.control.ok} of ${D.control.n} runs. The views answer what they should.`;
document.getElementById("foot").innerHTML=`Batch ${esc(D.batch)} · ${D.rows} rows · ${esc(D.first_ts)} to ${esc(D.last_ts)} · script commit ${esc(D.sha)}<br>
Raw CSV and scripts: <a href="__REPO__/tree/main/evidence/refusal_runs_2026-10-08">trust-sprint-demo/evidence</a> · rerun: <code>python scripts/run_refusal_batch.py out.csv --n 20</code> (needs a Snowflake account with Cortex Analyst; views built by scripts/make_refusal_views.py, run_refusal_experiments.py, make_wording_views.py)<br>
Fictional data. Cortex Analyst REST API, ${esc(D.first_ts.slice(0,10))}. Page built by scripts/build_refusal_page.py from the CSV.`;
</script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main())
