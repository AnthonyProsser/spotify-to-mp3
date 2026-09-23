"""
Print a labelling sheet for a benchmark run: each Spotify track next to
spotDL's pick, with the pick's yt-dlp metadata and flags for what to check
(duration gap, version words, other artists, other album).

Metadata comes from the same cache as scripts/judge_benchmark.py (fetched and
saved on a miss), so rerunning the sheet doesn't hit YouTube again.

Usage: uv run python bench/tools/label_sheet.py bench/baseline_es_picks.jsonl \
    --cache bench/cache > sheet.tsv
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

# pylint: disable=wrong-import-position
from judge_benchmark import DiskCache, install_cache  # noqa: E402

from spotdl.providers.audio import YouTubeMusic  # noqa: E402
from spotdl.providers.audio.base import AudioProviderError  # noqa: E402

VERSION_WORDS = re.compile(
    r"\b(live|en vivo|ao vivo|en directo|remix|cover|karaoke|lyrics?|letra|"
    r"sped|slowed|acoustic|ac[uú]stic[oa]|edit|version|versi[oó]n|remaster\w*|"
    r"instrumental|demo|mono|official video|video oficial|videoclip|visuali[sz]er|"
    r"extended|radio|mix|medley|reprise|8d)\b",
    re.IGNORECASE,
)


def words(text):
    """
    Version words in a title, lowercased.
    """

    return {match.lower() for match in VERSION_WORDS.findall(text or "")}


def main() -> None:
    """
    Print the sheet.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("picks")
    parser.add_argument("--cache", required=True)
    args = parser.parse_args()

    install_cache(DiskCache(Path(args.cache)))
    provider = YouTubeMusic()

    columns = [
        "n",
        "song",
        "sp_album",
        "sp_dur",
        "type",
        "pick_title",
        "pick_artists",
        "pick_album",
        "pick_dur",
        "dur_diff",
        "yt_channel",
        "yt_title",
        "views",
        "flags",
        "url",
    ]
    print("\t".join(columns))
    with open(args.picks, encoding="utf-8") as file:
        for index, line in enumerate(file, 1):
            row = json.loads(line)
            pick = row["pick"]
            if pick is None:
                print(
                    "\t".join(
                        [
                            str(index),
                            row["song"],
                            row["album"] or "",
                            str(row["duration"]),
                        ]
                        + ["UNMATCHED"]
                        + [""] * 10
                    )
                )
                continue

            try:
                meta = provider.get_download_metadata(pick["url"])
            except AudioProviderError as exception:
                meta = {"_error": str(exception)}

            flags = []
            gap = (pick["duration"] or 0) - row["duration"]
            if abs(gap) > 3:
                flags.append(f"dur{gap:+.0f}")
            extra = (words(pick["name"]) | words(meta.get("title"))) - words(
                row["name"]
            )
            if extra:
                flags.append("words:" + ",".join(sorted(extra)))
            sp_artists = {a.lower() for a in row["artists"]}
            if not sp_artists & {a.lower() for a in pick["artists"]}:
                flags.append("artist?")
            if (
                pick["album"]
                and row["album"]
                and pick["album"].lower() != row["album"].lower()
            ):
                flags.append("album")
            if "_error" in meta:
                flags.append("unavailable")

            print(
                "\t".join(
                    str(v)
                    for v in [
                        index,
                        row["song"],
                        row["album"],
                        row["duration"],
                        "song" if pick["verified"] else "video",
                        pick["name"],
                        "; ".join(pick["artists"]),
                        pick["album"] or "",
                        pick["duration"],
                        f"{gap:+.0f}",
                        meta.get("channel") or "",
                        meta.get("title") or "",
                        meta.get("view_count") or pick["views"] or "",
                        " ".join(flags),
                        pick["url"],
                    ]
                )
            )


if __name__ == "__main__":
    main()
