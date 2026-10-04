"""
Run Full pipeline (Modules 01-05 + Procedure FSM) independently.

Implementation status:
    Scaffold only. Exits with a non-zero status until implemented.

Configuration:
    configs/*.yaml + procedures/<file>.yaml

Intended behaviour:
    Run the complete offline pipeline and report procedure step outcomes
    (correct / wrong order / skipped) and next-step suggestions.

Usage (once implemented, from the repository root):
    python scripts/run_full_pipeline.py
"""

import sys


def main() -> int:
    # TODO: Accept --procedure procedures/demo_experiment.yaml.
    # TODO: Start the Module 01 pipeline manager.
    # TODO: Feed ActivityEvents into procedure/fsm.py.
    # TODO: Log measured per-module timings (no assumed targets).
    # NOTE: module directories start with digits (01_..05_) and cannot be imported
    # with `import`. Use the loading strategy agreed at integration time
    # (see root README.md -> Architecture -> Numbered module directories).
    print("run_full_pipeline: not implemented yet (scaffold only).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
