# CycleSync Telegram Bot — UI/UX Audit Report

**Date:** 2026-04-13
**Scope:** All bot handler files under `app/bots/handlers/`, router, rendering functions
**Reference pattern:** TradeFlow single-panel interaction (`app/core/flow.py` — `send_or_edit` + `remember_container`)

---

## A. General Verdict

**Current UI state: prototype-grade, not product-grade.**

The bot is functionally complete — search, draft, calculation, preview, activation, labs, triage, specialist cases, checkout, reminders all work end-to-end. However, the Telegram UI layer was built in "get it working" mode and never received a product-quality pass.

**Why it is not product-grade:**

1. **Zero use of `edit_message_text`** — every single callback handler creates a new message via `callback.message.answer()`. There is no panel-driven interaction anywhere. Every user tap spawns a new bubble, turning the chat into a wall of messages within minutes.

2. **No text formatting** — zero use of `parse_mode="HTML"` or `parse_mode="Markdown"` across all 8 handler files. Everything is plain text with no bold, italic, monospace, or structured layout.

3. **Raw technical data exposed to users** — UUIDs, internal field names (`protocol_input_mode`, `flatness_stability_score`), debug metrics, and raw decimal precision (`mg=500.0000`, `ml=1.0000`) are shown directly.

4. **Product card is a text dump** — official URLs rendered as raw text (triggers Telegram link preview noise), media refs as comma-joined strings, authenticity notes as plain lines.

5. **Mixed RU/EN language** — button labels, status messages, and prompts switch between Russian and English inconsistently within the same flow.

6. **No container/panel lifecycle** — TradeFlow stores a `container_msg_id` in FSM state and edits the same message across wizard steps. CycleSync has no equivalent mechanism.

---

## B. Concrete Problem Map

### B.1 Search (`search.py`)

| What's wrong | How it should be |
|---|---|
| Each search result is a separate message (`for idx, item` loop with `message.answer` per item) | Single panel with all results, paginated if >5 |
| No result count header ("Found 3 results for 'суст'") | Header line with query echo + count |
| Composition rendered as one long semicolon-joined line | Structured multi-line or abbreviated |
| No "Back to search" or "Search again" action | Navigation button to reset |
| `Open` button sends a NEW message with card (not edit) | Should edit the search results panel into the card view |

**Lines:** `search.py:28-34` — loop sends N messages; `search.py:44-54` — card opens as new message.

### B.2 Product Card (`search.py:on_open_card`)

| What's wrong | How it should be |
|---|---|
| Raw URL as plain text (`Official: https://...`) | InlineKeyboardButton with `url=` parameter |
| Authenticity notes as plain text dump | Collapsible or toggled via button |
| Media refs as `"Media: url1, url2, url3"` | Media toggle button or inline gallery |
| No formatting (bold name, monospace composition) | HTML parse_mode with `<b>`, `<code>` |
| No "Back to results" button | Navigation back to search panel |
| No "+Draft" button on card view | Should carry the add-to-draft action |

**Lines:** `search.py:44-54` — entire card rendering.

### B.3 Draft (`draft.py:_render_draft_summary`, `build_draft_actions`)

| What's wrong | How it should be |
|---|---|
| `on_open_draft` always sends NEW message | Should edit existing draft panel |
| `on_add_to_draft` sends confirmation + "Draft" shortcut button = 2 messages | Edit search panel into confirmation, or toast via `callback.answer()` |
| `on_remove_item` sends "Позиция удалена" + re-rendered draft = 2 messages | Single edit of draft panel with updated list |
| `on_clear_yes` sends "Черновик очищен" + re-rendered draft = 2 messages | Single edit |
| Settings displayed as raw field dump (`protocol_input_mode: auto_pulse`) | Human-readable labels, compact card |
| Delete buttons show truncated names (`Удалить: SP Sustanon FORTE 50`) | Cleaner layout with confirm flow |

**Lines:** `draft.py:88-93` (open), `draft.py:96-106` (remove), `draft.py:125-134` (clear).

### B.4 Calculation Flow (`draft.py` — FSM wizard)

