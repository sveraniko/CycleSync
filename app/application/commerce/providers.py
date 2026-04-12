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
