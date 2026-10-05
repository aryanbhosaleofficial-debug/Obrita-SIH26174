"""Strict local YAML settings for the explainable prototype baseline."""
from copy import deepcopy
from pathlib import Path
import math
import yaml
from shared.config import ConfigurationError

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "configs/fusion.yaml"
SOURCES = {"object", "gesture", "interaction", "motion", "contact", "boundary"}


def validate_config(data):
    cfg = deepcopy(data)
    expected = {"input", "evidence", "confidence", "conflict_resolution", "temporal", "activities", "output"}
    if not isinstance(cfg, dict) or set(cfg) != expected:
        raise ConfigurationError("fusion config requires the documented sections")
    try:
        def number(value, name, low=0, high=1):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ConfigurationError(f"invalid fusion {name}: {value!r}")

        number(cfg["input"]["max_timestamp_mismatch_s"], "timestamp tolerance", high=float("inf"))
        if type(cfg["input"]["allow_missing_boundary"]) is not bool:
            raise ConfigurationError("allow_missing_boundary must be boolean")
        if cfg["input"]["reject_statuses"] != ["error", "invalid_input"]:
            raise ConfigurationError("fusion must reject error and invalid_input statuses")
        for section in (cfg["evidence"]["min_confidence"], cfg["confidence"]["weights"]):
            if set(section) != SOURCES:
                raise ConfigurationError("fusion requires all six evidence source settings")
            for source, value in section.items():
                number(value, source)
        if not all(v > 0 for v in cfg["confidence"]["weights"].values()):
            raise ConfigurationError("fusion weights must be positive")
        number(cfg["confidence"]["min_event_confidence"], "event threshold")
        if cfg["confidence"]["method"] != "rule_based" or cfg["confidence"]["missing_evidence_policy"] != "unknown":
            raise ConfigurationError("baseline supports rule_based fusion and unknown missing evidence")
        if cfg["conflict_resolution"]["policy"] not in ("mark_uncertain", "prefer_confirmed_boundary"):
            raise ConfigurationError("unsupported conflict policy")
        if type(cfg["conflict_resolution"]["record_conflicts"]) is not bool:
            raise ConfigurationError("record_conflicts must be boolean")
        temporal = cfg["temporal"]
        for key in ("confirmation_min_hits", "confirmation_window", "end_gap_frames"):
            if type(temporal[key]) is not int or temporal[key] < 1:
                raise ConfigurationError(f"{key} must be a positive integer")
        if not 2 <= temporal["confirmation_min_hits"] <= temporal["confirmation_window"]:
            raise ConfigurationError("confirmation requires 2 <= hits <= window")
        number(temporal["max_time_gap_s"], "time gap", low=1e-9, high=float("inf"))
        number(cfg["evidence"]["motion_min_speed"], "motion speed", high=float("inf"))
        priority = cfg["evidence"]["interaction_priority"]
        if not isinstance(priority, list) or any(not isinstance(v, str) for v in priority) or len(set(priority)) != len(priority) or not priority:
            raise ConfigurationError("interaction_priority must contain unique state strings")
        labels = cfg["activities"]["labels"]
        if not isinstance(labels, list) or "unknown" not in labels or any(not isinstance(v, str) or not v for v in labels) or len(set(labels)) != len(labels):
            raise ConfigurationError("activity labels must be unique strings including unknown")
        rules = cfg["activities"]["rules"]
        if not isinstance(rules, list) or not rules:
            raise ConfigurationError("activity rules must be a nonempty list")
        names = set()
        for rule in rules:
            if set(rule) != {"name", "label", "all", "any"} or rule["label"] not in labels or rule["label"] == "unknown" or not isinstance(rule["name"], str) or not rule["name"] or rule["name"] in names:
                raise ConfigurationError("invalid or duplicate activity rule")
            names.add(rule["name"])
            if not isinstance(rule["all"], dict) or not rule["all"] or not isinstance(rule["any"], dict):
                raise ConfigurationError("rules require nonempty all and optional any mappings")
            for source, values in {**rule["all"], **rule["any"]}.items():
                if source not in SOURCES or not isinstance(values, list) or not values or any(not isinstance(v, str) or not v for v in values):
                    raise ConfigurationError("rule evidence must name a source and string values")
        if set(labels) - {"unknown"} != {r["label"] for r in rules}:
            raise ConfigurationError("every configured activity needs a rule")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ConfigurationError(f"invalid fusion configuration: {exc}") from exc
    return cfg


def load_config(path=DEFAULT_CONFIG):
    try:
        return validate_config(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"cannot load fusion config {path}: {exc}") from exc
