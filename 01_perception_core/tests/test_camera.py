"""Active Module 01 frame preparation with the shared external source adapter."""
import json
import cv2
import numpy as np
import pytest
from integration.cli import camera_main
from integration.sources import packets
from perception.core import FrameProcessor


def config():
    return {"source": {"type": "camera", "camera_index": None, "mirrored": False}, "capture": {}}


def test_config_rejects_missing_source():
    with pytest.raises(ValueError, match="unset"):
        next(packets(config()))


def test_reads_recorded_video_offline(tmp_path):
    path = tmp_path / "video.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 25, (80, 60))
    assert writer.isOpened()
    for _ in range(3):
        writer.write(np.zeros((60, 80, 3), np.uint8))
    writer.release()
    frames = list(packets(config(), video=path, session_id="replay"))
    assert len(frames) == 3
    assert [f.frame_id for f in frames] == [0, 1, 2]
    assert frames[1].timestamp_s == pytest.approx(1 / 25)
    assert all(f.session_id == "replay" for f in frames)


def test_reports_actual_resolution_and_fps(monkeypatch):
    import integration.sources as sources
    class Capture:
        def set(self, *args):
            return False
        def get(self, prop):
            return 24.0
    class Reader:
        fps = 24.0
        capture = Capture()
        def __init__(self, value):
            assert value == 0
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.closed = True
        def __iter__(self):
            yield 0, 0.1, np.zeros((48, 64, 3), np.uint8)
    monkeypatch.setattr(sources, "OpenCVSource", Reader)
    cfg = config()
    cfg["capture"] = {"requested_width": 1280, "requested_height": 720}
    frame = next(packets(cfg, camera=0))
    assert (frame.width, frame.height) == (64, 48)
    assert frame.metadata["reported_fps"] == 24.0


def test_read_failure_releases_source(monkeypatch):
    import integration.sources as sources
    from yolo.inputs.opencv_source import InputSourceError
    closed = []
    class Reader:
        capture = None
        fps = 30
        def __init__(self, value):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            closed.append(True)
        def __iter__(self):
            raise InputSourceError("camera/source frame read failed")
            yield
    monkeypatch.setattr(sources, "OpenCVSource", Reader)
    with pytest.raises(InputSourceError):
        list(packets(config(), camera=0))
    assert closed


def test_source_frame_not_modified(tmp_path):
    path = tmp_path / "input.png"
    image = np.full((60, 80, 3), 123, np.uint8)
    assert cv2.imwrite(str(path), image)
    frame = next(packets(config(), video=path, session_id="test"))
    result = FrameProcessor().process(frame)
    assert result.source.frame_id == frame.frame_id
    assert result.source.timestamp_s == frame.timestamp_s
    assert result.source.width == 80 and result.source.height == 60
    assert result.source.metadata == frame.metadata
    assert np.array_equal(frame.image, image)
    assert result.image is not frame.image
