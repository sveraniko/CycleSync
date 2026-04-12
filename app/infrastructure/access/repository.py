from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.access.repository import AccessRepository
from app.application.access.schemas import EntitlementGrantCreate, EntitlementGrantView
from app.domain.models.access import EntitlementGrant
from app.domain.models.ops import OutboxEvent


class SqlAlchemyAccessRepository(AccessRepository):
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory

    async def get_active_grant(self, *, user_id: str, entitlement_code: str) -> EntitlementGrantView | None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(EntitlementGrant)
                .where(
                    EntitlementGrant.user_id == user_id,
                    EntitlementGrant.entitlement_code == entitlement_code,
                    EntitlementGrant.grant_status == "active",
                )
                .order_by(EntitlementGrant.granted_at.desc())
            )
            return self._to_view(row) if row else None

    async def expire_grant(self, *, grant_id, now_utc: datetime) -> None:
        async with self.session_factory() as session:
            row = await session.scalar(select(EntitlementGrant).where(EntitlementGrant.id == grant_id))
            if row is None or row.grant_status != "active":
                return
            row.grant_status = "expired"
            row.revoked_at = now_utc
            session.add(row)
            await session.commit()

    async def create_grant(self, request: EntitlementGrantCreate, *, now_utc: datetime) -> EntitlementGrantView:
        async with self.session_factory() as session:
            row = EntitlementGrant(
                user_id=request.user_id,
                entitlement_code=request.entitlement_code,
                grant_status="active",
                granted_at=now_utc,
                expires_at=request.expires_at,
                granted_by_source=request.granted_by_source,
                source_ref=request.source_ref,
                notes=request.notes,
                revoked_at=None,
                revoked_reason=None,
                replaced_by_grant_id=None,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_view(row)

    async def revoke_active_grants(self, *, user_id: str, entitlement_code: str, revoked_by_source: str, now_utc: datetime, reason: str | None, source_ref: str | None) -> int:
        async with self.session_factory() as session:
            rows = list(
                await session.scalars(
                    select(EntitlementGrant).where(
                        EntitlementGrant.user_id == user_id,
                        EntitlementGrant.entitlement_code == entitlement_code,
                        EntitlementGrant.grant_status == "active",
                    )
                )
            )
            for row in rows:
                row.grant_status = "revoked"
                row.revoked_at = now_utc
                row.revoked_reason = reason
                row.notes = row.notes or f"revoked_by={revoked_by_source}"
                if source_ref and row.source_ref is None:
                    row.source_ref = source_ref
                session.add(row)
            await session.commit()
            return len(rows)

    async def list_user_grants(self, *, user_id: str, only_active: bool = False) -> list[EntitlementGrantView]:
        async with self.session_factory() as session:
            stmt = select(EntitlementGrant).where(EntitlementGrant.user_id == user_id)
            if only_active:
                stmt = stmt.where(EntitlementGrant.grant_status == "active")
            stmt = stmt.order_by(EntitlementGrant.granted_at.desc())
            rows = list(await session.scalars(stmt))
            return [self._to_view(row) for row in rows]

    async def enqueue_event(self, *, event_type: str, aggregate_type: str, aggregate_id, payload: dict) -> None:
        async with self.session_factory() as session:
            event = OutboxEvent(
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload_json=payload,
                status="pending",
            )
            session.add(event)
            await session.commit()

    @staticmethod
    def _to_view(row: EntitlementGrant) -> EntitlementGrantView:
        return EntitlementGrantView(
            grant_id=row.id,
            user_id=row.user_id,
            entitlement_code=row.entitlement_code,
            grant_status=row.grant_status,
            granted_at=row.granted_at,
            expires_at=row.expires_at,
            granted_by_source=row.granted_by_source,
            source_ref=row.source_ref,
            revoked_at=row.revoked_at,
            notes=row.notes,
        )
