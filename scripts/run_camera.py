"""Run actual Module 01 preparation on camera/video or synthetic frames."""
if __package__:
    from scripts._bootstrap import bootstrap
else:
    from _bootstrap import bootstrap
bootstrap()
from integration.cli import camera_main

if __name__ == "__main__":
    raise SystemExit(camera_main())
