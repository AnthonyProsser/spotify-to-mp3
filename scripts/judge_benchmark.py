"""
Compare spotDL's matching with and without the AI judge, without downloading.

For every song in the given Spotify URLs, run the YouTube Music search twice,
once with spotDL's matching alone and once with the judge on every song, and
write a CSV with both picks side by side. Label the `correct` column by hand
(spotdl / judge / both / neither) to measure accuracy.

Without `--judge`, only spotDL's own search runs and `judge_url` is left empty.

With `--cache DIR`, Spotify metadata, YouTube Music search results and yt-dlp
metadata (`download=False`) are saved to DIR and read back on later runs, so
experiments can be scored without searching again. Failed metadata lookups are
cached as well.

Next to the CSV, `*_picks.jsonl` records each song's Spotify data and the
details of spotDL's pick (title, artists, album, duration, verified), for
labelling.

Usage:
    uv run python scripts/judge_benchmark.py URL [URL ...] --judge kev \
        --out benchmark.csv
    uv run python scripts/judge_benchmark.py URL [URL ...] \
        --cache bench/cache --out bench/base_es.csv
"""

import argparse
import csv
import gzip
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ytmusicapi import YTMusic

from spotdl.providers.audio import YouTubeMusic
from spotdl.providers.audio.base import AudioProvider, AudioProviderError
from spotdl.types.result import Result
from spotdl.types.song import Song
from spotdl.utils.config import DEFAULT_CONFIG
from spotdl.utils.judge import JUDGE_BACKENDS, create_judge
from spotdl.utils.search import get_simple_songs, reinit_song
from spotdl.utils.spotify import SpotifyClient

# yt-dlp fields kept in the cache; the full info dict is mostly stream formats
METADATA_FIELDS = (
    "id",
    "title",
    "fulltitle",
    "channel",
    "channel_id",
    "uploader",
    "duration",
    "view_count",
    "availability",
    "age_limit",
    "categories",
    "tags",
    "track",
    "artist",
    "artists",
    "album",
    "release_year",
    "upload_date",
    "description",
    "live_status",
    "was_live",
)


