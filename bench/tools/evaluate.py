"""
Score spotDL's current matching code against the hand labels, from the cache.

Runs spotDL's search (judge off) for every song of the chosen playlists, with
searches and yt-dlp metadata read from `bench/cache` (a miss is fetched and
saved), and looks up each pick in `bench/labels/picks.tsv`, keyed by Spotify
track and YouTube URL. Picks without a label are printed so they can be
labelled and added to that file.

Usage: uv run python bench/tools/evaluate.py es en [friend] \
    [--save bench/run_name]
"""

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

# pylint: disable=wrong-import-position
from judge_benchmark import DiskCache, describe, install_cache, load_songs  # noqa

from spotdl.providers.audio import YouTubeMusic  # noqa: E402
from spotdl.utils.config import DEFAULT_CONFIG  # noqa: E402
from spotdl.utils.spotify import SpotifyClient  # noqa: E402

BENCH = Path(__file__).resolve().parents[1]
PLAYLISTS = {
    "es": "5VskdvX3OlGVAHhn1jgoAm",
    "en": "4PniezFG51rrLjQhkWqHsC",
    "friend": "0ADNLtVRNIEIvLNNqxykGG",
}


def main() -> None:
    """
    Score the playlists.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lists", nargs="+", choices=list(PLAYLISTS))
    parser.add_argument("--cache", default=str(BENCH / "cache"))
    parser.add_argument("--labels", default=str(BENCH / "labels" / "picks.tsv"))
    parser.add_argument("--save", help="write <save>_<list>_picks.jsonl")
    args = parser.parse_args()

    cache = DiskCache(Path(args.cache))
    install_cache(cache)
    SpotifyClient.init(
        client_id=DEFAULT_CONFIG["client_id"],
        client_secret=DEFAULT_CONFIG["client_secret"],
    )

    with open(args.labels, encoding="utf-8") as file:
        labels = {
            (row["spotify_url"], row["url"]): row["label"]
            for row in csv.DictReader(file, delimiter="\t")
        }

    provider = YouTubeMusic()
    seen = {}
    get_results = provider.get_results

    def recording_get_results(search_term, *a, **kw):
        results = get_results(search_term, *a, **kw)
        for result in results:
            seen.setdefault(result.url, result)
        return results

    provider.get_results = recording_get_results  # type: ignore

    totals = []
    for name in args.lists:
        url = f"https://open.spotify.com/playlist/{PLAYLISTS[name]}"
        songs = load_songs([url], cache)
        counts: collections.Counter = collections.Counter()
        rows = []
        for song in songs:
            seen.clear()
            pick_url = provider.search(song) or ""
            label = (
                labels.get((song.url, pick_url), "UNLABELLED")
                if pick_url
                else "unmatched"
            )
            counts[label] += 1
            pick = describe(seen.get(pick_url))
            rows.append(
                {
                    "song": song.display_name,
                    "spotify_url": song.url,
                    "duration": song.duration,
                    "label": label,
                    "pick": pick,
                }
            )
            if label != "correct":
                detail = ""
                if pick:
                    try:
                        meta = provider.get_download_metadata(pick_url)
                    except Exception:  # pylint: disable=broad-except
                        meta = {}
                    detail = (
                        f"{pick['name']} | {', '.join(pick['artists'])} | "
                        f"{pick['album']} | {pick['duration']} vs {song.duration}"
                        f" | {'song' if pick['verified'] else 'video'} | "
                        f"{meta.get('channel')}: {meta.get('title')} | "
                        f"{meta.get('view_count')} views"
                    )
                print(f"  [{label}] {song.display_name} -> {pick_url} {detail}")

        if args.save:
            with open(f"{args.save}_{name}_picks.jsonl", "w", encoding="utf-8") as out:
                for row in rows:
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")

        errors = counts["wrong"] + counts["unsure"] + counts["unmatched"]
        totals.append(
            f"{name:7} n={len(songs):3} correct {counts['correct']:3} wrong "
            f"{counts['wrong']:2} unsure {counts['unsure']:2} unmatched "
            f"{counts['unmatched']:2} unlabelled {counts['UNLABELLED']:2} "
            f"errors {errors:2} ({100 * errors / len(songs):.1f}%)"
        )

    print("\n".join(totals))


if __name__ == "__main__":
    main()
