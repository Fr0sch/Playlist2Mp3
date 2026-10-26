# playlist2mp3

A small tool that converts YouTube and Spotify playlists (or single
tracks/videos) to tagged MP3 files. Built on `yt-dlp` + `ffmpeg`, with Spotify
links delegated to `spotdl`. Comes as a CLI, an interactive TUI, and a full
desktop GUI (Windows, Linux + macOS).

- Whole playlist/album in one go, or pick exactly which tracks (TUI)
- MP3 conversion with selectable bitrate (128/192/256/320 kbps)
- ID3 tags: title, artist, album (playlist name) and track number
- Embedded cover art (thumbnail) on every track
- Live progress with speed and ETA
- Skips anything already downloaded (via a per-folder archive)
- Per-playlist subfolder, ordered `01 - Title.mp3`
- Spotify **album fallback**: a track spotdl can't match (intros, interludes)
  is cut out of a full-album YouTube upload using the Spotify track lengths

## Requirements

```sh
sudo pacman -S yt-dlp ffmpeg
```

On macOS (Apple Silicon, Homebrew):

```sh
brew install yt-dlp ffmpeg
```

Spotify links additionally need `spotdl` (install it with mise, from the AUR,
or with Homebrew):

```sh
mise use -g uv@latest && mise use -g pipx:spotdl@latest
# or
yay -S spotdl
# or (macOS)
brew install spotdl
```

The interactive TUI additionally needs Textual (optional — the CLI works
without it):

```sh
sudo pacman -S python-textual
# or (macOS)
pipx install textual
```

The desktop GUI needs PySide6:

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Install

```sh
ln -sf "$PWD/playlist2mp3" ~/.local/bin/playlist2mp3
```

`~/.local/bin` is on `PATH` on Omarchy. Afterwards just run `playlist2mp3`.

On macOS, `~/.local/bin` is not on `PATH` by default (zsh); add it or link
somewhere already on `PATH`:

```sh
mkdir -p ~/.local/bin
ln -sf "$PWD/playlist2mp3" ~/.local/bin/playlist2mp3
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
```

## GUI (desktop app)

A full Qt (PySide6) desktop app for Windows, Linux and macOS — same core as the
CLI and TUI, just a graphical frontend. Paste a URL, **Load**, tick the tracks,
choose options and **Download**.

The Windows release is 100 % plug-and-play: `yt-dlp`, `ffmpeg`, `ffprobe` and
`spotdl` are bundled in the zip's `bin\` folder (the app finds them next to
itself), so nothing has to be installed on Windows 11. The Linux build still
expects `yt-dlp` + `ffmpeg` on PATH (and `spotdl` for Spotify). The macOS
release is a double-clickable `playlist2mp3-gui.app`; it expects the Homebrew
tools (`brew install yt-dlp ffmpeg spotdl`), which it finds even when launched
from Finder.

