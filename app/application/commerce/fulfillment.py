from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.application.access import AccessEvaluationService, EntitlementGrantCreate
from app.application.commerce.repository import CommerceRepository
from app.application.commerce.schemas import CheckoutFulfillmentView


class CheckoutFulfillmentService:
    def __init__(self, repository: CommerceRepository, access_service: AccessEvaluationService) -> None:
        self.repository = repository
        self.access_service = access_service

    async def fulfill_checkout(self, *, checkout_id: UUID, now_utc: datetime | None = None) -> CheckoutFulfillmentView:
        now = now_utc or datetime.now(timezone.utc)
        state = await self.repository.get_checkout(checkout_id=checkout_id)
        if state is None:
            raise ValueError("checkout_not_found")
        if state.checkout.checkout_status != "completed":
            raise ValueError("checkout_not_completed")

        existing = await self.repository.get_checkout_fulfillment(checkout_id=checkout_id)
        if existing and existing.fulfillment_status == "succeeded":
            return existing

        await self.repository.upsert_checkout_fulfillment(
            checkout_id=checkout_id,
            fulfillment_status="started",
            now_utc=now,
            fulfilled_at=None,
            result_payload={"started_at": now.isoformat()},
            error_code=None,
            error_message=None,
        )
        await self.repository.enqueue_event(
            event_type="checkout_fulfillment_started",
            aggregate_type="checkout",
            aggregate_id=checkout_id,
            payload={"checkout_id": str(checkout_id)},
        )

        try:
            offer_ids = tuple({item.offer_id for item in state.items})
            mappings = await self.repository.list_offer_entitlements(offer_ids=offer_ids)
            entitlements_by_offer: dict[UUID, list] = {}
            for mapping in mappings:
                entitlements_by_offer.setdefault(mapping.offer_id, []).append(mapping)

            grants: list[dict] = []
            for item in state.items:
                offer_entitlements = entitlements_by_offer.get(item.offer_id, [])
                if not offer_entitlements:
                    raise ValueError(f"offer_entitlement_mapping_missing:{item.offer_code}")
                for entitlement in offer_entitlements:
                    expires_at = now + timedelta(days=entitlement.grant_duration_days) if entitlement.grant_duration_days else None
                    grant = await self.access_service.grant(
                        EntitlementGrantCreate(
                            user_id=state.checkout.user_id,
                            entitlement_code=entitlement.entitlement_code,
                            granted_by_source="checkout",
                            source_ref=f"checkout:{checkout_id}:{item.offer_code}:{entitlement.entitlement_code}",
                            expires_at=expires_at,
                            notes=f"checkout_item_id={item.checkout_item_id}",
                        ),
                        now_utc=now,
                    )
                    grants.append(
                        {
                            "offer_code": item.offer_code,
                            "entitlement_code": entitlement.entitlement_code,
                            "grant_id": str(grant.grant_id),
                            "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
                        }
                    )
                    await self.repository.enqueue_event(
                        event_type="offer_entitlement_granted",
                        aggregate_type="checkout",
                        aggregate_id=checkout_id,
                        payload={
                            "offer_code": item.offer_code,
                            "entitlement_code": entitlement.entitlement_code,
                            "grant_id": str(grant.grant_id),
                        },
                    )

            fulfilled = await self.repository.upsert_checkout_fulfillment(
                checkout_id=checkout_id,
                fulfillment_status="succeeded",
                now_utc=now,
                fulfilled_at=now,
                result_payload={"grants": grants},
                error_code=None,
                error_message=None,
            )
            await self.repository.enqueue_event(
                event_type="checkout_fulfillment_succeeded",
                aggregate_type="checkout",
                aggregate_id=checkout_id,
                payload={"checkout_id": str(checkout_id), "granted_count": len(grants)},
            )
            return fulfilled
        except Exception as exc:
            failed = await self.repository.upsert_checkout_fulfillment(
                checkout_id=checkout_id,
                fulfillment_status="failed",
                now_utc=now,
                fulfilled_at=None,
                result_payload={"error": str(exc)},
                error_code="fulfillment_failed",
                error_message=str(exc),
            )
            await self.repository.enqueue_event(
                event_type="checkout_fulfillment_failed",
                aggregate_type="checkout",
                aggregate_id=checkout_id,
                payload={"checkout_id": str(checkout_id), "error": str(exc)},
            )
            raise
