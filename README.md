# ClefTune

An unofficial YouTube Music client for **Windows, macOS and Linux**, inspired by [Metrolist](https://github.com/MetrolistGroup/Metrolist) for Android. It has ad-free playback that keeps going with the window closed, synced lyrics, an offline song cache, downloads, a local library, and media-key support.

> Not affiliated with YouTube, Google, or the Metrolist project. It uses YouTube's internal APIs the same way Metrolist and yt-dlp do, which YouTube's Terms of Service don't allow. Use it for personal listening, at your own risk.

## Install

Download the installer for your system. Each one includes everything it needs, so **nothing has to be installed first** (no Python or anything else).

| System | File | How |
|---|---|---|
| **Windows 10/11** | `ClefTune-<ver>-windows-x64-setup.exe` | Double-click. No admin rights needed. |
| **macOS 11+** | `ClefTune-<ver>-macos-arm64.pkg` (Apple Silicon) or `-macos-x86_64.pkg` (Intel) | Double-click. If macOS blocks it: System Settings → Privacy & Security → *Open Anyway*. |
| **Linux** (any distro, x86-64) | `ClefTune-<ver>-linux-x86_64.run` | Make it executable, then run it: `chmod +x ClefTune-*.run && ./ClefTune-*.run`. No root needed. |

**Window or browser?** Every installer asks how ClefTune should open:

* **In its own window** (recommended). Installs the small window add-on.
* **In my web browser.** A smaller install; the player opens as a browser tab.

**Changed your mind?** Switch any time in *Settings → Window*. To add the window later, run the installer again:

* **Windows:** pick "Own window".
* **macOS:** tick "Separate window".
* **Linux:** choose "Add the separate window".

Running it again is also how you update or remove the window.

The installers clean up after themselves: temporary files are removed, upgrades remove the previous version's files, and the app runs directly from its folder without unpacking anything at start-up.

### Uninstall

* **Windows:** *Settings → Apps → ClefTune → Uninstall*. It asks whether to also delete your library.
* **macOS:** run `/Library/Application Support/ClefTune/Uninstall ClefTune.command`.
* **Linux:** run the installer again and choose *Uninstall*, or run `~/.local/lib/cleftune/uninstall.sh` (add `--purge` to delete your library too).

Downloaded music in `Music/ClefTune` is never deleted.

## Features

| | |
|---|---|
| **Browse** | Home feed, Explore (charts, moods & genres, new videos), albums, artists, playlists, radio mixes |
| **Search** | Live suggestions, filters (songs / videos / albums / artists / playlists), top result |
| **Playback** | Native audio engine in the app: **keeps playing when you close the window or browser tab**. Gapless repeat-one, queue with drag-to-reorder, shuffle, repeat, autoplay radio, sleep timer, resume where you left off |
| **Fast starts** | Next songs and the song under your pointer are prepared ahead of time, so they start in well under a second. Stream links are remembered between launches |
| **Lyrics** | Time-synced from LRCLIB, YouTube Music and KuGou, with word-by-word highlighting where available. Click a line to seek; adjust timing per song (±0.25 s). Saved for offline use |
| **Cache** | Your last 50 played songs (adjustable) are kept on disk: they play instantly and offline |
| **Library** | Liked songs, your own playlists, saved albums/artists/playlists, history, 30-day stats |
| **Downloads** | Permanent offline copies in `Music/ClefTune` (tagged with cover art when ffmpeg is installed) |
| **Account** (optional) | One-click *Sign in with Google*, or reuse the login from Firefox/Chrome/Edge/Brave… Likes sync back |
| **Desktop** | Tray icon (Windows, Linux), media keys and the desktop media panel (Linux MPRIS), colors from album art, dark/light theme |

### Closing vs. quitting

Closing the window (or the browser tab) **keeps the music playing** in the background. Open ClefTune again from the app menu, tray icon or Dock to bring the window back. To stop completely, use **Quit** at the bottom of the sidebar, or *Quit* in the tray menu. You can turn this behaviour off in *Settings → Window*.

## Signing in (optional)

*Settings → Account* offers three ways:

1. **Sign in with Google.** A sign-in window opens. Log in as usual, and it closes by itself when you're done.
2. **Use my browser's login.** If you're already signed in to YouTube in Firefox, Chrome, Edge, Brave, Opera, Vivaldi or Safari, click that browser's button. (On Windows, Chrome and Edge lock their cookies while running; close the browser first or use option 1.)
3. **Advanced:** paste request headers copied from your browser's developer tools.

Your login is stored only on this computer. To also use it for playback (age-restricted songs, Premium audio quality), turn on **Use account for playback**.

## Keyboard shortcuts

| Key | Action | | Key | Action |
|---|---|---|---|---|
| Space | Play / pause | | ↑ / ↓ | Volume |
| ← / → | Seek 5 s | | Shift + ← / → | Previous / next |
| L | Like | | S / R | Shuffle / repeat |
| Q / Y | Queue / lyrics panel | | / or Ctrl+F | Search |
| M | Mute | | | |

## How it works

```
 ┌── own window (window add-on) ──┐      ┌── or your web browser ──┐
 │  HTML/CSS/JS user interface    │      │  same interface          │
 └──────────────┬─────────────────┘      └───────────┬──────────────┘
                └──── JSON RPC + live events (127.0.0.1, per-launch token) ────┐
                                                                               ▼
 ClefTune core (runs in the background until you Quit)
   native engine   FFmpeg (PyAV) decoding + miniaudio output: audio lives here, not in the UI
   streams.py      yt-dlp: videoId → audio URL (fast path, prefetch, URL memory, first chunk ready)
   song_cache.py   last N played songs on disk for instant/offline play
   server.py       audio relay with range requests and automatic recovery
   player.py       queue, shuffle, gapless repeat, autoplay radio, sleep timer
   lyrics.py       LRCLIB, YouTube Music, KuGou; offline copies
   ytm.py          ytmusicapi: home, search, albums, artists, playlists, account
   engine_update   downloads a newer YouTube engine (yt-dlp) when YouTube changes something
```

* **Why ad-free:** the app asks YouTube only for the song's metadata and audio stream and plays it itself, so YouTube's ad system never gets involved.
* **Why a brand-new song takes a few seconds:** YouTube needs about 3 s to hand out a stream link, then refuses that link for about 2 s before it works. Prefetching hides this for queued and hovered songs; cached songs skip it entirely.
* **Security:** the server listens on `127.0.0.1` only. Every call needs a random per-launch token, foreign `Host` headers are rejected, and the UI runs under a strict Content-Security-Policy.

## When songs stop loading

YouTube changes things every few weeks. Open *Settings → About → **Update YouTube engine***. It downloads the newest yt-dlp (checksum-verified), tests it, and uses it after a restart. No reinstall is needed. *Use bundled engine* undoes it.

## Data locations

| | Windows | macOS | Linux |
|---|---|---|---|
| App | `%LOCALAPPDATA%\Programs\ClefTune` | `/Applications`, `/Library/Application Support/ClefTune` | `~/.local/lib/cleftune` |
| Library, settings, login | `%LOCALAPPDATA%\ClefTune` | `~/Library/Application Support/ClefTune` | `~/.local/share/cleftune` |
| Cache | `…\ClefTune\cache` | `~/Library/Caches/ClefTune` | `~/.cache/cleftune` |
| Downloads | `Music\ClefTune` | `~/Music/ClefTune` | `~/Music/ClefTune` |

Logs: `cleftune.log` and `window.log` in the library folder.

## Building the installers

PyInstaller can't cross-compile, so each installer is built on its own OS.

* **All three at once:** push a tag like `v1.0.0` (or run the *Installers* workflow) on GitHub. `.github/workflows/installers.yml` builds Windows, macOS (Apple Silicon and Intel) and Linux and attaches them to a release.
* **Locally**, on the OS you're targeting:

  ```bash
  python -m pip install -r packaging/requirements-build.txt   # Windows also needs Inno Setup 6
  python packaging/build.py                                   # → dist/installers/
  ```

* **Signing:** macOS builds are ad-hoc signed. For a Developer ID, set `MACOS_SIGN_IDENTITY` and `MACOS_INSTALLER_IDENTITY` (with the certificates in the keychain), then notarize the `.pkg`. Windows builds are unsigned, so SmartScreen may warn on first run.

## Run from source (developers)

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"                          # + ".[window-qt]" on Linux for the window, ".[tray]" on Windows
python -m cleftune            # --browser / --window, --engine native|mpv|web, --debug
pytest
```

(`install/install.sh` and `install/install.ps1` install from source into a virtual environment; most people should use the installers above.)

## License

GPL-3.0-or-later. Built on [ytmusicapi](https://github.com/sigma67/ytmusicapi) (MIT), [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense), [PyAV](https://github.com/PyAV-Org/PyAV) / FFmpeg (BSD / LGPL), [miniaudio](https://github.com/irmen/pyminiaudio) (MIT), [pywebview](https://github.com/r0x0r/pywebview) (BSD), [PySide6](https://doc.qt.io/qtforpython-6/) (LGPL), [LRCLIB](https://lrclib.net), and Material Design icons (Apache 2.0).
