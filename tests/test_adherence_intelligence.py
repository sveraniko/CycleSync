from datetime import datetime, timezone

from app.application.reminders.adherence import (
    AdherenceCounterSnapshot,
    classify_protocol_integrity,
    compute_consecutive_negative_windows,
)


def _snapshot(
    *,
    completed: int,
    skipped: int,
    snoozed: int,
    expired: int,
    consecutive_negative: int,
    consecutive_expired: int,
) -> AdherenceCounterSnapshot:
    actionable = completed + skipped + expired
    return AdherenceCounterSnapshot(
        completed_count=completed,
        skipped_count=skipped,
        snoozed_count=snoozed,
        expired_count=expired,
        total_actionable_count=actionable,
        completion_rate=(completed / actionable) if actionable else 0.0,
        skip_rate=(skipped / actionable) if actionable else 0.0,
        expiry_rate=(expired / actionable) if actionable else 0.0,
        last_action_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
        consecutive_negative_count=consecutive_negative,
        consecutive_expiry_count=consecutive_expired,
    )


def test_adherence_summary_recompute_from_raw_events() -> None:
    actions = ["done", "skip", "expired", "done", "snooze", "skip"]
    completed = sum(1 for action in actions if action == "done")
    skipped = sum(1 for action in actions if action == "skip")
    expired = sum(1 for action in actions if action == "expired")
    snoozed = sum(1 for action in actions if action == "snooze")
    assert completed == 2
    assert skipped == 2
    assert expired == 1
    assert snoozed == 1


def test_healthy_classification() -> None:
    result = classify_protocol_integrity(
        _snapshot(
            completed=8,
            skipped=1,
            snoozed=1,
            expired=0,
            consecutive_negative=0,
            consecutive_expired=0,
        )
    )
    assert result.integrity_state == "healthy"
    assert result.reason_code is None


def test_watch_classification() -> None:
    result = classify_protocol_integrity(
        _snapshot(
            completed=4,
            skipped=2,
            snoozed=0,
            expired=0,
            consecutive_negative=2,
            consecutive_expired=0,
        )
    )
    assert result.integrity_state == "watch"
    assert result.reason_code == "recent_misses"


def test_degraded_classification() -> None:
    result = classify_protocol_integrity(
        _snapshot(
            completed=3,
            skipped=3,
            snoozed=1,
            expired=1,
            consecutive_negative=3,
            consecutive_expired=1,
        )
    )
    assert result.integrity_state == "degraded"
    assert result.reason_code in {"mixed_noncompliance_pattern", "high_skip_rate"}


def test_broken_classification() -> None:
    result = classify_protocol_integrity(
        _snapshot(
            completed=1,
            skipped=1,
            snoozed=0,
            expired=4,
            consecutive_negative=4,
            consecutive_expired=3,
        )
    )
    assert result.integrity_state == "broken"
    assert result.reason_code == "consecutive_expiries"


def test_consecutive_miss_rule() -> None:
    consecutive_negative, consecutive_expired = compute_consecutive_negative_windows(
        ["expired", "skip", "skip", "done", "expired"]
    )
    assert consecutive_negative == 3
    assert consecutive_expired == 0


def test_snooze_does_not_hard_break_protocol() -> None:
    result = classify_protocol_integrity(
        _snapshot(
            completed=0,
            skipped=0,
            snoozed=4,
            expired=0,
            consecutive_negative=0,
            consecutive_expired=0,
        )
    )
    assert result.integrity_state == "watch"
    assert result.reason_code == "high_snooze_volume"


def test_integrity_reason_codes_present_for_non_healthy() -> None:
    result = classify_protocol_integrity(
        _snapshot(
            completed=2,
            skipped=3,
            snoozed=0,
            expired=1,
            consecutive_negative=3,
            consecutive_expired=1,
        )
    )
    assert result.integrity_state in {"watch", "degraded", "broken"}
    assert result.reason_code is not None
