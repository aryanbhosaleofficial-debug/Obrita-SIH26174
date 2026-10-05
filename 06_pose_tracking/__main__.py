"""python -m 06_pose_tracking --camera 0 (run from the repository root)."""

# ruff: noqa: N999
if __package__ != "pose_tracking":
    from .standalone import bootstrap

    bootstrap()

from pose_tracking.cli import main  # registered by bootstrap() above

if __name__ == "__main__":
    raise SystemExit(main())
