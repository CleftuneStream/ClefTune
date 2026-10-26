"""Process entry point. Sets up the updatable engine before anything imports yt_dlp."""

import sys


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--check-engine":
        from .engine_update import check_engine
        sys.exit(check_engine(sys.argv[2]))
    from . import engine_update
    engine_update.activate()
    from .app import main as app_main
    app_main()
