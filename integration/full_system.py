"""Authoritative frame loop: frozen Modules 01–06, procedure and optional outputs."""
from collections import deque
from contextlib import ExitStack
from dataclasses import asdict
import logging
from threading import Event
from time import perf_counter

from pose_tracking.integration import TrackingIntegration
from pose_tracking.sync import FrameSyncError
from pose_tracking.visualization import render_overlay
from procedure import ProcedureFSM, ProcedureIntegration
from procedure.contracts import DecisionType
from procedure.integration import gui_snapshot
from shared.enums.module_status import ModuleStatus

LOGGER = logging.getLogger(__name__)


def require_frame_identity(packet, milestone, tracking):
    """Reject boundary identity drift before any event can reach the FSM."""
    retained = milestone.upstream.prepared.source
    if retained is None:
        raise FrameSyncError("Module 01 did not retain source identity")
    outputs = (retained, milestone.upstream.objects, milestone.upstream.optimization,
               milestone.boundary, milestone.activity, tracking)
    for output in outputs:
        if output.frame_id != packet.frame_id or output.timestamp_s != packet.timestamp_s:
            raise FrameSyncError("full-system frame/timestamp mismatch")
        for name in ("source_id", "session_id"):
            actual = output.metadata.get(name) if output is milestone.activity else getattr(output, name, None)
            if actual is not None and actual != getattr(packet, name):
                raise FrameSyncError(f"full-system {name} mismatch")
    if milestone.activity.metadata.get("source_id") is None or milestone.activity.metadata.get("session_id") is None:
        raise FrameSyncError("semantic event is missing stream identity")
    if tracking.image_width != packet.width or tracking.image_height != packet.height:
        raise FrameSyncError("Module 06 coordinates differ from source dimensions")


