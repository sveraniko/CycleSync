from datetime import datetime, timezone
from uuid import uuid4

from app.application.access.schemas import AccessKeyRedemptionResult, EntitlementGrantView
from app.bots.handlers.access_keys import _render_failure, _render_success


def test_access_key_failure_render_variants() -> None:
    assert "не найден" in _render_failure("access_key_invalid").lower()
    assert "истек" in _render_failure("access_key_expired").lower()


def test_access_key_success_render_smoke() -> None:
    result = AccessKeyRedemptionResult(
        ok=True,
        reason_code="access_key_redeemed",
        key_status="active",
        granted_entitlements=(
            EntitlementGrantView(
                grant_id=uuid4(),
                user_id="tg:1",
                entitlement_code="reminders_access",
                grant_status="active",
                granted_at=datetime(2026, 4, 12, tzinfo=timezone.utc),
                expires_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
                granted_by_source="access_key",
                source_ref="W8-PR2-001",
                revoked_at=None,
                notes=None,
            ),
        ),
    )
    text = _render_success(result)
    assert "Ключ активирован" in text
    assert "Reminders access" in text
