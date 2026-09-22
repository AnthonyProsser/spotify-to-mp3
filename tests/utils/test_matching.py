import pytest

from spotdl.types.result import Result
from spotdl.types.song import Song
from spotdl.utils.matching import calc_album_match, check_forbidden_words


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
