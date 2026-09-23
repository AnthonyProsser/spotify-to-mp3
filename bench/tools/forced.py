"""For each logged judge request: which candidate is spotDL's pick, and which
candidate Kev ranks highest when 'none' is excluded."""
import csv, json, sys
cache = json.load(open(sys.argv[3]))
rows = {r["song"]: r for r in csv.DictReader(open(sys.argv[2]))}
def key(t, a): return f"{', '.join(a)} - {t}" if False else None
out = []
for line in open(sys.argv[1]):
    d = json.loads(line)
    st = d.get("state")
    if not isinstance(st, dict) or "spotify_track" not in st or "best_match" not in (d.get("answers") or {}):
        continue
    t = st["spotify_track"]
    probs = {k: v for k, v in d["answers"]["best_match"]["probabilities"].items() if k != "none"}
    top = max(probs, key=probs.get)
    # find the benchmark row for this song
    row = next((r for s, r in rows.items() if s.endswith(" - " + t["title"]) and s.startswith(t["artists"][0])), None)
    if not row: continue
    m = cache.get(row["spotdl_url"].split("v=")[-1], {})
    # spotDL's pick = candidate with same duration and title (from yt metadata)
    sp_idx = None
    for k, c in st["candidates"].items():
        if m and abs(c["duration_s"] - (m.get("duration") or -99)) <= 1 and (c["title"] == m.get("title") or c["title"] == m.get("track")):
            sp_idx = k; break
    cands = st["candidates"]
    out.append((row["song"], t["duration_s"], sp_idx, top, round(probs[top], 3), cands))
agree = sum(1 for o in out if o[2] == o[3])
print(f"judged {len(out)}  forced pick == spotDL pick: {agree}  differs: {sum(1 for o in out if o[2] is not None and o[2]!=o[3])}  spotDL pick not identified: {sum(1 for o in out if o[2] is None)}")
for song, dur, sp, top, p, c in out:
    if sp == top: continue
    f = lambda k: f"#{k} {c[k]['title'][:48]!r} ch={c[k]['channel'][:18]!r} {c[k]['duration_s']}s off={c[k]['official_audio']}" if k in c else f"#{k} ?"
    print(f"\n{song[:50]} (spotify {dur}s)  kev p={p}")
    print("   spotDL:", f(sp) if sp else "not identified")
    print("   Kev   :", f(top))
