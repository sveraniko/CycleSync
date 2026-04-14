import asyncio
from types import SimpleNamespace
from uuid import UUID

from app.application.search.schemas import CardMediaItem, CardSourceLink, OpenCard, SearchResponse, SearchResultItem
from app.bots.handlers.draft import on_add_to_draft
from app.bots.handlers.search import (
    SEARCH_STATE_KEY,
    PAGE_SIZE,
    CARD_STATE_KEY,
    _effective_media_gallery,
    _render_product_card,
    _resolve_media_display_mode,
    _resolve_primary_cover,
    _render_search_panel,
    build_card_actions,
    build_results_actions,
    on_back_to_results,
    on_media_gallery_nav,
    on_search_page,
    on_toggle_section,
    search_entrypoint,
    on_admin_product_media_policy,
    on_admin_product_display_mode,
    on_admin_product_sync_toggle,
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

    async def delete(self):
        return None


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
        self.card = OpenCard(
            product_id=UUID("00000000-0000-0000-0000-000000000001"),
            product_name="Prod",
            brand="Brand",
            composition_summary="Comp",
            form_factor="oil",
            official_url="https://official.example",
            authenticity_notes="Auth",
            media_policy="merge",
            media_display_mode="on_demand",
            sync_images=True,
            sync_videos=True,
            sync_sources=True,
            source_links=[
                CardSourceLink(kind="source", label="Source A", url="https://src.example", priority=1, source_layer="import", is_active=True)
            ],
            media_items=[
                CardMediaItem(
                    media_kind="image",
                    ref="https://cdn/1.png",
                    priority=1,
                    is_cover=True,
                    source_layer="import",
                    is_active=True,
                ),
                CardMediaItem(
                    media_kind="video",
                    ref="https://cdn/2.mp4",
                    priority=2,
                    is_cover=False,
                    source_layer="import",
                    is_active=True,
                ),
            ],
        )

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

    async def open_card(self, product_id: UUID) -> OpenCard | None:
        if product_id == self.card.product_id:
            return self.card
        return None

    async def admin_update_product_media_settings(self, product_id: UUID, **kwargs):
        if product_id != self.card.product_id:
            return False
        for k, v in kwargs.items():
            setattr(self.card, k, v)
        return True


class FakeDraftService:
    def __init__(self, *, added: bool) -> None:
        self.added = added

    async def add_product_to_draft(self, user_id: str, product_id: UUID):
        return SimpleNamespace(added=self.added)

    async def get_or_create_active_draft(self, user_id: str):
        return SimpleNamespace(items=[])

    async def list_draft(self, user_id: str):
        return SimpleNamespace(items=[])


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
    assert "<b>Поиск</b>" in text
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
        source_links=[
            CardSourceLink(kind="source", label="Lab test", url="https://src1.example", priority=1, is_active=True),
            CardSourceLink(kind="community", label="Community", url="https://src2.example", priority=2, is_active=True),
        ],
        media_items=[],
    )
    text = _render_product_card(card, show_auth=False, show_media=False, show_sources=False)
    assert "https://" not in text

    keyboard = build_card_actions(card, show_auth=False, show_media=False, show_sources=False)
    url_buttons = [b for row in keyboard.inline_keyboard for b in row if b.url]
    assert any(button.text == "Официальный сайт" for button in url_buttons)
    assert any(button.text == "Lab test" for button in url_buttons)
    assert any(button.text == "Community" for button in url_buttons)


def test_show_sources_does_not_claim_buttons_when_no_links() -> None:
    card = OpenCard(
        product_id=UUID("00000000-0000-0000-0000-000000000001"),
        product_name="Prod",
        brand="Brand",
        composition_summary="Comp",
        form_factor="oil",
        official_url=None,
        authenticity_notes=None,
        source_links=[],
        media_items=[],
    )
    text = _render_product_card(card, show_auth=False, show_media=False, show_sources=True)
    assert "Нет данных." in text


def test_media_section_renders_structured_media_items() -> None:
    card = OpenCard(
        product_id=UUID("00000000-0000-0000-0000-000000000001"),
        product_name="Prod",
        brand="Brand",
        composition_summary="Comp",
        form_factor="oil",
        official_url=None,
        authenticity_notes=None,
        source_links=[],
        media_items=[
            CardMediaItem(
                media_kind="image",
                ref="https://cdn/x.png",
                priority=1,
                is_cover=True,
                source_layer="import",
                is_active=True,
            )
        ],
    )
    text = _render_product_card(card, show_auth=False, show_media=True, show_sources=False)
    assert "Primary cover: Image (import)" in text
    assert "Текущий [1/1]: Image" in text


