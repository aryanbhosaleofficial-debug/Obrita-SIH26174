"""Model-free Module 02 fixtures. Production code never imports these mocks."""

import socket
import sys
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from perception.core import FrameProcessor
from shared.config import PreprocessingConfig
from shared.schemas.frame_packet import FramePacket
from shared.schemas.observations import BoundingBox, Detection


@pytest.fixture(autouse=True)
def reject_network(monkeypatch):
    """Every Module 02 unit/integration test must operate locally."""

    def reject(*args, **kwargs):
        raise AssertionError("Module 02 tests must not access the network")

    monkeypatch.setattr(socket.socket, "connect", reject)
    monkeypatch.setattr(socket.socket, "sendto", reject)
    monkeypatch.setattr(socket, "getaddrinfo", reject)


@pytest.fixture(autouse=True)
def no_real_speech(monkeypatch):
    """Tests never reach a speaker or the OS speech engine unless they inject fakes."""

    def refuse(*args, **kwargs):
        raise AssertionError("Module 02 tests must not open a real audio device")

    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(
            RawOutputStream=refuse, CallbackAbort=Exception, CallbackStop=Exception
        ),
    )
    monkeypatch.setitem(sys.modules, "comtypes", None)  # import -> ImportError
    monkeypatch.setitem(sys.modules, "comtypes.client", None)


class ScriptedDetector:
    def __init__(self, frames=()):
        self.frames = list(frames)
        self.initializations = 0
        self.calls = 0
        self.closed = 0

    def initialize(self):
        self.initializations += 1

    def close(self):
        self.closed += 1

    def detect(self, image):
        self.calls += 1
        return (
            deepcopy(self.frames[min(self.calls - 1, len(self.frames) - 1)])
            if self.frames
            else []
        )


@pytest.fixture
def backend():
    return ScriptedDetector


@pytest.fixture
def prepared():
    def make(
        width=800, height=400, max_width=400, frame_id=13, timestamp=12.75, color="BGR"
    ):
        image = np.zeros((height, width, 3), np.uint8)
        image[..., 0] = 123
        source = FramePacket(
            frame_id,
            timestamp,
            image,
            width,
            height,
            source_id="camera-test",
            session_id="experiment-test",
            color_format=color,
        )
        return FrameProcessor(PreprocessingConfig(max_width=max_width)).process(source)

    return make


@pytest.fixture
def detection():
    return Detection(0, "vial", 0.85, BoundingBox(20, 30, 80, 90))


@pytest.fixture
def raw_result():
    def make(
        coords=((20, 30, 80, 90),),
        scores=(0.85,),
        classes=(0,),
        ids=None,
        names=None,
        shape=(200, 400),
    ):
        return SimpleNamespace(
            orig_shape=shape,
            names=names or {0: "vial", 1: "tool"},
            boxes=SimpleNamespace(
                xyxy=np.asarray(coords).reshape((-1, 4)),
                conf=np.asarray(scores),
                cls=np.asarray(classes),
                id=None if ids is None else np.asarray(ids),
            ),
        )

    return make
