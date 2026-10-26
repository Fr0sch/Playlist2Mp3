"""PyInstaller entry point for the bundled `spotdl` command.

`packaging/spotdl.spec` freezes this into a self-contained `spotdl` program so
the Windows release can ship Spotify support without asking the user to install
Python or spotdl. The real CLI lives in `spotdl.__main__.console_entry_point`.
"""

import multiprocessing

from spotdl.__main__ import console_entry_point


def main():
    # spotdl uses multiprocessing for provider downloads; without this a frozen
    # executable would spawn itself in a loop on Windows.
    multiprocessing.freeze_support()
    console_entry_point()


if __name__ == "__main__":
    main()