| What's wrong | How it should be |
|---|---|
| Each wizard step creates a new message: mode selection, duration prompt, preset selection, volume prompt, injections prompt, readiness summary = **6+ messages** | Single panel edited at each step (TradeFlow pattern) |
| Mode selection sends selector + optional "current mode" as separate message | One panel with current mode highlighted |
| No back/cancel navigation in wizard steps | "Back" button on each step, "Cancel" to exit |
| Stack smoothing flow sends composition summary + prompt per product = 2N messages | Single panel updated per product |
| Inventory flow same pattern | Same fix |
| `on_mode_selected` for `inventory_constrained` sends access denial as new message | Edit the mode panel with denial + back |

**Lines:** `draft.py:137-156` (mode), `draft.py:310-323` (duration), `draft.py:326-337` (preset), `draft.py:340-364` (volume/injections).

### B.5 Preview / Start (`draft.py:_render_preview_summary`)

| What's wrong | How it should be |
|---|---|
| Preview is a massive text dump (30+ lines) | Compact summary card with expandable details |
| Raw UUIDs in per-product breakdown (`e01d7182-a2d0-426d-...`) | Product names, not UUIDs |
| Schedule shown as `day+0 \| mg=500.0000 \| ml=1.0000 \| event=evt_d0` | Formatted table or human-readable schedule |
| Decimal precision noise (`500.0000`, `1.0000`) | Round to reasonable precision |
| `_render_pre_start_estimate_snapshot` sends as new message | Edit the preview panel |
| `_render_active_protocol_summary` includes developer commentary ("Wave 3 расширит delivery/adherence") | Remove internal notes from user-facing text |

**Lines:** `draft.py:564-627` (preview render), `draft.py:630-645` (active protocol), `draft.py:648-666` (pre-start).

### B.6 Active Protocol (`draft.py:on_activate_latest_preview`)

| What's wrong | How it should be |
|---|---|
| Shows `protocol_id` and `pulse_plan_id` UUIDs | Hide technical IDs |
| Developer note in user text | Clean confirmation card |
| Only 2 buttons (Course estimate + Draft) | Should include protocol status, reminders link, labs link |

### B.7 Labs (`labs.py`)

| What's wrong | How it should be |
|---|---|
| Root menu sends new message every time | Edit existing panel |
| `build_report_entry_actions()` has **11 flat buttons** | Group: Panels (6) / AI (3) / Actions (2) with sub-menus |
| Marker entry flow: each marker prompt is a new message | Edit single panel through markers |
| History rendered as plain text with `id=UUID` | Compact list with open buttons, no raw UUIDs |
| Triage result sent as new message on top of report panel | Edit or structured expansion |
| Specialist case creation shows raw `id=`, `status=`, `snapshot=v1` | Human card |
| Operator flow (awaiting/open/take/answer/close) all spawn new messages | Panel-driven operator console |

**Lines:** `labs.py:564-572` (root 4 buttons), `labs.py:575-590` (11-button report panel), `labs.py:532-561` (marker loop).

### B.8 Specialist Cases (`labs.py`)

| What's wrong | How it should be |
|---|---|
| Case list shows raw UUIDs and dates | Compact numbered cards |
| Case detail is raw field dump | Structured card with status badge |
| Answer submission has no confirmation | Confirm before submitting |
| No user notification on case answer | Should notify original user |

### B.9 Commerce / Checkout (`checkout.py`)

| What's wrong | How it should be |
|---|---|
| `build_checkout_actions` shows **7 buttons** including debug-only ones ("Settle free (test)", "Fail Stars payment") | Show only user-relevant buttons; admin/debug behind role check |
| Checkout rendered with raw `id=UUID`, `status=`, `mode=` | Clean payment card |
| Coupon flow: button sends text instruction "Apply coupon with command: /apply_coupon UUID CODE" | Inline coupon input via FSM |
| Status refresh creates new message | Edit existing checkout panel |
| `/checkout_demo` is a test command exposed in production | Remove or guard behind admin check |

**Lines:** `checkout.py:108-120` (7-button keyboard), `checkout.py:81-85` (coupon text instruction).

---

## C. Message Lifecycle Analysis

### Legend
- **EDIT** = should edit existing panel (use `edit_message_text` or `send_or_edit`)
- **NEW** = new message is acceptable
- **TOAST** = use `callback.answer(text, show_alert=True)` for brief confirmations
- **SPAM** = currently sends new message where edit/toast should be used

