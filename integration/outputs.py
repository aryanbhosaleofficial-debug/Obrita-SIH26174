"""Optional local outputs. Bounded recorder queue and latest-frame LAN stream."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue, Full
from threading import Event, Lock, Thread, BoundedSemaphore
from time import monotonic

import cv2

from yolo.procedure.event_log import EventLog


class SessionLog:
    """Reuse EventLog, add session and UTC timestamps, survive output failure."""
    def __init__(self, path, session_id):
        self.path, self.session_id = Path(path), session_id
        self.error = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.log = EventLog(self.path)
        except OSError as exc:
            self.error = str(exc)
            self.log = EventLog()

    def emit(self, record):
        from datetime import datetime, timezone
        try:
            self.log.emit({"utc": datetime.now(timezone.utc).isoformat(), **record,
                           "session_id": record.get("session_id") or self.session_id})
            self.error = self.error or self.log.last_error
        except Exception as exc:
            self.error = str(exc)

    @property
    def records(self):
        return self.log.snapshot()

    def close(self):
        try:
            self.log.close()
        except OSError as exc:
            self.error = str(exc)


class AsyncRecorder:
    """Record annotated BGR frames without disk writes in the inference loop.

    Overflow drops recording frames, never blocks perception; sidecar lists only
    successfully written source frame identities. Video is fixed-rate playback.
    """
    def __init__(self, path, fps=30., capacity=32):
        if not 0 < fps <= 240 or capacity < 1:
            raise ValueError("recording FPS/capacity must be positive")
        self.path, self.fps = Path(path), fps
        self.queue = Queue(capacity)
        self.written = self.dropped = 0
        self.error = None
        self.closed = False
        self.thread = Thread(target=self._run, name="full-system-recorder", daemon=True)
        self.thread.start()

    def submit(self, image, packet):
        if self.closed or self.error:
            return
        item = (image.copy(), {"frame_id": packet.frame_id, "timestamp_s": packet.timestamp_s,
                              "source_id": packet.source_id, "session_id": packet.session_id})
        try:
            self.queue.put_nowait(item)
        except Full:
            self.dropped += 1

    def _run(self):
        writer = metadata = None
        size = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            while True:
                item = self.queue.get()
                try:
                    if item is None:
                        return
                    image, identity = item
                    if writer is None:
                        size = (image.shape[1], image.shape[0])
                        codec = "MJPG" if self.path.suffix.lower() == ".avi" else "mp4v"
                        writer = cv2.VideoWriter(str(self.path), cv2.VideoWriter.fourcc(*codec), self.fps, size)
                        if not writer.isOpened():
                            raise OSError(f"VideoWriter cannot open {self.path}")
                        metadata = self.path.with_suffix(self.path.suffix + ".jsonl").open("w", encoding="utf-8")
                    if (image.shape[1], image.shape[0]) != size:
                        raise ValueError("source dimensions changed while recording")
                    writer.write(image)
                    metadata.write(json.dumps(identity) + "\n")
                    self.written += 1
                finally:
                    self.queue.task_done()
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            if writer is not None:
                writer.release()
            if metadata is not None:
                metadata.close()

    def close(self):
        if self.closed:
            return
        self.closed = True
        deadline = monotonic() + 5
        while self.thread.is_alive():
            try:
                self.queue.put(None, timeout=.1)
                break
            except Full:
                if monotonic() >= deadline:
                    self.error = self.error or "recorder drain timeout"
                    break
        self.thread.join(timeout=max(0., deadline - monotonic()))
        if self.thread.is_alive():
            self.error = self.error or "recorder shutdown timeout"


class LocalStream:
    """Optional HTTP/JPEG + MJPEG, default loopback; explicit host enables LAN.

    Clients receive newest frames only. There is no external network request,
    authentication or cloud dependency. Use only a trusted isolated demo LAN.
    """
    def __init__(self, host="127.0.0.1", port=8080):
        self.lock, self.stop = Lock(), Event()
        self.clients = BoundedSemaphore(4)
        self.jpeg = None
        self.error = None
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path not in ("/frame.jpg", "/stream"):
                    self.send_error(404)
                    return
                if not owner.clients.acquire(blocking=False):
                    self.send_error(503)
                    return
                try:
                    self.connection.settimeout(2.)
                    with owner.lock:
                        jpeg = owner.jpeg
                    if jpeg is None:
                        self.send_error(503, "waiting for first frame")
                        return
                    self.send_response(200)
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Type", "image/jpeg" if self.path == "/frame.jpg" else "multipart/x-mixed-replace; boundary=frame")
                    if self.path == "/frame.jpg":
                        self.send_header("Content-Length", str(len(jpeg)))
                    self.end_headers()
                    if self.path == "/frame.jpg":
                        self.wfile.write(jpeg)
                        return
                    while not owner.stop.is_set():
                        with owner.lock:
                            jpeg = owner.jpeg
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
                        self.wfile.flush()
                        owner.stop.wait(.1)
                except (OSError, TimeoutError):
                    pass  # disconnected/slow client cannot stop perception
                finally:
                    owner.clients.release()
        self.server = ThreadingHTTPServer((host, port), Handler)
        self.server.daemon_threads = True
        address = self.server.server_address
        self.url = f"http://{address[0]}:{address[1]}/stream"
        self.thread = Thread(target=lambda: self.server.serve_forever(poll_interval=.1),
                             name="full-system-stream", daemon=True)
        self.thread.start()

    def submit(self, image):
        ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            raise OSError("stream JPEG encoding failed")
        with self.lock:
            self.jpeg = data.tobytes()

    def close(self):
        if self.stop.is_set():
            return
        self.stop.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3.)


class VoiceOutput:
    """Own existing offline AlertManager lifecycle; mute is a host control."""
    def __init__(self, definition, config, *, emit, tts=None, player=None):
        from procedure.integration import voice_definition
        from yolo.alerts.manager import AlertManager
        self.manager = AlertManager(voice_definition(definition), config, emit=emit, tts=tts, player=player)
        self.enabled = True

    @property
    def status(self):
        return self.manager.status if self.enabled else "MUTED"

    def enqueue(self, event):
        return self.manager.enqueue(event) if self.enabled else False

    def mute(self, enabled):
        self.enabled = enabled
        if not enabled:
            self.manager.reset()

    def close(self):
        self.manager.close()
        thread = self.manager._thread  # existing manager's close only waits 250 ms
        if thread is not None:
            thread.join(timeout=5.)
            if thread.is_alive():
                raise RuntimeError("voice worker shutdown timeout")