def test_cover_resolution_prefers_manual_cover_then_import_then_priority() -> None:
    card = OpenCard(
        product_id=UUID("00000000-0000-0000-0000-000000000001"),
        product_name="Prod",
        brand="Brand",
        composition_summary="Comp",
        form_factor="oil",
        official_url=None,
        authenticity_notes=None,
        media_policy="merge",
        source_links=[],
        media_items=[
            CardMediaItem(media_kind="image", ref="https://cdn/import-cover.png", priority=2, is_cover=True, source_layer="import", is_active=True),
            CardMediaItem(media_kind="image", ref="https://cdn/manual-cover.png", priority=3, is_cover=True, source_layer="manual", is_active=True),
            CardMediaItem(media_kind="image", ref="https://cdn/fallback.png", priority=1, is_cover=False, source_layer="import", is_active=True),
        ],
    )
    assert _resolve_primary_cover(card).ref == "https://cdn/manual-cover.png"

    card.media_policy = "import_only"
    assert _resolve_primary_cover(card).ref == "https://cdn/import-cover.png"

    card.media_items = [CardMediaItem(media_kind="image", ref="https://cdn/p1.png", priority=1, is_cover=False, source_layer="import", is_active=True)]
    assert _resolve_primary_cover(card).ref == "https://cdn/p1.png"


def test_show_cover_on_open_rendering() -> None:
    card = OpenCard(
        product_id=UUID("00000000-0000-0000-0000-000000000001"),
        product_name="Prod",
        brand="Brand",
        composition_summary="Comp",
        form_factor="oil",
        official_url=None,
        authenticity_notes=None,
        media_display_mode="show_cover_on_open",
        source_links=[],
        media_items=[
            CardMediaItem(media_kind="image", ref="https://cdn/x.png", priority=1, is_cover=True, source_layer="import", is_active=True)
        ],
    )
    text = _render_product_card(card, show_auth=False, show_media=False, show_sources=False)
    assert "Обложка при открытии: Image • cover" in text
    assert _resolve_media_display_mode(card) == "show_cover_on_open"


def test_on_demand_media_rendering_mode() -> None:
    card = OpenCard(
        product_id=UUID("00000000-0000-0000-0000-000000000001"),
        product_name="Prod",
        brand="Brand",
        composition_summary="Comp",
        form_factor="oil",
        official_url=None,
        authenticity_notes=None,
        media_display_mode="on_demand",
        source_links=[],
        media_items=[CardMediaItem(media_kind="video", ref="https://cdn/v.mp4", priority=1, is_cover=False, source_layer="import", is_active=True)],
    )
    text = _render_product_card(card, show_auth=False, show_media=False, show_sources=False)
    assert "по запросу через Show media" in text


def test_no_media_truthful_rendering() -> None:
    card = OpenCard(
        product_id=UUID("00000000-0000-0000-0000-000000000001"),
        product_name="Prod",
        brand="Brand",
        composition_summary="Comp",
        form_factor="oil",
        official_url=None,
        authenticity_notes=None,
        source_links=[],
        media_items=[],
    )
    text = _render_product_card(card, show_auth=False, show_media=False, show_sources=False)
    assert "Нет медиа-файлов." in text


def test_card_actions_preserve_official_source_media_separation_and_ordering() -> None:
    card = OpenCard(
        product_id=UUID("00000000-0000-0000-0000-000000000001"),
        product_name="Prod",
        brand="Brand",
        composition_summary="Comp",
        form_factor="oil",
        official_url="https://official.example",
        authenticity_notes=None,
        source_links=[
            CardSourceLink(kind="source", label="Source 2", url="https://s2.example", priority=2, is_active=True),
            CardSourceLink(kind="source", label="Source 1", url="https://s1.example", priority=1, is_active=True),
        ],
        media_items=[
            CardMediaItem(
                media_kind="video",
                ref="https://video.example",
                priority=10,
                is_cover=False,
                source_layer="import",
                is_active=True,
            )
        ],
    )
    keyboard = build_card_actions(card, show_auth=False, show_media=False, show_sources=False)
    url_buttons = [b for row in keyboard.inline_keyboard for b in row if b.url]
    assert [b.text for b in url_buttons] == ["Официальный сайт", "Source 1", "Source 2"]
    assert all(not text.startswith("Image") and not text.startswith("Video") for text in [b.text for b in url_buttons])


