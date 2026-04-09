from time import perf_counter
from typing import Any

import httpx

from app.application.search.gateway import SearchGatewayError
from app.application.search.schemas import SearchDocument


class MeiliSearchGateway:
    def __init__(self, base_url: str, api_key: str, index_name: str, timeout_seconds: float = 2.0) -> None:
        self.index_name = index_name
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = httpx.AsyncClient(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout_seconds)

    async def close(self) -> None:
        await self.client.aclose()

    async def ensure_index(self) -> None:
        try:
            response = await self.client.post("/indexes", json={"uid": self.index_name, "primaryKey": "id"})
            if response.status_code not in (200, 201, 202, 400):
                raise SearchGatewayError(f"failed to ensure index: {response.text}")

            await self.client.patch(
                f"/indexes/{self.index_name}/settings",
                json={
                    "searchableAttributes": [
                        "trade_name",
                        "product_name",
                        "brand",
                        "aliases",
                        "ingredient_names",
                        "ester_component_tokens",
                        "concentration_tokens",
                        "dosage_unit_tokens",
                        "normalized_tokens",
                    ],
                    "filterableAttributes": ["brand", "form_factor"],
                    "displayedAttributes": [
                        "id",
                        "product_id",
                        "product_name",
                        "brand",
                        "composition_summary",
                        "form_factor",
                        "official_url",
                        "authenticity_notes",
                        "media_refs",
                    ],
                },
            )
        except httpx.HTTPError as exc:  # pragma: no cover
            raise SearchGatewayError(f"meili ensure index failed: {exc}") from exc

    async def upsert_documents(self, documents: list[SearchDocument]) -> None:
        payload = [doc.__dict__ for doc in documents]
        try:
            response = await self.client.post(f"/indexes/{self.index_name}/documents", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover
            raise SearchGatewayError(f"meili upsert failed: {exc}") from exc

    async def delete_documents(self, document_ids: list[str]) -> None:
        if not document_ids:
            return
        try:
            response = await self.client.post(f"/indexes/{self.index_name}/documents/delete-batch", json=document_ids)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover
            raise SearchGatewayError(f"meili delete failed: {exc}") from exc

    async def search(self, query: str, limit: int = 10, offset: int = 0) -> tuple[list[dict], int]:
        try:
            response = await self.client.post(
                f"/indexes/{self.index_name}/search",
                json={
                    "q": query,
                    "limit": limit,
                    "offset": offset,
                    "showRankingScore": False,
                },
            )
            response.raise_for_status()
            body = response.json()
            hits = body.get("hits", [])
            estimated_total = int(body.get("estimatedTotalHits", len(hits)))
            return hits, estimated_total
        except httpx.HTTPError as exc:
            raise SearchGatewayError(f"meili search failed: {exc}") from exc

    async def healthcheck(self) -> dict[str, Any]:
        started = perf_counter()
        try:
            response = await self.client.get("/health")
            response.raise_for_status()
            latency_ms = round((perf_counter() - started) * 1000, 2)
            return {
                "ok": True,
                "status": "ok",
                "latency_ms": latency_ms,
            }
        except httpx.HTTPError as exc:  # pragma: no cover
            return {
                "ok": False,
                "status": "error",
                "latency_ms": round((perf_counter() - started) * 1000, 2),
                "error": str(exc),
            }