### Search flow

| Action | Current | Should be |
|---|---|---|
| User types query | NEW (acceptable) | NEW |
| Bot sends result 1 | NEW | NEW (single combined panel) |
| Bot sends result 2..N | **SPAM** (N messages) | Part of single panel |
| User taps "Open" | **SPAM** (new msg) | EDIT search panel -> card |
| User taps "+Draft" | **SPAM** (new msg + shortcut) | TOAST + keep search panel |

### Draft flow

| Action | Current | Should be |
|---|---|---|
| User types "draft" | NEW (acceptable) | NEW |
| Callback "draft:open" | **SPAM** (new msg) | EDIT |
| Item added from search | **SPAM** (confirmation + shortcut) | TOAST |
| Item removed | **SPAM** (confirmation + re-render) | EDIT |
| Draft cleared | **SPAM** (confirmation + re-render) | EDIT |

### Calculation wizard (6-step)

| Step | Current | Should be |
|---|---|---|
| "К расчету" -> mode selector | **SPAM** | EDIT draft panel -> wizard |
| Mode selected -> duration prompt | **SPAM** | EDIT |
| Duration entered -> preset selector | **SPAM** | EDIT |
| Preset selected -> volume prompt | **SPAM** | EDIT |
| Volume entered -> injections prompt | **SPAM** | EDIT |
| Injections entered -> readiness | **SPAM** | EDIT |

**Total current messages for one calculation: 12+ (6 prompts + 6 user inputs). Target: 6 user inputs + 1 panel edited 6 times.**

### Preview / Activation

| Action | Current | Should be |
|---|---|---|
| Generate preview | **SPAM** | EDIT readiness -> preview |
| Course estimate | **SPAM** | EDIT or NEW (long content) |
| Start protocol -> pre-start | **SPAM** | EDIT preview -> pre-start |
| Confirm activation | **SPAM** | EDIT -> active protocol card |

### Labs

| Action | Current | Should be |
|---|---|---|
| "labs" entry | NEW | NEW |
| New report created | **SPAM** | EDIT |
| Panel selected -> first marker | **SPAM** | EDIT |
| Each marker prompt | **SPAM** | EDIT |
| Panel finished | **SPAM** | EDIT |
| Triage result | **SPAM** | EDIT or NEW |
| History | **SPAM** | EDIT |

### Settings

| Action | Current | Should be |
|---|---|---|
| "settings" entry | NEW | NEW |
| Toggle on/off | **SPAM** (confirmation + re-render = 2 msgs) | EDIT |
| Set time -> prompt | **SPAM** | EDIT |
| Time saved | **SPAM** (confirmation + re-render = 2 msgs) | EDIT |

### Checkout

| Action | Current | Should be |
|---|---|---|
| `/checkout_demo` | NEW | NEW |
| Any status change | **SPAM** | EDIT |
| Coupon prompt | **SPAM** | EDIT |

**Summary: ~40+ handler paths produce SPAM; zero use EDIT.**

---

## D. Product Card Redesign Recommendations

### Current card (`search.py:44-54`):
```
SP Sustanon FORTE 500
Бренд: SP Laboratories
Состав: Testosterone 6mg; Testosterone 12mg; Testosterone 12mg; Testosterone 2mg
Форма: oil injection
Official: https://roidsmall.to/sp-labs-1995/sustanon-forte-22877
Authenticity: Verify composition label, vial print, and brand presentation...
Media: url1, url2, url3
```

### Proposed card (HTML parse_mode):
```html
<b>SP Sustanon FORTE 500</b>
<i>SP Laboratories</i> · oil injection

<b>Composition:</b>
  Testosterone Propionate — 6 mg
  Testosterone Phenylpropionate — 12 mg
  Testosterone Isocaproate — 12 mg
  Testosterone Decanoate — 2 mg

Total active: 32 mg/mL
```

### Button layout:
```
[ Official source ]  (url button -> link)
[ Authenticity info ] (callback -> toggle text block)
[ Media gallery ]     (callback -> show/hide media)
[ + Add to Draft ]    (callback -> add + toast)
[ Back to results ]   (callback -> edit back to search)
```

