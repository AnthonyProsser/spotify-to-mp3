import pytest

from spotdl.types.result import Result
from spotdl.types.song import Song
from spotdl.utils.matching import (
    calc_album_match,
    calc_artists_match,
    calc_main_artist_match,
    calc_name_match,
    check_forbidden_words,
    check_version_words,
    order_results,
    strip_credits,
    strip_remaster_suffix,
)


def make_song(name, artists, duration=200, album="Album"):
    return Song.from_missing_data(
        name=name,
        artists=artists,
        artist=artists[0],
        album_name=album,
        duration=duration,
        song_id="song",
    )


def make_result(name, artists, duration=200, verified=True, album=None, rid="x"):
    return Result(
        source="YouTubeMusic",
        url=f"https://music.youtube.com/watch?v={rid}",
        verified=verified,
        name=name,
        duration=duration,
        author=artists[0],
        result_id=rid,
        artists=tuple(artists),
        album=album,
    )


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Killer Queen - Remastered 2011", "Killer Queen"),
        ("Panama - 2015 Remaster", "Panama"),
        ("Black Dog - Remaster", "Black Dog"),
        ("Burn - Remastered 2004", "Burn"),
        ("Tusa - En Vivo", "Tusa - En Vivo"),
        ("Remaster", "Remaster"),
    ],
)
def test_strip_remaster_suffix(name, expected):
    assert strip_remaster_suffix(name) == expected


@pytest.mark.parametrize(
    "song_name, result_name, expected",
    [
        # Another language's version is protected
        (
            "Waka Waka (Esto es Africa) (feat. Freshlyground)",
            "Waka Waka (This Time for Africa) (feat. Freshlyground)",
            ["this-time-for"],
        ),
        ("Under Pressure", "Under Pressure (Rah Mix)", ["rah-mix"]),
        (
            "Hot for Teacher - 2015 Remaster",
            "Hot for Teacher (2004 Remaster)",
            ["2004"],
        ),
        # Credits, neutral words and the song's own words are fine
        ("Chantaje", "Chantaje (feat. Maluma)", []),
        ("Bailando - Spanish Version", "Bailando (Spanish Version) (mit X)", []),
        ("Paranoid", "Paranoid (Official Video)", []),
        ("Tusa", "Tusa (Letra/Lyrics)", []),
        ("Ella Baila Sola", "Ella Baila Sola (Peso Pluma)", []),
    ],
)
def test_check_version_words(song_name, result_name, expected):
    song = make_song(song_name, ["Artist", "Peso Pluma"])
    result = make_result(result_name, ["Artist"])

    assert check_version_words(song, result) == expected


@pytest.mark.parametrize(
    "result_name, expected",
    [
        ("Ella Baila Sola (Peso Pluma)", "Ella Baila Sola"),
        ("Bailar (mit Pitbull & Elvis Crespo)", "Bailar"),
        ("Bailar (Remix)", "Bailar (Remix)"),
        ("Bailar (Peso Pluma Remix)", "Bailar (Peso Pluma Remix)"),
    ],
)
def test_strip_credits(result_name, expected):
    song = make_song("Bailar", ["Eslabon Armado", "Peso Pluma"])

    assert strip_credits(song, result_name) == expected


def test_strip_credits_keeps_brackets_of_the_song_name():
    song = make_song("Rosa (feat. Peso Pluma)", ["Eslabon Armado", "Peso Pluma"])

    assert strip_credits(song, "Rosa (feat. Peso Pluma)") == "Rosa (feat. Peso Pluma)"


def test_calc_album_match_ignores_edition_notes():
    song = make_song("Song", ["Queen"], album="Jazz")
    deluxe = make_result("Song", ["Queen"], album="Jazz (Deluxe Edition)")
    other = make_result("Song", ["Queen"], album="Greatest Hits")

    assert calc_album_match(song, deluxe) == 100.0
    assert calc_album_match(song, other) < 80


