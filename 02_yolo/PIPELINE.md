# Module 02 implemented pipeline

The current [integration decision](../perception/INTEGRATION.md) supersedes the
older letterbox/stability/anchor plan. There is one active synchronous stage:

```text
Module 01 FrameProcessor -> shared.PreparedFrame
  -> yolo.pipeline.YoloPipeline.process
     -> input_validation.input_error (image + restoration prerequisites)
     -> inference.detector.UltralyticsYoloDetector [loaded once]
        -> local predict / optional track
           [model adaptation, inference, NMS, internal restoration]
        -> inference.postprocess.parse_results
           [shared Detection in prepared-image pixels]
     -> inference.detector.filter_detections
        [confidence, classes, positive boxes, diagnostic clipping]
     -> PreparedFrame.source_detection
        [existing x/y scale restoration, exactly once]
     -> clamp_source_box [source boundary roundoff only; no second scaling]
     -> shared.ObjectFrame [original-source pixels + unchanged metadata]
  -> Module 03 OptimizationPipeline.process(prepared, objects)
```

ObjectDetector is the backend protocol, not a second frame pipeline. Tests inject
this protocol or mock the framework. The explicitly configured none backend
represents a disabled detector; real inference uses Ultralytics.

Module 01 owns generic preparation, validation, ordering and source transforms.
Ultralytics owns its tensor/letterbox/NMS adaptation. Module 02 owns parsing,
filtering and project contract conversion. Module 03 owns hands, spatial continuity,
temporal confirmation, calibration, motion and interactions. Boundary/HAR/FSM/GUI
algorithms stay with their owners.

Inactive preprocessing, tracking, stability, reference and output-builder scaffold
leaves are explicitly marked DEPRECATED / UNUSED and are not called by this stage. Do not
implement another pipeline from their obsolete TODOs. See [README](README.md)
for coordinates, lifecycle, errors, configuration and limitations.

Tracked accelerator failures return ERROR and pause inference until a coordinated
reset; predictor/tracker state is never transparently rebuilt on CPU. Untracked
inference may still retry CPU. ReferenceAnchor/reference_anchors are reserved
legacy schema leaves; Module 03's calibration uses ReferenceFrameInfo instead.
