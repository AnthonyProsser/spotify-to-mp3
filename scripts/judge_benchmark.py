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
import json
import time
from typing import Dict, List

from spotdl.providers.audio import YouTubeMusic
from spotdl.providers.audio.base import AudioProvider
from spotdl.utils.config import DEFAULT_CONFIG
from spotdl.utils.judge import JUDGE_BACKENDS, create_judge
from spotdl.utils.search import get_simple_songs, reinit_song
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

    # Both searches look up the same videos' view counts; do it once
    view_cache: Dict[str, int] = {}
    get_views = AudioProvider.get_views

    def cached_get_views(provider, url):
        if url not in view_cache:
            view_cache[url] = get_views(provider, url)
        return view_cache[url]

    AudioProvider.get_views = cached_get_views  # type: ignore

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

    # The first request to a local server loads the model; keep it out of
    # the latency numbers
    judged.judge.client.system_one(  # type: ignore
        "warm up", {"q": {"type": "noul", "instructions": "Is this a test?"}}
    )

    # Time the judge's model calls on their own, without the YouTube search
    judge_times: List[float] = []
    client = judged.judge.client  # type: ignore
    system_one = client.system_one

    # Log every judge request and answer, to check what the judge saw
    requests_log = open(  # pylint: disable=consider-using-with
        args.out.replace(".csv", "_requests.jsonl"), "w", encoding="utf-8"
    )

    def timed_system_one(state, questions):
        start = time.monotonic()
        answers = None
        try:
            answers = system_one(state, questions)
            return answers
        finally:
            judge_times.append(time.monotonic() - start)
            requests_log.write(
                json.dumps({"state": state, "answers": answers}, ensure_ascii=False)
                + "\n"
            )
            requests_log.flush()

    client.system_one = timed_system_one

    fields = [
        "list",
        "song",
        "spotify_url",
        "spotdl_url",
        "judge_url",
        "same",
        "search_seconds",
        "judge_seconds",
        "correct",
    ]
    with open(args.out, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for index, song in enumerate(songs, 1):
            # Fill in the album and other fields playlist loading leaves out,
            # as the downloader does before searching
            try:
                song = reinit_song(song)
            except Exception as exception:  # pylint: disable=broad-except
                print(f"Couldn't reinitialize {song.display_name}: {exception!r}")

            # Retry network errors so one dropped connection doesn't end the run
            for attempt in range(3):
                try:
                    spotdl_url = plain.search(song)
                    judge_times.clear()
                    start = time.monotonic()
                    judge_url = judged.search(song)
                    seconds = time.monotonic() - start
                    break
                except Exception as exception:  # pylint: disable=broad-except
                    print(f"Error on {song.display_name}: {exception!r}")
                    time.sleep(10 * (attempt + 1))
            else:
                print(f"Skipping {song.display_name} after 3 errors")
                continue

            writer.writerow(
                {
                    "list": song.list_name,
                    "song": song.display_name,
                    "spotify_url": song.url,
                    "spotdl_url": spotdl_url or "",
                    "judge_url": judge_url or "",
                    "same": spotdl_url == judge_url,
                    "search_seconds": round(seconds, 2),
                    "judge_seconds": round(sum(judge_times), 3) if judge_times else "",
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