def test_main_artist_matches_single_result_artist():
    # YouTube Music lists only Queen and names David Bowie in the title
    song = make_song("Under Pressure", ["Queen", "David Bowie"])
    result = make_result("Under Pressure (feat. David Bowie)", ["Queen"])

    assert calc_main_artist_match(song, result) == 100.0
    assert calc_artists_match(song, result) == 100.0


def test_main_artist_found_after_sorting():
    song = make_song("Ella Baila Sola", ["Eslabon Armado", "Peso Pluma"])
    result = make_result("Ella Baila Sola", ["Eslabon Armado", "Peso Pluma"])

    assert calc_main_artist_match(song, result) == 100.0


def test_name_match_ignores_remaster_note_and_credits():
    remastered = make_song("Killer Queen - Remastered 2011", ["Queen"])
    assert calc_name_match(remastered, make_result("Killer Queen", ["Queen"])) == 100

    song = make_song("Ella Baila Sola", ["Eslabon Armado", "Peso Pluma"])
    result = make_result("Ella Baila Sola (Peso Pluma)", ["Eslabon Armado"])
    assert calc_name_match(song, result) == 100


def test_album_penalty_only_when_length_differs():
    song = make_song("Paranoid", ["Black Sabbath"], 167, "The Ultimate Collection")
    same_length = make_result("Paranoid", ["Black Sabbath"], 168, album="Paranoid")
    longer = make_result("Paranoid", ["Black Sabbath"], 175, album="Paranoid", rid="y")

    scores = order_results([same_length, longer], song)

    assert scores[same_length] >= 95
    assert scores.get(longer, 0) < 80


def test_close_match_keeps_length_in_score():
    song = make_song("Que Calor", ["Major Lazer"], 169)
    audio = make_result("Que Calor", ["Major Lazer"], 170, verified=False)
    video = make_result("Que Calor", ["Major Lazer"], 176, verified=False, rid="y")

    scores = order_results([audio, video], song)

    assert scores[audio] - scores[video] >= 10


def test_other_version_is_not_a_sure_match():
    song = make_song(
        "Waka Waka (Esto es Africa) (feat. Freshlyground)",
        ["Shakira", "Freshlyground"],
        202,
    )
    english = make_result(
        "Waka Waka (This Time for Africa) (feat. Freshlyground)", ["Shakira"], 204
    )

    assert order_results([english], song).get(english, 0) < 80


def test_calc_album_match_without_song_album(mocker):
    """
    Test album matching when the song has no album name.
    """

    song = mocker.Mock(album_name=None)
    result = mocker.Mock(album="Album")

    assert calc_album_match(song, result) == 0.0


@pytest.mark.parametrize(
    "song_name, result_name, expected",
    [
        ("Tusa", "Tusa (En Vivo)", ["en-vivo"]),
        ("Tusa", "TUSA - En Directo", ["en-directo"]),
        ("Garota de Ipanema", "Garota de Ipanema (Ao Vivo)", ["ao-vivo"]),
        ("Corazón", "Corazón (Versión Acústica)", ["acustica"]),
        ("Tusa (En Vivo)", "Tusa (En Vivo)", []),
        ("Quien vivo", "Quien Vivo", []),
        ("Tusa", "TUSA (Video Oficial)", []),
        ("Tusa", "Tusa - Lead Vocal Track Isolated", ["isolated"]),
        ("Tusa", "Tusa (Drumless)", ["drumless"]),
    ],
)
def test_check_forbidden_words_other_languages(song_name, result_name, expected):
    song = Song.from_missing_data(name=song_name, artists=["X"], artist="X")
    result = Result(
        source="YouTube",
        url="https://youtube.com/watch?v=x",
        verified=False,
        name=result_name,
        duration=200,
        author="X",
        result_id="x",
    )

    assert check_forbidden_words(song, result)[1] == expected
