#!/usr/bin/env python3
"""playlist2mp3 - full Qt desktop app (Windows, Linux + macOS).

A PySide6 GUI around the same core as the CLI/TUI version of playlist2mp3.
The download logic is not duplicated here: it is imported from p2m_core, so
every improvement (Spotify support, album fallback, ...) applies to the GUI
automatically.

Requires external tools on PATH: yt-dlp, ffmpeg, and spotdl (for Spotify roots).
"""

import os
import re
import sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2m_core as core  # noqa: E402


class LoadWorker(QThread):
    loaded = Signal(str, object)
    failed = Signal(str)

    def __init__(self, url, no_playlist):
        super().__init__()
        self.url = url
        self.no_playlist = no_playlist

    def run(self):
        try:
            kind = core.spotify_kind(self.url)
            if kind:
                info = core.spotify_probe(self.url, kind)
            else:
                info = core.probe(self.url, no_playlist=self.no_playlist)
        except core.ToolError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:
            self.failed.emit("Unexpected error: %s" % exc)
            return
        self.loaded.emit(self.url, info)


class DownloadWorker(QThread):
    line = Signal(str)
    progress = Signal(int, int)
    spotify_mode = Signal(bool)
    fallback_note = Signal(str)
    finished_dl = Signal(int, int, int, bool)

    def __init__(self, spotify, cmd, total, fallback):
        super().__init__()
        self.spotify = spotify
        self.cmd = cmd
        self.total = total
        self.fallback = fallback

    def run(self):
        if self.spotify:
            self.spotify_mode.emit(True)
            done, failed, rc = core.stream_spotify(self.cmd, on_line=self.line.emit)
            if self.fallback and failed and not done:
                song, settings, base = self.fallback
                self.fallback_note.emit(
                    "Not matched on YouTube; trying album fallback (cutting from a full-album upload)..."
                )
                ok = core.album_fallback_track(
                    song, settings, base, log=self.line.emit
                )
                self.finished_dl.emit(1 if ok else 0, 0 if ok else failed, rc, True)
                return
            self.finished_dl.emit(done, failed, rc, True)
        else:
            def on_track(d):
                self.progress.emit(d, self.total)

            done, failed, rc = core.stream_download(
                self.cmd, on_line=self.line.emit, on_track=on_track
            )
            self.finished_dl.emit(done, failed, rc, False)


