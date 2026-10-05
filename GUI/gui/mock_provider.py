from .state import StatusSnapshot, StepState, EventLogLine, Alert, NextStep
from typing import Callable
import copy

class MockProvider:
    def __init__(self):
        self.trial = "Correct run"
        self.rotation = 0
        self.voice_muted = False
        self.callbacks = []
    
    def set_trial(self, trial: str):
        if self.trial != trial:
            self.trial = trial
            self.emit()
            
    def set_rotation(self, deg: int):
        if self.rotation != deg:
            self.rotation = deg
            self.emit()
            
    def set_voice_muted(self, muted: bool):
        if self.voice_muted != muted:
            self.voice_muted = muted
            self.emit()

    def add_listener(self, cb: Callable[[StatusSnapshot], None]):
        self.callbacks.append(cb)

    def emit(self):
        snap = self.get_snapshot()
        for cb in self.callbacks:
            cb(snap)

    def get_snapshot(self) -> StatusSnapshot:
        # Base common data
        steps_base = [
            StepState("pick_red", "Pick up the red box", "pending", "—"),
            StepState("place_red", "Place the red box on the rack spot", "pending", "—"),
            StepState("pick_yellow", "Pick up the yellow box", "pending", "—"),
            StepState("rotate_yellow", "Rotate the yellow box by 90°", "pending", "—"),
            StepState("place_yellow", "Place the yellow box on the rack spot", "pending", "—")
        ]
        
        events = [
            EventLogLine("00:00:12.311", "info", "camera", "source=0 opened once, timestamps increasing"),
            EventLogLine("00:00:12.040", "info", "session_start", "procedure=procedures/red_yellow_box.md steps=5")
        ]
        
        if self.trial == "Correct run":
            steps = copy.deepcopy(steps_base)
            steps[0].status = "done"
            steps[0].time = "00:00:41"
            steps[1].status = "done"
            steps[1].time = "00:01:21"
            steps[2].status = "active"
            steps[2].time = "in progress"
            
            alerts = [
                Alert("00:01:22", "Advisory", "Step 2 complete. Next: pick up the yellow box."),
                Alert("00:00:41", "Advisory", "Step 1 complete. Next: place the red box.")
            ]
            
            next_step = NextStep("03", "Next step", "A pick is confirmed after 300 ms of consistent detection.", "PICK yellow_box · 212 / 300 ms", 71, "0.88")
            
            events = [
                EventLogLine("00:01:38.207", "event", "pick", "object=yellow_box candidate 212 / 300 ms", "0.88"),
                EventLogLine("00:01:22.004", "voice", "speak", '"Step 2 complete. Next: pick up the yellow box."'),
                EventLogLine("00:01:21.870", "step", "place_red", "state=done"),
                EventLogLine("00:01:19.455", "event", "place", "object=red_box back at rest and still", "0.90"),
                EventLogLine("00:00:41.140", "voice", "speak", '"Step 1 complete. Next: place the red box."'),
                EventLogLine("00:00:41.120", "step", "pick_red", "state=done"),
                EventLogLine("00:00:38.902", "event", "pick", "object=red_box confirmed over 300 ms", "0.93"),
            ] + events
            
            return StatusSnapshot(
                trial_name=self.trial, met="00:01:38", frame_time="T+00:01:38.207",
                status_level="Nominal", status_message="Procedure on track. Step 2 confirmed.",
                spoken_text="Step 2 complete. Next: pick up the yellow box.",
                steps=steps, next_step=next_step, alerts=alerts, events=events,
                rotation_deg=self.rotation, voice_muted=self.voice_muted
            )
            
        elif self.trial == "Skipped step":
            steps = copy.deepcopy(steps_base)
            steps[0].status = "done"
            steps[0].time = "00:00:41"
            steps[1].status = "done"
            steps[1].time = "00:01:21"
            steps[2].status = "skipped"
            steps[2].time = "skipped"
            steps[3].status = "active"
            steps[3].time = "in progress"
            
            alerts = [
                Alert("00:01:45", "Caution", "Step 3 skipped. Pick up the yellow box first."),
                Alert("00:01:22", "Advisory", "Step 2 complete. Next: pick up the yellow box."),
                Alert("00:00:41", "Advisory", "Step 1 complete. Next: place the red box.")
            ]
            
            next_step = NextStep("03", "Return to", "Then continue with step 04, rotate_yellow.", "ROTATE yellow_box · 300 / 300 ms", 100, "")
            
            events = [
                EventLogLine("00:01:45.020", "voice", "speak", '"Step 3 skipped. Pick up the yellow box first."'),
                EventLogLine("00:01:44.930", "caution", "skipped", "steps=[pick_yellow]"),
                EventLogLine("00:01:44.912", "step", "rotate_yellow", "state=active, pick_yellow=skipped"),
                EventLogLine("00:01:44.610", "event", "manipulate", "object=yellow_box rotating, confirmed over 300 ms", "0.84"),
                EventLogLine("00:01:22.004", "voice", "speak", '"Step 2 complete. Next: pick up the yellow box."'),
                EventLogLine("00:01:21.870", "step", "place_red", "state=done"),
                EventLogLine("00:01:19.455", "event", "place", "object=red_box back at rest and still", "0.90"),
                EventLogLine("00:00:41.140", "voice", "speak", '"Step 1 complete. Next: place the red box."'),
                EventLogLine("00:00:41.120", "step", "pick_red", "state=done"),
                EventLogLine("00:00:38.902", "event", "pick", "object=red_box confirmed over 300 ms", "0.93"),
            ] + events
            
            return StatusSnapshot(
                trial_name=self.trial, met="00:01:45", frame_time="T+00:01:45.020",
                status_level="Caution", status_message="Step 3 (pick_yellow) was skipped. Step 4 is in progress.",
                spoken_text="Step 3 skipped. Pick up the yellow box first.",
                steps=steps, next_step=next_step, alerts=alerts, events=events,
                rotation_deg=self.rotation, voice_muted=self.voice_muted
            )
            
        elif self.trial == "Wrong order":
            steps = copy.deepcopy(steps_base)
            steps[0].status = "done"
            steps[0].time = "00:00:41"
            steps[1].status = "active"
            steps[1].time = "in progress"
            steps[2].status = "wrong"
            steps[2].time = "00:01:03"
            
            alerts = [
                Alert("00:01:03", "Warning", "Wrong order. Place the red box first."),
                Alert("00:00:41", "Advisory", "Step 1 complete. Next: place the red box.")
            ]
            
            next_step = NextStep("02", "Do first", "Then continue with step 03, pick_yellow.", "PICK yellow_box · 300 / 300 ms · not expected", 100, "")
            
            events = [
                EventLogLine("00:01:03.700", "voice", "speak", '"Wrong order. Place the red box first."'),
                EventLogLine("00:01:03.642", "warning", "wrong_order", "expected=place_red got=pick_yellow"),
                EventLogLine("00:01:03.340", "event", "pick", "object=yellow_box confirmed over 300 ms", "0.89"),
                EventLogLine("00:00:41.140", "voice", "speak", '"Step 1 complete. Next: place the red box."'),
                EventLogLine("00:00:41.120", "step", "pick_red", "state=done"),
                EventLogLine("00:00:38.902", "event", "pick", "object=red_box confirmed over 300 ms", "0.93"),
            ] + events
            
            return StatusSnapshot(
                trial_name=self.trial, met="00:01:04", frame_time="T+00:01:03.700",
                status_level="Warning", status_message="Pick yellow detected while step 2 (place_red) is expected.",
                spoken_text="Wrong order. Place the red box first.",
                steps=steps, next_step=next_step, alerts=alerts, events=events,
                rotation_deg=self.rotation, voice_muted=self.voice_muted
            )
            
        return StatusSnapshot("", "", "", "Nominal", "", "", steps_base, NextStep("", "", "", "", 0), [], events)
