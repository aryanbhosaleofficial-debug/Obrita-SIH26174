"""Create the parent of pytest's repository-local generated fixture directory."""
from pathlib import Path


def pytest_configure(config):
    (Path(__file__).resolve().parent / "tests_tmp").mkdir(exist_ok=True)
