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


def test_command_transitions_do_not_invent_sheet_writes():
    import pytest

    store = DeviceCommandStore()
    command, _ = store.enqueue({"device_id": "panel", "request_id": "r-flow", "text": "Cambiar tarea"})
    cid = command["id"]
    assert command["status"] == "pending_confirmation"
    assert command["proposal_id"] is None
    preview = store.update(cid, "pending_review", proposal_id="proposal-1")
    assert preview["status"] == "pending_review"
    assert preview["proposal_id"] == "proposal-1"
    approved = store.update(cid, "approved_not_applied", proposal_id="proposal-1")
    assert approved["status"] == "approved_not_applied"
    with pytest.raises(ValueError, match="Transicion"):
        store.update(cid, "pending_review")
    with pytest.raises(ValueError, match="otra propuesta"):
        store.update(cid, "applied", proposal_id="proposal-2")
    applied = store.update(cid, "applied", proposal_id="proposal-1")
    assert applied["status"] == "applied"
    assert store.update(cid, "applied")["status"] == "applied"
    with pytest.raises(ValueError, match="Transicion"):
        store.update(cid, "rejected")


def test_linked_proposal_updates_status_without_sheet_write(monkeypatch):
    from app import main as backend
    from app.history_store import HistoryStore
    from app.review_store import ReviewStore
    from app.google_sheets import SheetsError

    monkeypatch.setattr(backend, "device_commands", DeviceCommandStore())
    monkeypatch.setattr(backend, "review_store", ReviewStore())
    monkeypatch.setattr(backend, "history_store", HistoryStore())
    monkeypatch.setattr(backend.gateway, "verify_template", lambda: {"ok": True})

    def forbid_write(_changes):
        raise SheetsError("Writes disabled")

    monkeypatch.setattr(backend.gateway, "batch_update_cells", forbid_write)
    command, _ = backend.device_commands.enqueue({
        "device_id": "panel", "request_id": "r-proposal", "text": "Cambiar tarea"
    })
    with TestClient(backend.app) as client:
        proposal = client.post("/api/review/proposals", json={
            "row": 7, "matched": "Tarea", "external_command_id": command["id"],
            "operations": [{
                "campo": "frecuencia", "columna_actualizar": "L",
                "encabezado": "Frecuencia", "valor_actualizar": 1,
            }],
        })
        assert proposal.status_code == 201
        pid = proposal.json()["id"]
        assert backend.device_commands.get(command["id"])["status"] == "pending_review"
        approved = client.post(f"/api/review/proposals/{pid}/approve")
        assert approved.status_code == 200
        assert backend.device_commands.get(command["id"])["status"] == "approved_not_applied"
        blocked = client.post(f"/api/review/proposals/{pid}/apply")
        assert blocked.status_code == 502
        assert backend.device_commands.get(command["id"])["status"] == "approved_not_applied"
        assert backend.history_store.recent("panel")["sheet_changes"] == []


def test_command_cannot_be_applied_without_proposal():
    import pytest

    store = DeviceCommandStore()
    command, _ = store.enqueue({"device_id": "panel", "request_id": "r-safe", "text": "Cambiar tarea"})
    with pytest.raises(ValueError, match="Transicion"):
        store.update(command["id"], "applied")
