"""Standalone default entry point, with the legacy --input SIH smoke preserved."""

# ruff: noqa: N999
import sys

if __package__ != "yolo":
    from .standalone import bootstrap

    bootstrap()


def main() -> int:
    if "--input" in sys.argv:
        from yolo.cli import main as pipeline_main

        return pipeline_main()
    from yolo.standalone_cli import main as standalone_main

    return standalone_main()


if __name__ == "__main__":
    raise SystemExit(main())
