from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.application.commerce.schemas import CheckoutStateView


@dataclass(slots=True)
class ProviderInitResult:
    provider_reference: str | None
    session_status: str
    session_payload: dict


@dataclass(slots=True)
class ProviderSettleResult:
    provider_reference: str | None
    status: str
    reason_code: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class PaymentProviderGateway:
    provider_code: str

    async def initialize_checkout(self, *, checkout: CheckoutStateView, now_utc: datetime) -> ProviderInitResult:
        raise NotImplementedError

    async def confirm_payment(self, *, checkout: CheckoutStateView, now_utc: datetime, metadata: dict | None = None) -> ProviderSettleResult:
        raise NotImplementedError

    def diagnostics(self) -> dict[str, object]:
        raise NotImplementedError


class FreePaymentProvider(PaymentProviderGateway):
    provider_code = "free"

    async def initialize_checkout(self, *, checkout: CheckoutStateView, now_utc: datetime) -> ProviderInitResult:
        return ProviderInitResult(
            provider_reference=f"free_init_{checkout.checkout.checkout_id}",
            session_status="initialized",
            session_payload={
                "checkout_id": str(checkout.checkout.checkout_id),
                "provider": self.provider_code,
                "mode": "internal",
            },
        )

    async def confirm_payment(self, *, checkout: CheckoutStateView, now_utc: datetime, metadata: dict | None = None) -> ProviderSettleResult:
        reason_code = (metadata or {}).get("reason_code", "manual_free_checkout")
        return ProviderSettleResult(
            provider_reference=f"free_settled_{uuid4()}",
            status="succeeded",
            reason_code=reason_code,
        )

    def diagnostics(self) -> dict[str, object]:
        return {
            "provider_code": self.provider_code,
            "kind": "internal",
            "supports_live_money": False,
        }


class PaymentProviderRegistry:
    def __init__(self, providers: dict[str, PaymentProviderGateway], declared_providers: tuple[str, ...]) -> None:
        self.providers = providers
        self.declared_providers = declared_providers

    def get(self, provider_code: str) -> PaymentProviderGateway | None:
        return self.providers.get(provider_code)

    def diagnostics(self) -> dict[str, dict[str, object]]:
        summary: dict[str, dict[str, object]] = {}
        for code in self.declared_providers:
            provider = self.providers.get(code)
            summary[code] = {
                "enabled": provider is not None,
                "implementation": provider.diagnostics() if provider else None,
            }
        return summary


class StarsPaymentProvider(PaymentProviderGateway):
    provider_code = "stars"

    def __init__(self, *, bot_username: str) -> None:
        self.bot_username = bot_username.strip().lstrip("@")

    async def initialize_checkout(self, *, checkout: CheckoutStateView, now_utc: datetime) -> ProviderInitResult:
        session_id = f"stars_{checkout.checkout.checkout_id.hex[:12]}_{int(now_utc.timestamp())}"
        action_url = f"https://t.me/{self.bot_username}?start=stars_checkout_{checkout.checkout.checkout_id}"
        return ProviderInitResult(
            provider_reference=action_url,
            session_status="initiated",
            session_payload={
                "provider": self.provider_code,
                "session_id": session_id,
                "checkout_id": str(checkout.checkout.checkout_id),
                "currency": "XTR",
                "amount": checkout.checkout.total_amount,
                "action_url": action_url,
                "instruction": "Open payment link in Telegram and complete Stars purchase.",
            },
        )

    async def confirm_payment(
        self,
        *,
        checkout: CheckoutStateView,
        now_utc: datetime,
        metadata: dict | None = None,
    ) -> ProviderSettleResult:
        payload = metadata or {}
        outcome = str(payload.get("outcome", "succeeded")).lower()
        reference = payload.get("provider_reference")
        if reference is None:
            reference = f"stars_confirm_{checkout.checkout.checkout_id.hex[:12]}_{int(now_utc.timestamp())}"
        if outcome == "succeeded":
            return ProviderSettleResult(
                provider_reference=str(reference),
                status="succeeded",
                reason_code="telegram_stars_paid",
            )
        if outcome in {"cancelled", "expired", "failed", "pending"}:
            error_code = payload.get("error_code")
            if outcome == "failed" and not error_code:
                error_code = "telegram_stars_failed"
            return ProviderSettleResult(
                provider_reference=str(reference),
                status=outcome,
                reason_code=payload.get("reason_code"),
                error_code=error_code,
                error_message=payload.get("error_message"),
            )
        return ProviderSettleResult(
            provider_reference=str(reference),
            status="failed",
            error_code="invalid_provider_outcome",
            error_message=f"unsupported_outcome:{outcome}",
        )

    def diagnostics(self) -> dict[str, object]:
        return {
            "provider_code": self.provider_code,
            "kind": "telegram_stars",
            "supports_live_money": True,
            "bot_username_configured": bool(self.bot_username),
        }
