import threading
from cachetools import TTLCache


class IdempotencyGuard:
    """
    Thread-safe in-memory idempotency guard with TTL.

    Keys expire automatically after ttl_seconds.
    """

    def __init__(self, ttl_seconds: int = 24 * 60 * 60, maxsize: int = 100_000):
        self._lock = threading.Lock()
        self._processed = TTLCache(maxsize=maxsize, ttl=ttl_seconds)

    def is_processed(self, control_id: str) -> bool:
        with self._lock:
            return control_id in self._processed

    def mark_processed(self, control_id: str) -> None:
        with self._lock:
            self._processed[control_id] = True

    def mark_if_new(self, control_id: str) -> bool:
        """
        Atomic check+mark.
        Returns True if newly marked, False if already seen.
        """
        with self._lock:
            if control_id in self._processed:
                return False
            self._processed[control_id] = True
            return True

    def unmark(self, control_id: str) -> None:
        with self._lock:
            self._processed.pop(control_id, None)

    def clear(self) -> None:
        with self._lock:
            self._processed.clear()