### Key principles:
1. **URL buttons** instead of raw links — use `InlineKeyboardButton(text="Official source", url=card.official_url)`
2. **Toggle buttons** for secondary info (authenticity, media) — show/hide on tap via edit
3. **Composition formatting** — break semicolon-joined string into lines, use ester names
4. **Bold product name** — `parse_mode="HTML"` with `<b>` tags
5. **No raw UUIDs** — product card should never expose internal IDs
6. **Admin media seam** — separate `[ Manage media ]` button visible only to admin users, leading to attach/remove/reorder flow

---

## E. Proposed Remediation Plan

### PR-1: Foundation — `send_or_edit` container pattern (HIGH PRIORITY)
**Scope:** Create `app/bots/core/flow.py` with:
- `send_or_edit(bot, chat_id, state_data, text, reply_markup)` — edit existing container or send new
- `remember_container(state, message_id)` — save container ID in FSM
- `schedule_delete_user_message(bot, message)` — clean up user input messages

**Files:** New file `app/bots/core/flow.py` (port from TradeFlow pattern)
**Risk:** Low — additive only, no existing behavior changes
**Estimate:** Small

### PR-2: Search panel + product card redesign (HIGH PRIORITY)
**Scope:**
- Combine search results into single panel message
- Add pagination (if >5 results)
- Product card with HTML formatting
- URL buttons for official/source links
- Toggle buttons for authenticity/media
- "+Draft" as toast confirmation
- "Back to results" navigation

**Files:** `app/bots/handlers/search.py`
**Risk:** Medium — changes user-visible search experience
**Estimate:** Medium

### PR-3: Draft panel — edit-in-place (HIGH PRIORITY)
**Scope:**
- Draft view uses `send_or_edit` — always edits same panel
- Remove/clear actions edit panel directly (no confirmation + re-render spam)
- Add-to-draft from search uses `callback.answer()` toast

**Files:** `app/bots/handlers/draft.py` (lines 55-134)
**Risk:** Medium
**Estimate:** Medium

### PR-4: Calculation wizard — single-panel FSM (HIGH PRIORITY)
**Scope:**
- Entire calculation wizard (mode -> duration -> preset -> volume -> injections -> readiness) edits one panel
- Back navigation at each step
- Cancel to exit wizard
- Delete user input messages after processing

**Files:** `app/bots/handlers/draft.py` (lines 137-440)
**Risk:** High — touches FSM state machine, needs careful testing
**Estimate:** Large

### PR-5: Preview + activation — formatted cards (MEDIUM PRIORITY)
**Scope:**
- Preview summary as compact HTML card (no raw UUIDs, rounded decimals)
- Schedule as readable mini-table
- Pre-start estimate as clean card
- Active protocol confirmation — remove developer notes
- All use `send_or_edit`

**Files:** `app/bots/handlers/draft.py` (lines 564-730)
**Risk:** Medium
**Estimate:** Medium

### PR-6: Labs panel hierarchy + edit-in-place (MEDIUM PRIORITY)
**Scope:**
- Split 11-button report entry into sub-menus (Panels / AI / Actions)
- Marker entry flow edits single panel
- History/triage results use `send_or_edit`
- Remove raw UUIDs from user-facing text

**Files:** `app/bots/handlers/labs.py`
**Risk:** Medium
**Estimate:** Large

### PR-7: Checkout cleanup — role-gated buttons (MEDIUM PRIORITY)
**Scope:**
- Remove debug buttons ("Settle free (test)", "Fail Stars payment") from user view
- Guard `/checkout_demo` behind admin check
- Coupon input via FSM instead of `/apply_coupon` command
- Checkout status edits existing panel

**Files:** `app/bots/handlers/checkout.py`
**Risk:** Low
**Estimate:** Small

### PR-8: Settings — edit-in-place + toggle pattern (LOW PRIORITY)
**Scope:**
- Settings view uses `send_or_edit`
- Toggle on/off edits panel (no confirmation + re-render)
- Time set prompt edits panel

**Files:** `app/bots/handlers/settings.py`
**Risk:** Low
**Estimate:** Small

### PR-9: HTML formatting pass (LOW PRIORITY, can merge with above PRs)
**Scope:**
- Add `parse_mode="HTML"` to all message sends
- Bold headers, monospace values, structured layout
- Consistent RU language (or full i18n if planned)

