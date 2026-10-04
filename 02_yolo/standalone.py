"""Copy this directory anywhere and run: python standalone.py --source 0."""

import importlib.util
import sys
from pathlib import Path


def bootstrap():
    root = Path(__file__).resolve().parent
    if "yolo" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "yolo", root / "__init__.py", submodule_search_locations=[str(root)]
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["yolo"] = module
        spec.loader.exec_module(module)


if __name__ == "__main__":
    bootstrap()
    from yolo.standalone_cli import main

    raise SystemExit(main())
