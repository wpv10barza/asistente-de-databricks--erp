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
