"""Real numbered-module orchestration, substituting only model inference."""
from dataclasses import replace
import json

import pytest

from integration.chain import PerceptionChain
from integration.milestone import MilestonePipeline
from integration.synthetic import configure, scene
from pose_tracking.integration import TrackingIntegration
from pose_tracking.pipeline_runner import main
from pose_tracking.sync import FrameSyncError
from shared.config import PipelineConfig
from shared.schemas.observations import CoordinateFrame


def test_modules_01_through_06_preserve_contracts_and_rack_coordinates(make_tracker, raw):
    frames, detector, hands = scene()
    pipeline = MilestonePipeline(PerceptionChain(configure(PipelineConfig()),
                                                 detector=detector, hand_tracker=hands))
    tracker, backend = make_tracker([raw.result(raw.body(), (raw.hand("Left"), raw.hand("Right")))])
    adapter = TrackingIntegration(tracker)
    with pipeline, tracker:
        for frame in frames:
            result = pipeline.process(frame)
            output = adapter.process(result)
            assert output.frame_id == result.activity.frame_id == result.boundary.frame_id == frame.frame_id
            assert output.timestamp_s == result.activity.timestamp_s == frame.timestamp_s
            assert output.feature_coordinate_frame == CoordinateFrame.RACK_RELATIVE
            assert output.reference_id == "synthetic-rack"
            assert output.body_landmarks[0].rack_xy is not None
            assert output.left_hand_detected and output.right_hand_detected
    assert backend.initializations == 1 and backend.closes == 1


@pytest.mark.parametrize("mismatch", ["frame_id", "timestamp_s", "source_id", "session_id"])
def test_module05_pairing_rejects_mismatch_before_inference(make_tracker, mismatch):
    frames, detector, hands = scene(1)
    with MilestonePipeline(PerceptionChain(configure(PipelineConfig()), detector=detector,
                                           hand_tracker=hands)) as pipeline:
        result = pipeline.process(frames[0])
    if mismatch in ("frame_id", "timestamp_s"):
        result.activity = replace(result.activity, **{mismatch: 99})
    else:
        result.activity.metadata[mismatch] = "other"
    tracker, backend = make_tracker()
    with pytest.raises(FrameSyncError):
        TrackingIntegration(tracker).process(result)
    assert backend.calls == 0


def test_integrated_runner_uses_real_interfaces_without_display_or_models(tmp_path):
    path = tmp_path / "tracking.jsonl"
    assert main(["--synthetic", "--output", str(path)]) == 0
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 36 and all(r["synthetic"] for r in rows)
    assert rows[0]["tracking"]["body_detected"]
    assert len(rows[0]["tracking"]["hands"]) == 2
    assert rows[-1]["tracking"]["hands"] == []
    assert rows[-1]["tracking"]["body_landmarks"] == []
    assert rows[-1]["activity"]["activity_label"] == "unknown"


def test_integrated_runner_rejects_invalid_frame_limit():
    assert main(["--synthetic", "--max-frames", "0"]) == 2


def test_integrated_runner_reports_upstream_inference_failure(tmp_path, monkeypatch):
    from integration import cli
    from integration.mocks import MockDetector

    class FailedDetector(MockDetector):
        def detect(self, image):
            raise RuntimeError("synthetic upstream inference failed")

    def failing_scene(count, session):
        frames, _, hands = scene(count, session)
        return frames, FailedDetector(), hands

    monkeypatch.setattr(cli, "scene", failing_scene)
    path = tmp_path / "failed.jsonl"
    assert main(["--synthetic", "--max-frames", "1", "--output", str(path)]) == 1
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["activity"]["status"] == "invalid_input"
    assert row["tracking"]["status"] == "ok"  # independent tracker can still work
