import json
from dataclasses import dataclass

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account


@dataclass(slots=True)
class GoogleSheetsConfig:
    sheet_id: str
    tab_name: str
    credentials_path: str | None
    service_account_json: str | None
    use_service_account: bool


class GoogleSheetsCatalogGateway:
    def __init__(self, config: GoogleSheetsConfig) -> None:
        self._config = config

    def _get_access_token(self) -> str:
        if not self._config.use_service_account:
            raise RuntimeError("Service account mode is disabled")

        creds_info: dict | None = None
        if self._config.service_account_json:
            creds_info = json.loads(self._config.service_account_json)

        if creds_info is not None:
            credentials = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
            )
        elif self._config.credentials_path:
            credentials = service_account.Credentials.from_service_account_file(
                self._config.credentials_path,
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
            )
        else:
            raise RuntimeError("Google Sheets credentials are not configured")

        credentials.refresh(Request())
        token = credentials.token
        if not token:
            raise RuntimeError("Failed to obtain Google access token")
        return token

    async def fetch_rows(self) -> list[dict[str, str]]:
        range_expr = f"{self._config.tab_name}!A:Z"
        encoded_range = httpx.QueryParams({"ranges": range_expr})
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{self._config.sheet_id}/values:batchGet"
            f"?{encoded_range}&majorDimension=ROWS"
        )

        headers: dict[str, str] = {}
        if self._config.use_service_account:
            headers["Authorization"] = f"Bearer {self._get_access_token()}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        payload = response.json()
        ranges = payload.get("valueRanges", [])
        if not ranges:
            return []

        values = ranges[0].get("values", [])
        if not values:
            return []

        headers_row = [str(cell).strip() for cell in values[0]]
        rows: list[dict[str, str]] = []
        for row in values[1:]:
            entry = {header: str(row[idx]).strip() if idx < len(row) else "" for idx, header in enumerate(headers_row)}
            rows.append(entry)
        return rows
