from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.ops import (
    JOB_STATUS_DEAD_LETTER,
    JOB_STATUS_QUEUED,
    OUTBOX_STATUS_DEAD_LETTERED,
    OUTBOX_STATUS_FAILED_RETRYABLE,
    OUTBOX_STATUS_PENDING,
)
from app.domain.models.ops import JobRun, OutboxEvent


class SqlAlchemyOpsRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory

    async def create_job_run(
        self,
        *,
        job_name: str,
        status: str = JOB_STATUS_QUEUED,
        started_at: datetime,
        details_json: dict | None = None,
        attempt_count: int = 0,
        max_attempts: int = 4,
    ) -> UUID:
        async with self.session_factory() as session:
            row = JobRun(
                id=uuid4(),
                job_name=job_name,
                status=status,
                started_at=started_at,
                finished_at=None,
                details_json=details_json,
                attempt_count=attempt_count,
                max_attempts=max_attempts,
                next_attempt_at=None,
                last_error=None,
                dead_lettered_at=None,
                replayable=True,
                replayed_from_job_run_id=None,
                created_at=started_at,
                updated_at=started_at,
            )
            session.add(row)
            await session.commit()
            return row.id

    async def update_job_run(
        self,
        *,
        job_run_id: UUID,
        status: str,
        now_utc: datetime,
        attempt_count: int | None = None,
        next_attempt_at: datetime | None = None,
        last_error: str | None = None,
        details_json: dict | None = None,
        dead_lettered_at: datetime | None = None,
        replayed_from_job_run_id: UUID | None = None,
    ) -> None:
        async with self.session_factory() as session:
            row = await session.scalar(select(JobRun).where(JobRun.id == job_run_id))
            if row is None:
                return
            row.status = status
            row.updated_at = now_utc
            if status in {"succeeded", "failed", JOB_STATUS_DEAD_LETTER}:
                row.finished_at = now_utc
            if attempt_count is not None:
                row.attempt_count = attempt_count
            row.next_attempt_at = next_attempt_at
            row.last_error = last_error
            row.dead_lettered_at = dead_lettered_at
            row.replayed_from_job_run_id = replayed_from_job_run_id
            if details_json is not None:
                row.details_json = details_json
            session.add(row)
            await session.commit()

    async def retry_dead_letter_jobs(self, *, job_name: str | None = None, limit: int = 100) -> int:
        async with self.session_factory() as session:
            stmt: Select = (
                select(JobRun)
                .where(JobRun.status == JOB_STATUS_DEAD_LETTER, JobRun.replayable.is_(True))
                .order_by(JobRun.updated_at.asc())
                .limit(limit)
            )
            if job_name:
                stmt = stmt.where(JobRun.job_name == job_name)
            rows = list(await session.scalars(stmt))
            now = datetime.now(timezone.utc)
            for row in rows:
                row.status = JOB_STATUS_QUEUED
                row.next_attempt_at = now
                row.last_error = None
                row.dead_lettered_at = None
                row.updated_at = now
                session.add(row)
            await session.commit()
            return len(rows)

    async def replay_outbox(self, *, aggregate_type: str | None = None, limit: int = 100) -> int:
        async with self.session_factory() as session:
            stmt: Select = (
                select(OutboxEvent)
                .where(OutboxEvent.status.in_([OUTBOX_STATUS_FAILED_RETRYABLE, OUTBOX_STATUS_DEAD_LETTERED]))
                .order_by(OutboxEvent.updated_at.asc())
                .limit(limit)
            )
            if aggregate_type:
                stmt = stmt.where(OutboxEvent.aggregate_type == aggregate_type)
            rows = list(await session.scalars(stmt))
            now = datetime.now(timezone.utc)
            for row in rows:
                row.status = OUTBOX_STATUS_PENDING
                row.next_attempt_at = now
                row.last_error = None
                row.updated_at = now
                session.add(row)
            await session.commit()
            return len(rows)

    async def operational_counts(self) -> dict[str, object]:
        async with self.session_factory() as session:
            job_rows = await session.execute(select(JobRun.job_name, JobRun.status, func.count()).group_by(JobRun.job_name, JobRun.status))
            outbox_rows = await session.execute(select(OutboxEvent.status, func.count()).group_by(OutboxEvent.status))
            oldest_pending = await session.scalar(
                select(func.min(OutboxEvent.created_at)).where(OutboxEvent.status.in_([OUTBOX_STATUS_PENDING, OUTBOX_STATUS_FAILED_RETRYABLE]))
            )
            reminder_dispatch_failures = await session.scalar(
                select(func.count()).select_from(JobRun).where(JobRun.job_name == "reminder_dispatch", JobRun.status.in_(["failed", JOB_STATUS_DEAD_LETTER]))
            )
            triage_failures = await session.scalar(
                select(func.count()).select_from(JobRun).where(JobRun.job_name == "lab_triage_execution", JobRun.status.in_(["failed", JOB_STATUS_DEAD_LETTER]))
            )
            fulfillment_failures = await session.scalar(
                select(func.count()).select_from(JobRun).where(JobRun.job_name == "checkout_fulfillment", JobRun.status.in_(["failed", JOB_STATUS_DEAD_LETTER]))
            )

        lag_seconds = 0
        if oldest_pending is not None:
            lag_seconds = max(0, int((datetime.now(timezone.utc) - oldest_pending).total_seconds()))
        return {
            "job_counts": {
                f"{row[0]}::{row[1]}": int(row[2]) for row in job_rows
            },
            "outbox_counts": {row[0]: int(row[1]) for row in outbox_rows},
            "outbox_pending_lag_seconds": lag_seconds,
            "failed_job_counts": {
                "reminder_dispatch": int(reminder_dispatch_failures or 0),
                "lab_triage_execution": int(triage_failures or 0),
                "checkout_fulfillment": int(fulfillment_failures or 0),
            },
        }
