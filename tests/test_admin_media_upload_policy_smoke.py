import asyncio
from types import SimpleNamespace
from uuid import UUID

from app.bots.handlers.admin import AdminMediaUploadState, on_media_input


class FakeState:
    def __init__(self) -> None:
        self.data = {"admin_media_product_id": "00000000-0000-0000-0000-000000000001"}
        self.current_state = AdminMediaUploadState.waiting_input

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def set_state(self, value):
        self.current_state = value


class FakeMessage:
    def __init__(self) -> None:
        self.from_user = SimpleNamespace(id=11)
        self.photo = [SimpleNamespace(file_id="abc")]
        self.video = None
        self.animation = None
        self.text = None
        self.chat = SimpleNamespace(id=1)
        self.bot = None
        self.answers: list[dict] = []

    async def answer(self, text, reply_markup=None, parse_mode=None):
        self.answers.append({"text": text, "reply_markup": reply_markup, "parse_mode": parse_mode})
        sent = SimpleNamespace(message_id=1)
        return sent

    async def delete(self):
        return None


class FakeSearchService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def admin_add_media_ref(self, product_id: UUID, ref_url: str, media_kind: str = "external"):
        self.calls.append({"product_id": product_id, "ref_url": ref_url, "media_kind": media_kind})
        return True


def test_existing_upload_flow_still_works_with_policy_controls_present() -> None:
    async def runner() -> None:
        message = FakeMessage()
        state = FakeState()
        service = FakeSearchService()
        await on_media_input(message=message, state=state, search_service=service, admin_ids=(11,))
        assert service.calls
        assert service.calls[0]["ref_url"].startswith("tg-photo:")
        assert state.data.get("admin_media_product_id") is None

    asyncio.run(runner())
