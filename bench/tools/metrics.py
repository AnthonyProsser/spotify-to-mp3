"""metrics.py verdicts.json run.csv [...]: accuracy of spotDL alone vs with judge.
A song missing from a run (search crashed) counts as unmatched."""
import csv, json, sys, collections, statistics
V = json.load(open(sys.argv[1])); total = int(sys.argv[2])
def verdict(url):
    if not url: return "unmatched"
    return V.get(url.split("v=")[-1], V.get("_default", "unreviewed"))
for path in sys.argv[3:]:
    rows = list(csv.DictReader(open(path)))
    jr = list(csv.DictReader(open(path.replace(".csv", "_judge.csv"))))
    out = {}
    for col in ("spotdl_url", "judge_url"):
        c = collections.Counter(verdict(r[col]) for r in rows)
        c["unmatched"] += total - len(rows)
        out[col] = c
    oc = collections.Counter(r["outcome"] for r in jr)
    acted = [r for r in jr if r["outcome"] in ("overrode", "rescued")]
    wrong_over = [r["song"] for r in acted if verdict(r["final_url"]) != "correct"]
    good_over = [r["song"] for r in acted if verdict(r["final_url"]) == "correct"]
    variance = [r["song"] for r in rows if r["spotdl_url"] != r["judge_url"] and r["song"] not in {a["song"] for a in acted}]
    js = [float(r["judge_seconds"]) for r in rows if r.get("judge_seconds") not in (None, "")]
    js = [x for x in js if x > 0]
    print(f"== {path}  ({len(rows)}/{total} songs searched)")
    for col, c in out.items():
        print(f"  {col:11} correct {c['correct']}/{total} ({100*c['correct']/total:.0f}%)  wrong {c['wrong']}  unsure {c['unsure']}  unmatched {c['unmatched']}  unreviewed {c['unreviewed']}")
    print(f"  outcomes {dict(oc)}")
    print(f"  rescued(judge) {oc.get('rescued',0)}  overrides {oc.get('overrode',0)}  wrong-overrides {len(wrong_over)} {wrong_over}  correct judge actions {good_over}")
    print(f"  diffs not caused by judge (search variance / fallback) {variance}")
    if js: print(f"  judge latency mean {statistics.mean(js):.2f}s median {statistics.median(js):.2f}s p95 {sorted(js)[int(.95*len(js))-1]:.1f}s max {max(js):.1f}s (n={len(js)})")
