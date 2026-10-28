playlist2mp3 - Windows x64 (ready to run)
=========================================

This repository already contains the built Windows app: nothing has to be
installed or compiled.

Double-click playlist2mp3-gui.exe. yt-dlp, ffmpeg, ffprobe and spotdl are in
the bin folder next to it, and the app finds them there.

Paste a YouTube or Spotify link, press Load, tick the tracks you want and press
Download. Files are written to the folder shown under "Output folder"
(%USERPROFILE%\Music by default).

Notes
-----
- Windows SmartScreen may warn about an unsigned app. Choose "More info"
  then "Run anyway".
- Spotify links are handled by the bundled spotdl. A free Spotify account is
  enough; no API keys are needed.
- Keep the exe next to the bin folder. If you move the exe, move the whole
  folder.
- ffmpeg is licensed under the LGPL v3 (shared libraries, which also keep every
  file small enough for GitHub); see bin\ffmpeg-LICENSE.txt.
- The exe and bin\ are rebuilt by GitHub Actions and committed back to the repo
  on release tags and on manual runs (see .github\workflows\build-gui.yml), so a
  normal "git pull" updates sources and binaries together and there is nothing
  to rebuild to run the app. Locally, packaging\build_windows.ps1 does the same.

Source: https://github.com/Fr0sch/Playlist2Mp3
