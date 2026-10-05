"""Thread-safe optional JSONL plus bounded in-memory diagnostic history."""

import json
import logging
from collections import deque
from contextlib import ExitStack, contextmanager
from pathlib import Path
from threading import Lock


@contextmanager
def _open_log(path):
    with Path(path).open("w", encoding="utf-8") as stream:
        yield stream


class EventLog:
    def __init__(self, path=None):
        self.last_error: str | None = None
        self.records: deque[dict] = deque(maxlen=128)
        self._lock = Lock()
        self._stack = ExitStack()
        self._file = (
            self._stack.enter_context(_open_log(path)) if path is not None else None
        )

    def emit(self, record):
        with self._lock:
            self.records.append(dict(record))
            if self._file is not None:
                try:
                    self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
                    self._file.flush()
                except OSError as exc:
                    self.last_error = str(exc)
                    logging.getLogger(__name__).error(
                        "Procedure event log unavailable: %s", exc
                    )
        logging.getLogger(__name__).debug("procedure event: %s", record)

    def snapshot(self) -> tuple[dict, ...]:
        """Read bounded records safely while the voice worker is logging."""
        with self._lock:
            return tuple(dict(record) for record in self.records)

    def close(self):
        with self._lock:
            if self._file is not None:
                self._stack.close()
                self._file = None
