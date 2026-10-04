"""Explicit local setup: extract ONLY the statically audited prototype best.pt."""

import hashlib
import zipfile
from pathlib import Path

EXPECTED = "b9ab5c71a5c4e0ed151d6e8001983e5e7d5a5995a73cc419d580da304f1c687d"


def main():
    root = Path(__file__).resolve().parents[1]
    with zipfile.ZipFile(root / "HAR.zip") as archive:
        member = archive.getinfo("HAR/best.pt")
        if member.file_size != 6249770:
            raise ValueError("prototype checkpoint size differs from audited asset")
        data = archive.read(member)
    if hashlib.sha256(data).hexdigest() != EXPECTED:
        raise ValueError("prototype checkpoint digest differs from audited asset")
    target = root / "models/best.pt"
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != EXPECTED:
            raise ValueError("refusing to overwrite a different checkpoint")
    else:
        target.write_bytes(data)
    print(f"Local model ready: {target}")


if __name__ == "__main__":
    main()
