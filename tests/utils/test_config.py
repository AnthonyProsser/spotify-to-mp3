import os
import platform
from pathlib import Path
from types import SimpleNamespace

import pytest

from spotdl.utils.config import *


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    data = SimpleNamespace()
    data.directory = tmp_path
    # Linux follows XDG (~/.config/spotdl) unless ~/.spotdl already exists
    if platform.system() == "Linux":
        data.spotdl = Path(tmp_path, ".config", "spotdl")
    else:
        data.spotdl = Path(tmp_path, ".spotdl")
    yield data


def test_get_spotdl_path(setup):
    """
    Tests that the spotdl path is created if it does not exist.
    """

    assert get_spotdl_path() == setup.spotdl
    assert os.path.exists(setup.spotdl)


def test_get_spotdl_path_keeps_old_folder_on_linux(setup, monkeypatch):
    """
    Tests that an existing ~/.spotdl folder is still used on Linux.
    """

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    Path(setup.directory, ".spotdl").mkdir()

    assert get_spotdl_path() == Path(setup.directory, ".spotdl")


def test_get_config_path(setup):
    """
    Tests if the path to config file is correct.
    """

    assert get_config_file() == Path(setup.spotdl, "config.json")


def test_get_cache_path(setup):
    """
    Tests if the path to the cache file is correct.
    """

    assert get_cache_path() == Path(setup.spotdl, ".spotipy")


def test_get_temp_path(setup):
    """
    Tests if the path to the temp folder is correct.
    """

    assert get_temp_path() == Path(setup.spotdl, "temp")


def test_get_config_not_created(setup):
    """
    Tests if exception is raised if config file does not exist.
    """

    with pytest.raises(ConfigError):
        get_config()


def test_use_official_api_default():
    """
    Tests that the official API client is opt-in.
    """

    settings = create_settings_type(SimpleNamespace(), {}, SPOTIFY_OPTIONS)

    assert settings["use_official_api"] is False


def test_use_official_api_from_config():
    """
    Tests that config can enable the official API client.
    """

    settings = create_settings_type(
        SimpleNamespace(),
        {"use_official_api": True},
        SPOTIFY_OPTIONS,
    )

    assert settings["use_official_api"] is True


def test_use_official_api_argument_overrides_config():
    """
    Tests that CLI arguments take priority over config values.
    """

    settings = create_settings_type(
        SimpleNamespace(use_official_api=True),
        {"use_official_api": False},
        SPOTIFY_OPTIONS,
    )

    assert settings["use_official_api"] is True
