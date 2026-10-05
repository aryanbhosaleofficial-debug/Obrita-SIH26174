"""Interactive Streamlit demo for Module 04 Boundary Detection."""

from __future__ import annotations

import importlib
from dataclasses import asdict, is_dataclass
from pathlib import Path
import sys

import cv2
import numpy as np
import streamlit as st

try:
    import mediapipe as mp
except ImportError:
    mp = None
try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


st.set_page_config(page_title="Boundary Detection", page_icon="◉", layout="wide")
st.title("Module 04 — Boundary Detection")
st.caption("Offline ROI, segmentation, contour, Freeman chain-code, interaction and quality demo")

# Streamlit may put the script directory, rather than the repository root, on
# sys.path. Add the root explicitly so the numbered package can be imported.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
BoundaryPipeline = importlib.import_module("04_boundary.boundary_pipeline").BoundaryPipeline


def demo_frame() -> np.ndarray:
    image = np.zeros((420, 640, 3), dtype=np.uint8)
    cv2.rectangle(image, (170, 105), (475, 315), (235, 235, 235), -1)
    cv2.circle(image, (330, 210), 35, (190, 190, 190), -1)
    return image


def packet_dict(packet):
    if is_dataclass(packet):
        return asdict(packet)
    return packet


@st.cache_resource
def hand_detector():
    if mp is None or not hasattr(mp, "solutions"):
        return None
    return mp.solutions.hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.55,
        min_tracking_confidence=0.55,
    )


def detect_hands(frame: np.ndarray):
    detector = hand_detector()
    if detector is None:
        return [], None
    height, width = frame.shape[:2]
    result = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    if not result.multi_hand_landmarks:
        return [], result
    hands = []
    for hand_index, landmarks in enumerate(result.multi_hand_landmarks):
        points = np.asarray([(landmark.x * width, landmark.y * height) for landmark in landmarks.landmark], dtype=float)
        x1, y1 = np.floor(points.min(axis=0)).astype(int)
        x2, y2 = np.ceil(points.max(axis=0)).astype(int)
        pad = max(12, int(0.25 * max(x2 - x1, y2 - y1)))
        hands.append({
            "hand_id": hand_index,
            "label": result.multi_handedness[hand_index].classification[0].label,
            "points": points,
            "bbox": (max(0, x1 - pad), max(0, y1 - pad), min(width, x2 + pad), min(height, y2 + pad)),
        })
    return hands, result


@st.cache_resource
def object_detector():
    if YOLO is None:
        return None
    return YOLO("yolo11n.pt")


def detect_people_and_objects(frame: np.ndarray):
    model = object_detector()
    if model is None:
        return [], None
    result = model.predict(frame, conf=0.35, imgsz=640, verbose=False, device="cpu")[0]
    names = result.names
    detections = []
    if result.boxes is None:
        return detections, result
    for box in result.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        class_id = int(box.cls[0].item())
        detections.append({"label": str(names[class_id]), "confidence": float(box.conf[0].item()), "bbox": (x1, y1, x2, y2)})
    return detections, result


def release_camera() -> None:
    capture = st.session_state.get("camera_capture")
    if capture is not None:
        capture.release()
    st.session_state.camera_capture = None
    st.session_state.camera_active = False


