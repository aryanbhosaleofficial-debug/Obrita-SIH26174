"""Validated semantic candidates, kept separate from ObjectFrame and the FSM."""

import ipaddress
import math
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlsplit


class SemanticStatus(str, Enum):
    DISABLED = "DISABLED"
    WAITING = "WAITING"
    BUSY = "BUSY"
    READY = "READY"
    MODEL_MISSING = "MODEL_MISSING"
    OLLAMA_UNAVAILABLE = "OLLAMA_UNAVAILABLE"
    VLM_ERROR = "VLM_ERROR"
    VLM_PARSE_ERROR = "VLM_PARSE_ERROR"


def default_actions():
    return {
        **{
            f"{verb}_{color}": f"{color.lower()}_box"
            for color in ("RED", "YELLOW")
            for verb in ("PICK", "PLACE", "MANIPULATE")
        },
        "NONE": None,
        "UNCERTAIN": None,
    }


@dataclass(frozen=True)
class SemanticResult:
    action: str
    object_name: str | None
    status: SemanticStatus
    timestamp_s: float
    frame_id: int
    event_id: int = 0
    reason: str | None = None


@dataclass(frozen=True)
class SemanticConfig:
    enabled: bool = False
    model: str = "qwen3-vl:2b-instruct"
    host: str = "http://localhost:11434"
    timeout_s: float = 30.0
    context_tokens: int = 16384
    retry_interval_s: float = 10.0
    capacity: int = 8
    sample_every_frames: int = 2
    keyframes: int = 4
    max_image_side: int = 640
    cooldown_s: float = 3.0
    displacement_threshold: float = 0.04
    interval_s: float | None = None
    action_objects: dict[str, str | None] = field(default_factory=default_actions)

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError("semantic.enabled must be boolean")
        for name, low, high in (
            ("context_tokens", 4096, 65536),
            ("capacity", 2, 64),
            ("sample_every_frames", 1, 10000),
            ("keyframes", 2, self.capacity),
            ("max_image_side", 32, 2048),
        ):
            v = getattr(self, name)
            if type(v) is not int or not low <= v <= high:
                raise ValueError(f"semantic.{name} must be integer in [{low},{high}]")
        for name in (
            "timeout_s",
            "retry_interval_s",
            "cooldown_s",
            "displacement_threshold",
            "interval_s",
        ):
            v = getattr(self, name)
            if name == "interval_s" and v is None:
                continue
            if (
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not math.isfinite(v)
                or v <= 0
            ):
                raise ValueError(f"semantic.{name} must be finite and positive")
        if self.timeout_s > 120:
            raise ValueError("semantic timeout must not exceed 120 seconds")
        local_host(self.host)
        if (
            not isinstance(self.model, str)
            or not self.model.strip()
            or "cloud" in self.model.lower()
        ):
            raise ValueError("semantic model must be a local model name")
        actions = self.action_objects
        if (
            not isinstance(actions, dict)
            or not {"NONE", "UNCERTAIN"} <= actions.keys()
            or actions["NONE"] is not None
            or actions["UNCERTAIN"] is not None
            or any(
                not isinstance(a, str)
                or not a
                or (o is not None and (not isinstance(o, str) or not o))
                for a, o in actions.items()
            )
        ):
            raise ValueError(
                "action_objects requires valid names and NONE/UNCERTAIN: null"
            )
        object.__setattr__(self, "action_objects", dict(actions))


def local_host(host):
    """Loopback only, no credentials, URL paths, proxies or redirects."""
    if not isinstance(host, str):
        raise TypeError("Ollama host must be a loopback HTTP URL")
    p = urlsplit(host)
    try:
        allowed = (
            p.hostname == "localhost" or ipaddress.ip_address(p.hostname).is_loopback
        )
    except ValueError:
        allowed = False
    if (
        p.scheme != "http"
        or not allowed
        or p.username
        or p.password
        or p.path not in ("", "/")
        or p.query
        or p.fragment
    ):
        raise ValueError("Ollama host must be a loopback HTTP URL")
    hostname = "127.0.0.1" if p.hostname == "localhost" else p.hostname
    if ":" in hostname:
        hostname = f"[{hostname}]"
    return f"http://{hostname}:{p.port or 11434}"
