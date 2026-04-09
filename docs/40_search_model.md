# CycleSync Search Model

> Search architecture and retrieval model document for **CycleSync**.

---

## 1. Purpose of this document

This document defines the search model of CycleSync.

Its goals are to:

- define why search is a first-class system capability;
- formalize the distinction between internal catalog truth and user-facing search-first UX;
- describe search intents and retrieval classes;
- define Meilisearch-based architecture and fallback behavior;
- describe normalization, tokenization and ranking rules;
- define how search connects to `Open` and `+Draft` flows;
- prepare the foundation for search index schema, sync jobs, query logging and voice search.

This document is **not**:

- a final Meilisearch settings dump;
- a detailed API payload catalog;
- a migration document;
- a pulse-engine formula document;
- a UI pixel spec.

Those belong in separate docs.

---

## 2. Search is not an accessory — it is the facade

CycleSync is **not** a storefront and **not** a pharmacy catalog.

For the user, the product should not feel like:

- a shop;
- a catalog browser;
- a category tree;
- a showcase with endless filters and showcase pages.

CycleSync should feel like:

- a precision tool;
- a calculation assistant;
- a focused retrieval interface for people who already know what they are looking for.

Therefore the correct product stance is:

> **For the system there is a full compound catalog. For the user there is a search-first facade.**

This distinction is critical.

The system must own a rich internal compound registry, but the user-facing flow starts from search, not from browsing.

---

## 3. Search-first product principle

### 3.1 Main rule

The default entry point of CycleSync should be **search**.

The user is expected to:

- know the trade name; or
- know the brand + product; or
- know the active ingredient / ester; or
- know a component of composition and dosage; or
- dictate it via voice.

### 3.2 No public catalog mode in v1

User-facing browse/catalog mode should not exist in v1.

That means:

- no categories page;
- no brand showcase page;
- no storefront browsing;
- no “show me all products in this section” UX.

If something is not found in the database, the product should say so directly.

### 3.3 Internal catalog still exists

The system must still maintain a complete internal compound catalog because search depends on:

- normalized names;
- aliases;
- brands;
- substances;
- esters;
- composition entries;
- dosage tokens;
- release forms;
- media;
- authenticity references;
- official links.

So the correct principle is:

> **No catalog UX does not mean no catalog domain.**

---

## 4. Search objectives

CycleSync search must solve these jobs:

1. Find a concrete product by trade name.
2. Find a product by brand + trade name.
3. Find products by active substance.
4. Find products by ester.
5. Find products by composition component and mg amount.
6. Find all compounds containing a component with a given amount.
7. Open a compound card.
8. Add the compound into calculation draft (`+Draft`).
9. Parse voice search into structured retrieval actions.
10. Log not-found intent for future catalog enrichment.

---

## 5. Search target types

Search in CycleSync is not “one search”. It is a compound retrieval system with multiple target classes.

### 5.1 Product-name search

Examples:

- `sustanon`
- `pharma sust 500`
- `pharmasust`
- `sust 500`
- `суст`
- `сустанон`

This is primarily trade-name retrieval.

### 5.2 Brand + product search

Examples:

- `sustanon Pharmacom`
- `suстанон SP`
- `pharma sust 500 pharmacom labs`

This is mixed brand/product retrieval.

### 5.3 Substance search

Examples:

- `testosterone phenylpropionate`
- `phenylpropionate`
- `тестостерон фенилпропионат`
- `фенилпропионат`

This is not product-level search only. It requires composition-aware retrieval.

### 5.4 Composition search

Examples:

- `phenylpropionate 60 mg`
- `фенилпропионат 60мг`
- `test phenyl 60`

This requires reading composition entries, not just product titles.

### 5.5 Mixed/noisy search

Examples:

- pasted brand names with extra symbols;
- transliterated fragments;
- shorthand slang;
- combined product + dosage + brand phrases.

This requires aggressive normalization and tolerant retrieval.

