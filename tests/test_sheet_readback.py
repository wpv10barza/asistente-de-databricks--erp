"""Google Sheets write is only successful after an authentic cell-value readback.

All Google calls are mocked. These tests never modify a spreadsheet.
"""
from dataclasses import replace

from fastapi.testclient import TestClient

from app import main as backend
from app.device_store import DeviceCommandStore
from app.history_store import HistoryStore
from app.review_store import ReviewStore


def _setup(monkeypatch, *, writes_reach_sheet: bool):
    monkeypatch.setattr(
        backend, "settings", replace(backend.settings, allow_sheet_write=True)
    )
    monkeypatch.setattr(backend, "device_commands", DeviceCommandStore())
    monkeypatch.setattr(backend, "review_store", ReviewStore())
    monkeypatch.setattr(backend, "history_store", HistoryStore())
    monkeypatch.setattr(backend.gateway, "verify_template", lambda: {"ok": True})
    simulated_row = [""] * 32
    simulated_row[4] = "102497"
    simulated_row[11] = "3"
    simulated_row[12] = "Mes"

    def read_values(_range):
        return [list(simulated_row)]

    def batch_update_cells(changes):
        if writes_reach_sheet:
            for cell, value in changes:
                col = "".join(ch for ch in cell if ch.isalpha())
                simulated_row[ord(col) - ord("A")] = str(value)
        return {"totalUpdatedCells": len(changes)}

    monkeypatch.setattr(backend.gateway, "read_values", read_values)
    monkeypatch.setattr(backend.gateway, "batch_update_cells", batch_update_cells)
    command, _ = backend.device_commands.enqueue({
        "device_id": "panel", "request_id": "verify-1",
        "text": "Cambiar tarea 102497 a seis meses"
    })
    return command, simulated_row


def _make_proposal(client, command):
    response = client.post("/api/review/proposals", json={
        "row": 6,
        "external_command_id": command["id"],
        "matched": "TareaId=102497",
        "operations": [
            {
                "campo": "frecuencia", "columna_actualizar": "L",
                "encabezado": "Frecuencia", "valor_actualizar": 6,
            },
            {
                "campo": "unidad", "columna_actualizar": "M",
                "encabezado": "UnidadTiempo", "valor_actualizar": "Mes",
            },
        ]
    })
    assert response.status_code == 201
    proposal_id = response.json()["id"]
    assert client.post(f"/api/review/proposals/{proposal_id}/approve").status_code == 200
    return proposal_id


def test_readback_reports_real_frequency_change_and_unchanged_unit(monkeypatch):
    command, row = _setup(monkeypatch, writes_reach_sheet=True)
    with TestClient(backend.app) as client:
        proposal_id = _make_proposal(client, command)
        response = client.post(f"/api/review/proposals/{proposal_id}/apply")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "applied"
    assert body["post_write_verification"] == "live_google_sheets_readback"
    changes = body["verified_changes"]
    assert changes[0] == {
        "cell": "L6", "field": "Frecuencia", "before": "3",
        "after": "6", "changed": True, "verified": True,
    }
    assert changes[1] == {
        "cell": "M6", "field": "UnidadTiempo", "before": "Mes",
        "after": "Mes", "changed": False, "verified": True,
    }
    assert row[11:13] == ["6", "Mes"]
    status = backend.device_commands.get(command["id"])
    assert status["status"] == "applied"
    assert "102497" in status["result"] and "L6=6 M6=Mes" in status["result"]
    assert len(backend.history_store.recent("panel")["sheet_changes"]) == 1


def test_successful_batch_api_without_cell_change_is_not_applied(monkeypatch):
    command, row = _setup(monkeypatch, writes_reach_sheet=False)
    with TestClient(backend.app) as client:
        proposal_id = _make_proposal(client, command)
        response = client.post(f"/api/review/proposals/{proposal_id}/apply")
    assert response.status_code == 502
    assert row[11] == "3"
    assert backend.device_commands.get(command["id"])["status"] == "approved_not_applied"
    assert backend.history_store.recent("panel")["sheet_changes"] == []
    assert backend.history_store.recent("panel")["summary"]["blocked"] == 1
