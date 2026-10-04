import sys
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from perception.config import DetectorConfig, HandTrackerConfig
from perception.contracts import BoundingBox, Point2D
from perception.detector import (
    InitializationError,
    UltralyticsYoloDetector,
    filter_detections,
)
from perception.hand_tracker import MediaPipeHandTracker, filter_hands


class Tensor:
    def __init__(self, values):
        self.values = np.asarray(values)

    def cpu(self):
        return self

    def numpy(self):
        return self.values


def test_yolo_output_conversion_and_threshold_arguments():
    captured = {}

    class Model:
        def predict(self, **kwargs):
            captured.update(kwargs)
            return [
                SimpleNamespace(
                    names={2: "tool"},
                    boxes=SimpleNamespace(
                        xyxy=Tensor([[10, 20, 30, 40]]),
                        conf=Tensor([0.8]),
                        cls=Tensor([2]),
                        id=Tensor([99]),
                    ),
                )
            ]

    adapter = UltralyticsYoloDetector(
        DetectorConfig(confidence_threshold=0.6, iou_threshold=0.4, class_whitelist=[2])
    )
    adapter._model = Model()
    result = adapter.detect(np.zeros((100, 100, 3), np.uint8))
    assert result[0].class_id == 2 and result[0].class_name == "tool"
    assert result[0].bbox == BoundingBox(10, 20, 30, 40)
    assert result[0].track_id is None  # predict mode must not leak IDs
    assert captured["conf"] == 0.6 and captured["iou"] == 0.4
    assert captured["classes"] == [2] and captured["save"] is False


def test_yolo_tracking_preserves_only_supplied_track_id(tmp_path):
    captured = {}

    class Model:
        def track(self, **kwargs):
            captured.update(kwargs)
            return [
                SimpleNamespace(
                    names={0: "tool"},
                    boxes=SimpleNamespace(
                        xyxy=Tensor([[10, 20, 30, 40]]),
                        conf=Tensor([0.8]),
                        cls=Tensor([0]),
                        id=Tensor([99]),
                    ),
                )
            ]

    adapter = UltralyticsYoloDetector(
        DetectorConfig(tracking=True, tracker_path=tmp_path / "tracker.yaml")
    )
    adapter._model = Model()
    assert adapter.detect(np.zeros((100, 100, 3), np.uint8))[0].track_id == 99
    assert captured["persist"] is True


def test_cpu_retry_only_for_accelerator_error():
    class Model:
        def __init__(self):
            self.devices = []

        def predict(self, **kwargs):
            self.devices.append(kwargs["device"])
            if kwargs["device"] != "cpu":
                raise RuntimeError("CUDA unavailable")
            return []

        def to(self, device):
            assert device == "cpu"

    adapter = UltralyticsYoloDetector(DetectorConfig())
    adapter._model, adapter._device = Model(), "0"
    assert adapter.detect(np.zeros((2, 2, 3), np.uint8)) == []
    assert adapter._model.devices == ["0", "cpu"]
    assert adapter.pop_warnings() == ["detector_cpu_fallback"]
    assert adapter.pop_warnings() == []
    adapter._device = "cpu"
    adapter._model.predict = lambda **kwargs: (_ for _ in ()).throw(
        RuntimeError("bad tensor")
    )
    with pytest.raises(RuntimeError, match="bad tensor"):
        adapter.detect(np.zeros((2, 2, 3), np.uint8))


def test_missing_local_models_fail_before_import(tmp_path):
    with pytest.raises(InitializationError, match="not found"):
        UltralyticsYoloDetector(
            DetectorConfig(model_path=tmp_path / "missing.pt")
        ).initialize()
    with pytest.raises(InitializationError, match="not found"):
        MediaPipeHandTracker(
            HandTrackerConfig(model_path=tmp_path / "missing.task")
        ).initialize()


@pytest.mark.parametrize(
    "device,available,fallback,expected",
    [
        ("auto", False, True, "cpu"),
        ("0", False, True, "cpu"),
        ("0", True, True, "0"),
        ("cpu", False, False, "cpu"),
    ],
)
def test_yolo_initialization_device_selection(
    monkeypatch, tmp_path, device, available, fallback, expected
):
    model_path = tmp_path / "local.pt"
    model_path.touch()
    classes_path = tmp_path / "classes.yaml"
    classes_path.write_text("classes: [{id: 0, name: tool}]")
    loaded = []
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            cuda=SimpleNamespace(is_available=lambda: available),
            backends=SimpleNamespace(),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "ultralytics",
        SimpleNamespace(
            YOLO=lambda path, task: (
                loaded.append(path) or SimpleNamespace(names={0: "tool"})
            )
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "ultralytics.utils",
        SimpleNamespace(checks=SimpleNamespace(AUTOINSTALL=False)),
    )
    adapter = UltralyticsYoloDetector(
        DetectorConfig(
            model_path=model_path,
            device=device,
            cpu_fallback=fallback,
            classes_path=classes_path,
        )
    )
    adapter.initialize()
    assert adapter._device == expected and loaded == [str(model_path)]
    assert bool(adapter.pop_warnings()) == (device == "0" and not available)


