"""
Run Module 01 — Perception Core independently.

Implementation status:
    Scaffold only. Exits with a non-zero status until implemented.

Configuration:
    configs/camera.yaml

Intended behaviour:
    Open the configured camera or video file, assign frame_id / timestamp_s,
    show or record frames, and log measured capture timing.

Usage (once implemented, from the repository root):
    python scripts/run_camera.py
"""

import sys


def main() -> int:
    # TODO: Load configs/camera.yaml.
    # TODO: Start camera capture and print actual resolution/FPS reported by the driver.
    # TODO: Optionally record to outputs/recordings/.
    # NOTE: module directories start with digits (01_..05_) and cannot be imported
    # with `import`. Use the loading strategy agreed at integration time
    # (see root README.md -> Architecture -> Numbered module directories).
    print("run_camera: not implemented yet (scaffold only).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
