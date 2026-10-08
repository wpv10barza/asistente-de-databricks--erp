import pytest

from app.config import Settings
from app.google_sheets import SheetsError, SheetsGateway


def make_settings(**overrides):
    values = {
        "spreadsheet_id": "sheet-id",
        "sheet_name": "Data",
        "header_row": 4,
        "google_api_key": "",
        "google_access_token": "",
        "google_service_account_json": "",
        "allow_sheet_write": False,
        "gemini_api_key": "",
        "gemini_model": "gemini-test",
        "esp32_api_token": "",
        "allow_insecure_device_api": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_sheet_auth_unconfigured():
    assert make_settings().sheet_auth_mode == "unconfigured"


def test_write_disabled_is_fail_closed():
    gateway = SheetsGateway(make_settings(google_access_token="temporary"))
    with pytest.raises(SheetsError, match="disabled"):
        gateway.batch_update_cells([("J5", "x")])


def test_template_mismatch_is_detected(monkeypatch):
    gateway = SheetsGateway(make_settings(google_api_key="read-key"))
    monkeypatch.setattr(
        gateway,
        "read_values",
        lambda _range: [["EstrategiaId", "WRONG"]],
    )
    result = gateway.verify_template()
    assert result["ok"] is False
    assert result["mismatches"]


def test_blue_text_detector():
    metadata = {
        "effectiveFormat": {
            "textFormat": {
                "foregroundColor": {"red": 0.0, "green": 0.2, "blue": 0.9}
            }
        }
    }
    assert SheetsGateway._is_blue_text(metadata) is True


def test_black_text_is_not_blue():
    metadata = {
        "effectiveFormat": {
            "textFormat": {
                "foregroundColor": {"red": 0.0, "green": 0.0, "blue": 0.0}
            }
        }
    }
    assert SheetsGateway._is_blue_text(metadata) is False
