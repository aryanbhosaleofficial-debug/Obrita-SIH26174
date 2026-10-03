import cv2
import pyttsx3
import time
import threading
from collections import deque
from ultralytics import YOLO


# ---------------------------------------------------------
# 1. THREADED VOICE ENGINE (Non-Blocking)
# ---------------------------------------------------------
def speak_async(text):
    def speech_worker(message):
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 150)
            print(f"\n[ASSISTANT VOICE]: {message}\n")
            engine.say(message)
            engine.runAndWait()
        except Exception as e:
            print(f"Speech error: {e}")

    threading.Thread(target=speech_worker, args=(text,), daemon=True).start()


# ---------------------------------------------------------
# 2. SEQUENCE TRACKER
# ---------------------------------------------------------
class ExperimentSequence:
    def __init__(self):
        self.steps = [
            "PICK_RED",
            "MANIPULATE_RED",
            "PLACE_RED",
            "PICK_YELLOW",
            "MANIPULATE_YELLOW",
            "PLACE_YELLOW",
        ]
        self.current_step_idx = 0
        self.last_action_time = time.time()
        self.step_cooldown = 3.0
        self.warning_cooldown = 4.0

    def get_current_step(self):
        if self.current_step_idx < len(self.steps):
            return self.steps[self.current_step_idx]
        return "COMPLETED"

    def advance_step(self):
        current_time = time.time()
        if current_time - self.last_action_time < self.step_cooldown:
            return

        self.current_step_idx += 1
        self.last_action_time = current_time

        next_step = self.get_current_step()
        if next_step != "COMPLETED":
            readable_step = next_step.replace("_", " ").lower()
            speak_async(f"Step complete. Next step: {readable_step}.")
        else:
            speak_async("Experiment complete. Great job astronaut!")

    def trigger_warning(self, wrong_action):
        current_time = time.time()
        if current_time - self.last_action_time > self.warning_cooldown:
            expected = self.get_current_step().replace("_", " ").lower()
            speak_async(f"Warning! Please perform {expected} first.")
            self.last_action_time = current_time


# ---------------------------------------------------------
# 3. ROBUST TRACKER WITH SMOOTHING & DEBOUNCING
# ---------------------------------------------------------
class ObjectTracker:
    def __init__(self, buffer_size=5):
        # Rolling buffer for Y-centers and Aspect Ratios to reduce noise
        self.cy_buffer = deque(maxlen=buffer_size)
        self.ar_buffer = deque(maxlen=buffer_size)
        self.baseline_cy = None
        self.baseline_ar = None
        self.action_counter = {}

    def update(self, cy, ar):
        self.cy_buffer.append(cy)
        self.ar_buffer.append(ar)

        smooth_cy = sum(self.cy_buffer) / len(self.cy_buffer)
        smooth_ar = sum(self.ar_buffer) / len(self.ar_buffer)

        if self.baseline_cy is None:
            self.baseline_cy = smooth_cy
            self.baseline_ar = smooth_ar

        return smooth_cy, smooth_ar

    def check_debounced_action(self, action_key, condition, required_frames=3):
        """Requires condition to persist for 'required_frames' before triggering."""
        if condition:
            self.action_counter[action_key] = self.action_counter.get(action_key, 0) + 1
        else:
            self.action_counter[action_key] = 0

        return self.action_counter[action_key] >= required_frames


# ---------------------------------------------------------
# 4. MAIN DETECTOR LOOP
# ---------------------------------------------------------
def main():
    model = YOLO("best.pt")
    sequence = ExperimentSequence()
    trackers = {
        "red_box": ObjectTracker(),
        "yellow_box": ObjectTracker(),
    }

    cap = cv2.VideoCapture(0)

    first_step = sequence.get_current_step().replace("_", " ").lower()
    speak_async(f"System active. First step: {first_step}.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Run model with slightly lower confidence to prevent frame dropouts
        results = model(frame, conf=0.45, verbose=False)[0]
        current_detections = {}

        for box in results.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id].lower().strip()
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            w, h = (x2 - x1), (y2 - y1)
            aspect_ratio = w / float(h) if h > 0 else 1.0

            current_detections[cls_name] = {
                "box": [x1, y1, x2, y2],
                "center": (cx, cy),
                "ar": aspect_ratio,
            }

            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(
                frame,
                f"{cls_name.upper()}",
                (int(x1), int(y1) - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

        expected_step = sequence.get_current_step()
        active_actions = []

        # Evaluate Red and Yellow box detections
        for obj_name in ["red_box", "yellow_box"]:
            if obj_name in current_detections:
                raw_cy = current_detections[obj_name]["center"][1]
                raw_ar = current_detections[obj_name]["ar"]

                tracker = trackers[obj_name]
                smooth_cy, smooth_ar = tracker.update(raw_cy, raw_ar)

                color_label = "RED" if "red" in obj_name else "YELLOW"

                # 1. PICK (Displacement UP > 45 pixels from baseline)
                is_picking = (tracker.baseline_cy - smooth_cy) > 45
                if tracker.check_debounced_action(f"PICK_{color_label}", is_picking):
                    active_actions.append(f"PICK_{color_label}")

                # 2. PLACE (Returned within 20 pixels of original table baseline)
                is_placing = abs(smooth_cy - tracker.baseline_cy) < 20 and (
                    sequence.get_current_step() == f"PLACE_{color_label}"
                )
                if tracker.check_debounced_action(f"PLACE_{color_label}", is_placing):
                    active_actions.append(f"PLACE_{color_label}")

                # 3. MANIPULATE (Aspect ratio shift > 0.35 from baseline)
                is_manipulating = abs(smooth_ar - tracker.baseline_ar) > 0.35
                if tracker.check_debounced_action(
                    f"MANIPULATE_{color_label}", is_manipulating
                ):
                    active_actions.append(f"MANIPULATE_{color_label}")

        # Step Advancement / Warning triggers
        if expected_step in active_actions:
            sequence.advance_step()
            # Reset baselines after a valid step completion
            for trk in trackers.values():
                trk.baseline_cy = None
                trk.baseline_ar = None
        else:
            for act in active_actions:
                if (
                    act in sequence.steps
                    and sequence.steps.index(act) > sequence.current_step_idx
                ):
                    sequence.trigger_warning(act)

        # On-screen HUD
        cv2.putText(
            frame,
            f"TARGET STEP: {expected_step}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 0, 0),
            2,
        )

        cv2.imshow("Astronaut AI Assistant", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
