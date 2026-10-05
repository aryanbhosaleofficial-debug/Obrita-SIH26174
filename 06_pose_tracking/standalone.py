"""Run from anywhere: python 06_pose_tracking/standalone.py --camera 0

The numbered directory cannot be imported with a normal statement, so this
registers it under the import-safe name ``pose_tracking`` (the same technique
Module 02 uses) and puts the repository root on sys.path for ``shared``,
``perception`` and, with --yolo, the ``yolo`` locator.
"""

import importlib.util
import sys
from pathlib import Path

PACKAGE = "pose_tracking"


def bootstrap():
    root = Path(__file__).resolve().parent
    repo = str(root.parent)
    if repo not in sys.path:
        sys.path.insert(0, repo)
    if PACKAGE not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            PACKAGE, root / "__init__.py", submodule_search_locations=[str(root)]
        )
        if spec is None or spec.loader is None:
            raise ImportError("cannot load the local Module 06 package")
        module = importlib.util.module_from_spec(spec)
        sys.modules[PACKAGE] = module
        spec.loader.exec_module(module)


if __name__ == "__main__":
    bootstrap()
    from pose_tracking.cli import main

    raise SystemExit(main())
