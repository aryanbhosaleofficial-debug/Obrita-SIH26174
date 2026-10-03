# ORBITA: AI Human Activity Recognition for On-board BAS Experiments

> **SIH26174 Prototype**  
> Integrated with Google MediaPipe Pose Landmarker for 3D spatial representation, multi-person tracking, kinematic feature extraction, and Bottleneck+ReLU+Bottleneck temporal activity recognition.

---

## 1. Project Overview & Context

In microgravity spaceflight environments (such as the Bio-Astro Science [BAS] racks on space stations), crew members perform complex maintenance, experiment operations, and payload inspections. Automated Human Activity Recognition (HAR) provides real-time operational logging, safety monitoring, and procedure verification.

This repository adapts the Google MediaPipe source tree (`orbita-mediapipe`) without altering upstream MediaPipe functionality. All custom ORBITA capabilities are modularly organized inside `orbita_human_activity/`.

---

## 2. Architecture & The Four Assigned Tasks

```
Camera / Video Input
        ↓
MediaPipe Pose Landmarker (configured for num_poses=2)
        ↓
Multi-Person Association & Tracking (HUMAN_1 & HUMAN_2)
        ↓
3D Spatial Frame Transformation (Rack-Relative Coordinates)
        ↓
Kinematic & Temporal Feature Extraction (Angles, Distances, Frame-Valid Roll/Pitch/Yaw)
        ↓
Sliding Window Sequence Buffer (T=30 Frames)
        ↓
Bottleneck → ReLU → Bottleneck Neural Network
        ↓
Adam Optimizer (Training) / Softmax Probabilities (Inference)
        ↓
Documented Logging (JSONL / CSV) & Optional 3D Visualization
```

### Task 1 — 3D Spatial Representation & Rack Reference Frame
* **Coordinate Spaces**: Explicitly distinguishes between:
  1. `NORMALIZED_IMAGE`: Sensor $[0.0, 1.0]$ space.
  2. `MEDIAPIPE_WORLD`: Metric-scale ($\sim$meters), hip-centered 3D landmark coordinates estimated by the model.
  3. `RACK_RELATIVE_CALIBRATED`: Metric physical coordinates in the certified Equipment Rack reference frame via rigid body transformation $P_{\text{rack}} = R \cdot (P_{\text{cam}} - T)$.
* **Microgravity Handling**: Does **not** assume gravity defines "up". In microgravity, orientation is referenced to rigid spacecraft structures (the rack panel).
* **Calibration Protocol**: Documented Kabsch-Umeyama SVD solver with a strict acceptance threshold ($\text{RMS} < 15.0\text{ mm}$). Metric rack accuracy cannot be claimed without optical fiducial calibration.

### Task 2 — Gesture → 3D Movement Feature Extraction
* Converts 33 pose landmarks into a 74-dimensional numerical feature vector:
  * 13 Key 3D anatomical positions ($39$ dims).
  * 6 Upper/lower body 3D velocities ($18$ dims).
  * 6 Joint angles ($6$ dims: elbow flexions, shoulder elevations, knee angles).
  * 5 Inter-joint distances ($5$ dims: bimanual wrist distance, shoulder/hip spans).
  * 3 Torso orientation angles ($3$ dims: Roll, Pitch, Yaw).
  * 3 Torso centroid velocities ($3$ dims).
* **Orientation Constraints**: Euler angles are calculated **only** from valid 3D coordinates using Gram-Schmidt orthonormalization of the anatomical torso frame. They are **never** inferred from raw 2D pixel coordinates.
* **Missingness Mask**: Low-confidence or occluded joints are explicitly tracked in an element-wise boolean mask ($1.0 = \text{valid}$, $0.0 = \text{missing}$) rather than silently fabricated.

### Task 3 — Multi-Person (Human 1 & Human 2) Tracking
* Configures detection for up to two subjects.
* **Spatial-Temporal Association**: Minimum-weight matching combining 3D Torso/Hip Euclidean distance and 2D bounding-box IoU.
* **Track State Machine**: `TENTATIVE` $\to$ `CONFIRMED` $\to$ `COASTING` $\to$ `DELETED`.
* **Occlusion & Co-presence**: Handles crossing paths and temporary line-of-sight occlusion by coasting velocity for up to `max_lost_frames` (15 frames).
* **Documented Limitations**: Short-term spatial-temporal tracker only; does not perform biometric face or clothing re-identification over extended room exits.

### Task 4 — Bottleneck + ReLU + Bottleneck Model & Adam Training
* **Model Architecture**:
  * Input: Projected temporal sequence $X \in \mathbb{R}^{B \times T \times 74}$.
  * **First Bottleneck**: Linear layer compressing $74 \to 32$ dimensions.
  * **Activation**: Explicit $\text{ReLU}(x) = \max(0, x)$.
  * **Regularization**: Dropout ($p=0.25$).
  * **Second Bottleneck**: Linear layer compressing $32 \to 16$ dimensions.
  * **Classification Head**: Linear layer projecting $16 \to 6$ BAS activity classes.
