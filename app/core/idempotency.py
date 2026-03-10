import threading
from cachetools import TTLCache


class IdempotencyGuard:
    """
    Thread-safe in-memory idempotency guard with TTL.

    Keys expire automatically after ttl_seconds.
    """

    def __init__(self, ttl_seconds: int = 24 * 60 * 60, maxsize: int = 100_000):
        """Initialize the idempotency cache with TTL expiration and maximum key capacity."""
        self._lock = threading.Lock()
        self._processed = TTLCache(maxsize=maxsize, ttl=ttl_seconds)

    def is_processed(self, control_id: str) -> bool:
        """Return True if the given message control ID is currently marked as processed."""
        with self._lock:
            return control_id in self._processed

    def mark_processed(self, control_id: str) -> None:
        """Mark the given message control ID as processed in the TTL cache."""
        with self._lock:
            self._processed[control_id] = True

    def mark_if_new(self, control_id: str) -> bool:
        """
        Atomically check whether a control ID was seen and mark it if not.

        Returns True if newly marked, False if already present.
        """
        with self._lock:
            if control_id in self._processed:
                return False
            self._processed[control_id] = True
            return True

    def unmark(self, control_id: str) -> None:
        """Remove a control ID from the processed cache to allow reprocessing if needed."""
        with self._lock:
            self._processed.pop(control_id, None)

    def clear(self) -> None:
        """Clear all tracked control IDs from the idempotency cache."""
        with self._lock:
            self._processed.clear()