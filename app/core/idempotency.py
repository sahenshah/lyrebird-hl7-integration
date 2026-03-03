import threading


class IdempotencyGuard:
    """
    Thread-safe in-memory idempotency guard.

    Stores successfully processed message_control_id values.
    Does NOT persist across restarts.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._processed = set()

    def is_processed(self, control_id: str) -> bool:
        with self._lock:
            return control_id in self._processed

    def mark_processed(self, control_id: str) -> None:
        with self._lock:
            self._processed.add(control_id)

    def clear(self) -> None:
        """Used only for testing."""
        with self._lock:
            self._processed.clear()