from datetime import datetime, timezone

from app.application.ops import (
    JOB_STATUS_DEAD_LETTER,
    JOB_STATUS_RETRY_SCHEDULED,
    RetryPolicy,
    classify_retry,
    is_outbox_replayable,
)


def test_retry_scheduling_behavior() -> None:
    policy = RetryPolicy(max_attempts=4, base_delay_seconds=10, backoff_multiplier=2.0, max_delay_seconds=120)
    decision = classify_retry(policy=policy, attempt_count=1, now_utc=datetime(2026, 4, 12, 0, 0, tzinfo=timezone.utc))
    assert decision.status == JOB_STATUS_RETRY_SCHEDULED
    assert decision.attempt_count == 2
    assert decision.next_attempt_at == datetime(2026, 4, 12, 0, 0, 10, tzinfo=timezone.utc)
    assert decision.terminal is False


def test_terminal_failure_transitions_to_dead_letter() -> None:
    policy = RetryPolicy(max_attempts=3)
    decision = classify_retry(policy=policy, attempt_count=2)
    assert decision.status == JOB_STATUS_DEAD_LETTER
    assert decision.attempt_count == 3
    assert decision.next_attempt_at is None
    assert decision.terminal is True


def test_outbox_replay_path_marks_only_recoverable_statuses() -> None:
    assert is_outbox_replayable("failed_retryable") is True
    assert is_outbox_replayable("dead_lettered") is True
    assert is_outbox_replayable("pending") is False
    assert is_outbox_replayable("published") is False
