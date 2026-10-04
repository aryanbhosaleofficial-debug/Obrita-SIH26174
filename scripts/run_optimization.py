"""
Run Module 03 — Optimization Sequence independently.

Implementation status:
    Scaffold only. Exits with a non-zero status until implemented.

Configuration:
    configs/optimization.yaml

Intended behaviour:
    Run Modules 01-03 and display skeleton, rack reference, motion,
    interaction and gesture outputs.

Usage (once implemented, from the repository root):
    python scripts/run_optimization.py
"""

import sys


def main() -> int:
    # TODO: Support a --spatial-only flag so Teammate 3 can test without Teammate 4's section.
    # TODO: Save debug frames to outputs/debug_frames/ when enabled.
    # NOTE: module directories start with digits (01_..05_) and cannot be imported
    # with `import`. Use the loading strategy agreed at integration time
    # (see root README.md -> Architecture -> Numbered module directories).
    print("run_optimization: not implemented yet (scaffold only).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