def test_effective_media_gallery_respects_manual_only_policy() -> None:
    card = OpenCard(
        product_id=UUID("00000000-0000-0000-0000-000000000001"),
        product_name="Prod",
        brand="Brand",
        composition_summary=None,
        form_factor=None,
        official_url=None,
        authenticity_notes=None,
        media_policy="manual_only",
        source_links=[],
        media_items=[
            CardMediaItem(media_kind="image", ref="https://cdn/import.png", priority=1, is_cover=False, source_layer="import", is_active=True),
            CardMediaItem(media_kind="image", ref="https://cdn/manual.png", priority=2, is_cover=False, source_layer="manual", is_active=True),
        ],
    )
    gallery = _effective_media_gallery(card)
    assert [item.ref for item in gallery] == ["https://cdn/manual.png"]


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
        await on_add_to_draft(
            callback=callback,
            state=FakeFSMContext(),
            draft_service=FakeDraftService(added=True),
            search_service=FakeSearchService(),
        )
        assert len(message.answers) == 0
        assert callback.answers[-1]["text"] is None

    asyncio.run(runner())


def test_back_to_results_navigation_smoke() -> None:
    async def runner() -> None:
        state = FakeFSMContext()
        message = FakeMessage()
        service = FakeSearchService(total=6)

        await search_entrypoint(message=message, state=state, search_service=service, draft_service=FakeDraftService(added=True))
        assert len(message.answers) == 1

        open_page = FakeCallback(message, "search:page:1")
        await on_search_page(callback=open_page, state=state, search_service=service, draft_service=FakeDraftService(added=True))
        assert message.bot.edits[-1]["parse_mode"] == "HTML"

        back = FakeCallback(message, "search:back")
        await on_back_to_results(callback=back, state=state, draft_service=FakeDraftService(added=True))
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

        await search_entrypoint(message=message, state=state, search_service=service, draft_service=FakeDraftService(added=True))
        assert len(message.answers) == 1

        callback = FakeCallback(message, "search:page:0")
        await on_search_page(callback=callback, state=state, search_service=service, draft_service=FakeDraftService(added=True))
        assert len(message.bot.edits) == 1

    asyncio.run(runner())


def test_product_card_media_toggle_smoke() -> None:
    async def runner() -> None:
        state = FakeFSMContext()
        message = FakeMessage()
        service = FakeSearchService(total=1)
        await state.update_data(
            **{
                CARD_STATE_KEY: {
                    "product_id": str(service.card.product_id),
                    "show_auth": False,
                    "show_media": False,
                    "show_sources": False,
                    "media_index": 0,
                }
            }
        )
        callback = FakeCallback(message, "search:toggle:media")
        await on_toggle_section(callback=callback, state=state, search_service=service)
        card_state = (await state.get_data())[CARD_STATE_KEY]
        assert card_state["show_media"] is True
        assert "Галерея медиа" in message.answers[0]["text"]

    asyncio.run(runner())


def test_panel_driven_media_interaction_smoke() -> None:
    async def runner() -> None:
        state = FakeFSMContext()
        message = FakeMessage()
        service = FakeSearchService(total=1)
        await state.update_data(
            **{
                CARD_STATE_KEY: {
                    "product_id": str(service.card.product_id),
                    "show_auth": False,
                    "show_media": True,
                    "show_sources": False,
                    "media_index": 0,
                }
            }
        )
        callback = FakeCallback(message, "search:media:next")
        await on_media_gallery_nav(callback=callback, state=state, search_service=service)
        card_state = (await state.get_data())[CARD_STATE_KEY]
        assert card_state["media_index"] == 1
        assert len(message.answers) == 1
        assert len(message.bot.edits) == 0

    asyncio.run(runner())