def test_offline_tracking_rejects_reid_model(tmp_path):
    model_path, tracker_path = tmp_path / "local.pt", tmp_path / "tracker.yaml"
    model_path.touch()
    tracker_path.write_text("tracker_type: botsort\nwith_reid: true\nmodel: auto")
    adapter = UltralyticsYoloDetector(
        DetectorConfig(model_path=model_path, tracking=True, tracker_path=tracker_path)
    )
    with pytest.raises(InitializationError, match="with_reid"):
        adapter.initialize()


def test_missing_tracker_dependency_fails_at_startup(monkeypatch, tmp_path):
    model = tmp_path / "local.pt"
    model.touch()
    classes = tmp_path / "classes.yaml"
    classes.write_text("classes: [{id: 0, name: tool}]")
    tracker = tmp_path / "tracker.yaml"
    tracker.write_text("tracker_type: bytetrack")
    monkeypatch.setattr("yolo.inference.detector.find_spec", lambda name: None)
    adapter = UltralyticsYoloDetector(
        DetectorConfig(
            model_path=model, classes_path=classes, tracking=True, tracker_path=tracker
        )
    )
    with pytest.raises(InitializationError, match="requires local lap"):
        adapter.initialize()


def test_whitelist_outside_project_classes_fails_at_startup(tmp_path):
    model = tmp_path / "local.pt"
    model.touch()
    classes = tmp_path / "classes.yaml"
    classes.write_text("classes: [{id: 0, name: tool}]")
    adapter = UltralyticsYoloDetector(
        DetectorConfig(model_path=model, classes_path=classes, class_whitelist=[9])
    )
    with pytest.raises(InitializationError, match="class_whitelist"):
        adapter.initialize()


def test_detection_filtering_invalid_clipped_whitelist_and_duplicate_ids(scene):
    d = scene[0][0]
    detections = [
        replace(d, bbox=BoundingBox(-10, -20, 30, 40)),
        replace(d, confidence=0.1),
        replace(d, confidence=float("nan")),
        replace(d, bbox=BoundingBox(10, 20, 0, 1)),
        replace(d, class_id=8),
        replace(d, bbox=BoundingBox(500, 500, 510, 510)),
        replace(d),
    ]
    output, invalid = filter_detections(
        detections, (240, 320), DetectorConfig(class_whitelist=[0])
    )
    assert len(output) == 1 and output[0].bbox == BoundingBox(0, 0, 30, 40)
    assert invalid == 4


def test_mediapipe_rgb_pixels_and_handedness_score_separate():
    observed = {}

    class Image:
        def __init__(self, **kwargs):
            observed.update(kwargs)

    class Landmarker:
        def detect_for_video(self, image, timestamp_ms):
            return SimpleNamespace(
                hand_landmarks=[[SimpleNamespace(x=0.5, y=0.25) for _ in range(21)]],
                handedness=[[SimpleNamespace(category_name="Left", score=0.95)]],
            )

        def close(self):
            observed["closed"] = True

    adapter = MediaPipeHandTracker(HandTrackerConfig())
    adapter._landmarker = Landmarker()
    adapter._mp = SimpleNamespace(Image=Image, ImageFormat=SimpleNamespace(SRGB="rgb"))
    image = np.zeros((100, 200, 3), np.uint8)
    image[..., 0] = 123
    hand = adapter.track(image, timestamp_s=0)[0]
    assert observed["data"][0, 0].tolist() == [0, 0, 123]
    assert hand.landmarks[0] == Point2D(100, 25)
    assert hand.palm_center == Point2D(100, 25)
    assert hand.handedness == "Left" and hand.handedness_confidence == 0.95
    assert hand.confidence is None and not hand.identity_persistent
    adapter.close()
    assert observed["closed"] and adapter._landmarker is None


def test_mediapipe_tasks_initialization_options(monkeypatch, tmp_path):
    captured = {}
    task = tmp_path / "hand.task"
    task.touch()

    class Options:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class Factory:
        @staticmethod
        def create_from_options(options):
            return SimpleNamespace(close=lambda: None)

    python = SimpleNamespace(BaseOptions=lambda **kwargs: kwargs)
    vision = SimpleNamespace(
        HandLandmarkerOptions=Options,
        HandLandmarker=Factory,
        RunningMode=SimpleNamespace(VIDEO="VIDEO"),
    )
    monkeypatch.setitem(sys.modules, "mediapipe", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "mediapipe.tasks", SimpleNamespace(python=python))
    monkeypatch.setitem(
        sys.modules, "mediapipe.tasks.python", SimpleNamespace(vision=vision)
    )
    adapter = MediaPipeHandTracker(HandTrackerConfig(model_path=task, max_hands=2))
    adapter.initialize()
    assert captured["running_mode"] == "VIDEO" and captured["num_hands"] == 2
    assert captured["base_options"]["model_asset_path"] == str(task)
    adapter.close()


def test_invalid_hand_score_and_persistent_duplicate_filtered(scene):
    hand = scene[1][0]
    result, invalid = filter_hands(
        [hand, replace(hand), replace(hand, confidence=float("nan"))]
    )
    assert len(result) == 1 and invalid == 2
