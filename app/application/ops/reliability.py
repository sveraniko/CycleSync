from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


JOB_STATUS_QUEUED = "queued"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_SUCCEEDED = "succeeded"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_RETRY_SCHEDULED = "retry_scheduled"
JOB_STATUS_DEAD_LETTER = "dead_letter"

OUTBOX_STATUS_PENDING = "pending"
OUTBOX_STATUS_IN_PROGRESS = "in_progress"
OUTBOX_STATUS_PUBLISHED = "published"
OUTBOX_STATUS_FAILED_RETRYABLE = "failed_retryable"
OUTBOX_STATUS_DEAD_LETTERED = "dead_lettered"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: int = 15
    backoff_multiplier: float = 2.0
    max_delay_seconds: int = 900

    def compute_delay_seconds(self, *, attempt_number: int) -> int:
        if attempt_number <= 1:
            return 0
        exponent = max(0, attempt_number - 2)
        delay = int(self.base_delay_seconds * (self.backoff_multiplier**exponent))
        return min(max(delay, self.base_delay_seconds), self.max_delay_seconds)

    def next_attempt_at(self, *, attempt_number: int, now_utc: datetime | None = None) -> datetime:
        now = now_utc or datetime.now(timezone.utc)
        return now + timedelta(seconds=self.compute_delay_seconds(attempt_number=attempt_number))


@dataclass(frozen=True)
class RetryDecision:
    status: str
    attempt_count: int
    next_attempt_at: datetime | None
    terminal: bool


def classify_retry(*, policy: RetryPolicy, attempt_count: int, now_utc: datetime | None = None) -> RetryDecision:
    next_attempt = attempt_count + 1
    if next_attempt >= policy.max_attempts:
        return RetryDecision(
            status=JOB_STATUS_DEAD_LETTER,
            attempt_count=next_attempt,
            next_attempt_at=None,
            terminal=True,
        )
    return RetryDecision(
        status=JOB_STATUS_RETRY_SCHEDULED,
        attempt_count=next_attempt,
        next_attempt_at=policy.next_attempt_at(attempt_number=next_attempt, now_utc=now_utc),
        terminal=False,
    )


def is_outbox_replayable(status: str) -> bool:
    return status in {OUTBOX_STATUS_FAILED_RETRYABLE, OUTBOX_STATUS_DEAD_LETTERED}
