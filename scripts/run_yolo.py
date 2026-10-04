"""
Run Module 02 — YOLO independently.

Implementation status:
    Scaffold only. Exits with a non-zero status until implemented.

Configuration:
    configs/yolo.yaml

Intended behaviour:
    Run detection + tracking on a camera or recorded video and display / save
    ObjectFrame results with original-frame coordinates.

Usage (once implemented, from the repository root):
    python scripts/run_yolo.py
"""

import sys


def main() -> int:
    # TODO: Load configs/camera.yaml, configs/yolo.yaml and configs/classes.yaml.
    # TODO: Run Module 01 frame source + Module 02 per frame.
    # TODO: Draw boxes / track ids on a copy of the frame for debugging.
    # NOTE: module directories start with digits (01_..05_) and cannot be imported
    # with `import`. Use the loading strategy agreed at integration time
    # (see root README.md -> Architecture -> Numbered module directories).
    print("run_yolo: not implemented yet (scaffold only).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