### 5.6 Voice search intent

Examples:

- “найди pharma sust 500 и добавь в расчет”
- “найди фенилпропионат 60 миллиграмм”
- “добавь сустанон pharmacom и мастерон энантат в draft”

Voice is not a separate domain. It is an input channel into search and draft actions.

---

## 6. Search architecture decision

### 6.1 Search engine choice

CycleSync should use **Meilisearch** from the beginning.

This is justified because the product depends on:

- high-speed fuzzy retrieval;
- tolerant matching for noisy data;
- multi-token matching;
- flexible ranking;
- future voice-assisted lookup;
- composition-aware retrieval using indexed projection documents.

### 6.2 Why DB-only search is insufficient

Pure DB lookup is insufficient because the product must support:

- transliteration mismatches;
- alias matching;
- fuzzy trade names;
- shorthand fragments;
- brand/product mixing;
- composition tokens and dosage fragments;
- voice-derived noisy input.

### 6.3 Fallback behavior

If Meilisearch is unavailable:

- basic DB fallback must still allow reduced lookup by exact normalized values;
- core operations should degrade, not fail completely;
- user experience may become reduced, but not dead.

---

## 7. Search data sources

Search reads from the internal compound catalog domain and builds projection documents.

Primary source entities:

- `compounds`
- `brands`
- `compound_aliases`
- `brand_aliases`
- `substances`
- `substance_aliases`
- `esters`
- `compound_composition_entries`
- `compound_media_links` (selected fields only)

These are transformed into search-optimized documents.

---

## 8. Core search document model

The primary search document is:

### `CompoundSearchDocument`

This document represents one searchable product entity.

Candidate fields:

- `compound_id`
- `display_name`
- `normalized_name`
- `trade_name`
- `brand_display_name`
- `brand_tokens`
- `compound_alias_tokens`
- `brand_alias_tokens`
- `substance_tokens`
- `ester_tokens`
- `composition_tokens`
- `mg_tokens`
- `release_form_tokens`
- `packaging_tokens`
- `official_url` (optional, read support only)
- `has_media`
- `status`
- `search_quality_score` (optional internal helper)

### 8.1 Purpose of field groups

#### Name fields

Support exact or fuzzy lookup by trade/product naming.

#### Brand fields

Support queries like:

- `sustanon pharmacom`
- `pharma sust`

#### Substance / ester fields

Support queries like:

- `phenylpropionate`
- `testosterone phenylpropionate`

#### Composition / mg fields

Support queries like:

- `phenylpropionate 60mg`
- `60 mg phenyl`

#### Packaging / release-form fields

Support queries where users include form factor or pack context.

---

## 9. Normalization model

Search quality depends on normalization more than on wishful thinking.

### 9.1 Required normalization steps

For incoming queries:

- trim whitespace;
- normalize case;
- normalize punctuation;
- collapse repeated spaces;
- standardize units (`mg`, `мг`, `ml`, `мл`);
- token cleanup;
- transliteration normalization where applicable;
- slang/alias expansion later where useful.

For indexed catalog data:

- store normalized names;
- store alias tokens;
- store brand aliases;
- store substance aliases;
- normalize composition text;
- normalize mg tokens;
- normalize release-form tokens.

### 9.2 Unit normalization

The system must normalize equivalent user expressions such as:

- `60мг`
- `60 мг`
- `60mg`
- `60 mg`

Similarly for ml volume strings.

### 9.3 Token strategy

Index tokens should be split and stored in ways useful for retrieval, not just copied blindly from source text.

Examples:

- `Pharma Sust 500`
- `Pharmacom Labs`
- `Testosterone Phenylpropionate`
- `Phenylpropionate`

should yield meaningful searchable fragments.

---

## 10. Search intents and routing

The search layer should classify retrieval intent at a lightweight level.

### 10.1 Intent classes

#### A. Exact product lookup

User is trying to find one concrete trade product.

#### B. Brand-constrained product lookup

