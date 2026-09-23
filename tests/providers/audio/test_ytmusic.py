import pytest

from spotdl.providers.audio import YouTubeMusic
from spotdl.providers.audio.ytmusic import parse_views
from spotdl.types.song import Song


@pytest.mark.vcr()
def test_ytm_search():
    provider = YouTubeMusic()

    assert (
        provider.search(
            Song.from_dict(
                {
                    "name": "Nobody Else",
                    "artists": ["Abstrakt"],
                    "artist": "Abstrakt",
                    "album_id": "0kx3ml8bdAYrQtcIwvkhp8",
                    "album_name": "Nobody Else",
                    "album_artist": "Abstrakt",
                    "album_type": "album",
                    "genres": [],
                    "disc_number": 1,
                    "disc_count": 1,
                    "duration": 162.406,
                    "year": 2022,
                    "date": "2022-03-17",
                    "track_number": 1,
                    "tracks_count": 1,
                    "isrc": "GB2LD2210007",
                    "song_id": "0kx3ml8bdAYrQtcIwvkhp8",
                    "cover_url": "https://i.scdn.co/image/ab67616d0000b27345f5ba253b9825efc88bc236",
                    "explicit": False,
                    "publisher": "NCS",
                    "url": "https://open.spotify.com/track/0kx3ml8bdAYrQtcIwvkhp8",
                    "copyright_text": "2022 NCS",
                    "download_url": None,
                }
            )
        )
        is not None
    )


@pytest.mark.vcr()
def test_ytm_get_results():
    provider = YouTubeMusic()

    results = provider.get_results("Lost Identities Moments")

    assert len(results) > 3


def test_ytm_get_results_retries_with_new_client(mocker):
    first_client = mocker.Mock()
    first_client.search.return_value = []
    second_client = mocker.Mock()
    second_client.search.return_value = [
        {
            "videoId": "video_0",
            "resultType": "song",
            "title": "Test Song",
            "artists": [{"name": "Test Artist"}],
            "duration": "1:23",
        }
    ]
    mocker.patch(
        "spotdl.providers.audio.ytmusic.YTMusic",
        side_effect=[first_client, second_client],
    )

    provider = YouTubeMusic()
    results = provider.get_results("Test Song")

    assert len(results) == 1
    assert results[0].url == "https://music.youtube.com/watch?v=video_0"
    assert results[0].name == "Test Song"
    assert first_client.search.call_count == 1
    assert second_client.search.call_count == 1


@pytest.mark.parametrize(
    "text, require_word, expected",
    [
        ("968\xa0Mio.\xa0Wiedergaben", True, 968_000_000),
        ("1,8\xa0Mrd.\xa0Wiedergaben", True, 1_800_000_000),
        ("294.406\xa0Wiedergaben", True, 294_406),
        ("12\xa0Tsd.\xa0Aufrufe", True, 12_000),
        ("243\xa0Mio.", False, 243_000_000),
        ("3,2\xa0Mio.", False, 3_200_000),
        ("243\xa0Mio.", True, None),
        ("Bad Bunny", False, None),
        ("2Pac", True, None),
        (None, False, None),
    ],
)
def test_parse_views(text, require_word, expected):
    assert parse_views(text, require_word=require_word) == expected


def test_ytm_get_results_moves_play_count_to_views(mocker):
    client = mocker.Mock()
    client.search.return_value = [
        {
            "videoId": "video_0",
            "resultType": "song",
            "title": "DtMF",
            "artists": [
                {"name": "Bad Bunny", "id": "UCiY3z8HAGD6BlSNKVn2kSvQ"},
                {"name": "968\xa0Mio.\xa0Wiedergaben", "id": None},
            ],
            "duration": "3:58",
        },
        {
            "videoId": "video_1",
            "resultType": "video",
            "title": "Bad Bunny - DtMF (Letra)",
            "artists": [{"name": "iPerol", "id": "UCFwS8sLuE4Du7VA_DDnhmeg"}],
            "views": "243\xa0Mio.",
            "duration": "4:01",
        },
        {
            "videoId": "video_2",
            "resultType": "song",
            "title": "Only a play count",
            "artists": [{"name": "5\xa0Wiedergaben", "id": None}],
            "duration": "1:00",
        },
    ]
    mocker.patch("spotdl.providers.audio.ytmusic.YTMusic", return_value=client)

    results = YouTubeMusic().get_results("bad bunny dtmf")

    assert len(results) == 2
    assert results[0].artists == ("Bad Bunny",)
    assert results[0].views == 968_000_000
    assert results[1].artists == ("iPerol",)
    assert results[1].views == 243_000_000
