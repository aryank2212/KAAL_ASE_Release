"""PyInstaller entry point for the Windows build."""
import multiprocessing
import os
import sys

from app.launcher import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    args = sys.argv[1:]
    if not os.environ.get("KAAL_NO_OPEN") and args[:1] != ["--run-tool"] and "--version" not in args:
        args = ["--open"] + args           # double-click: open the console in the browser
    main(args)
