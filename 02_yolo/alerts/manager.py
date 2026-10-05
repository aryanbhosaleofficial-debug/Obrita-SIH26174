"""One bounded voice worker: preload/cache, keyed cooldown and error priority."""

import logging
from collections import Counter
from dataclasses import asdict
from threading import Condition, Event, Thread

from yolo.alerts.audio_cache import AudioCache
from yolo.alerts.contracts import AlertEvent, VoiceConfig
from yolo.alerts.messages import ERRORS, procedure_messages, step_message
from yolo.alerts.piper_tts import VoiceUnavailable
from yolo.alerts.playback import SoundDevicePlayback
from yolo.alerts.timing import host_time
from yolo.alerts.voice_router import build_voice_router

__all__ = ["ERRORS", "AlertManager", "procedure_messages", "step_message"]


class AlertManager:
    def __init__(
        self,
        definition,
        config=None,
        *,
        tts=None,
        player=None,
        emit=None,
        clock=host_time,
    ):
        self.config = config or VoiceConfig()
        self.clock = clock
        self.emit = emit or (lambda record: None)
        self.tts = tts or build_voice_router(self.config, definition)
        self.player = player or SoundDevicePlayback(self.config.device, clock=clock)
        self.cache = AudioCache(self.config.cache_entries, self.config.cache_bytes)
        self.messages = procedure_messages(definition, self.config)
        self._condition = Condition()
        self._queue = []
        self._cooldown = {}  # bounded by procedure action keys + 256-entry cap
        self._sequence = 0
        self._generation = 0
        self._closed = False
        self._active = None
        self._cancel = Event()
        self._status = "WARMING" if self.config.enabled else "DISABLED"
        self.last_latency_ms = None
        self.preload_sources: Counter[str] = Counter()
        self._thread = None
        if self.config.enabled:
            self._thread = Thread(target=self._run, name="module02-voice", daemon=True)
            self._thread.start()

    @property
    def status(self):
        with self._condition:
            return self._status

    @property
    def backend_status(self):
        """Startup probe result per backend plus which one voiced fixed messages."""
        summary = getattr(self.tts, "summary", None)
        if summary is None:
            return None
        with self._condition:
            fixed = dict(self.preload_sources)
        return {**summary(), "fixed_messages": fixed}

    def _log(self, record):
        try:
            self.emit(record)
        except Exception as exc:  # noqa: BLE001 -- logging cannot break audio/perception
            logging.getLogger(__name__).debug("Alert event logging failed: %s", exc)

    def enqueue(self, event):
        now = self.clock()
        with self._condition:
            if (
                self._closed
                or not self.config.enabled
                or self._status == "VOICE_UNAVAILABLE"
            ):
                self._log(
                    {
                        "event": "alert_suppressed",
                        "reason": self._status,
                        "frame_id": event.frame_id,
                    }
                )
                return False
            if (
                (event.alert_type in ERRORS and not self.config.speak_errors)
                or (
                    event.alert_type in {"NEXT_STEP", "COMPLETED"}
                    and not self.config.speak_next_step
                )
                or (event.alert_type == "SUCCESS" and not self.config.speak_success)
            ):
                return False
            keys = [item[3].key for item in self._queue]
            last = self._cooldown.get(event.key)
            if (
                event.key in keys
                or (self._active and self._active.key == event.key)
                or (
                    last is not None
                    and (now - last) * 1000 < self.config.alert_cooldown_ms
                )
            ):
                self._log(
                    {
                        "event": "alert_suppressed",
                        "reason": "duplicate_or_cooldown",
                        "frame_id": event.frame_id,
                    }
                )
                return False
            # Errors supersede queued informational speech, and can cancel an
            # active lower-priority prompt on the same single playback worker.
            if event.priority <= 2:
                removed = [item for item in self._queue if item[0] > event.priority]
                self._queue = [
                    item for item in self._queue if item[0] <= event.priority
                ]
                for item in removed:
                    self._log(
                        {
                            "event": "alert_dropped",
                            "reason": "superseded",
                            "frame_id": item[3].frame_id,
                        }
                    )
                if self._active and self._active.priority > event.priority:
                    self._cancel.set()
            if len(self._queue) >= self.config.queue_capacity:
                worst = max(self._queue, key=lambda item: (item[0], item[1]))
                if worst[0] <= event.priority:
                    self._log(
                        {
                            "event": "alert_dropped",
                            "reason": "bounded_queue_full",
                            "frame_id": event.frame_id,
                        }
                    )
                    return False
                self._queue.remove(worst)
            self._sequence += 1
            self._queue.append(
                (event.priority, self._sequence, self._generation, event, now)
            )
            self._queue.sort(key=lambda item: (item[0], item[1]))
            if len(self._cooldown) >= 256:
                del self._cooldown[next(iter(self._cooldown))]
            self._cooldown[event.key] = now
            self._log(
                {
                    "event": "alert_queued",
                    **asdict(event),
                    "alert_queued_timestamp": now,
                    "clock": "host_perf_counter_seconds",
                }
            )
            self._condition.notify_all()
            return True

    def _run(self):
        try:
            self.tts.load()
            for message in self.messages:  # critical warnings are prepared first
                with self._condition:
                    if self._closed:
                        return
                try:
                    clip = self.tts.synthesize(message)
                except VoiceUnavailable as exc:
                    # One unvoiceable message must not silence the others.
                    self._log(
                        {
                            "event": "voice_preload_miss",
                            "message": message,
                            "reason": str(exc),
                        }
                    )
                    continue
                self.cache.put(message, clip)
                with self._condition:
                    self.preload_sources[clip.source or "unknown"] += 1
            with self._condition:
                self._status = "READY"
                self._condition.notify_all()
            self._log(
                {
                    "event": "voice_ready",
                    "cached_messages": len(self.cache.items),
                    "cache_bytes": self.cache.bytes_used,
                    "backends": self.backend_status,
                }
            )
            self._play_loop()
        except Exception as exc:  # noqa: BLE001 -- optional initialization only
            with self._condition:
                self._status = "VOICE_UNAVAILABLE"
                self._queue.clear()
                self._condition.notify_all()
            self._log({"event": "voice_unavailable", "reason": str(exc)})
        finally:
            self.cache.clear()
            try:
                self.tts.close()
            except Exception as exc:  # noqa: BLE001 -- optional backend cleanup
                logging.getLogger(__name__).debug("Voice cleanup failed: %s", exc)

    def _play_loop(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._queue or self._closed)
                if self._closed:
                    return
                _, _, generation, event, queued_s = self._queue.pop(0)
                self._active = event
                self._cancel = Event()
                cancel = self._cancel
                self._status = "PLAYING"
            try:
                clip = self.cache.get(event.message)
                dynamic = clip is None
                if dynamic:
                    self._log(
                        {"event": "dynamic_synthesis", "frame_id": event.frame_id}
                    )
                    clip = self.tts.synthesize(event.message)
                    try:
                        self.cache.put(event.message, clip)
                    except ValueError:
                        pass  # keep critical cached audio pinned; play uncached

                def on_start(
                    started_s,
                    method,
                    *,
                    event=event,
                    generation=generation,
                    cancel=cancel,
                    queued_s=queued_s,
                    dynamic=dynamic,
                    source=clip.source,
                ):
                    with self._condition:
                        if (
                            self._closed
                            or generation != self._generation
                            or cancel.is_set()
                        ):
                            return
                        latency = (
                            started_s - event.violation_confirmed_timestamp
                        ) * 1000
                        if event.alert_type in ERRORS:
                            self.last_latency_ms = latency
                        self._log(
                            {
                                "event": "audio_playback_started",
                                **asdict(event),
                                "alert_queued_timestamp": queued_s,
                                "audio_playback_start_timestamp": started_s,
                                "warning_start_latency_ms": latency
                                if event.alert_type in ERRORS
                                else None,
                                "measurement_method": method,
                                "dynamic_synthesis": dynamic,
                                "voice_backend": source,
                                "clock": "host_perf_counter_seconds",
                            }
                        )
                        self._condition.notify_all()

                if not cancel.is_set():
                    self.player.play(clip, on_start, cancel)
                with self._condition:
                    if generation == self._generation:
                        self._status = "READY"
            except Exception as exc:  # noqa: BLE001 -- isolate synthesis/device failures
                with self._condition:
                    if generation == self._generation:
                        self._status = "VOICE_ERROR"
                self._log(
                    {
                        "event": "voice_error",
                        "frame_id": event.frame_id,
                        "reason": str(exc),
                    }
                )
            finally:
                with self._condition:
                    self._active = None
                    self._condition.notify_all()

    def reset(self):
        with self._condition:
            self._generation += 1
            self._queue.clear()
            self._cooldown.clear()
            self._cancel.set()
            self._active = (
                None  # cancelled old-generation work cannot suppress a new prompt
            )
            self.last_latency_ms = None
            if self._status in {"PLAYING", "VOICE_ERROR"}:
                self._status = "READY"
            self._condition.notify_all()

    def close(self):
        self.reset()
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=0.25)

    def alert_for(self, event, definition):
        step = next((s for s in definition.steps if s.step_id == event.step_id), None)
        if step and event.event in ERRORS:
            return AlertEvent(
                event.event,
                step_message(step, event.event),
                2 if event.event == "STEP_TIMEOUT" else 1,
                event.frame_id,
                event.timestamp_s,
                step.step_id,
                event.observed,
                event.confirmed_monotonic_s,
            )
        return None