**Files:** All handler files
**Risk:** Low
**Estimate:** Medium (spread across all files)

### PR-10: Voice input handler (DEFERRED — post-stabilization)
**Scope:** As designed in `docs/40_search_model.md` section 14
**Status:** Not implemented, infrastructure ready
**Dependency:** Search panel (PR-2) should land first

### Recommended order:
```
PR-1 (foundation) -> PR-2 (search) -> PR-3 (draft) -> PR-4 (wizard) -> PR-5 (preview)
                                                                      -> PR-7 (checkout)
                  -> PR-6 (labs) -> PR-8 (settings) -> PR-9 (formatting)
                                                     -> PR-10 (voice, deferred)
```

---

## F. Files / Handlers Map

### UI debt concentration

| File | Lines | Severity | Key issues |
|---|---|---|---|
| `app/bots/handlers/draft.py` | 890 | **CRITICAL** | Largest file; entire wizard spawns spam; preview is data dump; 0 edits |
| `app/bots/handlers/search.py` | 67 | **CRITICAL** | N messages per search; card is raw text; no URL buttons |
| `app/bots/handlers/labs.py` | 663 | **HIGH** | 11-button flat keyboard; marker flow spam; raw UUIDs everywhere |
| `app/bots/handlers/checkout.py` | 205 | **HIGH** | Debug buttons exposed; command-based coupon; raw checkout render |
| `app/bots/handlers/settings.py` | 193 | **MEDIUM** | Double message on toggle; no edit pattern |
| `app/bots/handlers/access_keys.py` | 59 | **LOW** | Simple 2-step flow; minor formatting |
| `app/bots/handlers/reminder_actions.py` | 43 | **LOW** | Toast-only handler; already reasonable |

### Missing infrastructure files (to be created)

| File | Purpose |
|---|---|
| `app/bots/core/__init__.py` | Package init |
| `app/bots/core/flow.py` | `send_or_edit`, `remember_container`, `schedule_delete_user_message` |
| `app/bots/core/formatting.py` | HTML card builders, decimal rounding, UUID hiding |
| `app/bots/core/permissions.py` | Role check for admin-only buttons |

### Rendering functions to rewrite

| Function | File | Issue |
|---|---|---|
| `_render_draft_summary` | `draft.py:524` | Plain text, raw field names |
| `_render_readiness_summary` | `draft.py:551` | No formatting |
| `_render_preview_summary` | `draft.py:564` | 60+ line data dump, UUIDs, raw decimals |
| `_render_active_protocol_summary` | `draft.py:630` | Developer notes in user text |
| `_render_pre_start_estimate_snapshot` | `draft.py:648` | Raw fields |
| `_render_course_estimate` | `draft.py:669` | 60+ line dump |
| `_render_checkout` | `checkout.py:170` | Raw IDs, debug info |
| `_render_settings` | `settings.py:145` | Minimal |
| `_format_triage_result` | `labs.py:648` | No formatting |
| `build_report_entry_actions` | `labs.py:575` | 11 flat buttons |
| `build_checkout_actions` | `checkout.py:108` | Debug buttons visible |

---

## Appendix: Critical Quick-Fix Candidates

These are small, obvious UX bugs that could be fixed immediately without architectural changes:

1. **Remove developer note from active protocol text** (`draft.py:643`):
   `"Execution/reminders слой продолжается отсюда (Wave 3 расширит delivery/adherence)."` — delete this line.

2. **Hide debug checkout buttons** (`checkout.py:116-117`):
   Remove "Fail Stars payment" and "Settle free (test)" from `build_checkout_actions`, or gate behind admin flag.

3. **Remove raw UUIDs from preview** (`draft.py:590-591`):
   Replace `product_id: {product_id}` with product name lookup.

4. **Round decimal noise** (`draft.py:621`):
   `mg=500.0000` -> `mg=500`, `ml=1.0000` -> `ml=1.0`.

5. **Add URL button for official link** (`search.py:49`):
   Replace `f"Official: {card.official_url}"` with `InlineKeyboardButton(text="Official source", url=card.official_url)`.

---

*Generated by CycleSync UI/UX audit, 2026-04-13.*
