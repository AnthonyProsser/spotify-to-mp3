import logging

import pytest

import spotdl.utils.spotify as spotify_module
from spotdl.utils.spotify import SpotifyClient, SpotifyError


def test_init(patch_dependencies):
    """
    Test SpotifyClient initialization
    """

    SpotifyClient.init(
        client_id="client_id",
        client_secret="client_secret",
        user_auth=False,
        no_cache=True,
    )

    assert SpotifyClient._instance is not None


def test_multiple_init():
    """
    Test multiple SpotifyClient initialization.
    It was initialized in the previous function so there is no need to initialize it again.
    """

    with pytest.raises(SpotifyError):
        SpotifyClient.init(
            client_id="client_id",
            client_secret="client_secret",
            user_auth=False,
            no_cache=True,
        )
        SpotifyClient.init(
            client_id="client_id",
            client_secret="client_secret",
            user_auth=False,
            no_cache=True,
        )


def test_init_uses_free_client_by_default(monkeypatch):
    """
    Test SpotifyClient uses SpotipyFree unless the official API is requested.
    """

    client = object()
    calls = []

    def fake_free_client(**kwargs):
        calls.append(("free", kwargs))
        return client

    def fake_official_client(**kwargs):
        calls.append(("official", kwargs))
        return object()

    monkeypatch.setattr(SpotifyClient, "_instance", None)
    monkeypatch.setattr(SpotifyClient, "_use_official_api", False)
    monkeypatch.setattr(spotify_module, "_init_free_spotify_client", fake_free_client)
    monkeypatch.setattr(
        spotify_module, "_init_official_spotify_client", fake_official_client
    )

    result = SpotifyClient.init(
        client_id="client_id",
        client_secret="client_secret",
    )

    assert result is client
    assert SpotifyClient() is client
    assert calls == [
        (
            "free",
            {
                "client_id": "client_id",
                "client_secret": "client_secret",
                "user_auth": False,
                "no_cache": False,
                "headless": False,
                "max_retries": 3,
                "use_cache_file": False,
                "auth_token": None,
                "cache_path": None,
            },
        )
    ]
    assert SpotifyClient._use_official_api is False


def test_init_uses_official_client_when_requested(monkeypatch):
    """
    Test SpotifyClient can opt into the official Spotipy client.
    """

    client = object()
    calls = []

    def fake_free_client(**kwargs):
        calls.append(("free", kwargs))
        return object()

    def fake_official_client(**kwargs):
        calls.append(("official", kwargs))
        return client

    monkeypatch.setattr(SpotifyClient, "_instance", None)
    monkeypatch.setattr(SpotifyClient, "_use_official_api", False)
    monkeypatch.setattr(spotify_module, "_init_free_spotify_client", fake_free_client)
    monkeypatch.setattr(
        spotify_module, "_init_official_spotify_client", fake_official_client
    )

    result = SpotifyClient.init(
        client_id="client_id",
        client_secret="client_secret",
        use_official_api=True,
    )

    assert result is client
    assert SpotifyClient() is client
    assert calls == [
        (
            "official",
            {
                "client_id": "client_id",
                "client_secret": "client_secret",
                "user_auth": False,
                "no_cache": False,
                "headless": False,
                "max_retries": 3,
                "use_cache_file": False,
                "auth_token": None,
                "cache_path": None,
            },
        )
    ]
    assert SpotifyClient._use_official_api is True


def test_init_uses_official_client_for_official_api_only_options(monkeypatch, caplog):
    """
    Test SpotifyClient routes official API only options to the official client.
    """

    client = object()
    calls = []

    def fake_free_client(**kwargs):
        calls.append(("free", kwargs))
        return object()

    def fake_official_client(**kwargs):
        calls.append(("official", kwargs))
        return client

    monkeypatch.setattr(SpotifyClient, "_instance", None)
    monkeypatch.setattr(SpotifyClient, "_use_official_api", False)
    monkeypatch.setattr(spotify_module, "_init_free_spotify_client", fake_free_client)
    monkeypatch.setattr(
        spotify_module, "_init_official_spotify_client", fake_official_client
    )
    caplog.set_level(logging.INFO, logger="spotdl.utils.spotify")

    result = SpotifyClient.init(
        client_id="client_id",
        client_secret="client_secret",
        user_auth=True,
        auth_token="auth_token",
        use_cache_file=True,
    )

    assert result is client
    assert calls[0][0] == "official"
    assert SpotifyClient._use_official_api is True
    assert "Using the official Spotify Web API because" in caplog.text


DESKTOP_SEARCH = {
    "data": {
        "searchV2": {
            "artists": {
                "items": [
                    {
                        "data": {
                            "uri": "spotify:artist:a1",
                            "profile": {"name": "Gorillaz"},
                        }
                    },
                    {"data": {"uri": "", "profile": {"name": "No uri"}}},
                ]
            },
            "albumsV2": {
                "items": [{"data": {"uri": "spotify:album:b2", "name": "Demon Days"}}]
            },
            "playlists": {
                "items": [
                    {
                        "data": {
                            "uri": "spotify:playlist:c3",
                            "name": "This Is Gorillaz",
                        }
                    },
                    {"data": {"uri": "spotify:user:x", "name": "Not a playlist"}},
                ]
            },
        }
    }
}


@pytest.mark.parametrize(
    "search_type, expected",
    [
        ("artist", [("Gorillaz", "a1")]),
        ("album", [("Demon Days", "b2")]),
        ("playlist", [("This Is Gorillaz", "c3")]),
    ],
)
def test_format_free_search_results(search_type, expected):
    result = spotify_module.format_free_search_results(DESKTOP_SEARCH, search_type)

    items = result[f"{search_type}s"]["items"]
    assert [(item["name"], item["id"]) for item in items] == expected
    assert all(item["type"] == search_type for item in items)


def test_format_free_search_results_empty_response():
    assert spotify_module.format_free_search_results({}, "artist") == {
        "artists": {"items": []}
    }


def test_free_client_searches_artists(monkeypatch):
    queries = []

    class FakeSong:
        def query_songs(self, query, limit=10, offset=0):
            queries.append(query)
            return DESKTOP_SEARCH

    import spotapi

    monkeypatch.setattr(spotapi, "Song", FakeSong)
    client = object.__new__(spotify_module._FreeSpotifyClient)

    result = client.search("artist: gorillaz", type="artist")

    assert queries == ["gorillaz"]
    assert result["artists"]["items"][0]["id"] == "a1"


@pytest.mark.parametrize(
    "raw_type, expected",
    [
        ("SINGLE", "single"),
        ("EP", "single"),
        ("ALBUM", "album"),
        ("COMPILATION", "compilation"),
    ],
)
def test_free_client_album_type(monkeypatch, raw_type, expected):
    def fake_album(self, album_id, *args, **kwargs):
        return {"name": "Ropes", "type": raw_type, "album_type": "album"}

    monkeypatch.setattr(spotify_module.FreeSpotify, "album", fake_album)
    client = object.__new__(spotify_module._FreeSpotifyClient)

    assert client.album("id")["album_type"] == expected
