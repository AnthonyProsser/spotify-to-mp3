
<!--- mdformat-toc start --slug=github --->

<!---
!!! IF EDITING THE README, MOST CHANGES SHOULD ALSO BE PROPAGATED TO index.md in `/docs/`.
!!! ADJUST FORMATTING THERE AS NEEDED, AND REMOVE README-ONLY / ReadTheDocs REFERENCES.
--->

<div align="center">

# spotDL v4

**spotDL** finds songs from Spotify playlists on YouTube and downloads them - along with album art, lyrics and metadata.

[![MIT License](https://img.shields.io/github/license/spotdl/spotify-downloader?color=44CC11&style=flat-square)](https://github.com/spotDL/spotify-downloader/blob/master/LICENSE)
[![PyPI version](https://img.shields.io/pypi/pyversions/spotDL?color=%2344CC11&style=flat-square)](https://pypi.org/project/spotdl/)
[![PyPi downloads](https://img.shields.io/pypi/dw/spotDL?label=downloads@pypi&color=344CC11&style=flat-square)](https://pypi.org/project/spotdl/)
![GitHub Repo stars](https://img.shields.io/github/stars/spotDL/spotify-downloader)
![Contributors](https://img.shields.io/github/contributors/spotDL/spotify-downloader?style=flat-square)
[![Discord](https://img.shields.io/discord/771628785447337985?label=discord&logo=discord&style=flat-square)](https://discord.gg/xCa23pwJWY)

> spotDL: The fastest, easiest and most accurate command-line music downloader.
</div>

______________________________________________________________________
**[Read the documentation on ReadTheDocs!](https://spotdl.readthedocs.io)**
______________________________________________________________________

## About this fork: AI match judge

This is a fork of [spotDL](https://github.com/spotDL/spotify-downloader) (MIT) that adds an optional AI "judge". spotDL ranks YouTube results with fuzzy matching as usual. The judge then looks at the top 5 results and picks the one that is the same recording as the Spotify track, or none of them. It rejects live, cover, remix and sped-up versions unless the Spotify track is that version.

The judge is a "System One" decision model. It returns a choice with a probability instead of generated text:

| `--judge` | Model | Runs | Setup |
| --- | --- | --- | --- |
| `jev` | TypeSafe Jev | Cloud | `TYPESAFE_API_KEY` |
| `jev-cloudflare` | Jev on Cloudflare Workers AI | Cloud | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` |
| `kev` | [Kev](https://github.com/jaredpalmer/kev), an open Jev-style model | Local | Start a Kev server (below) |

Jev costs about $0.042 per million input tokens and output is free, so judging a 1,000-song playlist costs a few cents.

To run Kev locally (it needs Python 3.12+ and `uv`; Kev-0.8B needs about 4 GB of RAM, Kev-4B about 8 GB):

```bash
git clone https://github.com/jaredpalmer/kev.git && cd kev
uv sync --extra serve
uv run --extra serve python -m kev.serve --run jaredpalmer/kev-4b --port 8009
```

Kev also comes in 0.8B and 9B sizes. See its README for the model names.

Then:

```bash
spotdl download "https://open.spotify.com/playlist/..." --judge kev
```

Options:

- `--judge-threshold 0.7`: the minimum probability needed to use the judge's pick. Below it, spotDL's own pick is kept.
- `--judge-all`: judge every song. By default, songs spotDL is already sure of (ISRC match, or a verified result scoring 80 or more) skip the judge.
- `--judge-url` / `--judge-model`: point to a different server or model.
- `--judge-report path.csv`: where the report goes (default `judge_report.csv`). It has one row per judged song: spotDL's pick, the judge's pick and confidence, and the outcome (`agreed`, `overrode`, `low_confidence`, `rejected_all`, `not_original` or `judge_error`).

If the judge can't be reached, spotDL's own pick is used and the song is logged as `judge_error`.

Downloading from YouTube may break YouTube's Terms of Service. Use this for personal use only.

______________________________________________________________________

## Installation

Refer to our [Installation Guide](docs/installation.md) for more details.

### Python (Recommended Method)

- _spotDL_ can be installed by running `pip install spotdl`.
- To update spotDL run `pip install --upgrade spotdl`

  > On some systems you might have to change `pip` to `pip3`.

<details>
    <summary style="font-size:1.25em"><strong>Other options</strong></summary>

- Prebuilt executable
  - You can download the latest version from the
    [Releases Tab](https://github.com/spotDL/spotify-downloader/releases)
- On Termux
  - `curl -L https://raw.githubusercontent.com/spotDL/spotify-downloader/master/scripts/termux.sh | sh`
- Arch
  - There is an [Arch User Repository (AUR) package](https://aur.archlinux.org/packages/spotdl/) for
    spotDL.
- Docker
  - Build image:

    ```bash
    docker build -t spotdl .
    ```

  - Launch container with spotDL parameters (see section below). You need to create mapped
    volume to access song files

    ```bash
    docker run --rm -v $(pwd):/music spotdl download [trackUrl]
    ```

  - For Docker Compose and permission-managed Docker downloads, see
    [the Docker section in `/docs/index.md`](docs/index.md#docker).

  - Build from source

    ```bash
    git clone https://github.com/spotDL/spotify-downloader && cd spotify-downloader
    pip install uv
    uv sync
    uv run scripts/build.py
    ```

    An executable is created in `spotify-downloader/dist/`.

</details>

### Installing FFmpeg

FFmpeg is required for spotDL. If using FFmpeg only for spotDL, you can simply install FFmpeg to your spotDL installation directory:
`spotdl --download-ffmpeg`

We recommend the above option, but if you want to install FFmpeg system-wide,
follow these instructions

- [Windows Tutorial](https://windowsloop.com/install-ffmpeg-windows-10/)
- OSX - `brew install ffmpeg`
- Linux - `sudo apt install ffmpeg` or use your distro's package manager

### Installing Deno

We strongly recommend installing Deno. spotDL uses yt-dlp for YouTube downloads, and some
videos require Deno to download successfully. Without Deno, spotDL may fail to download some
songs, including videos marked as "made for kids".

If using Deno only for spotDL, install Deno to your spotDL directory:
`spotdl --download-deno`

If you want to install Deno system-wide instead, follow the
[official Deno installation guide](https://docs.deno.com/runtime/getting_started/installation/).

## Usage

Using SpotDL without options:

```sh
spotdl [urls]
```

You can run _spotDL_ as a package if running it as a script doesn't work:

```sh
python -m spotdl [urls]
```

General usage:

```sh
spotdl [operation] [options] QUERY
```

There are different **operations** spotDL can perform. The _default_ is `download`, which simply downloads the songs from YouTube and embeds metadata.

The **query** for spotDL is usually a list of Spotify URLs, but for some operations like **sync**, only a single link or file is required.
For a list of all **options** use ```spotdl -h```

<details>
<summary style="font-size:1em"><strong>Supported operations</strong></summary>

- `save`: Saves only the metadata from Spotify without downloading anything.
    - Usage:
        `spotdl save [query] --save-file {filename}.spotdl`

- `web`: Starts a web interface instead of using the command line. However, it has limited features and only supports downloading individual songs.

- `url`: Get user-friendly URL for each song from the query.
    - Usage:
        `spotdl url [query]`

- `sync`: Updates directories. Compares the directory with the current state of the playlist. Newly added songs will be downloaded and removed songs will be deleted. No other songs will be downloaded and no other files will be deleted.

    - Usage:
        `spotdl sync [query] --save-file {filename}.spotdl`

        This creates a new **sync** file. To update the directory in the future, use:

        `spotdl sync {filename}.spotdl`

- `meta`: Updates metadata for the provided song files.

</details>

## Music Sourcing and Audio Quality

spotDL uses YouTube as a source for music downloads. This method is used to avoid any issues related to downloading music from Spotify.

> **Note**
> Users are responsible for their actions and potential legal consequences. We do not support unauthorized downloading of copyrighted material and take no responsibility for user actions.

### Audio Quality

spotDL downloads music from YouTube and is designed to always download the highest possible bitrate; which is 128 kbps for regular users and 256 kbps for YouTube Music premium users.

Check the [Audio Formats](docs/usage.md#audio-formats-and-quality) page for more info.

## Contributing

Interested in contributing? Check out our [CONTRIBUTING.md](docs/CONTRIBUTING.md) to find
resources around contributing along with a guide on how to set up a development environment.

### Join our amazing community as a code contributor

<a href="https://github.com/spotDL/spotify-downloader/graphs/contributors">
  <img class="dark-light" src="https://contrib.rocks/image?repo=spotDL/spotify-downloader&anon=0&columns=25&max=100&r=true" />
</a>

## License

This project is Licensed under the [MIT](/LICENSE) License.
