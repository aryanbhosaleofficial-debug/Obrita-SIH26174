"""Shared lifecycle error contract; no backend ownership."""


class InitializationError(RuntimeError):
    """A configured dependency/model cannot initialize; caller must repair setup."""
