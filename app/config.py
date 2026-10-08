from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    spreadsheet_id: str = os.getenv(
        "SPREADSHEET_ID",
        "1tLNo0_xjtmWKM9Y7PcChFut8S0w0kMKeAvFi9zg52gA",
    )
    sheet_name: str = os.getenv("SHEET_NAME", "Data")
    header_row: int = int(os.getenv("HEADER_ROW", "4"))

    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    google_access_token: str = os.getenv("GOOGLE_ACCESS_TOKEN", "")
    google_service_account_json: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    allow_sheet_write: bool = os.getenv("ALLOW_SHEET_WRITE", "false").lower() == "true"

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    esp32_api_token: str = os.getenv("ESP32_API_TOKEN", "")
    allow_insecure_device_api: bool = (
        os.getenv("ALLOW_INSECURE_DEVICE_API", "false").lower() == "true"
    )

    ota_volume_path: str = os.getenv("OTA_VOLUME_PATH", "")
    ota_channel: str = os.getenv("OTA_CHANNEL", "stable")

    @property
    def sheet_auth_mode(self) -> str:
        if self.google_service_account_json:
            return "service_account"
        if self.google_access_token:
            return "oauth_bearer"
        if self.google_api_key:
            return "api_key_read_only"
        return "unconfigured"

    @property
    def databricks_runtime(self) -> bool:
        return bool(os.getenv("DATABRICKS_APP_PORT") or os.getenv("DATABRICKS_RUNTIME_VERSION"))
