"""
SIH26174 — AI Human Activity Recognition for On-board BAS Experiments.

Implementation status:
    Scaffold only. Exits with a non-zero status until implemented.

Configuration:
    configs/*.yaml + procedures/<file>.yaml

Intended behaviour:
    Single entry point for the demo. Delegates to the full pipeline
    (scripts/run_full_pipeline.py). Keep this file thin: no module logic here.

Usage (once implemented, from the repository root):
    python main.py
"""

import sys


def main() -> int:
    # TODO: Parse --procedure and --config-dir arguments.
    # TODO: Delegate to the full-pipeline runner.
    # NOTE: module directories start with digits (01_..05_) and cannot be imported
    # with `import`. Use the loading strategy agreed at integration time
    # (see root README.md -> Architecture -> Numbered module directories).
    print("main: not implemented yet (scaffold only).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
