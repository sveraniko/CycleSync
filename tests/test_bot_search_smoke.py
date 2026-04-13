import asyncio
from types import SimpleNamespace
from uuid import UUID

from app.application.search.schemas import OpenCard, SearchResponse, SearchResultItem
from app.bots.handlers.draft import on_add_to_draft
from app.bots.handlers.search import (
    SEARCH_STATE_KEY,
    PAGE_SIZE,
    _render_product_card,
    _render_search_panel,
    build_card_actions,
    build_results_actions,
    on_back_to_results,
    on_search_page,
    search_entrypoint,
)


class FakeFSMContext:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def get_data(self):
        return dict(self.data)

    async def set_data(self, data):
        self.data = dict(data)


class FakeBot:
    def __init__(self) -> None:
        self.edits: list[dict[str, object]] = []

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)
        return SimpleNamespace(message_id=kwargs["message_id"])


class FakeMessage:
    def __init__(self, text: str = "sust") -> None:
        self.bot = FakeBot()
        self.chat = SimpleNamespace(id=42)
        self.from_user = SimpleNamespace(id=11)
        self.answers: list[dict[str, object]] = []
        self.text = text

    async def answer(self, text, reply_markup=None, parse_mode=None):
        sent = FakeMessage()
        sent_id = 1000 + len(self.answers)
        sent.message_id = sent_id
        self.answers.append(
            {"text": text, "reply_markup": reply_markup, "parse_mode": parse_mode, "sent": sent}
        )
        return sent


class FakeCallback:
    def __init__(self, message: FakeMessage, data: str) -> None:
        self.message = message
        self.data = data
        self.from_user = SimpleNamespace(id=11)
        self.answers: list[dict[str, object]] = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append({"text": text, "show_alert": show_alert})


class FakeSearchService:
    def __init__(self, total: int = 6) -> None:
        self.total = total
        self.calls: list[dict[str, object]] = []

    async def search_products(self, query: str, user_id: str | None, limit: int = 5, offset: int = 0, source: str = "text"):
        self.calls.append({"query": query, "user_id": user_id, "limit": limit, "offset": offset})
        start = offset
        end = min(self.total, start + limit)
        items = [
            SearchResultItem(
                document_id=f"d-{i}",
                product_id=UUID(f"00000000-0000-0000-0000-{i:012d}"),
                product_name=f"Prod {i}",
                brand="BrandX",
                composition_summary="Testosterone Enanthate 250 mg/ml",
                form_factor="oil",
            )
            for i in range(start + 1, end + 1)
        ]
        return SearchResponse(query=query, normalized_query=query, results=items, total=self.total)


class FakeDraftService:
    def __init__(self, *, added: bool) -> None:
        self.added = added

    async def add_product_to_draft(self, user_id: str, product_id: UUID):
        return SimpleNamespace(added=self.added)


def test_search_result_panel_rendering_smoke() -> None:
    items = [
        SearchResultItem(
            document_id="d1",
            product_id=UUID("00000000-0000-0000-0000-000000000001"),
            product_name="Sustanon Forte",
            brand="SP Labs",
            composition_summary="A very long composition summary that should be shortened significantly for readability",
            form_factor="oil injection",
        )
    ]
    text = _render_search_panel(query="sust", total=12, page=0, items=items)
    assert "<b>Search</b>" in text
    assert "Страница <b>1/3</b>" in text
    assert "Sustanon Forte" in text


def test_product_card_rendering_and_url_buttons() -> None:
    card = OpenCard(
        product_id=UUID("00000000-0000-0000-0000-000000000001"),
        product_name="Prod",
        brand="Brand",
        composition_summary="Comp",
        form_factor="oil",
        official_url="https://official.example",
        authenticity_notes="Check batch code",
        media_refs=["https://src1.example", "https://src2.example"],
    )
    text = _render_product_card(card, show_auth=False, show_media=False, show_sources=False)
    assert "https://" not in text

    keyboard = build_card_actions(card, show_auth=False, show_media=False, show_sources=False)
    url_buttons = [b for row in keyboard.inline_keyboard for b in row if b.url]
    assert any(button.text == "Official" for button in url_buttons)
    assert any(button.text == "Source 1" for button in url_buttons)


def test_pagination_controls_smoke() -> None:
    items = [
        SearchResultItem(
            document_id="d1",
            product_id=UUID("00000000-0000-0000-0000-000000000001"),
            product_name="Prod",
            brand="Brand",
            composition_summary="Comp",
            form_factor="oil",
        )
    ]
    keyboard = build_results_actions(items=items, page=0, total=11)
    labels = [b.text for row in keyboard.inline_keyboard for b in row]
    assert "Next →" in labels


def test_draft_callback_uses_toast_without_spam_message() -> None:
    async def runner() -> None:
        message = FakeMessage()
        callback = FakeCallback(message, "search:draft:00000000-0000-0000-0000-000000000001")
        await on_add_to_draft(callback=callback, draft_service=FakeDraftService(added=True))
        assert len(message.answers) == 0
        assert callback.answers[-1]["text"] == "Добавлено в Draft."

    asyncio.run(runner())


def test_back_to_results_navigation_smoke() -> None:
    async def runner() -> None:
        state = FakeFSMContext()
        message = FakeMessage()
        service = FakeSearchService(total=6)

        await search_entrypoint(message=message, state=state, search_service=service)
        assert len(message.answers) == 1

        open_page = FakeCallback(message, "search:page:1")
        await on_search_page(callback=open_page, state=state, search_service=service)
        assert message.bot.edits[-1]["parse_mode"] == "HTML"

        back = FakeCallback(message, "search:back")
        await on_back_to_results(callback=back, state=state)
        assert message.bot.edits[-1]["reply_markup"] is not None

        stored = (await state.get_data())[SEARCH_STATE_KEY]
        assert stored["page"] == 1
        assert len(stored["items"]) <= PAGE_SIZE

    asyncio.run(runner())


def test_search_flow_uses_single_panel_container_semantics() -> None:
    async def runner() -> None:
        state = FakeFSMContext()
        message = FakeMessage()
        service = FakeSearchService(total=3)

        await search_entrypoint(message=message, state=state, search_service=service)
        assert len(message.answers) == 1

        callback = FakeCallback(message, "search:page:0")
        await on_search_page(callback=callback, state=state, search_service=service)
        assert len(message.bot.edits) == 1

    asyncio.run(runner())
