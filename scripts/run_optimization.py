"""Run the canonical offline Module 03 replay CLI from any working directory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from optimization.standalone_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
