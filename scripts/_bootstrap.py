"""Direct-script launchers share one repository-root import boundary."""
import sys
from pathlib import Path


def bootstrap():
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)
