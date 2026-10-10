from fastapi.testclient import TestClient

from app.config import Settings
from app.device_store import DeviceCommandStore, normalize_device_command, verify_device_token
from app.main import app, settings

client = TestClient(app)


def test_normalize_device_command():
    command = normalize_device_command(
        {"device_id": "esp-hi-3c-01", "request_id": "req-1", "text": "Revisar tarea"}
    )
    assert command["device_id"] == "esp-hi-3c-01"
    assert command["request_id"] == "req-1"


def test_device_store_is_idempotent():
    store = DeviceCommandStore()
    command = {"device_id": "esp-1", "request_id": "same", "text": "hola"}
    first, duplicate1 = store.enqueue(command)
    second, duplicate2 = store.enqueue(command)
    assert duplicate1 is False
    assert duplicate2 is True
    assert first["id"] == second["id"]


def test_token_compare():
    assert verify_device_token("abc", "abc") is True
    assert verify_device_token("abc", "abd") is False
    assert verify_device_token("", "") is False


def test_device_api_fails_closed_without_token():
    if settings.esp32_api_token or settings.allow_insecure_device_api:
        return
    response = client.post(
        "/api/device/v1/commands",
        json={"device_id": "esp-1", "request_id": "r-1", "text": "test"},
    )
    assert response.status_code == 503

def test_recent_command_history_scoped_and_only_applied_has_changes():
    store = DeviceCommandStore()
    a, _ = store.enqueue({"device_id": "panel-a", "request_id": "1", "text": "Cambiar J10"})
    b, _ = store.enqueue({"device_id": "panel-b", "request_id": "2", "text": "Otra orden"})
    assert store.recent("panel-a")["total"] == 1
    pending = store.recent("panel-a")
    assert pending["status"] == "pending_confirmation"
    assert pending["change_count"] == 0
    assert pending["changes_summary"] == ""
    store.update(a["id"], "applied", "Google Sheets actualizado", changes=[("J10", "mensual")])
    applied = store.recent("panel-a")
    assert applied["status"] == "applied"
    assert applied["change_count"] == 1
    assert "J10: mensual" in applied["changes_summary"]
    assert store.recent("panel-a", 1)["status"] == "empty"
    assert store.recent("panel-b")["command_id"] == b["id"]


def test_recent_history_endpoint_protected_and_scoped(monkeypatch):
    from dataclasses import replace
    from app import main as module
    store = DeviceCommandStore()
    store.enqueue({"device_id": "panel-a", "request_id": "hist", "text": "Revisar recurso"})
    monkeypatch.setattr(module, "device_commands", store)
    monkeypatch.setattr(module, "settings", replace(module.settings,
        esp32_api_token="test-history-secret", allow_insecure_device_api=False))
    denied = client.get("/api/device/v1/commands/history?device_id=panel-a")
    assert denied.status_code == 401
    response = client.get("/api/device/v1/commands/history?device_id=panel-a",
        headers={"X-3C-Device-Token": "test-history-secret"})
    assert response.status_code == 200
    assert response.json()["status"] == "pending_confirmation"
    assert response.json()["change_count"] == 0
    assert client.get("/api/device/v1/commands/history?device_id=panel-a&offset=-1",
        headers={"X-3C-Device-Token": "test-history-secret"}).status_code == 400


def test_recent_history_expires_and_never_claims_unconfirmed_change():
    store = DeviceCommandStore(ttl_seconds=1)
    command, _ = store.enqueue({"device_id": "panel", "request_id": "x", "text": "Cambiar"})
    command_ref = store._commands[0]
    command_ref["_created_epoch"] -= 5
    assert store.recent("panel")["total"] == 0
