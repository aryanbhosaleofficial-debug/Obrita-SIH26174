"""Opt-in calibrated demo rules, never image-axis gravity inference."""

import math
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from yolo.procedure.contracts import FastActionResult
from yolo.semantic.contracts import default_actions


@dataclass(frozen=True)
class HomeRegion:
    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self):
        values = (self.x1, self.y1, self.x2, self.y2)
        if any(
            isinstance(v, bool)
            or not isinstance(v, (float, int))
            or not math.isfinite(v)
            for v in values
        ) or not (0 <= self.x1 < self.x2 <= 1 and 0 <= self.y1 < self.y2 <= 1):
            raise ValueError("home ROI must be normalized x1,y1,x2,y2 in [0,1]")


@dataclass(frozen=True)
class FastConfig:
    home_regions: dict[str, HomeRegion] = field(default_factory=dict)
    displacement_threshold: float = 0.03
    boundary_margin: float = 0.01
    reference_object: str | None = None
    reference_tolerance: float = 0.01
    work_regions: dict[str, HomeRegion] = field(default_factory=dict)
    work_dwell_frames: int = 3

    def __post_init__(self):
        if len(self.home_regions) > 64 or any(
            not isinstance(k, str) or not isinstance(v, HomeRegion)
            for k, v in self.home_regions.items()
        ):
            raise ValueError("invalid or excessive home regions")
        for name in (
            "displacement_threshold",
            "boundary_margin",
            "reference_tolerance",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (float, int))
                or not math.isfinite(value)
                or not 0 < value < 0.5
            ):
                raise ValueError(f"fast.{name} must be finite in (0,0.5)")
        if self.reference_object is not None and (
            not isinstance(self.reference_object, str) or not self.reference_object
        ):
            raise ValueError("reference_object must be a class name or null")
        if (
            type(self.work_dwell_frames) is not int
            or not 1 <= self.work_dwell_frames <= 120
        ):
            raise ValueError("fast.work_dwell_frames must be integer 1..120")
        if not isinstance(self.work_regions, dict) or any(
            k not in self.home_regions or not isinstance(v, HomeRegion)
            for k, v in self.work_regions.items()
        ):
            raise ValueError("work regions require matching home regions")
        for name, work in self.work_regions.items():
            home = self.home_regions[name]
            if max(home.x1, work.x1) < min(home.x2, work.x2) and max(
                home.y1, work.y1
            ) < min(home.y2, work.y2):
                raise ValueError(
                    f"home and work ROI interiors must not overlap: {name}"
                )
        for kind, regions in (("home", self.home_regions), ("work", self.work_regions)):
            for name, roi in regions.items():
                if min(roi.x2 - roi.x1, roi.y2 - roi.y1) <= 2 * self.boundary_margin:
                    raise ValueError(
                        f"{kind} ROI has no usable interior after margin: {name}"
                    )
        object.__setattr__(self, "home_regions", dict(self.home_regions))
        object.__setattr__(self, "work_regions", dict(self.work_regions))


def load_fast_config(path, action_objects):
    if path is None:
        return FastConfig()
    path = Path(path)
    if path.stat().st_size > 65536:
        raise ValueError("fast config exceeds 64 KiB")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or set(data) != {"fast"}
        or not isinstance(data["fast"], dict)
    ):
        raise ValueError("fast YAML requires a single fast mapping")
    values = dict(data["fast"])
    regions = values.pop("home_regions", {})
    work_regions = values.pop("work_regions", {})
    if not isinstance(regions, dict) or any(
        k not in action_objects.values() for k in regions
    ):
        raise ValueError("home regions must name configured experiment objects")
    if not isinstance(work_regions, dict) or any(
        k not in regions for k in work_regions
    ):
        raise ValueError("work regions must name objects with configured home regions")
    try:
        return FastConfig(
            home_regions={k: HomeRegion(*v) for k, v in regions.items()},
            work_regions={k: HomeRegion(*v) for k, v in work_regions.items()},
            **values,
        )
    except TypeError as exc:
        raise ValueError(f"invalid fast configuration: {exc}") from exc


@dataclass
class _ObjectState:
    track_id: int
    home: bool
    anchor: tuple[float, float]
    current: tuple[float, float]
    candidate: str = "UNCERTAIN"
    work_count: int = 0
    work_anchor: tuple[float, float] | None = None
    last_work_frame: int = -1