@st.fragment(run_every=0.5)
def live_camera_demo(method_name: str, min_area: int, roi_padding: int, target_roi: dict[str, float], automatic_hands: bool, automatic_objects: bool) -> None:
    """Refresh and analyze one camera frame every 0.5 seconds."""
    capture = st.session_state.get("camera_capture")
    if capture is None or not st.session_state.get("camera_active", False):
        st.info("Select Start camera to begin live boundary detection.")
        return
    ok, camera_frame = capture.read()
    if not ok:
        st.error("OpenCV could not read a frame from the camera.")
        return
    frame_id = int(st.session_state.get("camera_frame_id", 0)) + 1
    st.session_state.camera_frame_id = frame_id
    live_pipeline = st.session_state.get("live_pipeline")
    if live_pipeline is None or st.session_state.get("live_settings") != (method_name, min_area, roi_padding):
        live_pipeline = BoundaryPipeline(segmentation_method=method_name, min_area=min_area, roi_padding=roi_padding)
        st.session_state.live_pipeline = live_pipeline
        st.session_state.live_settings = (method_name, min_area, roi_padding)
    hands, hand_result = detect_hands(camera_frame) if automatic_hands else ([], None)
    detections, yolo_result = detect_people_and_objects(camera_frame) if automatic_objects else ([], None)
    active_roi = target_roi
    hand_data = None
    if hands:
        selected_hand = hands[0]
        x1, y1, x2, y2 = selected_hand["bbox"]
        active_roi = {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}
        hand_data = [{"hand_id": hand["hand_id"], "point": hand["points"]} for hand in hands]
    person = next((item for item in detections if item["label"] == "person"), None)
    objects = [item for item in detections if item["label"] != "person"]
    target = max(objects, key=lambda item: (item["bbox"][2] - item["bbox"][0]) * (item["bbox"][3] - item["bbox"][1])) if objects else person
    if target is not None:
        x1, y1, x2, y2 = target["bbox"]
        active_roi = {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}
    if automatic_objects and target is not None:
        live_packet = live_pipeline.process_detections(camera_frame, frame_id, frame_id / 30.0,
                                                        person_bbox=person["bbox"] if person else None,
                                                        object_bbox=active_roi, hand_data=hand_data)
    else:
        live_packet = live_pipeline.process(camera_frame, frame_id, frame_id / 30.0, roi=active_roi, hand_data=hand_data)
    contour = getattr(live_packet, "contour_px", [])
    display = camera_frame.copy()
    if contour:
        polygon = np.asarray(contour, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(display, [polygon], True, (0, 255, 0), 2)
        centroid = getattr(live_packet, "centroid_px", None)
        if centroid:
            cv2.circle(display, tuple(map(int, centroid)), 5, (0, 0, 255), -1)
    for hand in hands:
        x1, y1, x2, y2 = hand["bbox"]
        cv2.rectangle(display, (x1, y1), (x2, y2), (255, 160, 0), 2)
        cv2.putText(display, f"{hand['label']} hand", (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 160, 0), 2)
    for detection in detections:
        x1, y1, x2, y2 = detection["bbox"]
        color = (255, 0, 255) if detection["label"] == "person" else (0, 200, 255)
        cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
        cv2.putText(display, f"{detection['label']} {detection['confidence']:.2f}", (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    if automatic_hands and mp is None:
        cv2.putText(display, "Install mediapipe for automatic hand detection", (15, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    status = getattr(live_packet, "status", "UNKNOWN")
    confidence = float(getattr(live_packet, "confidence", 0.0))
    cv2.putText(display, f"{status}  confidence={confidence:.2f}", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)
    st.image(cv2.cvtColor(display, cv2.COLOR_BGR2RGB), channels="RGB", width="stretch")
    target_label = target["label"] if target else "none"
    st.write(f"Frame {frame_id}  |  humans/objects: {len(detections)}  |  hands: {len(hands)}  |  target: {target_label}  |  status: {status}  |  confidence: {confidence:.2f}  |  chain length: {len(getattr(live_packet, 'chain_code', []))}")


with st.sidebar:
    st.header("Controls")
    uploaded = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg", "bmp"])
    method = st.selectbox("Segmentation", ["threshold", "adaptive", "canny"])
    threshold = st.slider("Minimum contour area", 1, 5000, 100)
    padding = st.slider("ROI padding", 0, 100, 0)
    use_hand = st.checkbox("Show demo hand point", value=True)
    live_mode = st.checkbox("Use live camera")
    if live_mode:
        automatic_hands = st.checkbox("Automatic hand detection", value=True)
        automatic_objects = st.checkbox("YOLO human/object detection", value=True)
        st.caption("Set the target ROI around one hand/object. Upstream YOLO boxes can replace these controls.")
        roi_x = st.slider("Target ROI left", 0.0, 0.9, 0.15, 0.01)
        roi_y = st.slider("Target ROI top", 0.0, 0.9, 0.10, 0.01)
        roi_w = st.slider("Target ROI width", 0.1, 1.0, 0.35, 0.01)
        roi_h = st.slider("Target ROI height", 0.1, 1.0, 0.65, 0.01)
        target_roi = {"x": roi_x, "y": roi_y, "width": min(roi_w, 1.0 - roi_x), "height": min(roi_h, 1.0 - roi_y)}

if live_mode:
    if "camera_capture" not in st.session_state:
        st.session_state.camera_capture = None
        st.session_state.camera_active = False
        st.session_state.camera_frame_id = 0
    start_col, stop_col = st.columns(2)
    with start_col:
        if st.button("Start camera", type="primary", width="stretch"):
            release_camera()
            capture = cv2.VideoCapture(0)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if capture.isOpened():
                st.session_state.camera_capture = capture
                st.session_state.camera_active = True
                st.session_state.camera_frame_id = 0
            else:
                capture.release()
                st.error("Could not open camera 0. Check that it is connected and not in use.")
    with stop_col:
        if st.button("Stop camera", width="stretch"):
            release_camera()
    st.caption("The camera is processed by the machine running Streamlit. The live view refreshes twice per second.")
    live_camera_demo(method, threshold, padding, target_roi, automatic_hands, automatic_objects)
    st.stop()

if uploaded is not None:
    raw = np.frombuffer(uploaded.getvalue(), dtype=np.uint8)
    frame = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    source_label = uploaded.name
else:
    frame = demo_frame()
    source_label = "built-in synthetic demo"

if frame is None or frame.size == 0:
    st.error("The selected image could not be decoded.")
    st.stop()

hand_data = [{"hand_id": 0, "point": (330, 210)}] if use_hand and uploaded is None else None
pipeline = BoundaryPipeline(segmentation_method=method, min_area=threshold, roi_padding=padding)
packet = pipeline.process(frame, frame_id=1, timestamp=0.0, hand_data=hand_data)
data = packet_dict(packet)

left, right = st.columns(2)
with left:
    st.subheader("Input")
    st.write(source_label)
    st.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB", width="stretch")
with right:
    st.subheader("Boundary result")
    quality = data.get("quality", {}) if isinstance(data, dict) else {}
    status = quality.get("status", getattr(packet, "status", "UNKNOWN"))
    confidence = quality.get("confidence", getattr(packet, "confidence", 0.0))
    st.metric("Status", str(status))
    st.metric("Confidence", f"{float(confidence):.2f}")
    if isinstance(data, dict):
        st.json(data)
    else:
        st.json(packet_dict(packet))

st.info("Coordinates and contour points are reported in original-frame pixels.")
