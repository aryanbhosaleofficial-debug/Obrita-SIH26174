"""Standalone default entry point, with the legacy --input SIH smoke preserved."""
# ruff: noqa: N999
import sys
if __package__ != "yolo":
    from .standalone import bootstrap
    bootstrap()
if "--input" in sys.argv:
    from yolo.cli import main
else:
    from yolo.standalone_cli import main
raise SystemExit(main())