Grab the latest builds from
[GitHub Releases](https://github.com/Fr0sch/Playlist2Mp3/releases/latest):

| Platform | Download |
| --- | --- |
| Windows 11 x64 (everything bundled) | `playlist2mp3-gui-windows-x64.zip` |
| macOS 12+ Apple Silicon (arm64) | `playlist2mp3-gui-macos-arm64.zip` |
| Linux x86_64 (needs `yt-dlp` + `ffmpeg`) | `playlist2mp3-gui-linux-x64.tar.gz` |

On Windows, unzip the archive and run `playlist2mp3-gui.exe` from inside the
folder (keep it next to `bin\`). SmartScreen may warn about an unsigned app:
choose **More info** → **Run anyway**.

On macOS, unzip and drag `playlist2mp3-gui.app` into `Applications`.

```sh
.venv/bin/python playlist2mp3_gui.py
```

Build a standalone binary yourself with the provided scripts (each writes its
release archive to `dist/`):

```sh
# Linux -> dist/playlist2mp3-gui-linux-x64.tar.gz
./packaging/build_linux.sh

# Windows (PowerShell) -> dist/playlist2mp3-gui-windows-x64.zip
.\packaging\build_windows.ps1

# macOS (Apple Silicon) -> dist/playlist2mp3-gui-macos-arm64.zip
./packaging/build_macos.sh
```

GitHub Actions builds all three automatically on every push to `main` and, for
`v*` tags, attaches the archives to a GitHub Release (see
`.github/workflows/build-gui.yml`). The GUI shares the exact same core
(`p2m_core.py`) as the CLI and TUI.

> The macOS `.app` is built and ad-hoc signed but not notarized. If macOS
> blocks the first launch, right-click the app → **Open**, or run
> `xattr -dr com.apple.quarantine /Applications/playlist2mp3-gui.app`.

## TUI

Run with no arguments (or `--tui`) for a full-screen Textual UI:

```sh
playlist2mp3
playlist2mp3 --tui
```

Paste a URL, press **Load**, then tick the tracks you want (or **Select all** /
**Select none**) and press **Download**. Quality, output folder and the tag /
cover / flat options are all in the panel.

The **Mode** switch flips between:

- **Playlist** — download the whole playlist into `~/Music/<playlist>/01 - Track.mp3`
- **Song** — treat the URL as a single song, ignoring any playlist / `&list=`
  reference (saved as plain `Track.mp3`)

Changing the mode re-reads an already loaded URL automatically.

Spotify `track`, `album` and `playlist` links work too. The link kind decides
whether it's one track or a whole list; the **Mode** switch only affects
YouTube links.

| Key | Action |
| --- | --- |
| `Enter` | Load the URL |
| `a` / `n` | Select all / none |
| `d` | Download |
| `Ctrl+R` | Reload the URL |
| `q` | Quit |

> The single-letter keys only fire when a text field isn't focused — click a
> button instead if a field has focus.

## CLI

```sh
playlist2mp3 'https://www.youtube.com/playlist?list=...'
playlist2mp3 'https://youtu.be/VIDEO_ID' -o ~/Music/Hits -q 320
playlist2mp3 URL --limit 10          # first 10 tracks
playlist2mp3 URL --song              # one song, ignore the playlist
playlist2mp3 URL --info              # list tracks and exit
playlist2mp3 URL --dry-run           # show what would be downloaded
playlist2mp3 URL --cookies-from-browser firefox   # private playlists

playlist2mp3 'https://open.spotify.com/playlist/...'
playlist2mp3 'https://open.spotify.com/album/...'
playlist2mp3 'https://open.spotify.com/track/...'
```

Output defaults to `~/Music/<playlist title>/01 - Track.mp3`.

For Spotify, `spotdl` is used instead of yt-dlp: playlists go to
`~/Music/<playlist>/<n> - Title.mp3`, albums to
`~/Music/<album>/<track#>- Title.mp3`, and single tracks to
`~/Music/<artists> - <title>.mp3`.

If a single Spotify track can't be matched on YouTube (common for short
intros/interludes that only exist inside a full-album upload), playlist2mp3
automatically falls back to: find the full-album video, download its audio and
cut the track's segment with `ffmpeg` using the Spotify track lengths. Disable
with `--no-album-fallback`.

### Options

| Flag | Description |
| --- | --- |
| `--tui` | Open the interactive Textual UI |
| `-o, --output DIR` | Output base directory (default `~/Music`) |
| `-q, --quality N` | MP3 bitrate: 128/192/256/320 kbps (default 320) |
| `--flat` | Do not create a per-playlist subfolder |
| `--song` | Treat the URL as a single song (ignore the playlist) |
| `--no-tags` | Do not embed metadata |
| `--no-thumbnail` | Do not embed cover art |
| `--no-archive` | Re-download tracks already fetched |
| `--no-album-fallback` | Don't cut an unmatched Spotify track from a full-album upload |
| `--limit N` | Only the first N tracks |
| `--start N` / `--end N` | Playlist index range |
| `--track-start N` | Start file numbering at N (does not skip tracks) |
| `--prefix TEXT` | Replace the `#NN_` filename prefix with TEXT |
| `--fragments N` | Concurrent fragment downloads (default 4) |
| `--cookies-from-browser B` | Use browser cookies (private/age-restricted) |
| `--info` | List tracks and exit |
| `--dry-run` | Show what would be downloaded and exit |
| `-v, --verbose` | Verbose yt-dlp output |

## Skip existing

An archive file `.playlist2mp3-archive.txt` is kept in the output directory
(Spotify uses `.playlist2mp3-spotify.txt`). Track IDs recorded there are not
downloaded again. Delete it, or pass `--no-archive`, to force a fresh download.

On Spotify links, `--no-tags` and `--no-thumbnail` are ignored (spotdl always
embeds metadata and cover art).
