"""Recovery and architecture invariants at public module boundaries."""

import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from boundary.input.input_validator import BoundaryInputError, validate_boundary_input
from optimization.hands.hand_tracker import MediaPipeHandTracker
from yolo.inference.class_map import load_class_map

from integration.chain import PerceptionChain
from integration.mocks import MockDetector, MockHandTracker
from perception.core import FrameProcessor
from shared.config import ConfigurationError, HandTrackerConfig, PipelineConfig
from shared.diagnostics import WarningCode
from shared.enums.module_status import ModuleStatus
from shared.schemas.observations import BoundingBox, Point2D, PoseObservation


@pytest.mark.parametrize("stage", ["detector", "hands", "both"])
def test_temporary_backend_failure_recovers_without_fabrication(
    config, scene, packet, stage
):
    class Detector(MockDetector):
        calls = 0

        def detect(self, image):
            self.calls += 1
            if stage in ("detector", "both") and self.calls == 5:
                raise RuntimeError("temporary tracker/inference failure")
            return super().detect(image)

    class Hands(MockHandTracker):
        calls = 0

        def track(self, image, timestamp_s=None):
            self.calls += 1
            if stage in ("hands", "both") and self.calls == 5:
                raise RuntimeError("temporary hand tracking loss")
            return super().track(image, timestamp_s)

    with PerceptionChain(
        config, detector=Detector([scene[0]]), hand_tracker=Hands([scene[1]])
    ) as chain:
        outputs = [chain.process(packet(i)).optimization for i in range(6)]
    assert outputs[4].status == (
        ModuleStatus.ERROR if stage == "both" else ModuleStatus.DEGRADED
    )
    assert (
        not outputs[4].reliable_for_temporal_reasoning and not outputs[4].interactions
    )
    assert outputs[5].status == ModuleStatus.OK and outputs[5].interactions
    assert (
        outputs[5].observations.detections[0].continuity_key
        == outputs[3].observations.detections[0].continuity_key
    )


def test_many_objects_and_disappearance_emit_only_current_evidence(
    config, scene, packet
):
    detections = [
        replace(scene[0][0], track_id=i, bbox=BoundingBox(i * 4, 80, i * 4 + 20, 160))
        for i in range(50)
    ]
    with PerceptionChain(
        config,
        detector=MockDetector([detections] * 4 + [[]] + [detections]),
        hand_tracker=MockHandTracker([scene[1]]),
    ) as chain:
        outputs = [chain.process(packet(i)).optimization for i in range(6)]
    assert len(outputs[3].observations.associations) == 50
    assert not outputs[4].object_frame.detections and not outputs[4].interactions
    assert len(outputs[5].object_frame.detections) == 50
    assert (
        outputs[5].object_frame.detections[0].continuity_key
        == outputs[3].object_frame.detections[0].continuity_key
    )


def test_stage_rejects_mismatched_objects_before_hands(config, scene, packet):
    with PerceptionChain(
        config,
        detector=MockDetector([scene[0]]),
        hand_tracker=MockHandTracker([scene[1]]),
    ) as chain:
        result = chain.process(packet())
        with pytest.raises(ValueError, match="metadata"):
            chain.optimization.process(
                result.prepared, replace(result.objects, session_id="other")
            )
        result.optimization.object_frame.source_id = "other"
        with pytest.raises(BoundaryInputError, match="metadata"):
            validate_boundary_input(result.optimization, result.prepared.source)


def test_pose_passes_through_real_spatial_contract(config, scene, packet):
    class Pose:
        def initialize(self):
            pass

        def close(self):
            pass

        def track(self, image):
            return [PoseObservation([Point2D(160, 120)], None)]

    with PerceptionChain(
        config,
        detector=MockDetector([scene[0]]),
        hand_tracker=MockHandTracker([scene[1]]),
        pose_tracker=Pose(),
    ) as chain:
        result = chain.process(packet()).optimization
    assert result.spatial.pose_landmarks[0].x_px == 160
    assert result.spatial.rack_relative_pose == [(0.5, 0.5, None)]
    assert result.observations.poses[0].confidence is None


