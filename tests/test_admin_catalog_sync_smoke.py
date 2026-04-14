import asyncio
from types import SimpleNamespace

from app.application.catalog.admin_sync import CatalogAdminRunSummary
from app.bots.handlers.admin import (
    on_catalog_gsheets_apply,
    on_catalog_search_rebuild,
    on_catalog_sync_panel,
    on_catalog_xlsx_apply,
    on_catalog_xlsx_validate,
)


class FakeState:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def get_data(self):
        return dict(self.data)


class FakeMessage:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(id=1)
        self.bot = SimpleNamespace(edit_message_text=self._edit_message_text)
        self.answers: list[dict] = []

    async def _edit_message_text(self, **kwargs):
        return SimpleNamespace(message_id=kwargs["message_id"])

    async def answer(self, text, reply_markup=None, parse_mode=None):
        self.answers.append({"text": text, "reply_markup": reply_markup, "parse_mode": parse_mode})
        return SimpleNamespace(message_id=999)


class FakeCallback:
    def __init__(self, user_id: int) -> None:
        self.message = FakeMessage()
        self.from_user = SimpleNamespace(id=user_id)
        self.answer_calls: list[dict] = []

    async def answer(self, text=None, show_alert=False):
        self.answer_calls.append({"text": text, "show_alert": show_alert})


class FakeCatalogAdminService:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.gsheets_ok = False

    def get_default_workbook_path(self) -> str:
        return "docs/medical_v2.xlsx"

    def gsheets_is_configured(self) -> tuple[bool, str]:
        if self.gsheets_ok:
            return True, "ok"
        return False, "Google Sheets missing config"

    def validate_workbook(self, workbook_path=None) -> CatalogAdminRunSummary:
        self.calls.append("validate")
        return CatalogAdminRunSummary(
            source_type="xlsx",
            mode="validate",
            status="success",
            timestamp="2026-04-14T00:00:00+00:00",
            message="validated",
            counts={"rows_total": 2},
        )

    async def run_xlsx_ingest_apply(self) -> CatalogAdminRunSummary:
        self.calls.append("xlsx_apply")
        return CatalogAdminRunSummary(
            source_type="xlsx",
            mode="apply",
            status="success",
            timestamp="2026-04-14T00:00:00+00:00",
            message="applied",
            counts={"created": 1},
        )

    async def run_gsheets_sync_apply(self) -> CatalogAdminRunSummary:
        self.calls.append("gsheets_apply")
        return CatalogAdminRunSummary(
            source_type="gsheets",
            mode="apply",
            status="failed",
            timestamp="2026-04-14T00:00:00+00:00",
            message="Google Sheets missing config",
            counts={},
        )

    async def rebuild_search(self) -> CatalogAdminRunSummary:
        self.calls.append("search_rebuild")
        return CatalogAdminRunSummary(
            source_type="search_rebuild",
            mode="apply",
            status="success",
            timestamp="2026-04-14T00:00:00+00:00",
            message="rebuilt",
            counts={"indexed_documents": 10},
        )


def test_non_admin_cannot_access_catalog_sync_panel() -> None:
    async def runner() -> None:
        callback = FakeCallback(user_id=999)
        await on_catalog_sync_panel(callback=callback, state=FakeState(), admin_ids=(1,))
        assert callback.answer_calls[-1]["show_alert"] is True
        assert callback.message.answers == []

    asyncio.run(runner())


def test_admin_can_open_catalog_sync_panel() -> None:
    async def runner() -> None:
        callback = FakeCallback(user_id=1)
        service = FakeCatalogAdminService()
        await on_catalog_sync_panel(
            callback=callback,
            state=FakeState(),
            admin_ids=(1,),
            catalog_admin_service=service,
        )
        assert callback.message.answers
        assert "Catalog sync" in callback.message.answers[0]["text"]

    asyncio.run(runner())


def test_validate_dry_run_action_wiring_smoke() -> None:
    async def runner() -> None:
        callback = FakeCallback(user_id=1)
        service = FakeCatalogAdminService()
        await on_catalog_xlsx_validate(
            callback=callback,
            state=FakeState(),
            admin_ids=(1,),
            catalog_admin_service=service,
        )
        assert "validate" in service.calls
        assert "mode: <code>validate</code>" in callback.message.answers[0]["text"]

    asyncio.run(runner())


def test_apply_ingest_action_wiring_smoke() -> None:
    async def runner() -> None:
        callback = FakeCallback(user_id=1)
        service = FakeCatalogAdminService()
        await on_catalog_xlsx_apply(
            callback=callback,
            state=FakeState(),
            admin_ids=(1,),
            catalog_admin_service=service,
        )
        assert "xlsx_apply" in service.calls
        assert "mode: <code>apply</code>" in callback.message.answers[0]["text"]

    asyncio.run(runner())


def test_gsheets_missing_config_behavior() -> None:
    async def runner() -> None:
        callback = FakeCallback(user_id=1)
        service = FakeCatalogAdminService()
        await on_catalog_gsheets_apply(
            callback=callback,
            state=FakeState(),
            admin_ids=(1,),
            catalog_admin_service=service,
        )
        assert "gsheets_apply" in service.calls
        assert "Google Sheets missing config" in callback.message.answers[0]["text"]

    asyncio.run(runner())


def test_rebuild_search_action_wiring_smoke() -> None:
    async def runner() -> None:
        callback = FakeCallback(user_id=1)
        service = FakeCatalogAdminService()
        await on_catalog_search_rebuild(
            callback=callback,
            state=FakeState(),
            admin_ids=(1,),
            catalog_admin_service=service,
        )
        assert "search_rebuild" in service.calls
        assert "indexed_documents" in callback.message.answers[0]["text"]

    asyncio.run(runner())


def test_last_run_summary_rendering_after_action() -> None:
    async def runner() -> None:
        callback = FakeCallback(user_id=1)
        service = FakeCatalogAdminService()
        admin_config = SimpleNamespace(last_catalog_operation=None)
        await on_catalog_xlsx_validate(
            callback=callback,
            state=FakeState(),
            admin_ids=(1,),
            admin_config=admin_config,
            catalog_admin_service=service,
        )
        callback2 = FakeCallback(user_id=1)
        await on_catalog_sync_panel(
            callback=callback2,
            state=FakeState(),
            admin_ids=(1,),
            admin_config=admin_config,
            catalog_admin_service=service,
        )
        assert "source: <code>xlsx</code>" in callback2.message.answers[0]["text"]
        assert "status: <b>success</b>" in callback2.message.answers[0]["text"]

    asyncio.run(runner())
