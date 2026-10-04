"""The project class mapping is a required local startup contract for real weights."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


def load_class_map(path: Path | None) -> dict[int, str]:
    if path is None or not path.is_file():
        raise ValueError("classes_path must name the project's local classes.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = data.get("classes") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError("classes.yaml requires a nonempty classes list")
    mapping: dict[int, str] = {}
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or type(entry.get("id")) is not int
            or entry["id"] < 0
            or not isinstance(entry.get("name"), str)
            or not entry["name"].strip()
            or entry["id"] in mapping
            or entry["name"] in mapping.values()
        ):
            raise ValueError(
                "classes.yaml requires unique nonnegative integer IDs and names; replace scaffold placeholders"
            )
        mapping[entry["id"]] = entry["name"]
    return mapping


def class_mapping(names: Any) -> Mapping[int, str]:
    if isinstance(names, (list, tuple)):
        actual = dict(enumerate(names))
    elif isinstance(names, dict):
        actual = names
    else:
        raise TypeError("weights do not expose a class mapping")
    if any(
        type(key) is not int
        or key < 0
        or not isinstance(value, str)
        or not value.strip()
        for key, value in actual.items()
    ):
        raise ValueError(
            "model class mapping requires nonnegative integer IDs and nonempty names"
        )
    return actual


def validate_model_classes(names: Any, expected: dict[int, str]) -> None:
    actual = class_mapping(names)
    if actual != expected:
        raise ValueError(
            f"model class mapping incompatible with project classes: expected {expected}, got {actual}"
        )
