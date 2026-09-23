"""
For a benchmark CSV, fetch yt-dlp metadata of spotDL's and the judge's picks
for disagreements plus a random sample of agreements, and print them next to
the Spotify track so they can be labelled by hand.

Usage: uv run python verify.py bench/es_t07.csv [n_agree_sample] > out.txt
"""

import csv
import json
import random
import sys
from functools import lru_cache
from pathlib import Path

from yt_dlp import YoutubeDL

from spotdl.types.song import Song
from spotdl.utils.config import DEFAULT_CONFIG
from spotdl.utils.spotify import SpotifyClient

CACHE = Path(__file__).with_name("ytmeta_cache.json")
cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}

ydl = YoutubeDL({"quiet": True, "skip_download": True, "no_warnings": True})


def meta(url):
    if not url:
        return None
    vid = url.split("v=")[-1]
    if vid not in cache:
        try:
            info = ydl.extract_info(url, download=False)
            cache[vid] = {
                "title": info.get("title"),
                "track": info.get("track"),
                "artists": info.get("artists") or info.get("artist"),
                "album": info.get("album"),
                "channel": info.get("channel"),
                "duration": info.get("duration"),
                "views": info.get("view_count"),
                "desc": (info.get("description") or "")[:300].replace("\n", " | "),
            }
        except Exception as exc:  # noqa
            cache[vid] = {"error": str(exc)[:200]}
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0))
    return cache[vid]


def main():
    path = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    judge_rows = {
        r["spotify_url"]: r
        for r in csv.DictReader(
            open(path.replace(".csv", "_judge.csv"), encoding="utf-8")
        )
    }
    SpotifyClient.init(
        client_id=DEFAULT_CONFIG["client_id"],
        client_secret=DEFAULT_CONFIG["client_secret"],
    )
    diff = [r for r in rows if r["spotdl_url"] != r["judge_url"]]
    same = [r for r in rows if r["spotdl_url"] == r["judge_url"]]
    random.seed(42)
    sample = random.sample(same, min(n, len(same)))
    for kind, group in (("DIFF", diff), ("SAME", sample)):
        for r in group:
            song = Song.from_url(r["spotify_url"])
            j = judge_rows.get(r["spotify_url"], {})
            print(f"=== [{kind}] {r['song']}  ({r['spotify_url']})")
            print(
                f"  spotify: title={song.name!r} artists={song.artists} "
                f"album={song.album_name!r} dur={song.duration}"
            )
            print(
                f"  judge: outcome={j.get('outcome')} choice={j.get('judge_choice')} "
                f"conf={j.get('judge_confidence')} orig={j.get('judge_original')}"
            )
            for label, url in (("spotdl", r["spotdl_url"]), ("judge ", r["judge_url"])):
                if kind == "SAME" and label == "judge ":
                    continue
                print(f"  {label}: {url}")
                print(f"          {json.dumps(meta(url), ensure_ascii=False)}")
            if j.get("judge_url") and j["judge_url"] not in (r["judge_url"],):
                print(f"  judge's unused pick: {j['judge_url']}")
                print(f"          {json.dumps(meta(j['judge_url']), ensure_ascii=False)}")
            sys.stdout.flush()


main()
