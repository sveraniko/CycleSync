from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.access.repository import AccessRepository
from app.application.access.schemas import (
    AccessKeyCreate,
    AccessKeyEntitlementTemplate,
    AccessKeyRedemptionView,
    AccessKeyView,
    EntitlementGrantCreate,
    EntitlementGrantView,
)
from app.domain.models.access import AccessKey, AccessKeyEntitlement, AccessKeyRedemption, EntitlementGrant
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

    async def create_access_key(self, request: AccessKeyCreate, *, now_utc: datetime) -> AccessKeyView:
        async with self.session_factory() as session:
            row = AccessKey(
                key_code=request.key_code,
                status="active",
                max_redemptions=request.max_redemptions,
                redeemed_count=0,
                expires_at=request.expires_at,
                created_by_source=request.created_by_source,
                notes=request.notes,
                created_at=now_utc,
                updated_at=now_utc,
            )
            session.add(row)
            await session.flush()
            for template in request.entitlements:
                session.add(
                    AccessKeyEntitlement(
                        access_key_id=row.id,
                        entitlement_code=template.entitlement_code,
                        grant_duration_days=template.grant_duration_days,
                        grant_status_template=template.grant_status_template,
                        created_at=now_utc,
                        updated_at=now_utc,
                    )
                )
            await session.commit()
            await session.refresh(row)
            return await self.get_access_key_by_code(key_code=row.key_code)

    async def get_access_key_by_code(self, *, key_code: str) -> AccessKeyView | None:
        async with self.session_factory() as session:
            row = await session.scalar(select(AccessKey).where(AccessKey.key_code == key_code))
            if row is None:
                return None
            entitlements = await self._list_entitlements(session=session, key_id=row.id)
            return self._to_access_key_view(row, entitlements)

    async def update_access_key_status(self, *, key_id: UUID, status: str, now_utc: datetime) -> AccessKeyView | None:
        async with self.session_factory() as session:
            row = await session.scalar(select(AccessKey).where(AccessKey.id == key_id))
            if row is None:
                return None
            row.status = status
            row.updated_at = now_utc
            session.add(row)
            await session.commit()
            await session.refresh(row)
            entitlements = await self._list_entitlements(session=session, key_id=row.id)
            return self._to_access_key_view(row, entitlements)

    async def increment_access_key_redemption_count(self, *, key_id: UUID, now_utc: datetime) -> AccessKeyView | None:
        async with self.session_factory() as session:
            row = await session.scalar(select(AccessKey).where(AccessKey.id == key_id))
            if row is None:
                return None
            row.redeemed_count += 1
            row.updated_at = now_utc
            session.add(row)
            await session.commit()
            await session.refresh(row)
            entitlements = await self._list_entitlements(session=session, key_id=row.id)
            return self._to_access_key_view(row, entitlements)

    async def list_key_entitlements(self, *, key_id: UUID) -> tuple[AccessKeyEntitlementTemplate, ...]:
        async with self.session_factory() as session:
            return await self._list_entitlements(session=session, key_id=key_id)

    async def find_successful_redemption(self, *, key_id: UUID, user_id: str) -> AccessKeyRedemptionView | None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(AccessKeyRedemption)
                .where(
                    AccessKeyRedemption.access_key_id == key_id,
                    AccessKeyRedemption.user_id == user_id,
                    AccessKeyRedemption.result_status == "succeeded",
                )
                .order_by(AccessKeyRedemption.redeemed_at.desc())
            )
            return self._to_redemption_view(row) if row else None

    async def create_access_key_redemption(
        self,
        *,
        key_id: UUID,
        user_id: str,
        redeemed_at: datetime,
        result_status: str,
        result_reason_code: str | None,
        created_grant_ids: tuple[UUID, ...],
    ) -> AccessKeyRedemptionView:
        async with self.session_factory() as session:
            row = AccessKeyRedemption(
                access_key_id=key_id,
                user_id=user_id,
                redeemed_at=redeemed_at,
                result_status=result_status,
                result_reason_code=result_reason_code,
                created_grant_ids=[str(grant_id) for grant_id in created_grant_ids] or None,
                created_at=redeemed_at,
                updated_at=redeemed_at,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_redemption_view(row)

    async def list_access_key_redemptions(self, *, key_id: UUID) -> list[AccessKeyRedemptionView]:
        async with self.session_factory() as session:
            rows = list(
                await session.scalars(
                    select(AccessKeyRedemption)
                    .where(AccessKeyRedemption.access_key_id == key_id)
                    .order_by(AccessKeyRedemption.redeemed_at.desc())
                )
            )
            return [self._to_redemption_view(row) for row in rows]

    @staticmethod
    async def _list_entitlements(*, session, key_id: UUID) -> tuple[AccessKeyEntitlementTemplate, ...]:
        rows = list(
            await session.scalars(
                select(AccessKeyEntitlement)
                .where(AccessKeyEntitlement.access_key_id == key_id)
                .order_by(AccessKeyEntitlement.entitlement_code.asc())
            )
        )
        return tuple(
            AccessKeyEntitlementTemplate(
                entitlement_code=row.entitlement_code,
                grant_duration_days=row.grant_duration_days,
                grant_status_template=row.grant_status_template,
            )
            for row in rows
        )

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

    @staticmethod
    def _to_access_key_view(row: AccessKey, entitlements: tuple[AccessKeyEntitlementTemplate, ...]) -> AccessKeyView:
        return AccessKeyView(
            key_id=row.id,
            key_code=row.key_code,
            status=row.status,
            max_redemptions=row.max_redemptions,
            redeemed_count=row.redeemed_count,
            expires_at=row.expires_at,
            created_by_source=row.created_by_source,
            notes=row.notes,
            created_at=row.created_at,
            updated_at=row.updated_at,
            entitlements=entitlements,
        )

    @staticmethod
    def _to_redemption_view(row: AccessKeyRedemption) -> AccessKeyRedemptionView:
        parsed_ids = tuple(UUID(value) for value in (row.created_grant_ids or []))
        return AccessKeyRedemptionView(
            redemption_id=row.id,
            access_key_id=row.access_key_id,
            user_id=row.user_id,
            redeemed_at=row.redeemed_at,
            result_status=row.result_status,
            result_reason_code=row.result_reason_code,
            created_grant_ids=parsed_ids,
        )
