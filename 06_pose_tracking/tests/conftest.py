"""Model-free Module 06 fixtures. No webcam, GPU, display or network is used."""

import importlib.util
import socket
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

_spec = importlib.util.spec_from_file_location(
    "_module06_standalone", Path(__file__).resolve().parents[1] / "standalone.py"
)
_standalone = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_standalone)
_standalone.bootstrap()

from pose_tracking.backends import RawHand, RawLandmark, RawResult
from pose_tracking.config import PoseTrackingConfig
from pose_tracking.tracker import PoseHandTracker

from perception.core import FrameProcessor
from shared.config import PreprocessingConfig
from shared.schemas.frame_packet import FramePacket

MODULE_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def reject_network(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Module 06 tests must not access the network")

    monkeypatch.setattr(socket.socket, "connect", reject)
    monkeypatch.setattr(socket.socket, "sendto", reject)
    monkeypatch.setattr(socket, "getaddrinfo", reject)


def raw_body(cx=0.5, cy=0.5, visibility=0.9):
    return tuple(
        RawLandmark(
            cx + 0.004 * (i % 7) - 0.012,
            cy + 0.006 * (i // 7) - 0.012,
            -0.1,
            visibility,
            0.95,
        )
        for i in range(33)
    )


def raw_hand(label="Left", cx=0.3, cy=0.6, score=0.9):
    return RawHand(
        tuple(
            RawLandmark(cx + 0.003 * (i % 5), cy + 0.004 * (i // 5), 0.0)
            for i in range(21)
        ),
        label,
        score,
    )


class ScriptedBackend:
    """Returns scripted RawResults (or raises scripted exceptions) in order."""

    def __init__(self, results=(), *, repeat_last=True):
        self.results = list(results)
        self.repeat_last = repeat_last
        self.calls = 0
        self.initializations = 0
        self.closes = 0
        self.timestamps = []

    def initialize(self):
        self.initializations += 1

    def detect(self, image_bgr, timestamp_s):
        self.calls += 1
        self.timestamps.append(timestamp_s)
        if not self.results:
            return RawResult()
        index = self.calls - 1
        if index >= len(self.results):
            if not self.repeat_last:
                return RawResult()
            index = len(self.results) - 1
        item = self.results[index]
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        self.closes += 1


def model_free_config(**overrides):
    values = {
        "pose_model_path": Path("unused-pose.task"),
        "hand_model_path": Path("unused-hand.task"),
        "smoothing_alpha": 1.0,
        "max_hold_frames": 2,
    }
    values.update(overrides)
    return PoseTrackingConfig(**values).validate()


class FrameFactory:
    """Real Module 01 PreparedFrames with strictly increasing IDs/timestamps."""

    def __init__(
        self,
        width=640,
        height=480,
        *,
        max_width=None,
        source_id="camera-test",
        session_id="session-test",
        fps=30.0,
    ):
        self.width, self.height = width, height
        self.source_id, self.session_id = source_id, session_id
        self.fps = fps
        self.core = FrameProcessor(PreprocessingConfig(max_width=max_width))
        self.next_id = 0

    def packet(self, frame_id=None, timestamp_s=None):
        frame_id = self.next_id if frame_id is None else frame_id
        self.next_id = frame_id + 1
        image = np.full((self.height, self.width, 3), 40, np.uint8)
        return FramePacket(
            frame_id,
            frame_id / self.fps if timestamp_s is None else timestamp_s,
            image,
            self.width,
            self.height,
            source_id=self.source_id,
            session_id=self.session_id,
        )

    def __call__(self, frame_id=None, timestamp_s=None):
        return self.core.process(self.packet(frame_id, timestamp_s))


@pytest.fixture
def frames():
    return FrameFactory


@pytest.fixture
def raw():
    """Builders for synthetic model output: raw.body(), raw.hand(), raw.result()."""
    return SimpleNamespace(
        body=raw_body, hand=raw_hand, result=RawResult, Backend=ScriptedBackend
    )


@pytest.fixture
def config():
    return model_free_config


@pytest.fixture
def make_tracker():
    def make(results=(), backend=None, **config):
        backend = backend or ScriptedBackend(results)
        tracker = PoseHandTracker(model_free_config(**config), backend)
        tracker.initialize()
        return tracker, backend

    return make
