"""Compatibility entry point for canonical offline Module 03 replay."""

import sys

from optimization.standalone_cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["--synthetic"]))
