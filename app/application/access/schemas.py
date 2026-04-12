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
