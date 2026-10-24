"""playlist2mp3 core — download logic shared by the CLI, TUI and GUI.

Pure download/metadata logic around yt-dlp + ffmpeg, with Spotify links
delegated to spotdl. No UI code here so it can be imported by any frontend.

Tools (yt-dlp, spotdl, ffmpeg) are looked up in this order:
  1. next to a frozen executable (PyInstaller) or in its `bin/` subfolder,
     plus `Contents/Resources/bin` inside a macOS `.app`,
  2. in `bin/` next to this module (source distributions),
  3. the Homebrew prefixes on macOS (`/opt/homebrew/bin`, `/usr/local/bin`),
  4. on PATH.
This makes the Windows build self-contained ("plug and play") and lets a
macOS app launched from Finder still find Homebrew-installed tools.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from types import SimpleNamespace

ARCHIVE_NAME = ".playlist2mp3-archive.txt"
SPOTIFY_ARCHIVE_NAME = ".playlist2mp3-spotify.txt"
DEFAULT_BITRATE = 320
QUALITIES = [128, 192, 256, 320]

SPOTIFY_RE = re.compile(
    r"(?:open\.spotify\.com/(?:intl-[a-z-]+/)?|spotify:)"
    r"(track|album|playlist)[/:]([A-Za-z0-9]+)")


class ToolError(Exception):
    """User-facing error; surfaced nicely by the TUI, printed by the CLI."""


def die(msg, code=1):
    print("playlist2mp3: error: " + msg, file=sys.stderr)
    sys.exit(code)


def fail(msg):
    raise ToolError(msg)


_TOOL_CACHE = {}


def _tool_dirs():
    """Directories to look for helper tools in, in priority order.

    Covers a frozen executable (PyInstaller) and its `bin/` subfolder, a macOS
    `.app` bundle's `Contents/Resources/bin`, the `bin/` next to this module
    for source checkouts, and — on macOS — the usual Homebrew prefixes. The
    latter matters because a Finder-launched `.app` gets a minimal PATH that
    does not include `/opt/homebrew/bin`, so without this it could not find a
    Homebrew `yt-dlp`/`ffmpeg`/`spotdl`.
    """
    dirs = []
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        dirs += [base, os.path.join(base, "bin")]
        if sys.platform == "darwin":
            contents = os.path.dirname(base)  # .../Foo.app/Contents
            dirs += [os.path.join(contents, "Resources", "bin")]
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        dirs += [here, os.path.join(here, "bin")]
    if sys.platform == "darwin":
        dirs += ["/opt/homebrew/bin", "/usr/local/bin"]
    return dirs


def _tool(name):
    """Absolute path to a helper tool, or None if it cannot be found."""
    key = name.lower()
    if key in _TOOL_CACHE:
        return _TOOL_CACHE[key]
    exe = name + (".exe" if os.name == "nt" else "")
    path = None
    for directory in _tool_dirs():
        cand = os.path.join(directory, exe)
        if os.path.isfile(cand):
            path = cand
            break
    if path is None:
        path = shutil.which(name)
    _TOOL_CACHE[key] = path
    return path


def _spawn_kwargs():
    """Extra kwargs for subprocess calls: no console window on Windows, and a
    PATH that includes the bundled tools dir so child tools (e.g. spotdl)
    can find ffmpeg/ffprobe without the user installing anything."""
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    env = os.environ.copy()
    existing = env.get("PATH", "")
    if existing and not existing.endswith(os.pathsep):
        existing += os.pathsep
    env["PATH"] = existing + os.pathsep.join(
        d for d in _tool_dirs() if d and os.path.isdir(d))
    kwargs["env"] = env
    return kwargs


def require(tool):
    if _tool(tool) is None:
        die("'" + tool + "' not found. It was not bundled and is not on "
            "PATH either (yt-dlp and ffmpeg are both required).")


def spotify_kind(url):
    """Return 'track'/'album'/'playlist' if url is a Spotify link, else None."""
    match = SPOTIFY_RE.search(url or "")
    return match.group(1) if match else None


def require_spotdl():
    if _tool("spotdl") is None:
        fail("'spotdl' not found. It must be bundled or installed (needed for "
             "Spotify links). Install:\n"
             "  mise use -g uv@latest && mise use -g pipx:spotdl@latest\n"
             "  or: yay -S spotdl")


def human_duration(seconds):
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return "?"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%d:%02d" % (m, s)


def default_settings():
    return SimpleNamespace(
        output=os.path.expanduser("~/Music"),
        quality=DEFAULT_BITRATE,
        flat=False,
        no_playlist=False,
        no_tags=False,
        no_thumbnail=False,
        no_archive=False,
        limit=None,
        start=None,
        end=None,
        playlist_items=None,
        fragments=4,
        cookies_from_browser=None,
        verbose=False,
        track_offset=None,
        filename_prefix=None,
        track_range=None,
    )


def probe(url, cookies_from_browser=None, no_playlist=False):
    """Return metadata for a URL without downloading.

    Uses --flat-playlist so a playlist is listed quickly without extracting
    every video. With no_playlist the URL is treated as a single song even if
    it carries a playlist reference. Returns a dict with is_playlist, title,
    count and entries.
    """
    cmd = [
        _tool("yt-dlp"),
        "--dump-single-json",
        "--no-warnings",
        "--ignore-errors",
    ]
    cmd.append("--no-playlist" if no_playlist else "--flat-playlist")
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    cmd.append(url)

    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **_spawn_kwargs())
    raw = proc.stdout.strip()
    if not raw:
        tail = proc.stderr.strip().splitlines()
        fail("could not read playlist info" + (": " + tail[-1] if tail else ""))

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        fail("yt-dlp returned unexpected output")
    if not isinstance(data, dict):
        fail("could not read that URL (unsupported or DRM-protected)")

    entries = data.get("entries") if isinstance(data, dict) else None
    is_playlist = bool(entries) or data.get("_type") == "playlist"
    if is_playlist:
        entries = entries or []
        return {
            "is_playlist": True,
            "title": data.get("title") or "playlist",
            "count": len(entries),
            "entries": [
                {"title": e.get("title") or "(unknown)",
                 "duration": e.get("duration")}
                for e in entries
            ],
        }
    return {
        "is_playlist": False,
        "title": data.get("title") or "video",
        "count": 1,
        "entries": [{"title": data.get("title") or "(unknown)",
                     "duration": data.get("duration")}],
    }


def _parse_spotdl_json(text):
    """Load the JSON array from spotdl output, tolerating a preamble line."""
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def spotify_probe(url, kind=None):
    """Return metadata for a Spotify track/album/playlist without downloading.

    Delegates to `spotdl save`, which dumps the song metadata as JSON.
    Returns the same shape as probe() plus the raw song dicts.
    """
    require_spotdl()
    kind = kind or spotify_kind(url)
    cmd = [_tool("spotdl"), "save", url, "--save-file", "-",
           "--log-level", "ERROR"]
    songs = None
    tail = ""
    for attempt in range(3):
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              **_spawn_kwargs())
        songs = _parse_spotdl_json(proc.stdout)
        if songs:
            break
        out = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = out[-1] if out else ""
        if "token" not in tail.lower():
            break
        time.sleep(2 * (attempt + 1))
    if not songs:
        fail("could not read Spotify info" + (": " + tail if tail else ""))

    def artist(song):
        return song.get("artist") or ", ".join(song.get("artists") or []) or ""

    first = songs[0]
    if kind == "playlist":
        title = first.get("list_name") or "playlist"
    elif kind == "album":
        title = first.get("album_name") or "album"
    else:
        title = first.get("name") or "track"
    return {
        "is_playlist": kind in ("playlist", "album"),
        "source": "spotify",
        "kind": kind,
        "title": title,
        "count": len(songs),
        "songs": songs,
        "entries": [
            {"title": s.get("name") or "(unknown)",
             "artist": artist(s),
             "duration": s.get("duration")}
            for s in songs
        ],
    }


def build_spotify_output_template(base, kind, flat):
    if kind == "track":
        return os.path.join(base, "#{list-position:02d}_{artists} - {title}.{output-ext}")
    if kind == "album":
        return os.path.join(base, "{album}",
                            "#{track-number:02d}_{artists} - {title}.{output-ext}")
    if flat:
        return os.path.join(base, "#{list-position:02d}_{artists} - {title}.{output-ext}")
    return os.path.join(base, "{list-name}",
                        "#{list-position:02d}_{artists} - {title}.{output-ext}")


def build_spotify_cmd(settings, sources, kind, base, archive):
    cmd = [_tool("spotdl"), "download", *sources]
    cmd += [
        "--audio", "youtube-music", "youtube",
        "--format", "mp3",
        "--bitrate", str(settings.quality) + "k",
        "--threads", str(settings.fragments),
        "--output", build_spotify_output_template(base, kind, settings.flat),
        "--log-level", "DEBUG" if settings.verbose else "INFO",
        "--print-errors",
    ]
    ffmpeg = _tool("ffmpeg")
    if ffmpeg:
        cmd += ["--ffmpeg", ffmpeg]
    if not settings.no_archive:
        cmd += ["--archive", archive]
    return cmd


ALBUM_FALLBACK_TOL = 0.10


def _safe_name(text):
    return (text or "track").replace("/", "_").replace(os.sep, "_").strip() \
        or "track"


def _yt_search(query, limit=8):
    """Return flat YouTube search results: [{id, duration, title}, ...]."""
    proc = subprocess.run(
        [_tool("yt-dlp"), "--flat-playlist", "--no-warnings",
         "--ignore-errors",
         "--print", "%(id)s\t%(duration)s\t%(title)s",
         "ytsearch%d:%s" % (limit, query)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        **_spawn_kwargs())
    out = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        try:
            duration = float(parts[1])
        except (TypeError, ValueError):
            duration = None
        out.append({"id": parts[0], "duration": duration, "title": parts[2]})
    return out


def find_album_video(artist, album, total_seconds):
    """Find a single full-album YouTube video whose length matches the album.

    Returns the best {id, duration, title} match, or None.
    """
    if not album:
        return None
    tolerance = max(120.0, total_seconds * ALBUM_FALLBACK_TOL)
    queries = [
        "%s %s full album" % (artist, album),
        "%s %s album" % (artist, album),
        "%s - %s" % (artist, album),
    ]
    best = None
    for query in queries:
        for cand in _yt_search(query):
            if not cand["duration"]:
                continue
            diff = abs(cand["duration"] - total_seconds)
            if diff <= tolerance and (best is None or diff < best[0]):
                best = (diff, cand)
        if best is not None:
            break
    return best[1] if best else None


def album_fallback_track(song, settings, base, log=print):
    """Fetch one track by cutting it out of a full-album YouTube upload.

    Used when spotdl cannot match the track on its own (intros/interludes and
    other tracks that only exist inside an album upload). Returns True on
    success.
    """
    album_id = song.get("album_id")
    album = song.get("album_name")
    artist = song.get("artist") or ", ".join(song.get("artists") or [])
    title = song.get("name") or "track"
    if not album_id or not album:
        return False

    try:
        album_info = spotify_probe(
            "https://open.spotify.com/album/" + album_id, "album")
    except ToolError as exc:
        log("[fallback] %s" % exc)
        return False

    songs = album_info["songs"]
    total = sum((s.get("duration") or 0) for s in songs)
    if total <= 0:
        return False

    sid = song.get("song_id")
    index = next((i for i, s in enumerate(songs)
                  if s.get("song_id") == sid), None)
    if index is None:
        return False
    start = sum((s.get("duration") or 0) for s in songs[:index])
    duration = songs[index].get("duration") or 0
    if duration <= 0:
        return False

    log("[fallback] searching full album: %s - %s (~%s)"
        % (artist, album, human_duration(total)))
    video = find_album_video(artist, album, total)
    if not video:
        log("[fallback] no matching full-album video found")
        return False
    log("[fallback] using %s (%s), cutting %s..%s"
        % (video["title"], human_duration(video["duration"]),
           human_duration(start), human_duration(start + duration)))

    with tempfile.TemporaryDirectory(prefix="playlist2mp3-album-") as tmp:
        raw = os.path.join(tmp, "album.%(ext)s")
        rc = subprocess.run(
            [_tool("yt-dlp"), "-f", "bestaudio", "--no-playlist",
             "--no-warnings", "--force-overwrites", "-o", raw,
             "https://www.youtube.com/watch?v=" + video["id"]],
            **_spawn_kwargs()).returncode
        if rc != 0:
            log("[fallback] could not download the album video")
            return False
        files = [os.path.join(tmp, f) for f in os.listdir(tmp)]
        if not files:
            return False
        src = files[0]

        cover = None
        if not settings.no_thumbnail and song.get("cover_url"):
            cover = os.path.join(tmp, "cover.jpg")
            try:
                urllib.request.urlretrieve(song["cover_url"], cover)
            except Exception:
                cover = None

        ffmpeg = _tool("ffmpeg")
        if ffmpeg is None:
            log("[fallback] ffmpeg not found")
            return False

        out = os.path.join(base, "%s - %s.mp3"
                           % (_safe_name(artist), _safe_name(title)))
        cmd = [ffmpeg, "-y", "-ss", "%.3f" % start, "-i", src]
        if cover:
            cmd += ["-i", cover, "-map", "0:a", "-map", "1:v",
                    "-c:v", "mjpeg", "-id3v2_version", "3",
                    "-metadata:s:v", "title=Album cover",
                    "-metadata:s:v", "comment=Cover (front)"]
        else:
            cmd += ["-vn"]
        cmd += ["-t", "%.3f" % duration,
                "-c:a", "libmp3lame", "-b:a", str(settings.quality) + "k",
                "-metadata", "title=%s" % title,
                "-metadata", "artist=%s" % artist,
                "-metadata", "album=%s" % album]
        if song.get("track_number"):
            cmd += ["-metadata", "track=%s" % song["track_number"]]
        cmd.append(out)
        rc = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace",
                            **_spawn_kwargs()).returncode
        if rc != 0:
            log("[fallback] ffmpeg failed to cut the segment")
            return False

    log("[fallback] wrote %s" % out)
    return True


def build_output_template(base, info, flat):
    if not info["is_playlist"]:
        return os.path.join(base, "#%(playlist_index|1)02d_%(artist,uploader,creator,channel|Unknown)s - %(title)s.%(ext)s")
    track = "#%(playlist_index)02d_%(artist,uploader,creator,channel|Unknown)s - %(title)s.%(ext)s"
    if flat:
        return os.path.join(base, track)
    return os.path.join(base, "%(playlist_title)s", track)


def build_download_cmd(settings, url, info, base, archive):
    cmd = [
        _tool("yt-dlp"),
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", str(settings.quality) + "K",
        "--ignore-errors",
        "--no-overwrites",
        "--continue",
        "--no-warnings",
        "--newline",
        "--retries", "10",
        "--fragment-retries", "10",
        "--concurrent-fragments", str(settings.fragments),
        "--output", build_output_template(base, info, settings.flat),
    ]

    if settings.no_playlist:
        cmd += ["--no-playlist"]

    if not settings.no_archive:
        cmd += ["--download-archive", archive]

    if not settings.no_tags:
        cmd += ["--embed-metadata"]
        if info["is_playlist"]:
            cmd += ["--parse-metadata", "%(playlist_title)s:%(meta_album)s"]
        cmd += ["--parse-metadata",
                "%(artist,creator,channel,uploader)s:%(meta_artist)s"]
        if info["is_playlist"]:
            cmd += ["--parse-metadata", "%(playlist_index)s:%(meta_track)s"]

    if not settings.no_thumbnail:
        cmd += ["--embed-thumbnail", "--convert-thumbnails", "jpg"]

    if settings.playlist_items:
        cmd += ["--playlist-items",
                ",".join(str(i) for i in settings.playlist_items)]
    if settings.limit:
        cmd += ["--playlist-end", str(settings.limit)]
    if settings.start:
        cmd += ["--playlist-start", str(settings.start)]
    if settings.end:
        cmd += ["--playlist-end", str(settings.end)]

    if settings.cookies_from_browser:
        cmd += ["--cookies-from-browser", settings.cookies_from_browser]

    if settings.verbose:
        cmd += ["--verbose"]

    cmd.append(url)
    return cmd


def stream_download(cmd, on_line=None, on_track=None, rename=None):
    """Run yt-dlp, stream output. Returns (done, failed, returncode)."""
    done = 0
    failed = 0
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace",
                            bufsize=1, **_spawn_kwargs())
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip("\n")
        if on_line:
            on_line(line)
        if line.startswith("ERROR:") or " ERROR: " in line:
            failed += 1
        elif ("[ExtractAudio] Destination:" in line):
            try:
                dest = line.split("Destination:")[-1].strip()
                if rename and os.path.exists(dest):
                    newname = rename(dest)
                    if newname and newname != dest:
                        try:
                            os.rename(dest, newname)
                        except Exception:
                            pass
            except Exception:
                pass
            done += 1
            if on_track:
                on_track(done)
        elif ("has already been recorded in the archive" in line):
            done += 1
            if on_track:
                on_track(done)
    proc.wait()
    return done, failed, proc.returncode


def stream_spotify(cmd, on_line=None, on_track=None):
    """Run spotdl, stream output. Returns (done, failed, returncode).

    Best-effort counting: a finished track logs 'Downloaded', a track that
    could not be matched logs 'No results found' / 'LookupError'.
    """
    done = 0
    failed = 0
    not_found = 0
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace",
                            bufsize=1, **_spawn_kwargs())
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip("\n")
        if on_line:
            on_line(line)
        low = line.lower()
        if "no results found" in low:
            if not_found == 0:
                not_found += 1
                failed += 1
        elif line.startswith("ERROR") or " error:" in low:
            failed += 1
        elif "downloaded" in low and ("->" in line or '"' in line):
            done += 1
            if on_track:
                on_track(done)
    proc.wait()
    return done, failed, proc.returncode


def spotify_label(kind):
    return {"playlist": "Playlist", "album": "Album", "track": "Song"}[kind]