class FullSystemRuntime:
    """Synchronous core. GUI owns a worker; recorder/voice/stream own bounded outputs.

    Dependency injection substitutes inference only in synthetic mode. The loop
    executes the real perception owners and verifies their shared contracts.
    """
    def __init__(self, pipeline, tracker, definition, *, adapter, log,
                 recorder=None, stream=None, voice=None, semantic_scenario=None,
                 gui=None, stop=None, controls=None, diagnostics=None, realtime_fps=None):
        self.pipeline, self.tracker = pipeline, tracker
        self.adapter, self.log = adapter, log
        self.recorder, self.stream, self.voice = recorder, stream, voice
        self.scenario, self.gui = semantic_scenario, gui
        self.stop = stop if stop is not None else Event()
        self.controls = controls
        self.diagnostics, self.realtime_fps = diagnostics, realtime_fps
        self.fsm = ProcedureFSM(definition=definition)
        self.consumer = ProcedureIntegration(self.fsm,
            alert_sink=self._alert if voice else None, log_sink=self._guidance_log)
        self.health = {"Camera": "WAITING", "YOLO": "WAITING", "Optimization": "WAITING",
                       "Workspace": "WAITING", "Fusion": "WAITING", "Pose/Hands": "WAITING",
                       "FSM": "not_started", "Voice": "OFF", "Logging": "OK",
                       "Recording": "ON" if recorder else "OFF", "Streaming": "ON" if stream else "OFF"}
        self.health_errors = {}
        self.last_decision = None
        self.latest_snapshot = None
        self.frames = 0
        self.timings = deque(maxlen=1000)
        self.stage_totals = {}
        self.closed = False
        self.exit_reason = "not_started"
        self.error = None
        self._last_gui = 0.
        self._last_spoken = ""
        self._last_recovery = None

    def _guidance_log(self, decision):
        self.log.emit({"event": "guidance", **decision})

    def _alert(self, alert):
        if (alert.alert_type in ("NEXT_STEP", "COMPLETED")
                and self._last_recovery is not None and self.fsm.snapshot().recovery_action is None):
            self.voice.manager.reset()  # cancel recovery speech when its condition has resolved
        accepted = self.voice.enqueue(alert)
        self.log.emit({"event": "voice_dispatch", "accepted": accepted, **asdict(alert)})

    def _optional(self, name, callback):
        try:
            return callback()
        except Exception as exc:
            first_failure = name not in self.health_errors
            self.health[name] = "DEGRADED"
            self.health_errors[name] = str(exc)
            if first_failure:
                self.log.emit({"event": "output_error", "output": name, "reason": str(exc)})
                LOGGER.warning("%s degraded: %s", name, exc)
            return None

    def _controls(self):
        from queue import Empty
        if self.controls is None:
            return
        while True:
            try:
                command, value = self.controls.get_nowait()
            except Empty:
                break
            try:
                if command == "voice" and self.voice:
                    self.voice.mute(value)
                elif command in ("pause", "resume", "abort"):
                    self.last_decision = getattr(self.consumer, command)()
                elif command == "reset":
                    self.consumer.reset()
                    if self.voice:
                        self.voice.manager.reset()
                    self.last_decision = self.consumer.start()
                    self._last_recovery = None
            except ValueError as exc:
                self.log.emit({"event": "control_rejected", "control": command, "reason": str(exc)})

    def _status(self, packet, result, tracked):
        self.health.update({"Camera": "OK", "YOLO": result.upstream.objects.status.value,
            "Optimization": result.upstream.optimization.status.value,
            "Workspace": "OK" if result.upstream.optimization.spatial.reference_frame.valid else "UNAVAILABLE",
            "Fusion": result.activity.status.value, "Pose/Hands": tracked.status.value,
            "FSM": self.fsm.state.value, "Voice": self.voice.status if self.voice else "OFF",
            "Logging": "DEGRADED" if self.log.error else "OK"})
        for name in self.health_errors:
            self.health[name] = "DEGRADED"
        if self.recorder and self.recorder.error:
            self.health["Recording"] = "DEGRADED"
            self.health_errors["Recording"] = self.recorder.error
        # Publish actual playback records, never an enqueue request as spoken audio.
        for record in reversed(self.log.records):
            if record.get("event") == "audio_playback_started":
                self._last_spoken = record.get("message", "")
                break

    def _snapshot(self, packet, result, tracked, decision):
        view = self.last_decision or decision
        payload = gui_snapshot(view)
        payload.update(stamp=f"{packet.timestamp_s:.3f}", met_seconds=packet.timestamp_s,
            confidence=view.confidence, spoken=self._last_spoken,
            scene={"simulated": False, "overlays_rendered": True,
                   "objects": [{"name": d.class_name, "conf": d.confidence,
                       "cx": d.bbox.center.x / packet.width, "cy": d.bbox.center.y / packet.height,
                       "w": (d.bbox.x2 - d.bbox.x1) / packet.width,
                       "h": (d.bbox.y2 - d.bbox.y1) / packet.height}
                       for d in result.upstream.objects.detections],
                   "hands": [{"tip": (h.landmarks[8].normalized_xy or (0., 0.)),
                              "wrist": (h.wrist.normalized_xy or (0., 0.)),
                              "conf": h.handedness_score or 0.} for h in tracked.hands]},
            recording=bool(self.recorder and not self.recorder.error),
            lan_streaming=bool(self.stream and self.health["Streaming"] != "DEGRADED"),
            voice_on=bool(self.voice and self.voice.enabled), log_path=str(self.log.path),
            footer=("Synthetic inference and semantic events. " if self.scenario else "Synthetic inference; real fusion rules. " if packet.metadata.get("synthetic") else "Local inference. ")
                   + "Prototype BAS assistance. " + " | ".join(f"{k}: {v}" for k, v in self.health.items()))
        if view.metadata.get("upstream", {}).get("mapping_semantics") == "demo_proxy":
            payload["footer"] = "Contact/departure demo proxies, not verified pick/place recognition. " + payload["footer"]
        payload["chain"] = [{"stage": name, "module": name, "note": self.health_errors.get(name, ""), "status": status}
                            for name, status in self.health.items()]
        payload["chain"].append({"stage": "Activity", "module": "Semantic adapter",
                                 "note": view.observed_action or "waiting", "status": view.decision.value})
        payload["log"] = [{"t": f"{r.get('timestamp_s', 0.) or 0.:.3f}", "level": "event",
                           "event": str(r.get("event", r.get("decision", ""))),
                           "detail": str(r.get("message", r.get("reason", ""))),
                           "conf": r.get("confidence")} for r in self.log.records[-15:]]
        observations = result.upstream.optimization.observations
        payload["readings"] = [{"name": f"{h.handedness or 'Unknown'} hand",
                                "x": h.reference_palm_center.x if h.reference_palm_center else None,
                                "y": h.reference_palm_center.y if h.reference_palm_center else None,
                                "conf": h.confidence} for h in observations.hands] if observations else []
        payload["system_health"] = dict(self.health)
        payload["latest_decision"] = asdict(decision)
        payload["tracking"] = {"frame_id": tracked.frame_id, "reference_id": tracked.reference_id,
                               "coordinate_frame": tracked.feature_coordinate_frame.value,
                               "hands": [h.handedness for h in tracked.hands]}
        return payload

    def run(self, frames, *, max_frames=None):
        started = perf_counter()
        try:
            with ExitStack() as stack:
                stack.callback(getattr(frames, "close", lambda: None))
                stack.callback(self.close)
                stack.enter_context(self.pipeline)
                stack.enter_context(self.tracker)
                tracking_adapter = TrackingIntegration(self.tracker)
                self.last_decision = self.consumer.start()
                self.log.emit({"event": "system_started", "procedure_id": self.fsm.definition.experiment_id,
                               "synthetic_semantics": self.scenario is not None,
                               "stream_url": self.stream.url if self.stream else None})
                for packet in frames:
                    if self.stop.is_set():
                        self.exit_reason = "stop_requested"
                        break
                    self._controls()
                    frame_started = perf_counter()
                    result = self.pipeline.process(packet)
                    tracked = tracking_adapter.process(result)
                    require_frame_identity(packet, result, tracked)
                    parts = (result.upstream.prepared, result.upstream.objects,
                             result.upstream.optimization, result.boundary, result.activity, tracked)
                    if any(p.status in (ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT) for p in parts):
                        raise RuntimeError("critical perception error/invalid input; inspect module diagnostics")
                    # All semantic inputs, including simulator events, retain this physical frame identity.
                    event = self.scenario.event(packet) if self.scenario else self.adapter.adapt(result.activity)
                    if event is not None:
                        if (event.frame_id, event.timestamp_s, event.metadata.get("source_id"), event.metadata.get("session_id")) != (packet.frame_id, packet.timestamp_s, packet.source_id, packet.session_id):
                            raise FrameSyncError("semantic adapter changed frame identity")
                        decision = self.consumer.process(event)
                        if event.metadata.get("emitted") and decision.decision != DecisionType.DUPLICATE:
                            self.log.emit({"event": "activity_confirmed", **asdict(event)})
                        if decision.should_display:
                            self.last_decision = decision
                        recovery = self.fsm.snapshot().recovery_action
                        if recovery != self._last_recovery:
                            self.log.emit({"event": "recovery_entered" if recovery else "recovery_completed",
                                           "timestamp_s": packet.timestamp_s,
                                           "recovery_action": recovery.value if recovery else None})
                            self._last_recovery = recovery
                    else:
                        decision = self.last_decision
                    self.frames += 1
                    elapsed_ms = (perf_counter() - frame_started) * 1000
                    self.timings.append(elapsed_ms)
                    for name, value in {**result.timings_ms, "module06_ms": tracked.processing_time_ms}.items():
                        self.stage_totals[name] = self.stage_totals.get(name, 0.) + value
                    self._status(packet, result, tracked)
                    if self.consumer.last_dispatch_errors:
                        self.health_errors["Voice"] = "; ".join(self.consumer.last_dispatch_errors)
                    payload = self._snapshot(packet, result, tracked, decision)
                    self.latest_snapshot = payload
                    display = None
                    if self.gui or self.recorder or self.stream:
                        display = render_overlay(packet.image, tracked, result.upstream.objects,
                            extra_lines=[self.last_decision.message, f"FSM: {self.fsm.state.value}",
                                         "SYNTHETIC DEMO" if packet.metadata.get("synthetic") else "LOCAL INFERENCE"])
                        axes = result.upstream.optimization.spatial.reference_frame.axes_pixels
                        if axes:
                            import cv2
                            origin, xaxis, yaxis = axes
                            for point, text, colour in ((xaxis, "rack +X", (0, 200, 255)), (yaxis, "rack +Y", (255, 200, 0))):
                                end = (round(origin.x + .2 * (point.x - origin.x)),
                                       round(origin.y + .2 * (point.y - origin.y)))
                                cv2.arrowedLine(display, (round(origin.x), round(origin.y)), end, colour, 2)
                                cv2.putText(display, text, end, cv2.FONT_HERSHEY_SIMPLEX, .4, colour, 1)
                    if self.recorder:
                        self._optional("Recording", lambda: self.recorder.submit(display, packet))
                    if self.stream and self.health["Streaming"] != "DEGRADED":
                        self._optional("Streaming", lambda: self.stream.submit(display))
                    if self.gui:
                        self._optional("GUI", lambda: self.gui.push_frame(display))
                        now = perf_counter()
                        if now - self._last_gui >= .1 or (event is not None and decision.should_display):
                            self._optional("GUI", lambda: self.gui.push_snapshot(payload))
                            self._last_gui = now
                    if self.diagnostics:
                        self._optional("Diagnostics", lambda: self.diagnostics({"frame_id": packet.frame_id,
                            "timestamp_s": packet.timestamp_s, "source_id": packet.source_id,
                            "session_id": packet.session_id, "health": dict(self.health),
                            "activity": asdict(event) if event else None, "module05_activity": asdict(result.activity),
                            "tracking": asdict(tracked), "guidance": asdict(decision),
                            "timings_ms": {**result.timings_ms, "module06_ms": tracked.processing_time_ms,
                                           "core_frame_ms": elapsed_ms}}))
                    if max_frames and self.frames >= max_frames:
                        self.exit_reason = "frame_limit"
                        break
                    if self.realtime_fps:
                        self.stop.wait(max(0., 1 / self.realtime_fps - (perf_counter() - frame_started)))
                else:
                    self.exit_reason = "eof"
                if not self.frames and not self.stop.is_set():
                    raise RuntimeError("source produced no frames")
        except KeyboardInterrupt:
            self.exit_reason = "interrupt"
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self.exit_reason = "error"
            self.log.emit({"event": "system_error", "reason": self.error})
            LOGGER.error(self.error)
        finally:
            self.close()
            duration = perf_counter() - started
            summary = {"event": "system_stopped", "frames": self.frames, "exit_reason": self.exit_reason,
                       "error": self.error, "procedure_state": self.fsm.state.value,
                       "completed_steps": self.fsm.completed_steps,
                       "core_latency_mean_ms": sum(self.timings) / len(self.timings) if self.timings else None,
                       "core_latency_samples": len(self.timings),
                       "runtime_seconds": duration, "observed_loop_fps": self.frames / duration if duration else None,
                       "stage_mean_ms": {k: v / self.frames for k, v in self.stage_totals.items()} if self.frames else {},
                       "health": dict(self.health), "output_errors": dict(self.health_errors),
                       "recorded_frames": self.recorder.written if self.recorder else 0,
                       "recording_drops": self.recorder.dropped if self.recorder else 0}
            self.log.emit(summary)
            self.log.close()
        return summary

    def close(self):
        if self.closed:
            return
        self.closed = True
        for name, resource in (("Recording", self.recorder), ("Streaming", self.stream), ("Voice", self.voice)):
            if resource:
                if name == "Voice":
                    self.health["Voice_before_shutdown"] = resource.status
                self._optional(name, resource.close)
                if getattr(resource, "error", None):
                    self.health[name] = "DEGRADED"
                    self.health_errors[name] = resource.error
                if name == "Voice":
                    self.health[name] = "STOPPED" if name not in self.health_errors and self.health["Voice_before_shutdown"] not in ("VOICE_ERROR", "VOICE_UNAVAILABLE") else "DEGRADED"
