"""Active canonical output and downstream ownership checks."""

from optimization.pipeline import OptimizationPipeline
from yolo.pipeline import YoloPipeline

from shared.config import (
    DetectorConfig,
    HandTrackerConfig,
    PipelineConfig,
    ReferenceFrameConfig,
)
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.observations import ReferenceSource


def test_frame_metadata_copied_unchanged(prepared, backend):
    frame = prepared()
    output = YoloPipeline(DetectorConfig(), backend()).process(frame)
    source = frame.source
    assert (
        output.frame_id,
        output.timestamp_s,
        output.source_id,
        output.session_id,
    ) == (source.frame_id, source.timestamp_s, source.source_id, source.session_id)


def test_coordinates_in_original_frame(prepared, backend, detection):
    output = YoloPipeline(DetectorConfig(), backend([[detection]])).process(prepared())
    assert output.detections[0].bbox_xyxy == (40, 60, 160, 180)
    assert output.image_width == 800 and output.image_height == 400


def test_uses_shared_schema(prepared, backend):
    assert (
        type(YoloPipeline(DetectorConfig(), backend()).process(prepared()))
        is ObjectFrame
    )


def test_missing_anchor_reported(prepared, backend, detection):
    output = YoloPipeline(DetectorConfig(), backend([[detection]])).process(prepared())
    assert output.reference_anchors == []


def test_stability_flag_after_confirmation(prepared, backend, detection):
    stage = YoloPipeline(DetectorConfig(), backend([[detection]]))
    optimization = OptimizationPipeline(
        PipelineConfig(hand_tracker=HandTrackerConfig(enabled=False, backend="none"))
    )
    try:
        flags = []
        for i in range(3):
            frame = prepared(frame_id=i, timestamp=i / 30)
            output = stage.process(frame)
            assert not output.detections[0].is_stable  # Module 02 never votes.
            flags.append(
                optimization.process(frame, output).object_frame.detections[0].is_stable
            )
        assert flags == [False, False, True]
    finally:
        optimization.close()
        stage.close()


def test_module03_calibrates_with_empty_legacy_anchors(prepared, backend, detection):
    from dataclasses import replace

    frame = prepared()
    objects = YoloPipeline(
        DetectorConfig(), backend([[replace(detection, class_name="rack")]])
    ).process(frame)
    optimizer = OptimizationPipeline(
        PipelineConfig(
            hand_tracker=HandTrackerConfig(enabled=False, backend="none"),
            reference_frame=ReferenceFrameConfig(
                enabled=True, corners_normalized=[[0, 0], [1, 0], [1, 1], [0, 1]]
            ),
        )
    )
    try:
        consumed = optimizer.process(frame, objects)
        assert (
            objects.reference_anchors == consumed.object_frame.reference_anchors == []
        )
        assert consumed.spatial.reference_frame.valid
        assert consumed.spatial.reference_frame.source == ReferenceSource.STATIC_MANUAL
    finally:
        optimizer.close()