class FastClassifier:
    def __init__(self, config=None, action_objects=None):
        self.config = config or FastConfig()
        self.actions = (
            default_actions() if action_objects is None else dict(action_objects)
        )
        self.reset()

    def reset(self):
        self.states = {}
        self.reference = None

    def coverage(self, definition):
        result = {}
        for step in definition.steps:
            home = step.object_name in self.config.home_regions
            if step.action.startswith(("PICK_", "PLACE_")):
                supported = home
            elif step.action.startswith("MANIPULATE_"):
                supported = home and step.object_name in self.config.work_regions
            else:
                supported = False
            verb = step.action.partition("_")[0]
            emitted = next(
                (
                    a
                    for a, obj in self.actions.items()
                    if obj == step.object_name and a.startswith(verb + "_")
                ),
                None,
            )
            supported = supported and emitted == step.action
            result[step.action] = supported
        return result

    def classify(self, objects):
        def uncertain(reason):
            return FastActionResult(
                "UNCERTAIN", None, objects.frame_id, objects.timestamp_s, reason
            )

        if objects.status in ("error", "invalid_input"):
            self.reset()
            return uncertain("detector unavailable")
        if not self.config.home_regions:
            return uncertain("no calibrated demo home regions")
        width, height = objects.image_width, objects.image_height
        if self.config.reference_object:
            refs = [
                d
                for d in objects.detections
                if d.class_name == self.config.reference_object
                and d.track_id is not None
                and d.identity_persistent
            ]
            if len(refs) != 1:
                self.reset()
                return uncertain("reference identity unavailable")
            ref = refs[0]
            x1, y1, x2, y2 = ref.bbox_xyxy
            reference = (
                ref.track_id,
                (x1 + x2) / (2 * width),
                (y1 + y2) / (2 * height),
            )
            if self.reference is not None and (
                reference[0] != self.reference[0]
                or math.dist(reference[1:], self.reference[1:])
                > self.config.reference_tolerance
            ):
                self.states.clear()
                return uncertain(
                    "reference moved; recalibrate/reset before using fast rules"
                )
            self.reference = reference
        candidates = []
        for name, roi in self.config.home_regions.items():
            matches = [d for d in objects.detections if d.class_name == name]
            if (
                len(matches) != 1
                or matches[0].track_id is None
                or not matches[0].identity_persistent
            ):
                self.states.pop(name, None)
                continue  # absence/occlusion/ambiguous identity never means PICK
            obj = matches[0]
            x1, y1, x2, y2 = obj.bbox_xyxy
            center = ((x1 + x2) / (2 * width), (y1 + y2) / (2 * height))
            margin = self.config.boundary_margin
            if (
                roi.x1 + margin <= center[0] <= roi.x2 - margin
                and roi.y1 + margin <= center[1] <= roi.y2 - margin
            ):
                home = True
            elif not (
                roi.x1 - margin <= center[0] <= roi.x2 + margin
                and roi.y1 - margin <= center[1] <= roi.y2 + margin
            ):
                home = False
            else:
                continue  # boundary jitter cannot confirm a transition
            state = self.states.get(name)
            if state is None or state.track_id != obj.track_id:
                self.states[name] = _ObjectState(obj.track_id, home, center, center)
                continue
            state.current = center
            work = self.config.work_regions.get(name)
            in_work = work is not None and (
                work.x1 + margin <= center[0] <= work.x2 - margin
                and work.y1 + margin <= center[1] <= work.y2 - margin
            )
            if in_work and not state.home and not home:
                if state.last_work_frame != objects.frame_id - 1:
                    state.work_count = 0
                    state.work_anchor = center
                state.work_count += 1
                state.last_work_frame = objects.frame_id
            else:
                state.work_count = 0
                state.work_anchor = None
                state.last_work_frame = -1
            manipulation = (
                in_work
                and state.work_count >= self.config.work_dwell_frames
                and state.work_anchor is not None
                and math.dist(center, state.work_anchor)
                >= self.config.displacement_threshold
            )
            verb = (
                "PICK"
                if state.home and not home
                else "PLACE"
                if not state.home and home
                else "MANIPULATE"
                if manipulation
                else None
            )
            action = next(
                (
                    a
                    for a, o in self.actions.items()
                    if o == name and verb is not None and a.startswith(verb + "_")
                ),
                None,
            )
            state.candidate = action or "UNCERTAIN"
            if action:
                candidates.append(
                    FastActionResult(
                        action,
                        name,
                        objects.frame_id,
                        objects.timestamp_s,
                        "calibrated_demo_roi_transition"
                        if verb != "MANIPULATE"
                        else "calibrated_work_roi_dwell_and_displacement",
                    )
                )
        if len(candidates) != 1:
            return uncertain(
                "no supported transition"
                if not candidates
                else "simultaneous ambiguous actions"
            )
        return candidates[0]

    def acknowledge(self, action):
        state = self.states.get(action.object_name)
        if state is not None:
            if action.action.startswith("PICK_"):
                state.home = False
            elif action.action.startswith("PLACE_"):
                state.home = True
            state.anchor = state.current
            state.candidate = "UNCERTAIN"
            state.work_count = 0
            state.work_anchor = None
            state.last_work_frame = -1