class DiskCache:
    """
    A folder of gzipped JSON files, one per key.
    """

    def __init__(self, folder: Path):
        self.folder = folder

    def path(self, kind: str, key: str) -> Path:
        """
        Get the file for a key.
        """

        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        return self.folder / kind / f"{digest}.json.gz"

    def get(self, kind: str, key: str) -> Optional[Any]:
        """
        Get a cached value, or None if there isn't one.
        """

        path = self.path(kind, key)
        if not path.exists():
            return None

        with gzip.open(path, "rt", encoding="utf-8") as file:
            return json.load(file)["value"]

    def put(self, kind: str, key: str, value: Any) -> None:
        """
        Save a value.
        """

        path = self.path(kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as file:
            json.dump({"key": key, "value": value}, file, ensure_ascii=False)


def install_cache(cache: DiskCache) -> None:
    """
    Route YouTube Music searches and yt-dlp metadata lookups through the cache.
    """

    search = YTMusic.search

    def cached_search(client, query, *args, **kwargs):
        key = json.dumps([query, args, kwargs], sort_keys=True, ensure_ascii=False)
        value = cache.get("search", key)
        if value is None:
            value = search(client, query, *args, **kwargs)
            cache.put("search", key, value)
        return value

    YTMusic.search = cached_search  # type: ignore

    get_download_metadata = AudioProvider.get_download_metadata

    def cached_get_download_metadata(provider, url, download=False):
        if download:
            return get_download_metadata(provider, url, download)

        value = cache.get("metadata", url)
        if value is None:
            try:
                data = get_download_metadata(provider, url, download)
                value = {field: data.get(field) for field in METADATA_FIELDS}
            except AudioProviderError as exception:
                value = {"_error": str(exception)}
            cache.put("metadata", url, value)

        if "_error" in value:
            raise AudioProviderError(value["_error"])

        return value

    AudioProvider.get_download_metadata = cached_get_download_metadata  # type: ignore


def load_songs(urls: List[str], cache: Optional[DiskCache]) -> List[Song]:
    """
    Load the songs of every URL, with the fields playlist loading leaves out
    filled in, as the downloader does before searching.
    """

    songs: List[Song] = []
    for url in urls:
        cached = cache.get("songs", url) if cache else None
        if cached is not None:
            songs.extend(Song.from_dict(data) for data in cached)
            continue

        loaded = []
        for song in get_simple_songs([url]):
            try:
                song = reinit_song(song)
            except Exception as exception:  # pylint: disable=broad-except
                print(f"Couldn't reinitialize {song.display_name}: {exception!r}")
            loaded.append(song)

        if cache:
            cache.put("songs", url, [song.json for song in loaded])
        songs.extend(loaded)

    return songs


def describe(result: Optional[Result]) -> Optional[Dict[str, Any]]:
    """
    The fields of a search result needed to label it.
    """

    if result is None:
        return None

    return {
        "url": result.url,
        "name": result.name,
        "artists": list(result.artists or [result.author]),
        "album": result.album,
        "duration": result.duration,
        "verified": result.verified,
        "views": result.views,
        "isrc_search": result.isrc_search,
        "search_query": result.search_query,
    }


def main() -> None:
    """
    Run the benchmark.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--judge", choices=list(JUDGE_BACKENDS))
    parser.add_argument("--judge-url")
    parser.add_argument("--judge-model")
    parser.add_argument("--judge-threshold", type=float, default=0.7)
    parser.add_argument("--cache", help="folder for cached searches and metadata")
    parser.add_argument("--out", default="benchmark.csv")
    args = parser.parse_args()

    cache = DiskCache(Path(args.cache)) if args.cache else None
    if cache:
        install_cache(cache)

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

    songs = load_songs(args.urls, cache)
    print(f"Loaded {len(songs)} songs")

    plain = YouTubeMusic()

    # Remember every result spotDL's search saw, to describe its pick
    seen_results: Dict[str, Result] = {}
    plain_get_results = plain.get_results

    def recording_get_results(search_term, *a, **kw):
        results = plain_get_results(search_term, *a, **kw)
        for result in results:
            seen_results.setdefault(result.url, result)
        return results

    plain.get_results = recording_get_results  # type: ignore

    judged: Optional[YouTubeMusic] = None
    judge_times: List[float] = []
    requests_log = None
    if args.judge:
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
                requests_log.write(  # type: ignore
                    json.dumps({"state": state, "answers": answers}, ensure_ascii=False)
                    + "\n"
                )
                requests_log.flush()  # type: ignore

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
    picks_path = args.out.replace(".csv", "_picks.jsonl")
    with (
        open(args.out, "w", encoding="utf-8", newline="") as file,
        open(picks_path, "w", encoding="utf-8") as picks_file,
    ):
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for index, song in enumerate(songs, 1):
            # Retry network errors so one dropped connection doesn't end the run
            for attempt in range(3):
                try:
                    seen_results.clear()
                    start = time.monotonic()
                    spotdl_url = plain.search(song)
                    seconds = time.monotonic() - start
                    judge_url = None
                    if judged is not None:
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
                    "same": spotdl_url == judge_url if judged else "",
                    "search_seconds": round(seconds, 2),
                    "judge_seconds": round(sum(judge_times), 3) if judge_times else "",
                    "correct": "",
                }
            )
            file.flush()

            picks_file.write(
                json.dumps(
                    {
                        "song": song.display_name,
                        "spotify_url": song.url,
                        "name": song.name,
                        "artists": song.artists,
                        "album": song.album_name,
                        "duration": song.duration,
                        "isrc": song.isrc,
                        "explicit": song.explicit,
                        "pick": describe(seen_results.get(spotdl_url or "")),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            picks_file.flush()

            if judged is not None:
                status = "same" if spotdl_url == judge_url else "DIFFERENT"
            else:
                status = spotdl_url or "no match"
            print(f"[{index}/{len(songs)}] {song.display_name}: {status}")

    if requests_log is not None:
        requests_log.close()


if __name__ == "__main__":
    main()
