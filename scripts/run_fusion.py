"""
Run Module 05 — Perception Fusion independently.

Implementation status:
    Scaffold only. Exits with a non-zero status until implemented.

Configuration:
    configs/fusion.yaml

Intended behaviour:
    Run Modules 01-05 and print ActivityEvents as they are confirmed.

Usage (once implemented, from the repository root):
    python scripts/run_fusion.py
"""

import sys


def main() -> int:
    # TODO: Write ActivityEvents to outputs/events/.
    # NOTE: module directories start with digits (01_..05_) and cannot be imported
    # with `import`. Use the loading strategy agreed at integration time
    # (see root README.md -> Architecture -> Numbered module directories).
    print("run_fusion: not implemented yet (scaffold only).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
