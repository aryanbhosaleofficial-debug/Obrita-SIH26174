# ORBITA Output Data Schemas

This document defines the schema for frame-level spatial/kinematic feature logs and sequence-level activity prediction logs.

---

## 1. Frame Features Schema (`*.features.jsonl`)

Each line is a JSON object corresponding to one tracked person at one time step.

`feature_schema_version` is currently `2.0.0`. JSONL is the structured source
of truth; flattened CSV is for analysis/export and is not the conceptual model
input format.

```json
{
  "timestamp_ms": 1727834500123,
  "frame_id": 42,
  "frame_index": 42,
  "person_id": "HUMAN_1",
  "human_label": "HUMAN_1",
  "coordinate_space": "MEDIAPIPE_WORLD",
  "measurement_status": "VALID_3D",
  "orientation_status": "VALID_3D_ORIENTATION",
  "confidence_score": 0.9421,
  "feature_dim": 74,
  "features": [
    0.12, 0.45, -0.05,
    "..."
  ],
  "missingness_mask": [
    1, 1, 1,
    "..."
  ]
}
```

### Fields:
* `timestamp_ms` (integer): Monotonic timestamp of the video frame in milliseconds.
* `feature_schema_version` (string): Versioned feature-record schema identifier.
* `frame_id` (integer): Preserved frame identifier; currently equal to `frame_index`.
* `frame_index` (integer): Sequential frame counter.
* `person_id` (string): Stable tracking slot ID (`HUMAN_1` or `HUMAN_2`).
* `confidence_score` (float in `[0.0, 1.0]`): Average visibility/presence across tracked key joints.
* `feature_dim` (integer): Total length of the feature vector (nominally 74).
* `features` (list of floats): Normalized 1D kinematic vector:
  * Index `0..38` (39 dims): 13 Key 3D anatomical joint positions ($x, y, z$).
  * Index `39..56` (18 dims): 6 Key 3D joint velocities ($v_x, v_y, v_z$).
  * Index `57..62` (6 dims): 6 Joint angles normalized to `[0, 1]` ($0^\circ$ to $180^\circ$).
  * Index `63..67` (5 dims): 5 Inter-joint Euclidean distances in meters.
  * Index `68..70` (3 dims): Torso 3D orientation (Roll, Pitch, Yaw) normalized to `[-1, 1]`.
  * Index `71..73` (3 dims): Torso centroid velocity ($v_x, v_y, v_z$).
* `missingness_mask` (list of integers, `0` or `1`): Element-wise indicator where `1` = valid sensor/model measurement, `0` = missing, occluded, or low-confidence joint.
* `coordinate_space` and `measurement_status`: Coordinate-frame and measurement provenance metadata.
* `orientation_status`: Explicit valid/unsupported status for 3D Roll/Pitch/Yaw.
* `displacements`, `velocities`, `accelerations`, `kinematic_features`: Structured derived movement data; acceleration is omitted when its temporal inputs are invalid.

---

## 2. Activity Prediction Schema (`*.predictions.jsonl` & `*.predictions.csv`)

### JSONL Schema:
```json
{
  "timestamp_ms": 1727834501000,
  "person_id": "HUMAN_1",
  "predicted_class_id": 1,
  "predicted_class_name": "RACK_INSPECTION",
  "confidence": 0.8742,
  "probabilities": {
    "IDLE_MONITORING": 0.0412,
    "RACK_INSPECTION": 0.8742,
    "SWITCH_ACTUATION": 0.0511,
    "CABLE_ROUTING": 0.0123,
    "EQUIPMENT_MAINTENANCE": 0.0150,
    "EMERGENCY_SHUTDOWN": 0.0062
  },
  "is_reliable": true,
  "notes": "Nominal inference"
}
```

### CSV Schema:
| Column | Type | Description |
| :--- | :--- | :--- |
| `timestamp_ms` | Integer | Epoch timestamp in milliseconds |
| `person_id` | String | `HUMAN_1` or `HUMAN_2` |
| `predicted_class_id` | Integer | Integer class ID (0-5) |
| `predicted_class_name`| String | Human-readable activity name |
| `confidence` | Float | Softmax probability of top class |
| `is_reliable` | Boolean | True if tracking history ≥ 3 frames and confidence ≥ 0.35 |
| `notes` | String | Operational or diagnostic flags |
