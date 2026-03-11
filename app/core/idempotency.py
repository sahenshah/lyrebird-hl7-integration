import threading
from cachetools import TTLCache

# State constants for mark_if_new / mark_succeeded
IDEMPOTENCY_NEW = "new"
IDEMPOTENCY_PROCESSING = "processing"
IDEMPOTENCY_SUCCEEDED = "succeeded"


class IdempotencyGuard:
    """
    Thread-safe in-memory idempotency guard with TTL.

    Keys expire automatically after ttl_seconds.

    States
    ------
    IDEMPOTENCY_NEW        - control ID was not present; caller must process it.
    IDEMPOTENCY_PROCESSING - a prior attempt is still in-flight; caller should NACK.
    IDEMPOTENCY_SUCCEEDED  - already processed successfully; caller should ACK (duplicate).
    """

    def __init__(self, ttl_seconds: int = 24 * 60 * 60, maxsize: int = 100_000):
        """Initialize the idempotency cache with TTL expiration and maximum key capacity."""
        self._lock = threading.Lock()
        self._processed = TTLCache(maxsize=maxsize, ttl=ttl_seconds)

    def is_processed(self, control_id: str) -> bool:
        """Return True if the given message control ID is currently in the cache (any state)."""
        with self._lock:
            return control_id in self._processed

    def mark_processed(self, control_id: str) -> None:
        """Mark the given message control ID as succeeded (backward-compatible helper)."""
        with self._lock:
            self._processed[control_id] = IDEMPOTENCY_SUCCEEDED

    def mark_if_new(self, control_id: str) -> str:
        """
        Atomically check a control ID and transition its state.

        - If absent          → stored as IDEMPOTENCY_PROCESSING; returns IDEMPOTENCY_NEW.
        - If PROCESSING      → returns IDEMPOTENCY_PROCESSING (in-flight duplicate).
        - If SUCCEEDED       → returns IDEMPOTENCY_SUCCEEDED  (successful duplicate).
        """
        with self._lock:
            status = self._processed.get(control_id)
            if status is None:
                self._processed[control_id] = IDEMPOTENCY_PROCESSING
                return IDEMPOTENCY_NEW
            return status

    def mark_succeeded(self, control_id: str) -> None:
        """Transition a control ID from PROCESSING → SUCCEEDED after a successful API call."""
        with self._lock:
            self._processed[control_id] = IDEMPOTENCY_SUCCEEDED

    def unmark(self, control_id: str) -> None:
        """Remove a control ID from the cache to allow reprocessing (used on failure)."""
        with self._lock:
            self._processed.pop(control_id, None)

    def clear(self) -> None:
        """Clear all tracked control IDs from the idempotency cache."""
        with self._lock:
            self._processed.clear()