User is trying to find one concrete product from a specific brand.

#### C. Substance/ester lookup

User is trying to find all compounds containing a given active component.

#### D. Composition lookup

User is trying to find compounds that contain a component with a specific dosage.

#### E. Mixed/noisy lookup

The query contains multiple weak signals and requires tolerant ranking.

#### F. Voice action lookup

The query implies an action like add-to-draft, not just retrieval.

### 10.2 Why intent routing matters

Because the same query engine must decide whether to prioritize:

- name fields;
- brand fields;
- composition fields;
- dosage tokens;
- intent to act (`+Draft`).

---

## 11. Ranking model

Search ranking should not be naive.

### 11.1 Ranking priorities

Recommended ranking order:

1. exact product/trade-name match
2. exact brand + product match
3. exact alias match
4. strong substance/ester composition match
5. strong dosage token match
6. fuzzy product match
7. fuzzy composition match
8. weak partial token match

### 11.2 Important rule

When the user clearly typed a trade product name, search should not bury the exact product under broad composition results.

### 11.3 Composition-aware retrieval rule

When the query looks like a substance/ester/dosage lookup, search should prioritize products whose composition contains those values, even if the product title itself is weakly informative.

---

## 12. Search outputs and user actions

Search is not only about results. It is about what the user can do next.

### 12.1 Result list output

The search result list should show compact, actionable items.

Suggested display elements:

- display name
- brand
- short composition signal
- release form / pack label (if useful)
- maybe media flag

### 12.2 Primary actions per result

Each result should support:

- **Open** — open compound card
- **+Draft** — add compound into calculation draft

These are the two primary user actions.

### 12.3 Why `+Draft` matters

CycleSync is not a store. It is a preparation-and-calculation system.

Therefore the natural action is not “Buy”, but:

> **Use this compound in calculation draft.**

That is a core product distinction.

---

## 13. Compound card role in search flow

The card is not a storefront page. It is an information and action node.

### 13.1 Card purpose

A compound card may show:

- name;
- brand;
- composition;
- release form;
- media;
- authenticity guidance;
- official reference link;
- `+Draft` action.

### 13.2 Card role in product architecture

The card is a **search result drill-down**, not a browse-mode replacement.

---

## 14. Voice-assisted search model

Voice search is a high-value feature, but it must remain constrained.

### 14.1 Voice should not be a general chat bot

In v1, voice input should be limited to:

- find product;
- find by composition;
- open card;
- add found result to draft;
- show not-found fragments.

### 14.2 Voice processing pipeline

Recommended flow:

1. speech-to-text;
2. query normalization;
3. lightweight intent classification;
4. search execution;
5. optional add-to-draft action parsing;
6. result summary back to user.

### 14.3 Voice result behavior

If multiple compounds are mentioned:

- match each independently;
- show what was found;
- show what was not found;
- allow user to confirm add-to-draft.

---

## 15. Not-found handling and catalog growth

Not-found cases are strategically valuable.

### 15.1 Not-found rule

If the system does not find the query, it should say so directly.

No fake results.
No hallucinated matches.
No desperate approximation presented as truth.

### 15.2 Why not-found logging matters

Search failures help improve:

- catalog completeness;
- alias coverage;
- transliteration support;
- brand normalization;
- compound composition indexing.

### 15.3 Search query log

The system should log:

- raw query;
- normalized query;
- source (text/voice);
- found_count;
- top_hit if any;
- timestamp.

This becomes a growth signal for catalog maintenance.

---

## 16. “Find alternative” model

A product can expose “find alternative” only if the alternative logic is explicit.

### 16.1 Alternative classes

#### Exact active analogue

Same active substance / ester and close composition profile.

#### Composition-level analogue

Functionally similar composition, different brand or presentation.

#### Broader functional analogue (later)

A wider replacement concept, to be used later and probably specialist-facing.

### 16.2 MVP recommendation

For MVP, support only:

- exact active analogue;
- composition-level analogue.

