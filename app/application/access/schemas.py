from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


ENTITLEMENT_CODES = {
    "bot_access",
    "calculation_access",
    "active_protocol_access",
    "reminders_access",
    "adherence_access",
    "ai_triage_access",
    "expert_case_access",
}

ACTIVE_GRANT_STATUSES = {"active"}
TERMINAL_GRANT_STATUSES = {"expired", "revoked", "consumed"}
ACCESS_KEY_STATUSES = {"active", "disabled", "exhausted", "expired"}
ACCESS_KEY_REDEMPTION_RESULT_STATUSES = {"succeeded", "failed"}


@dataclass(slots=True)
class EntitlementGrantView:
    grant_id: UUID
    user_id: str
    entitlement_code: str
    grant_status: str
    granted_at: datetime
    expires_at: datetime | None
    granted_by_source: str
    source_ref: str | None
    revoked_at: datetime | None
    notes: str | None


@dataclass(slots=True)
class EntitlementDecision:
    allowed: bool
    reason_code: str
    entitlement_code: str
    grant_source: str | None
    expires_at: datetime | None
    grant_id: UUID | None


@dataclass(slots=True)
class EntitlementGrantCreate:
    user_id: str
    entitlement_code: str
    granted_by_source: str
    expires_at: datetime | None = None
    source_ref: str | None = None
    notes: str | None = None


@dataclass(slots=True)
class EntitlementRevokeRequest:
    user_id: str
    entitlement_code: str
    revoked_by_source: str
    reason: str | None = None
    source_ref: str | None = None


@dataclass(slots=True)
class AccessKeyEntitlementTemplate:
    entitlement_code: str
    grant_duration_days: int | None = None
    grant_status_template: str | None = None


@dataclass(slots=True)
class AccessKeyCreate:
    key_code: str
    max_redemptions: int
    expires_at: datetime | None
    created_by_source: str
    notes: str | None = None
    entitlements: tuple[AccessKeyEntitlementTemplate, ...] = ()


@dataclass(slots=True)
class AccessKeyView:
    key_id: UUID
    key_code: str
    status: str
    max_redemptions: int
    redeemed_count: int
    expires_at: datetime | None
    created_by_source: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    entitlements: tuple[AccessKeyEntitlementTemplate, ...] = ()


@dataclass(slots=True)
class AccessKeyRedemptionView:
    redemption_id: UUID
    access_key_id: UUID
    user_id: str
    redeemed_at: datetime
    result_status: str
    result_reason_code: str | None
    created_grant_ids: tuple[UUID, ...] = ()


@dataclass(slots=True)
class AccessKeyRedemptionResult:
    ok: bool
    reason_code: str
    key_status: str
    granted_entitlements: tuple[EntitlementGrantView, ...] = ()
