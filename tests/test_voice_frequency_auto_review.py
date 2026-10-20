"""End-to-end voice command to human review, with mocked Google Sheets only."""
from dataclasses import replace

from fastapi.testclient import TestClient

from app import main as backend
from app.device_store import DeviceCommandStore
from app.frequency_commands import parse_frequency_command, unique_task_row
from app.review_store import ReviewStore
from app.history_store import HistoryStore


def test_parser_accepts_only_explicit_unambiguous_commands():
    assert parse_frequency_command("cambiar la tarea 102497 a seis meses") == ("102497", 6, "Mes")
    assert parse_frequency_command("Cambia tarea 102497 a 6 años") == ("102497", 6, "año")
    assert parse_frequency_command("modificar 102497 cada 3 dias") == ("102497", 3, "Dia")
    assert parse_frequency_command("no cambiar tarea 102497 a 6 meses") is None
    assert parse_frequency_command("cambiar 102497 pronto") is None
    assert parse_frequency_command("cambiar la tarea 102497 a menos uno meses") is None
    assert parse_frequency_command("cambiar la tarea 102497 a 0 meses") is None
    assert parse_frequency_command("cambiar la tarea 102497 a 999999 meses") is None


def _setup(monkeypatch, *, unique=True):
    monkeypatch.setattr(backend, "settings", replace(
        backend.settings, allow_sheet_write=True, esp32_api_token="device-test-only",
        review_approval_token="reviewer-test-only",
    ))
    monkeypatch.setattr(backend, "device_commands", DeviceCommandStore())
    monkeypatch.setattr(backend, "review_store", ReviewStore())
    monkeypatch.setattr(backend, "history_store", HistoryStore())
    monkeypatch.setattr(backend.gateway, "verify_template", lambda: {"ok": True})
    before = [""] * 32
    before[4] = "102497"
    before[11] = "3"
    before[12] = "Mes"

    def read_values(a1):
        if "E5:E1000" in a1:
            rows = [[""], ["102497"]]
            if not unique:
                rows.append(["102497"])
            return rows
        if "A6:AF6" in a1:
            return [before[:]]
        raise AssertionError("Unexpected Google Sheets query: " + a1)

    def update_cells(changes):
        for cell, value in changes:
            before[ord(cell[0]) - ord("A")] = str(value)
        return {"totalUpdatedCells": len(changes)}

    monkeypatch.setattr(backend.gateway, "read_values", read_values)
    monkeypatch.setattr(backend.gateway, "batch_update_cells", update_cells)
    return before


def test_voice_to_proposal_auth_approval_readback_and_result(monkeypatch):
    row = _setup(monkeypatch)
    dev_headers = {"X-3C-Device-Token": "device-test-only"}
    reviewer = {"X-3C-Review-Token": "reviewer-test-only"}
    with TestClient(backend.app) as client:
        sent = client.post("/api/device/v1/commands", headers=dev_headers, json={
            "device_id": "panel-4848s040-3c-ota-2f26ec3f",
            "request_id": "voice-review-test-1",
            "text": "cambiar la tarea 102497 a seis meses",
        })
        assert sent.status_code == 200, sent.text
        assert sent.json()["status"] == "pending_review"
        command_id = sent.json()["command_id"]
        assert row[11:13] == ["3", "Mes"]
        assert client.get("/api/review/queue").status_code == 403
        assert client.get("/api/review/queue", headers=dev_headers).status_code == 403
        snapshot = client.get("/api/review/queue", headers=reviewer)
        assert snapshot.status_code == 200, snapshot.text
        proposal = snapshot.json()["proposal"]
        assert proposal["row"] == 6
        assert [(c["cell"], c["wanted"]) for c in snapshot.json()["changes"]] == [
            ("L6", 6), ("M6", "Mes"),
        ]
        pid = proposal["id"]
        assert client.post(f"/api/review/proposals/{pid}/approve", headers=dev_headers).status_code == 403
        assert client.post(f"/api/review/proposals/{pid}/apply", headers=reviewer).status_code == 409
        assert row[11:13] == ["3", "Mes"]
        assert client.post(f"/api/review/proposals/{pid}/approve", headers=reviewer).status_code == 200
        assert client.get("/api/review/queue", headers=reviewer).json()["proposal"]["status"] == "approved"
        applied = client.post(f"/api/review/proposals/{pid}/apply", headers=reviewer)
        assert applied.status_code == 200, applied.text
        assert applied.json()["post_write_verification"] == "live_google_sheets_readback"
        assert [(v["cell"], v["changed"]) for v in applied.json()["verified_changes"]] == [
            ("L6", True), ("M6", False),
        ]
        assert row[11:13] == ["6", "Mes"]
        command = client.get(f"/api/device/v1/commands/{command_id}", headers=dev_headers)
        assert command.status_code == 200
        assert command.json()["command"]["status"] == "applied"
        assert "L6=6 M6=Mes VERIFICADO" in command.json()["command"]["result"]


def test_ambiguous_task_id_never_generates_automatic_proposal(monkeypatch):
    _setup(monkeypatch, unique=False)
    with TestClient(backend.app) as client:
        result = client.post("/api/device/v1/commands",
            headers={"X-3C-Device-Token": "device-test-only"}, json={
            "device_id": "panel", "request_id": "conflict-1",
            "text": "cambiar tarea 102497 a seis meses",
        })
        assert result.status_code == 200
        assert result.json()["status"] == "pending_confirmation"
        assert backend.review_store._proposals == {}
