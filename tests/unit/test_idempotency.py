"""Unit tests for IdempotencyGuard behavior.

These tests verify that processed message IDs are recorded correctly
and that processing state is isolated between different IDs.
"""

from app.core.idempotency import IdempotencyGuard, IDEMPOTENCY_NEW, IDEMPOTENCY_PROCESSING, IDEMPOTENCY_SUCCEEDED


def test_idempotency_marks_processed():
    guard = IdempotencyGuard()

    assert guard.is_processed("123") is False

    guard.mark_processed("123")

    assert guard.is_processed("123") is True


def test_idempotency_isolated_ids():
    guard = IdempotencyGuard()

    guard.mark_processed("123")

    assert guard.is_processed("456") is False


def test_mark_if_new_returns_new_first_time():
    guard = IdempotencyGuard()
    assert guard.mark_if_new("abc") == IDEMPOTENCY_NEW


def test_mark_if_new_returns_processing_while_in_flight():
    guard = IdempotencyGuard()
    guard.mark_if_new("abc")  # moves to PROCESSING
    assert guard.mark_if_new("abc") == IDEMPOTENCY_PROCESSING


def test_mark_if_new_returns_succeeded_after_success():
    guard = IdempotencyGuard()
    guard.mark_if_new("abc")
    guard.mark_succeeded("abc")
    assert guard.mark_if_new("abc") == IDEMPOTENCY_SUCCEEDED


def test_unmark_allows_reprocessing():
    guard = IdempotencyGuard()
    guard.mark_if_new("abc")       # PROCESSING
    guard.unmark("abc")
    assert guard.mark_if_new("abc") == IDEMPOTENCY_NEW


def test_mark_processed_is_treated_as_succeeded():
    """Backward-compat: mark_processed should behave like mark_succeeded."""
    guard = IdempotencyGuard()
    guard.mark_processed("abc")
    assert guard.mark_if_new("abc") == IDEMPOTENCY_SUCCEEDED