def test_upstream_degradation_remains_visible(packet):
    prepared = FrameProcessor().process(replace(packet(), status=ModuleStatus.DEGRADED))
    assert prepared.status == ModuleStatus.DEGRADED
    assert prepared.warnings[0].code == WarningCode.UPSTREAM_FAILURE


def test_explicit_drop_count_ages_history_without_double_count(config, scene, packet):
    with PerceptionChain(
        config,
        detector=MockDetector([scene[0]]),
        hand_tracker=MockHandTracker([scene[1]]),
    ) as chain:
        for i in range(4):
            chain.process(packet(i))
        output = chain.process(replace(packet(6), dropped_frames_before=2))
        assert output.prepared.missing_frames == 2
        assert output.optimization.object_frame.detections[0].is_stable
        output = chain.process(replace(packet(7), dropped_frames_before=3))
        assert not output.optimization.object_frame.detections[0].is_stable


def test_malformed_frame_cannot_hide_long_time_gap(config, scene, packet):
    with PerceptionChain(
        config,
        detector=MockDetector([scene[0]]),
        hand_tracker=MockHandTracker([scene[1]]),
    ) as chain:
        for i in range(4):
            chain.process(packet(i))
        chain.process(replace(packet(4, timestamp=10), image=None))
        result = chain.process(packet(5, timestamp=10.1))
        assert result.prepared.reset_required
        assert not result.optimization.object_frame.detections[0].is_stable
        assert not result.optimization.interactions


@pytest.mark.parametrize("gap", [0, -1, float("nan"), True])
def test_invalid_time_gap_rejected(gap):
    with pytest.raises(ConfigurationError):
        FrameProcessor(max_time_gap_s=gap)


@pytest.mark.parametrize(
    "content",
    [
        "classes: [{id: null, name: vial}]",
        "classes: [{id: 0, name: vial}, {id: 0, name: tool}]",
        "classes: []",
    ],
)
def test_invalid_project_classes_fail_clearly(tmp_path, content):
    path = tmp_path / "classes.yaml"
    path.write_text(content)
    with pytest.raises(ValueError):
        load_class_map(path)


def test_core_imports_do_not_load_inference_or_optimization():
    code = "import sys; from perception import FrameProcessor; from perception.contracts import PreparedFrame; assert not any(k.split('.')[0] in {'ultralytics','mediapipe','torch','optimization','yolo','integration'} for k in sys.modules)"
    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        cwd=Path(__file__).resolve().parents[2],
    )


def test_video_timestamps_mirroring_and_optional_handedness():
    timestamps = []

    class Landmarker:
        def detect_for_video(self, image, milliseconds):
            timestamps.append(milliseconds)
            return SimpleNamespace(
                hand_landmarks=[[SimpleNamespace(x=0.5, y=0.5)] * 21], handedness=[]
            )

        def close(self):
            pass

    adapter = MediaPipeHandTracker(HandTrackerConfig(mirrored=True))
    adapter._landmarker = Landmarker()
    adapter._mp = SimpleNamespace(
        Image=lambda **kw: kw, ImageFormat=SimpleNamespace(SRGB="rgb")
    )
    image = np.zeros((100, 100, 3), np.uint8)
    hands = [adapter.track(image, timestamp_s=t)[0] for t in [100.0, 100.033, 100.1]]
    assert timestamps == [0, 33, 100]
    assert all(
        h.mirrored_input and h.handedness is None and h.confidence is None
        for h in hands
    )
    with pytest.raises(ValueError, match="millisecond"):
        adapter.track(image, timestamp_s=100.1001)
    adapter.close()


def test_profile_rejects_bad_owner_mapping(tmp_path):
    (tmp_path / "core.yaml").write_text("perception: {}")
    (tmp_path / "yolo.yaml").write_text("detector: {backend: mock}")
    (tmp_path / "opt.yaml").write_text("interaction: []")
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        "pipeline: {core: core.yaml, yolo: yolo.yaml, optimization: opt.yaml}"
    )
    with pytest.raises(ConfigurationError, match="mapping"):
        PipelineConfig.from_yaml(profile)
