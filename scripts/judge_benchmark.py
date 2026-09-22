"""
Compare spotDL's matching with and without the AI judge, without downloading.

For every song in the given Spotify URLs, run the YouTube Music search twice,
once with spotDL's matching alone and once with the judge on every song, and
write a CSV with both picks side by side. Label the `correct` column by hand
(spotdl / judge / both / neither) to measure accuracy.

Usage:
    uv run python scripts/judge_benchmark.py URL [URL ...] --judge kev \
        --out benchmark.csv
"""

import argparse
import csv
import time

from spotdl.providers.audio import YouTubeMusic
from spotdl.utils.config import DEFAULT_CONFIG
from spotdl.utils.judge import JUDGE_BACKENDS, create_judge
from spotdl.utils.search import get_simple_songs
from spotdl.utils.spotify import SpotifyClient


def main() -> None:
    """
    Run the benchmark.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--judge", choices=list(JUDGE_BACKENDS), required=True)
    parser.add_argument("--judge-url")
    parser.add_argument("--judge-model")
    parser.add_argument("--judge-threshold", type=float, default=0.7)
    parser.add_argument("--out", default="benchmark.csv")
    args = parser.parse_args()

    SpotifyClient.init(
        client_id=DEFAULT_CONFIG["client_id"],
        client_secret=DEFAULT_CONFIG["client_secret"],
    )

    songs = get_simple_songs(args.urls)
    print(f"Loaded {len(songs)} songs")

    plain = YouTubeMusic()
    judged = YouTubeMusic()
    judged.judge = create_judge(
        args.judge,
        url=args.judge_url,
        model=args.judge_model,
        threshold=args.judge_threshold,
        judge_all=True,
        report_path=args.out.replace(".csv", "_judge.csv"),
    )

    fields = [
        "list",
        "song",
        "spotify_url",
        "spotdl_url",
        "judge_url",
        "same",
        "judge_seconds",
        "correct",
    ]
    with open(args.out, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for index, song in enumerate(songs, 1):
            spotdl_url = plain.search(song)
            start = time.monotonic()
            judge_url = judged.search(song)
            seconds = time.monotonic() - start

            writer.writerow(
                {
                    "list": song.list_name,
                    "song": song.display_name,
                    "spotify_url": song.url,
                    "spotdl_url": spotdl_url or "",
                    "judge_url": judge_url or "",
                    "same": spotdl_url == judge_url,
                    "judge_seconds": round(seconds, 2),
                    "correct": "",
                }
            )
            file.flush()
            print(
                f"[{index}/{len(songs)}] {song.display_name}: "
                f"{'same' if spotdl_url == judge_url else 'DIFFERENT'}"
            )


if __name__ == "__main__":
    main()
