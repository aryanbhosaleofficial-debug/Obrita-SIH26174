"""
Run Module 04 — Boundary Detection independently.

Implementation status:
    Scaffold only. Exits with a non-zero status until implemented.

Configuration:
    configs/boundary.yaml

Intended behaviour:
    Run Modules 01-04 and display ROI, mask, contour, chain code and
    boundary state.

Usage (once implemented, from the repository root):
    python scripts/run_boundary.py
"""

import sys


def main() -> int:
    # TODO: Allow running on saved ROI images from data/samples/ for offline tuning.
    # NOTE: module directories start with digits (01_..05_) and cannot be imported
    # with `import`. Use the loading strategy agreed at integration time
    # (see root README.md -> Architecture -> Numbered module directories).
    print("run_boundary: not implemented yet (scaffold only).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
