"""
Replay logged judge states against Kev with different question designs.

Usage: uv run python replay.py labels.json requests.jsonl [...]
labels.json maps "<title> | <artists>" -> list of correct candidate keys
(may be missing; then only answers are printed).
"""

import json
import sys
import time

import requests

URL = "http://127.0.0.1:8009/v1/systemone"


def ask(state, questions):
    start = time.monotonic()
    r = requests.post(
        URL,
        json={"state": state, "model": "kev-latest", "questions": questions},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["answers"], time.monotonic() - start


CHOICE_INSTR = (
    "Which candidate is the same recording as the Spotify track? "
    "Titles and artist names can be in any language or script, "
    "translated, transliterated or with different accents, so "
    "compare meaning, not spelling. Durations should be close. "
    "Live (en vivo, ao vivo, en directo), cover, remix, "
    "karaoke, sped up or other versions are wrong unless the "
    "Spotify track is that version."
)


def design_choice(cands):
    crit = {k: None for k in cands}
    crit["none"] = "None of the candidates is this recording."
    return {"best_match": {"type": "choice", "instructions": CHOICE_INSTR, "criteria": crit}}


def per_candidate_instr(k):
    return (
        f"Is candidate {k} the Spotify track itself: the same song by the same "
        "artist, in the same version? Titles and artist names may be in any "
        "language or script, or spelled differently. Its duration should be "
        "within a few seconds of the Spotify track's. Live (en vivo, ao vivo), "
        "cover, remix, karaoke, sped up, slowed, pitched or instrumental "
        "versions are not the track unless the Spotify track is that version."
    )


def design_noul(cands):
    return {f"c{k}": {"type": "noul", "instructions": per_candidate_instr(k)} for k in cands}


def design_nonone(cands):
    return {"best_match": {"type": "choice", "instructions": CHOICE_INSTR, "criteria": {k: None for k in cands}}}


DESIGNS = {"choice": design_choice, "noul": design_noul, "nonone": design_nonone}


def pick(design, answers):
    if design in ("choice", "nonone"):
        bm = answers["best_match"]
        return bm["choice"], bm["probabilities"].get(bm["choice"], 0), bm["probabilities"]
    probs = {k[1:]: v["noul"] for k, v in answers.items()}
    best = max(probs, key=probs.get)
    return best, probs[best], probs


def main():
    labels = json.load(open(sys.argv[1])) if sys.argv[1] != "-" else {}
    designs = sys.argv[2].split(",")
    states = []
    for path in sys.argv[3:]:
        for line in open(path):
            d = json.loads(line)
            if isinstance(d["state"], dict) and "spotify_track" in d["state"]:
                states.append(d["state"])
    out = []
    for state in states:
        t = state["spotify_track"]
        key = f"{t['title']} | {', '.join(t['artists'])}"
        row = {"key": key, "labels": labels.get(key)}
        for design in designs:
            answers, secs = ask(state, DESIGNS[design](state["candidates"]))
            choice, p, probs = pick(design, answers)
            row[design] = {"choice": choice, "p": round(p, 3), "probs": {k: round(v, 3) for k, v in probs.items()}, "secs": round(secs, 2)}
        out.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)


main()