* **Architecture vs Optimizer Clarification**: The neural network defines the parameter hypothesis space; the **Adam optimizer** is the decoupled external algorithm providing adaptive momentum updates ($m_t, v_t$).
* **Data Leakage Prevention**: Training and validation sets are strictly split by continuous `recording_session_id`, preventing temporal window overlap leakage.
* **Synthetic Testing Notice**: Includes a synthetic test mode clearly labeled as software execution validation, not real performance evidence.

---

## 3. Directory Layout

```
orbita_mediapipe/orbita_human_activity/
├── configs/
│   ├── coordinates_config.yaml       # Rack reference frame, rotation R, translation T
│   ├── tracking_config.yaml          # Hungarian cost weights, gating, max lost frames
│   ├── model_config.yaml             # Bottleneck dimensions, dropout, sequence length
│   └── activity_classes.yaml         # 6 BAS activity classes
├── schemas/
│   ├── spatial_types.py              # Landmark3D, PersonPose3D, CoordinateSpace
│   ├── tracking_types.py             # TrackedPerson, TrackState, TrackingResult
│   ├── feature_types.py              # KinematicFeatures, OrientationFeatures, FrameFeatureVector
│   └── dataset_types.py              # TemporalSequenceSample, PredictionResult
├── spatial/
│   ├── coordinate_systems.py         # Frame manager, point and landmark converters
│   ├── calibration.py                # Kabsch-Umeyama SVD calibration solver
│   └── transforms.py                 # MediaPipe adapter to PersonPose3D
├── features/
│   ├── kinematics.py                 # 3D angles, distances, unit vectors
│   ├── orientation.py                # Frame-valid roll, pitch, yaw
│   └── temporal_features.py          # 74-D vector builder, missingness masks, sequence buffer
├── tracking/
│   ├── association.py                # 3D/2D cost matrix & bipartite matching
│   ├── identity_policy.py            # Slot manager (HUMAN_1 / HUMAN_2) & lifecycle
│   └── tracker.py                    # MultiPersonTracker
├── models/
│   └── bottleneck_network.py         # OrbitaBottleneckHAR (Bottleneck -> ReLU -> Bottleneck)
├── training/
│   ├── dataset.py                    # Session-based split dataset
│   ├── trainer.py                    # Adam training engine
│   └── smoke_train.py                # Synthetic tensor shape & training smoke test
├── pipeline/
│   ├── pose_adapter.py               # MediaPipe runner with offline synthetic fallback
│   ├── serialization.py              # JSONL / CSV data logger
│   ├── visualizer.py                 # 3D skeleton & trajectory visualizer
│   └── orbita_pipeline.py            # End-to-end integrated master pipeline
├── tests/
│   ├── test_spatial_transforms.py    # Unit tests for transforms & calibration
│   ├── test_tracking_association.py  # Unit tests for 2-person tracking & coasting
│   ├── test_feature_extraction.py    # Unit tests for kinematics & orientation
│   ├── test_model_architecture.py    # Unit tests for Bottleneck forward & gradients
│   └── test_pipeline_smoke.py        # Integration smoke test for end-to-end execution
├── sample_output/
│   ├── OUTPUT_SCHEMA.md              # Documented JSONL and CSV schema
│   ├── sample_features.jsonl         # Sample frame features
│   ├── sample_predictions.jsonl      # Sample activity predictions
│   └── sample_predictions.csv        # Sample CSV output
├── requirements.txt                  # Dependency specifications
└── README.md                         # Architecture and operations guide
```

---

## 4. Setup & Execution Commands

### Prerequisites
* Python 3.10, 3.11, or 3.12.
* Install dependencies:
```bash
pip install -r orbita_human_activity/requirements.txt
```

### MediaPipe Pose Landmarker Model Setup (Optional for Live Video)
For live camera/video execution, download the official MediaPipe pose landmarker bundle and place it in `models/`:
```bash
mkdir -p models
curl -L -o models/pose_landmarker.task https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task
```
*(If `models/pose_landmarker.task` is absent, ORBITA automatically activates its built-in offline test generator so all pipelines and tests can be fully evaluated offline).*

### Running Unit Tests
To execute all 16 test cases across spatial transforms, tracking association, feature extraction, model architecture, and pipeline smoke testing:
```bash
python -m unittest discover -s orbita_human_activity/tests -p "test_*.py" -v
```

### Running Model Training Smoke Test (Adam Optimizer)
To verify forward/backward passes, gradient flow, Adam parameter updates, and checkpoint serialization:
```bash
python -m orbita_human_activity.training.smoke_train
```

### Running the End-to-End Integrated Pipeline
```python
from orbita_human_activity.pipeline.orbita_pipeline import OrbitaHARPipeline

pipeline = OrbitaHARPipeline(sequence_length=30)
result = pipeline.run_smoke_pipeline(num_frames=60)
print("Pipeline result:", result["status"])
```

---

## 5. Licensing & Upstream Compliance
* Upstream Google MediaPipe code is licensed under the **Apache License 2.0**.
* ORBITA custom modules adhere to standard modular architecture principles and do not overwrite or modify upstream MediaPipe C++ or Python source files.
