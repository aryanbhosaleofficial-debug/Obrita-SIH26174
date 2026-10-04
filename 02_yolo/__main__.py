"""python -m yolo entry point; no alternate detector implementation."""

# ruff: noqa: N999 -- numbered team directory is exposed through the yolo package
from yolo.cli import main

raise SystemExit(main())
