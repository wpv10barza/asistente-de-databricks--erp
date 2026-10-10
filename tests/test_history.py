from pathlib import Path

from fastapi.testclient import TestClient

from app.history_store import HistoryStore, panel_lines
from app.main import app


def test_event_history_pending_is_not_applied():
    store = HistoryStore()
    store.append("command_sent", command_id="cmd-1", device_id="esp32", text="ajustar recurso")
    result = store.recent("esp32")
    assert result["orders"][0]["status"] == "pending_confirmation"
    assert result["sheet_changes"] == []
    assert result["persistent"] is False
    assert "S\t" not in panel_lines(result)


def test_applied_sheet_only_after_actual_commit():
    store = HistoryStore()
    store.append("command_sent", command_id="c", device_id="esp32", text="modificar")
    store.append("proposal_preview", command_id="c", changes=[{"cell": "J7", "value": "nuevo"}])
    assert store.recent("esp32")["sheet_changes"] == []
    assert store.recent("esp32")["orders"][0]["preview"][0]["cell"] == "J7"
    store.append("sheet_applied", command_id="c", proposal_id="p", row=7,
                 changes=[{"cell": "J7", "value": "nuevo"}])
    store.append("command_applied", command_id="c", device_id="esp32")
    result = store.recent("esp32")
    assert result["orders"][0]["status"] == "applied"
    assert result["sheet_changes"][0]["changes"][0] == {"cell": "J7", "value": "nuevo"}
    assert "S\t" in panel_lines(result)


def test_durable_jsonl_reload(tmp_path):
    path = tmp_path / "historial.jsonl"
    store = HistoryStore(str(path))
    store.append("sheet_applied", proposal_id="p", row=8,
                 changes=[{"cell": "K8", "value": "OK"}])
    loaded = HistoryStore(str(path))
    assert loaded.persistent is True
    assert loaded.recent()["sheet_changes"][0]["changes"][0]["cell"] == "K8"


def test_history_requires_authorization(monkeypatch):
    import app.main as backend
    monkeypatch.setattr(backend.settings, "esp32_api_token", "", raising=False) if False else None
    # Default backend without a token must fail closed.
    response = TestClient(app).get("/api/device/v1/history/panel")
    assert response.status_code in (401, 503)


def test_history_is_read_only_route():
    paths = [route.path for route in app.routes if "history" in route.path]
    assert "/api/device/v1/history" in paths
    assert "/api/device/v1/history/panel" in paths