Do not pretend broader analog logic is safe if the data model cannot support it yet.

---

## 17. Search document lifecycle

### 17.1 Search documents are projections

Search docs must be rebuildable from transactional catalog truth.

### 17.2 Reindex triggers

Reindex should happen after:

- compound created;
- compound updated;
- brand updated;
- alias updated;
- composition updated;
- sync run completed.

### 17.3 Rebuild mode

The system should support:

- incremental projection updates;
- full index rebuild.

---

## 18. Meilisearch index strategy

### 18.1 Index scope

At minimum, v1 should maintain a dedicated compound search index.

Optional later indexes:

- specialist-side user index;
- active protocol index;
- expert-case retrieval index.

### 18.2 Search document design principle

The Meilisearch document must contain enough flattened, normalized material to support search without forcing runtime joins.

### 18.3 Index update principle

Index updates must be asynchronous where practical and idempotent.

### 18.4 Operational rule

The product must not depend on manual reindex heroics after every normal catalog change.

---

## 19. Search fallback model

### 19.1 If Meilisearch is unavailable

The system should degrade to reduced lookup via DB-based exact/normalized search.

### 19.2 What fallback should still support

Minimum fallback capability:

- exact trade name match;
- exact normalized brand+product match;
- exact substance match in composition entries.

### 19.3 What fallback does not need to do perfectly

Fallback does not need to match Meilisearch quality for:

- fuzzy slang;
- deep noisy matching;
- advanced voice-derived parsing.

The goal is degraded operation, not equal quality.

---

## 20. Search model and draft flow

Search exists to feed calculation.

### 20.1 Draft relation

When a user clicks `+Draft`, the system should not clone arbitrary search text.
It should add the concrete `compound_id` to the calculation draft context.

### 20.2 Why this matters

Draft must be based on stable product identity, not on display strings.

### 20.3 Search-to-draft rule

Search is retrieval.
Draft is protocol preparation.
These must connect cleanly but remain distinct.

---

## 21. Search analytics and quality signals

The system should track search quality signals from day one.

### 21.1 Useful search metrics

- total searches;
- zero-result rate;
- top query clusters;
- voice vs text share;
- open rate from search result;
- add-to-draft rate from search result;
- not-found query families;
- brand alias mismatch frequency.

### 21.2 Why this matters

Because search quality is product quality in a search-first system.

---

## 22. Search model guardrails

The system must avoid the following mistakes.

### 22.1 Shop drift

Do not turn search into a hidden storefront with catalog browsing disguised as search.

### 22.2 Search-only-without-catalog delusion

Do not pretend search can work well without a proper internal compound catalog.

### 22.3 Exact-name fragility

Do not build search that only works when the user types the exact pristine catalog name.

### 22.4 Fuzzy chaos

Do not let noisy fuzzy matching swamp exact trade-name retrieval.

### 22.5 Draft-from-free-text

Do not allow unstable free-text draft lines when a real `compound_id` match exists.

### 22.6 Voice-as-general-AI-chat

Do not let voice search become unrestricted chat in v1.

---

## 23. Recommended future dependent documents

This search model should feed the creation of:

- `docs/45_search_index_schema.md`
- `docs/46_search_ranking_rules.md`
- `docs/47_voice_search_pipeline.md`
- `docs/48_search_to_draft_flow.md`
- `docs/70_search_analytics.md`

These names are recommendations and may change.

---

## 24. Final search model statement

CycleSync search must be built as a **search-first facade over a full internal compound registry**.

For the user, there is no storefront and no public catalog mode.  
For the system, there is a rich catalog domain, projection model and Meilisearch-powered retrieval layer.

Search must support:

- trade-name retrieval;
- brand-aware retrieval;
- substance/ester retrieval;
- composition-aware dosage retrieval;
- voice-assisted lookup;
- direct transition into `Open` and `+Draft` actions.

This document defines the retrieval spine of CycleSync.
