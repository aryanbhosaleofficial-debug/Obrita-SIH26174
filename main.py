"""Repository entry point for the procedure pipeline demo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.run_full_pipeline import main as run_pipeline_main


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the demo procedure pipeline.")
    parser.add_argument("--procedure", default="procedures/demo_experiment.yaml", help="Path to a YAML procedure file.")
    parser.add_argument("--config-dir", default="configs", help="Directory containing fusion.yaml and classes.yaml.")
    args = parser.parse_args()

    procedure_path = Path(args.procedure)
    config_dir = Path(args.config_dir)
    if not procedure_path.exists():
        raise FileNotFoundError(f"Procedure file not found: {procedure_path}")
    if not config_dir.exists():
        raise FileNotFoundError(f"Config directory not found: {config_dir}")

    return run_pipeline_main([str(procedure_path), str(config_dir)])


if __name__ == "__main__":
    sys.exit(main())
