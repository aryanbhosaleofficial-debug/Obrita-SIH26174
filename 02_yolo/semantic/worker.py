"""One daemon worker and at most one in-flight event; no frame backlog."""

from threading import Condition, Thread

from yolo.semantic.contracts import SemanticConfig, SemanticResult, SemanticStatus
from yolo.semantic.event_trigger import EventTrigger
from yolo.semantic.qwen_verifier import QwenVerifier
from yolo.semantic.temporal_buffer import TemporalBuffer
from yolo.visualization.renderer import source_bgr


class SemanticWorker:
    def __init__(self, config=None, verifier=None):
        self.config = config or SemanticConfig()
        self.buffer = TemporalBuffer(self.config)
        self.trigger = EventTrigger(self.config)
        self.verifier = verifier or QwenVerifier(self.config)
        self._condition = Condition()
        self._pending = None
        self._busy = False
        self._generation = 0
        self._event_id = 0
        self._closed = False
        self._latest = None
        self._status = (
            SemanticStatus.WAITING if self.config.enabled else SemanticStatus.DISABLED
        )
        self._thread = None
        if self.config.enabled:
            self._thread = Thread(target=self._run, name="module02-vlm", daemon=True)
            self._thread.start()

    @property
    def latest(self):
        with self._condition:
            return self._latest

    @property
    def status(self):
        with self._condition:
            return self._status

    def observe(self, frame, objects):
        if not self.config.enabled or self._closed:
            return
        if objects.status in ("error", "invalid_input"):
            return
        try:
            self.buffer.append(source_bgr(frame.source), objects)
            reason = self.trigger.check(objects)
            if reason and len(self.buffer.frames) >= 2:
                self.submit(self.buffer.select(), reason)
        except Exception:  # noqa: BLE001 -- isolate optional semantic encoding failures
            with self._condition:
                self._status = SemanticStatus.VLM_ERROR

    def submit(self, frames, reason="manual"):
        with self._condition:
            if self._closed or not self.config.enabled or self._busy or not frames:
                return False
            self._event_id += 1
            self._pending = (self._generation, tuple(frames), self._event_id, reason)
            self._busy = True
            self._status = SemanticStatus.BUSY
            self._condition.notify()
            return True

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(
                    lambda: self._pending is not None or self._closed
                )
                if self._closed:
                    return
                generation, frames, event_id, reason = self._pending
                self._pending = None
            try:
                result = self.verifier.verify(frames, event_id, reason)
                if not isinstance(result, SemanticResult):
                    raise TypeError("verifier violated semantic contract")
            except Exception:  # noqa: BLE001 -- isolate replaceable local VLM backend
                newest = frames[-1]
                result = SemanticResult(
                    "UNCERTAIN",
                    None,
                    SemanticStatus.VLM_ERROR,
                    newest.timestamp_s,
                    newest.frame_id,
                    event_id,
                    "semantic worker failed",
                )
            with self._condition:
                self._busy = False
                if generation == self._generation and not self._closed:
                    self._latest = result
                    self._status = result.status
                self._condition.notify_all()

    def reset(self):
        self.buffer.clear()
        self.trigger.clear()
        with self._condition:
            self._generation += 1
            if self._pending is not None:
                self._pending = None
                self._busy = False
            self._latest = None
            self._status = (
                SemanticStatus.WAITING
                if self.config.enabled
                else SemanticStatus.DISABLED
            )

    def close(self):
        self.reset()
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        # HTTP already in progress cannot be canceled safely; daemon exits after
        # the configured request timeout. Its generation cannot publish results.
