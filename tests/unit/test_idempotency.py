from app.core.idempotency import IdempotencyGuard


def test_idempotency_marks_processed():
    guard = IdempotencyGuard()

    assert guard.is_processed("123") is False

    guard.mark_processed("123")

    assert guard.is_processed("123") is True


def test_idempotency_isolated_ids():
    guard = IdempotencyGuard()

    guard.mark_processed("123")

    assert guard.is_processed("456") is False