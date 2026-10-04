# Module 03 Definition of Done

The module consumes frame metadata and Module 02 detections; it does not capture
camera frames or run YOLO. `OptimizationPipeline` handles missing people, optional
pose/hand results, timestamp-based hand velocity, object proximity/contact proxy,
bounded temporal history, gesture evidence and a JSON-serializable output dict.

The optional `PoseDetector` adapter uses the locally installed MediaPipe Solutions
API when available and returns an empty result when the dependency is unavailable.
No model is downloaded at runtime. Rack-relative geometry and shared dataclass
packet builders remain available for integration with Module 05.

Known limitations: monocular depth is relative, the baseline recognizer is
rule-based, and accurate physical contact requires calibrated/depth sensing.
