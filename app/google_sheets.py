from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

from .column_map import validate_header_row
from .config import Settings


class SheetsError(RuntimeError):
    pass


@dataclass
class SheetsGateway:
    settings: Settings
    _credentials: Any = field(default=None, init=False, repr=False)

    def _bearer_token(self) -> str:
        if self.settings.google_service_account_json:
            try:
                if self._credentials is None:
                    info = json.loads(self.settings.google_service_account_json)
                    self._credentials = service_account.Credentials.from_service_account_info(
                        info,
                        scopes=["https://www.googleapis.com/auth/spreadsheets"],
                    )
                if not self._credentials.valid:
                    self._credentials.refresh(GoogleAuthRequest())
                return str(self._credentials.token or "")
            except Exception as exc:
                raise SheetsError(f"Invalid Google service account configuration: {exc}") from exc

        return self.settings.google_access_token

    def _auth_headers(self) -> dict[str, str]:
        token = self._bearer_token()
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request(
        self,
        method: str,
        url: str,
        *,
        payload: dict | None = None,
        params: dict[str, str] | None = None,
    ) -> dict:
        query = dict(params or {})
        if not self._bearer_token():
            if not self.settings.google_api_key:
                raise SheetsError(
                    "Configure GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_ACCESS_TOKEN "
                    "or GOOGLE_API_KEY for read-only public access."
                )
            query["key"] = self.settings.google_api_key

        try:
            response = httpx.request(
                method,
                url,
                headers=self._auth_headers(),
                params=query,
                json=payload,
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise SheetsError(
                f"Google Sheets HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SheetsError(f"Google Sheets network error: {exc}") from exc

    def _values_url(self, a1_range: str) -> str:
        escaped = quote(a1_range, safe="!:'")
        return (
            "https://sheets.googleapis.com/v4/spreadsheets/"
            f"{self.settings.spreadsheet_id}/values/{escaped}"
        )

    def read_values(self, a1_range: str) -> list[list[object]]:
        result = self._request("GET", self._values_url(a1_range))
        return result.get("values", [])

    def verify_template(self) -> dict:
        a1 = (
            f"'{self.settings.sheet_name}'!"
            f"A{self.settings.header_row}:AF{self.settings.header_row}"
        )
        values = self.read_values(a1)
        header = values[0] if values else []
        mismatches = validate_header_row([str(value) for value in header])
        return {
            "ok": not mismatches,
            "spreadsheet_id": self.settings.spreadsheet_id,
            "sheet_name": self.settings.sheet_name,
            "header_row": self.settings.header_row,
            "auth_mode": self.settings.sheet_auth_mode,
            "mismatches": mismatches,
        }

    def _cell_metadata(self, cell: str) -> dict:
        a1 = f"'{self.settings.sheet_name}'!{cell}"
        url = (
            "https://sheets.googleapis.com/v4/spreadsheets/"
            f"{self.settings.spreadsheet_id}"
        )
        result = self._request(
            "GET",
            url,
            params={"includeGridData": "true", "ranges": a1},
        )
        try:
            return result["sheets"][0]["data"][0]["rowData"][0]["values"][0]
        except (KeyError, IndexError, TypeError):
            return {}

    @staticmethod
    def _is_blue_text(metadata: dict) -> bool:
        text_format = (
            metadata.get("effectiveFormat", {})
            .get("textFormat", {})
        )
        color = text_format.get("foregroundColor", {})
        if not color:
            color = (
                text_format.get("foregroundColorStyle", {})
                .get("rgbColor", {})
            )
        red = float(color.get("red", 0.0) or 0.0)
        green = float(color.get("green", 0.0) or 0.0)
        blue = float(color.get("blue", 0.0) or 0.0)
        return blue >= 0.45 and blue > red + 0.15 and blue > green + 0.05

    def guard_cells(self, cells: list[str]) -> None:
        for cell in cells:
            metadata = self._cell_metadata(cell)
            user_value = metadata.get("userEnteredValue", {})
            if "formulaValue" in user_value:
                raise SheetsError(f"Blocked formula cell: {cell}.")
            if self._is_blue_text(metadata):
                raise SheetsError(f"Blocked blue-text cell: {cell}.")

    def batch_update_cells(self, changes: list[tuple[str, object]]) -> dict:
        if not self.settings.allow_sheet_write:
            raise SheetsError(
                "Sheet writes are disabled. Set ALLOW_SHEET_WRITE=true only "
                "after the read-only validation stage."
            )
        if self.settings.sheet_auth_mode not in {"service_account", "oauth_bearer"}:
            raise SheetsError("Writes require OAuth or a Google service account.")
        if not changes:
            raise SheetsError("No changes supplied.")

        cells = [cell for cell, _ in changes]
        self.guard_cells(cells)

        data = []
        for cell, value in changes:
            a1 = f"'{self.settings.sheet_name}'!{cell}"
            data.append(
                {
                    "range": a1,
                    "majorDimension": "ROWS",
                    "values": [[value]],
                }
            )

        url = (
            "https://sheets.googleapis.com/v4/spreadsheets/"
            f"{self.settings.spreadsheet_id}/values:batchUpdate"
        )
        return self._request(
            "POST",
            url,
            payload={"valueInputOption": "USER_ENTERED", "data": data},
        )