class Playlist2Mp3Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("playlist2mp3")
        self.resize(860, 620)
        self.info = None
        self.url = ""
        self.no_playlist = False
        self.loader = None
        self.downloader = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("YouTube or Spotify URL")
        self.url_edit.returnPressed.connect(self.action_load)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.action_load)
        row.addWidget(self.url_edit, 1)
        row.addWidget(load_btn)
        layout.addLayout(row)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.tracks = QListWidget()
        self.tracks.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        layout.addWidget(self.tracks, 1)

        opts = QGroupBox("Options")
        grid = QHBoxLayout(opts)

        self.mode = QComboBox()
        self.mode.addItem("Playlist", "playlist")
        self.mode.addItem("Song", "song")
        self.mode.currentIndexChanged.connect(self.on_mode_changed)

        self.bitrate = QComboBox()
        for q in core.QUALITIES:
            self.bitrate.addItem("%d kbps" % q, q)
        self.bitrate.setCurrentIndex(core.QUALITIES.index(core.DEFAULT_BITRATE))

        self.output_edit = QLineEdit(core.default_settings().output)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.choose_output)

        self.start_num = QLineEdit()
        self.start_num.setPlaceholderText("Start # (e.g. 1)")
        self.start_num.setFixedWidth(80)

        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("#1-50_ or #1_")
        self.prefix_edit.setFixedWidth(120)

        self.flat = QCheckBox("Flat (no subfolders)")
        self.tags = QCheckBox("Embed tags")
        self.tags.setChecked(True)
        self.cover = QCheckBox("Embed cover art")
        self.cover.setChecked(True)
        self.archive = QCheckBox("Skip existing (archive)")
        self.archive.setChecked(True)

        grid.addWidget(QLabel("Mode:"))
        grid.addWidget(self.mode)
        grid.addWidget(QLabel("Bitrate:"))
        grid.addWidget(self.bitrate)
        grid.addWidget(QLabel("Start #:"))
        grid.addWidget(self.start_num)
        grid.addWidget(QLabel("Prefix/Range:"))
        grid.addWidget(self.prefix_edit)
        grid.addWidget(QLabel("Output:"))
        grid.addWidget(self.output_edit, 1)
        grid.addWidget(browse_btn)
        layout.addWidget(opts)

        checks = QHBoxLayout()
        for widget in (self.flat, self.tags, self.cover, self.archive):
            checks.addWidget(widget)
        checks.addStretch(1)
        layout.addLayout(checks)

        actions = QHBoxLayout()
        select_all = QPushButton("Select all")
        select_all.clicked.connect(self.select_all)
        select_none = QPushButton("Select none")
        select_none.clicked.connect(self.select_none)
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.action_download)
        self.update_btn = QPushButton("Update")
        self.update_btn.clicked.connect(self.action_update)
        actions.addWidget(select_all)
        actions.addWidget(select_none)
        actions.addStretch(1)
        actions.addWidget(self.update_btn)
        actions.addWidget(self.download_btn)
        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        layout.addWidget(self.log, 1)

        self.set_busy(False)

    # -- helpers ---------------------------------------------------------

    def set_busy(self, busy):
        self.download_btn.setEnabled(not busy)
        try:
            self.update_btn.setEnabled(not busy)
        except Exception:
            pass
        for widget in (self.url_edit, self.mode, self.bitrate, self.flat,
                       self.tags, self.cover, self.archive, self.start_num, self.prefix_edit):
            widget.setEnabled(not busy)

    def on_mode_changed(self, _index):
        self.flat.setEnabled(self.mode.currentData() == "playlist")

    def choose_output(self):
        selected = QFileDialog.getExistingDirectory(self, "Output folder", self.output_edit.text())
        if selected:
            self.output_edit.setText(selected)

    def select_all(self):
        for i in range(self.tracks.count()):
            self.tracks.item(i).setCheckState(Qt.CheckState.Checked)

    def select_none(self):
        for i in range(self.tracks.count()):
            self.tracks.item(i).setCheckState(Qt.CheckState.Unchecked)

    def log_line(self, text):
        self.log.appendPlainText(text)

    def selected_indexes(self):
        out = []
        for i in range(self.tracks.count()):
            if self.tracks.item(i).checkState() == Qt.CheckState.Checked:
                out.append(i)
        return out

    def make_settings(self):
        s = core.default_settings()
        s.output = os.path.abspath(os.path.expanduser(self.output_edit.text().strip()))
        s.quality = self.bitrate.currentData()
        s.flat = self.flat.isChecked()
        s.no_tags = not self.tags.isChecked()
        s.no_thumbnail = not self.cover.isChecked()
        s.no_archive = not self.archive.isChecked()
        s.filename_prefix = self.prefix_edit.text().strip() or None
        try:
            if self.start_num.text().strip():
                s.track_offset = int(self.start_num.text().strip()) - 1
        except Exception:
            s.track_offset = None
        return s

    # -- actions ---------------------------------------------------------

    def action_load(self):
        url = self.url_edit.text().strip()
        if not url:
            self.status.setText("Enter a URL first.")
            return
        self.info = None
        self.tracks.clear()
        self.log_line("Reading %s ..." % url)
        self.set_busy(True)
        self.no_playlist = self.mode.currentData() == "song"
        self.loader = LoadWorker(url, self.no_playlist)
        self.loader.loaded.connect(self.on_loaded)
        self.loader.failed.connect(self.on_load_failed)
        self.loader.finished.connect(lambda: setattr(self, "loader", None))
        self.loader.start()

    def on_loaded(self, url, info):
        self.url = url
        self.info = info
        self.set_busy(False)
        entries = info.get("entries") or info.get("songs") or []
        if not entries and info.get("title"):
            entries = [{"title": info["title"], "artist": info.get("artist") or info.get("uploader"), "duration": info.get("duration")}]
        for i, entry in enumerate(entries):
            title = entry.get("title") or "(unknown)"
            artist = entry.get("artist") or entry.get("uploader") or ""
            duration = entry.get("duration")
            dur = core.human_duration(duration) if isinstance(duration, (int, float)) and duration else ""
            label = "%2d. %s" % (i + 1, title)
            if artist:
                label += "  -  %s" % artist
            if dur:
                label += "  (%s)" % dur
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.tracks.addItem(item)
        self.status.setText(
            "%s - %s (%d tracks)" % (core.spotify_label(info.get("kind")) if info.get("kind") else "YouTube", info.get("title"), len(entries))
        )

    def on_load_failed(self, message):
        self.set_busy(False)
        self.status.setText("Failed")
        self.log_line("Error: %s" % message)
        QMessageBox.warning(self, "playlist2mp3", message)

    def action_download(self):
        if not self.info:
            self.status.setText("Load a URL first.")
            return
        selected = self.selected_indexes()
        if not selected:
            self.status.setText("Select at least one track.")
            return
        settings = self.make_settings()
        base = settings.output
        try:
            os.makedirs(base, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "playlist2mp3", "Cannot create output folder: %s" % exc)
            return

        is_spotify = bool(self.info.get("kind"))
        total = len(self.info.get("entries") or self.info.get("songs") or [])
        archive = os.path.join(base, core.SPOTIFY_ARCHIVE_NAME if is_spotify else core.ARCHIVE_NAME)
        fallback = None

        if is_spotify:
            songs = self.info.get("songs") or []
            whole = len(selected) >= len(songs)
            if whole:
                sources, tkind = [self.url], self.info["kind"]
                try:
                    offset = getattr(settings, 'track_offset', None)
                    if offset:
                        settings.track_offset = offset
                        settings.playlist_items = [x + 1 + offset for x in range(len(songs))]
                except Exception:
                    pass
            else:
                sources = [songs[i]["url"] for i in selected]
                tkind = "track"
                try:
                    offset = getattr(settings, 'track_offset', None)
                    if offset:
                        settings.playlist_items = [s + 1 + offset for s in selected]
                except Exception:
                    pass
            if not whole and len(sources) == 1:
                fallback = (songs[selected[0]], settings, base)
            cmd = core.build_spotify_cmd(settings, sources, tkind, base, archive)
            self.log_line(
                "Source: %s - %s (%d tracks)" % (core.spotify_label(tkind), self.info["title"], len(songs))
            )
        else:
            items = None
            if self.info.get("is_playlist"):
                items = [i + 1 for i in selected]
                if len(items) >= len(self.info.get("entries") or []):
                    items = None
            settings.playlist_items = items
            try:
                offset = getattr(settings, 'track_offset', None)
                if offset and items:
                    items = [x + offset for x in items]
                    settings.playlist_items = items
                elif offset and not items:
                    # whole playlist but we want to shift numbers
                    items = [x + 1 + offset for x in range(total)]
                    settings.playlist_items = items
            except Exception:
                pass
            cmd = core.build_download_cmd(settings, self.url, self.info, base, archive)
            source_label = "YouTube playlist" if self.info.get("is_playlist") else "YouTube"
            self.log_line("Source: %s - %s" % (source_label, self.info.get("title")))

        self.set_busy(True)
        self.progress.setRange(0, 0 if is_spotify else len(selected))
        self.progress.setValue(0)
        self.downloader = DownloadWorker(is_spotify, cmd, len(selected), fallback)
        self.downloader.line.connect(self.log_line)
        self.downloader.progress.connect(self.on_progress)
        self.downloader.spotify_mode.connect(self.on_spotify_mode)
        self.downloader.fallback_note.connect(self.log_line)
        self.downloader.finished_dl.connect(self.on_download_done)
        self.downloader.finished.connect(lambda: setattr(self, "downloader", None))
        self.downloader.start()

    def on_progress(self, done, total):
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)

    def on_spotify_mode(self, _flag):
        self.progress.setRange(0, 0)

    def action_update(self):
        self.log_line("Checking for updates...")
        self.status.setText("Checking for updates...")
        self.set_busy(True)
        import subprocess
        import threading
        def _upd():
            try:
                here = os.path.dirname(os.path.abspath(__file__))
                r = subprocess.run(["git", "-C", here, "pull", "--ff-only"], capture_output=True, text=True)
                if r.returncode == 0:
                    self.log_line(r.stdout.strip() or "Updated")
                    self.status.setText("Update complete. Restart may be needed.")
                else:
                    self.log_line("git pull failed")
                    self.status.setText("Update attempted (git failed).")
            except Exception as e:
                self.log_line("Update error: %s" % e)
                self.status.setText("Update failed.")
            finally:
                self.set_busy(False)
        threading.Thread(target=_upd, daemon=True).start()

    def on_download_done(self, done, failed, rc, spotify):
        self.set_busy(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(1 if rc == 0 and done else 0)
        try:
            settings = self.make_settings()
            offset = getattr(settings, 'track_offset', None)
            prefix = getattr(settings, 'filename_prefix', None)
            base = settings.output
            for fname in os.listdir(base):
                if fname.endswith('.mp3'):
                    old = os.path.join(base, fname)
                    m = re.match(r'^#(\d+)_(.+)$', fname)
                    if m:
                        num = int(m.group(1))
                        if offset is not None and offset != 0:
                            num = num + offset
                        if num > 50:
                            num = ((num - 1) % 50) + 1
                        if num < 1:
                            num = 1
                        rest = m.group(2)
                        if prefix:
                            newn = os.path.join(base, prefix + rest)
                        else:
                            newn = os.path.join(base, '#%02d_%s' % (num, rest))
                        try:
                            if old != newn:
                                os.rename(old, newn)
                        except Exception:
                            pass
                        continue
                    if prefix and not fname.startswith(prefix):
                        newn = os.path.join(base, prefix + fname)
                        try:
                            if old != newn:
                                os.rename(old, newn)
                        except Exception:
                            pass
        except Exception:
            pass
        if done:
            self.status.setText("Done. %d track(s) downloaded." % done)
            self.log_line("Done. %d track(s) downloaded." % done)
        elif failed:
            self.status.setText("%d track(s) failed." % failed)
            self.log_line("%d track(s) failed." % failed)


def main(argv=None):
    app = QApplication(sys.argv if argv is None else argv)
    window = Playlist2Mp3Window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())