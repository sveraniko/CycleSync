from dataclasses import dataclass
from datetime import datetime


NEGATIVE_ACTIONS = {"skip", "expired"}


@dataclass(slots=True)
class AdherenceCounterSnapshot:
    completed_count: int
    skipped_count: int
    snoozed_count: int
    expired_count: int
    total_actionable_count: int
    completion_rate: float
    skip_rate: float
    expiry_rate: float
    last_action_at: datetime | None
    consecutive_negative_count: int
    consecutive_expiry_count: int


@dataclass(slots=True)
class IntegrityClassification:
    integrity_state: str
    reason_code: str | None
    detail_payload: dict


def compute_consecutive_negative_windows(actions_desc: list[str]) -> tuple[int, int]:
    consecutive_negative = 0
    consecutive_expired = 0
    for action in actions_desc:
        if action == "snooze":
            continue
        if action in NEGATIVE_ACTIONS:
            consecutive_negative += 1
            if action == "expired":
                consecutive_expired += 1
            else:
                consecutive_expired = 0
            continue
        break
    return consecutive_negative, consecutive_expired


def classify_protocol_integrity(snapshot: AdherenceCounterSnapshot) -> IntegrityClassification:
    actionable = snapshot.total_actionable_count
    explanation = {
        "completed_count": snapshot.completed_count,
        "skipped_count": snapshot.skipped_count,
        "snoozed_count": snapshot.snoozed_count,
        "expired_count": snapshot.expired_count,
        "total_actionable_count": actionable,
        "completion_rate": snapshot.completion_rate,
        "skip_rate": snapshot.skip_rate,
        "expiry_rate": snapshot.expiry_rate,
        "consecutive_negative_count": snapshot.consecutive_negative_count,
        "consecutive_expiry_count": snapshot.consecutive_expiry_count,
    }

    if snapshot.consecutive_expiry_count >= 3:
        return IntegrityClassification("broken", "consecutive_expiries", explanation)
    if snapshot.consecutive_negative_count >= 4:
        return IntegrityClassification("broken", "consecutive_negative_events", explanation)
    if actionable >= 4 and snapshot.expiry_rate >= 0.50:
        return IntegrityClassification("broken", "high_expiry_rate", explanation)
    if actionable >= 6 and snapshot.completion_rate < 0.40:
        return IntegrityClassification("broken", "low_completion_ratio", explanation)

    if snapshot.consecutive_negative_count >= 3:
        return IntegrityClassification("degraded", "mixed_noncompliance_pattern", explanation)
    if actionable >= 4 and snapshot.skip_rate >= 0.50:
        return IntegrityClassification("degraded", "high_skip_rate", explanation)
    if actionable >= 3 and snapshot.expiry_rate >= 0.34:
        return IntegrityClassification("degraded", "elevated_expiry_rate", explanation)
    if actionable >= 5 and snapshot.completion_rate < 0.60:
        return IntegrityClassification("degraded", "low_completion_ratio", explanation)

    if snapshot.consecutive_negative_count >= 2:
        return IntegrityClassification("watch", "recent_misses", explanation)
    if actionable >= 4 and snapshot.skip_rate >= 0.30:
        return IntegrityClassification("watch", "rising_skip_rate", explanation)
    if actionable >= 4 and snapshot.completion_rate < 0.75:
        return IntegrityClassification("watch", "soft_completion_drop", explanation)
    if snapshot.snoozed_count >= 3:
        return IntegrityClassification("watch", "high_snooze_volume", explanation)

    return IntegrityClassification("healthy", None, explanation)
