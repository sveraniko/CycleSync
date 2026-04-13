import asyncio
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.application.catalog.mapping import map_sheet_row
from app.application.search.normalization import tokenize_for_search
from app.application.search.projection import CompoundSearchProjectionBuilder
from app.application.search.schemas import CatalogIngredientRow, CatalogProjectionRow
from app.infrastructure.catalog.xlsx_gateway import XlsxCatalogConfig, XlsxCatalogGateway


def _projection_docs(rows: list[dict[str, str]]) -> list[dict]:
    builder = CompoundSearchProjectionBuilder()
    documents = []
    for row in rows:
        product, issue = map_sheet_row(row=row, row_number=0)
        assert issue is None and product is not None
        projection = CatalogProjectionRow(
            product_id=uuid5(NAMESPACE_URL, f"cyclesync:{product.source_row_key}"),
            product_name=product.display_name,
            trade_name=product.trade_name,
            brand_name=product.brand_name,
            release_form=product.release_form,
            concentration_raw=product.concentration_raw,
            aliases=product.aliases,
            ingredients=[
                CatalogIngredientRow(
                    ingredient_name=ingredient.ingredient_name,
                    amount=str(ingredient.amount) if ingredient.amount is not None else None,
                    unit=ingredient.unit,
                    qualifier=ingredient.qualifier,
                )
                for ingredient in product.ingredients
            ],
            official_url=product.official_url,
            authenticity_notes=product.authenticity_notes,
            media_refs=[],
        )
        doc = builder.build_document(projection)
        documents.append({
            'trade_name': doc.trade_name,
            'pool': set(doc.normalized_tokens) | set(doc.ester_component_tokens) | set(doc.concentration_tokens) | set(doc.dosage_unit_tokens),
        })
    return documents


def _hits(query: str, documents: list[dict]) -> list[str]:
    tokens = set(tokenize_for_search(query))
    hits = [doc['trade_name'] for doc in documents if tokens and tokens.issubset(doc['pool'])]
    return sorted(hits)


def test_seed_catalog_search_regressions() -> None:
    workbook = Path('docs/medical.xlsx')

    async def _load(sheet: str) -> list[dict[str, str]]:
        return await XlsxCatalogGateway(XlsxCatalogConfig(workbook_path=str(workbook), sheet_name=sheet)).fetch_rows()

    catalog_rows = asyncio.run(_load('Catalog'))
    cases = asyncio.run(_load('SearchCases'))
    docs = _projection_docs(catalog_rows)

    for case in cases:
        hits = _hits(case['query'], docs)
        if case['expected_hit'] == 'yes':
            assert hits, case['query']
            assert hits[0] == case['expected_primary_trade_name'], case['query']
        else:
            assert not hits, case['query']
