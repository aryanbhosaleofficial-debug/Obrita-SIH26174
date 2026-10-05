"""Alias for the authoritative full-system launcher; no-argument legacy demo retained."""

from __future__ import annotations

import sys

from scripts.run_full_pipeline import main as run_pipeline_main


def main() -> int:
    if sys.argv[1:]:
        return run_pipeline_main(sys.argv[1:])
    from integration.full_cli import ROOT
    return run_pipeline_main([str(ROOT / "procedures/demo_experiment.yaml"), str(ROOT / "configs")])


if __name__ == "__main__":
    sys.exit(main())
