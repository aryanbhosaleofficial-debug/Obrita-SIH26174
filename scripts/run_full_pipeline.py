"""Historical procedure-demo entry point; delegates to the authoritative event runner.

This command simulates semantic activities. It does not claim camera inference.
Use scripts/run_fusion.py for the perception milestone and procedure.demo for replay.
"""
if __package__:
    from scripts._bootstrap import bootstrap
else:
    from _bootstrap import bootstrap
bootstrap()

import argparse
import sys
from pathlib import Path
from procedure.demo import run_demo
from procedure.procedure_loader import load_procedure


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("procedure", nargs="?", default="procedures/demo_experiment.yaml")
    parser.add_argument("config_dir", nargs="?", default="configs")
    args = parser.parse_args(argv)
    if not Path(args.procedure).is_file():
        print(f"procedure file not found: {args.procedure}", file=sys.stderr)
        return 1
    if not Path(args.config_dir).is_dir():
        print(f"config directory not found: {args.config_dir}", file=sys.stderr)
        return 1
    try:
        return run_demo(load_procedure(args.procedure, args.config_dir), legacy_output=True)
    except (OSError, ValueError) as exc:
        print(f"procedure configuration: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
