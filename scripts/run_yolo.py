"""Repository-root convenience launcher for the canonical Module 02 smoke CLI."""

import sys
from pathlib import Path

# Direct script execution puts scripts/, rather than the repository, on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yolo.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
