"""Static ZIP/checkpoint audit. No extraction paths or pickle code are executed."""

import hashlib
import io
import json
import pickletools
import zipfile
from pathlib import Path, PurePosixPath


def main():
    archive = Path(__file__).resolve().parents[1] / "HAR.zip"
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            path = PurePosixPath(item.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or ":" in item.filename:
                raise ValueError("unsafe archive member")
            print(item.filename, item.file_size)
            if item.file_size > 64 * 1024 * 1024:
                raise ValueError("archive member exceeds audit limit")
            if item.filename.endswith(".py"):
                print(z.read(item).decode("utf-8"))
            elif item.filename.endswith(".pt"):
                data = z.read(item)
                print("sha256", hashlib.sha256(data).hexdigest())
                with zipfile.ZipFile(io.BytesIO(data)) as checkpoint:
                    name = next(
                        n for n in checkpoint.namelist() if n.endswith("data.pkl")
                    )
                    operations = list(pickletools.genops(checkpoint.read(name)))
                    globals_ = [arg for op, arg, _ in operations if op.name == "GLOBAL"]
                    print("static globals", json.dumps(globals_))
                    for index, (_, arg, _) in enumerate(operations):
                        if arg in ("names", "yaml_file"):
                            print(
                                [
                                    (op.name, value)
                                    for op, value, _ in operations[index : index + 28]
                                ]
                            )


if __name__ == "__main__":
    main()
