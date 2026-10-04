"""Optional mypy check for active modules behind the dynamic yolo package path.

Mypy does not follow runtime __path__ assignment. Check unchanged source copies
under a temporary valid package name; never replace the application's packages.
Run from the repository root with python -m yolo.tests.verify_types.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ACTIVE_MODULES = (
    "__init__.py",
    "__main__.py",
    "config.py",
    "input_validation.py",
    "pipeline.py",
    "cli.py",
    "standalone.py",
    "standalone_cli.py",
    "inference/__init__.py",
    "inference/detector.py",
    "inference/postprocess.py",
    "inference/class_map.py",
)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    with TemporaryDirectory(prefix="orbita-mypy-source-") as temporary:
        view = Path(temporary)
        source_names = list(ACTIVE_MODULES)
        for package in ("core", "adapters", "inputs", "semantic", "visualization"):
            source_names.extend(
                str(path.relative_to(root / "02_yolo"))
                for path in (root / "02_yolo" / package).rglob("*.py")
            )
        for name in source_names:
            target = view / "yolo" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / "02_yolo" / name, target)
        env = dict(os.environ, MYPYPATH=f"{view}{os.pathsep}{root}")
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "mypy",
                "-p",
                "yolo",
                "--follow-imports=silent",
                "--ignore-missing-imports",
                "--check-untyped-defs",
                "--cache-dir",
                str(view / "cache"),
            ],
            cwd=view,
            env=env,
            check=False,
        ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
