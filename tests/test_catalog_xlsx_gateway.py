import asyncio
from pathlib import Path

from app.infrastructure.catalog.xlsx_gateway import XlsxCatalogConfig, XlsxCatalogGateway


def test_xlsx_gateway_reads_seed_catalog() -> None:
    workbook = Path('docs/medical.xlsx')

    async def _run() -> None:
        rows = await XlsxCatalogGateway(XlsxCatalogConfig(workbook_path=str(workbook), sheet_name='Catalog')).fetch_rows()
        assert len(rows) == 4
        assert rows[0]['brand'] == 'SP Laboratories'
        assert rows[-1]['trade_name'] == 'SP Sustanon FORTE'

    asyncio.run(_run())
