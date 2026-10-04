"""The project class mapping is a required local startup contract for real weights."""

from pathlib import Path

import yaml


def load_class_map(path: Path | None) -> dict[int, str]:
    if path is None or not path.is_file():
        raise ValueError("classes_path must name the project's local classes.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = data.get("classes") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError("classes.yaml requires a nonempty classes list")
    mapping = {}
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or type(entry.get("id")) is not int
            or entry["id"] < 0
            or not isinstance(entry.get("name"), str)
            or not entry["name"]
            or entry["id"] in mapping
            or entry["name"] in mapping.values()
        ):
            raise ValueError(
                "classes.yaml requires unique nonnegative integer IDs and names; replace scaffold placeholders"
            )
        mapping[entry["id"]] = entry["name"]
    return mapping


def validate_model_classes(names, expected: dict[int, str]) -> None:
    if isinstance(names, (list, tuple)):
        actual = dict(enumerate(names))
    elif isinstance(names, dict):
        actual = names
    else:
        raise TypeError("weights do not expose a class mapping")
    if actual != expected:
        raise ValueError(
            f"model class mapping incompatible with project classes: expected {expected}, got {actual}"
        )
