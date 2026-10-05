"""Vocabulary comes from the same YAML used by the procedure loader."""
from fusion.config import load_config


def labels(path=None):
    return tuple((load_config(path) if path else load_config())["activities"]["labels"])
