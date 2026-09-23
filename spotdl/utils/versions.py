"""
Words and notes in song and result names that tell versions apart:
remaster notes, album editions, artist credits and other versions in brackets
"""

import re
from typing import List

from spotdl.types.result import Result
from spotdl.types.song import Song
from spotdl.utils.formatter import slugify

__all__ = [
    "NEUTRAL_WORDS",
    "CREDIT_WORDS",
    "BRACKETS_REGEX",
    "REMASTER_SUFFIX_REGEX",
    "EDITION_REGEX",
    "check_version_words",
    "strip_credits",
    "strip_remaster_suffix",
    "strip_album_edition",
]


# Words in a result's brackets that don't name another version,
# e.g. "(Official Video)" or "(Letra/Lyrics)"
NEUTRAL_WORDS = {
    "official",
    "oficial",
    "video",
    "videoclip",
    "clip",
    "audio",
    "music",
    "musica",
    "lyrics",
    "lyric",
    "letra",
    "hd",
    "hq",
    "4k",
    "visualizer",
    "visualiser",
    "explicit",
    "album",
    "version",
    "original",
}

# Brackets that start with one of these credit artists, e.g. "(feat. Maluma)"
CREDIT_WORDS = {"feat", "ft", "featuring", "with", "mit", "con", "avec", "prod"}

BRACKETS_REGEX = re.compile(r"[\(\[]([^\(\)\[\]]*)[\)\]]")

# Spotify's remaster notes, e.g. "Killer Queen - Remastered 2011" or
# "Panama - 2015 Remaster"
REMASTER_SUFFIX_REGEX = re.compile(
    r"\s+-\s+(?:\d{4}\s+)?(?:digital(?:ly)?\s+)?remaster(?:ed)?"
    r"(?:\s+(?:version|\d{4}))*\s*$",
    re.IGNORECASE,
)

# Album edition notes, e.g. "Jazz (Deluxe Edition)" or "1984 (Remastered)"
EDITION_REGEX = re.compile(
    r"\s*[\(\[][^\)\]]*\b(?:deluxe|edition|remaster(?:ed)?|expanded|anniversary"
    r"|bonus|version|reissue|legacy|collector'?s|special)\b[^\)\]]*[\)\]]",
    re.IGNORECASE,
)


def check_version_words(song: Song, result: Result) -> List[str]:
    """
    Find words in the result's brackets that name another version, e.g.
    "(This Time for Africa)" or "(2004 Remaster)", ignoring artist credits,
    words from the song's name or artists, and neutral words like "Official
    Video"

    ### Arguments
    - song: song to match
    - result: result to match

    ### Returns
    - the extra words of each bracket that has any
    """

    song_words = set(slugify(song.name).split("-"))
    for artist in song.artists:
        song_words.update(slugify(artist).split("-"))

    groups = []
    for group in BRACKETS_REGEX.findall(result.name):
        words = [word for word in slugify(group).split("-") if word]
        if not words or words[0] in CREDIT_WORDS:
            continue

        extra = [
            word
            for word in words
            if word not in song_words and word not in NEUTRAL_WORDS
        ]
        if extra:
            groups.append("-".join(extra))

    return groups


def strip_credits(song: Song, name: str) -> str:
    """
    Remove brackets that only credit artists from a result name, e.g.
    "Ella Baila Sola (Peso Pluma)" -> "Ella Baila Sola", unless the song's
    own name has them

    ### Arguments
    - song: song to match
    - name: the result name

    ### Returns
    - the name without artist credits
    """

    artist_words = set()
    for artist in song.artists:
        artist_words.update(slugify(artist).split("-"))

    song_name = slugify(song.name)

    def is_credit(match: "re.Match") -> bool:
        words = [word for word in slugify(match.group(1)).split("-") if word]
        if not words or slugify(match.group(1)) in song_name:
            return False

        if words[0] in CREDIT_WORDS:
            return True

        return all(word in artist_words for word in words)

    return BRACKETS_REGEX.sub(
        lambda match: "" if is_credit(match) else match.group(0), name
    ).strip()


def strip_remaster_suffix(name: str) -> str:
    """
    Remove Spotify's remaster note from a song name,
    e.g. "Killer Queen - Remastered 2011" -> "Killer Queen"

    ### Arguments
    - name: the song name

    ### Returns
    - the name without the note
    """

    return REMASTER_SUFFIX_REGEX.sub("", name)


def strip_album_edition(album: str) -> str:
    """
    Remove edition notes from an album name,
    e.g. "Jazz (Deluxe Edition)" -> "Jazz"

    ### Arguments
    - album: the album name

    ### Returns
    - the album name without edition notes
    """

    return EDITION_REGEX.sub("", album)