def test_admin_sees_media_source_policy_controls() -> None:
    card = OpenCard(
        product_id=UUID("00000000-0000-0000-0000-000000000001"),
        product_name="Prod",
        brand="Brand",
        composition_summary="Comp",
        form_factor="oil",
        official_url=None,
        authenticity_notes=None,
        media_policy="merge",
        media_display_mode="on_demand",
        sync_images=True,
        sync_videos=False,
        sync_sources=True,
        source_links=[],
        media_items=[],
    )
    text = _render_product_card(card, show_auth=False, show_media=False, show_sources=False, is_admin=True, show_admin_media_controls=True)
    keyboard = build_card_actions(
        card,
        show_auth=False,
        show_media=False,
        show_sources=False,
        is_admin=True,
        show_admin_media_controls=True,
    )
    labels = [b.text for row in keyboard.inline_keyboard for b in row]
    assert "Админ: политика медиа и источников" in text
    assert "Политика медиа: <code>merge</code>" in text
    assert "Режим показа: <code>on_demand</code>" in text
    assert any("Синк изображений:" in label for label in labels)
    assert any("Синк видео:" in label for label in labels)
    assert any("Синк источников:" in label for label in labels)


def test_non_admin_does_not_see_media_source_controls() -> None:
    card = OpenCard(
        product_id=UUID("00000000-0000-0000-0000-000000000001"),
        product_name="Prod",
        brand="Brand",
        composition_summary="Comp",
        form_factor="oil",
        official_url=None,
        authenticity_notes=None,
        source_links=[],
        media_items=[],
    )
    keyboard = build_card_actions(card, show_auth=False, show_media=False, show_sources=False, is_admin=False)
    labels = [b.text for row in keyboard.inline_keyboard for b in row]
    assert not any("Media/source policy" in label for label in labels)


def test_source_links_obey_media_policy() -> None:
    card = OpenCard(
        product_id=UUID("00000000-0000-0000-0000-000000000001"),
        product_name="Prod",
        brand="Brand",
        composition_summary="Comp",
        form_factor="oil",
        official_url=None,
        authenticity_notes=None,
        media_policy="manual_only",
        source_links=[
            CardSourceLink(kind="source", label="Import src", url="https://import.example", priority=1, source_layer="import", is_active=True),
            CardSourceLink(kind="source", label="Manual src", url="https://manual.example", priority=2, source_layer="manual", is_active=True),
        ],
        media_items=[],
    )
    keyboard = build_card_actions(card, show_auth=False, show_media=False, show_sources=True)
    labels = [b.text for row in keyboard.inline_keyboard for b in row if b.url]
    assert "Manual src" in labels
    assert "Import src" not in labels


def test_admin_policy_and_display_persist_and_affect_card_behavior() -> None:
    async def runner() -> None:
        state = FakeFSMContext()
        message = FakeMessage()
        service = FakeSearchService(total=1)
        callback_policy = FakeCallback(message, f"a:p:mp:{service.card.product_id}:manual_only")
        await on_admin_product_media_policy(callback=callback_policy, state=state, search_service=service, admin_ids=(11,))
        assert service.card.media_policy == "manual_only"

        text = message.answers[0]["text"]
        assert "Нет медиа-файлов." in text

        callback_mode = FakeCallback(message, f"a:p:dm:{service.card.product_id}:sc")
        await on_admin_product_display_mode(callback=callback_mode, state=state, search_service=service, admin_ids=(11,))
        assert service.card.media_display_mode == "show_cover_on_open"
        assert "Нет медиа-файлов." in message.bot.edits[-1]["text"]

    asyncio.run(runner())


def test_admin_sync_toggles_persist() -> None:
    async def runner() -> None:
        state = FakeFSMContext()
        message = FakeMessage()
        service = FakeSearchService(total=1)

        c1 = FakeCallback(message, f"a:p:st:{service.card.product_id}:i")
        await on_admin_product_sync_toggle(callback=c1, state=state, search_service=service, admin_ids=(11,))
        assert service.card.sync_images is False

        c2 = FakeCallback(message, f"a:p:st:{service.card.product_id}:v")
        await on_admin_product_sync_toggle(callback=c2, state=state, search_service=service, admin_ids=(11,))
        assert service.card.sync_videos is False

        c3 = FakeCallback(message, f"a:p:st:{service.card.product_id}:s")
        await on_admin_product_sync_toggle(callback=c3, state=state, search_service=service, admin_ids=(11,))
        assert service.card.sync_sources is False

    asyncio.run(runner())
