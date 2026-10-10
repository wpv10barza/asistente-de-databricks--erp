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


def test_audit_enumerates_decisions_and_attempts_without_fabricated_writes():
    store = HistoryStore()
    store.append("command_sent", command_id="c1", device_id="panel", text="Cambiar frecuencia")
    store.append("proposal_created", proposal_id="p1", command_id="c1", row=7,
                 changes=[{"cell": "J7", "value": "mensual"}])
    store.append("proposal_approved", proposal_id="p1", command_id="c1", row=7,
                 changes=[{"cell": "J7", "value": "mensual"}])
    store.append("sheet_apply_attempt", proposal_id="p1", command_id="c1", row=7,
                 changes=[{"cell": "J7", "value": "mensual"}])
    store.append("sheet_apply_blocked", proposal_id="p1", command_id="c1", row=7,
                 reason="Escritura deshabilitada por configuracion")
    store.append("proposal_created", proposal_id="p2", row=8,
                 changes=[{"cell": "K8", "value": "nuevo"}])
    store.append("proposal_rejected", proposal_id="p2", row=8)
    snapshot = store.recent("panel", 8)
    counts = snapshot["summary"]
    assert counts["approved"] == 1
    assert counts["rejected"] == 1
    assert counts["pending"] == 0
    assert counts["apply_attempts"] == 1
    assert counts["blocked"] == 1
    assert counts["applied"] == 0
    assert snapshot["sheet_changes"] == []
    assert snapshot["orders"][0]["status"] == "approved_not_applied"
    assert snapshot["sheet_activity_is_global"] is True
    assert snapshot["scope"] == "current_backend_session"
    tsv = panel_lines(snapshot)
    assert tsv.splitlines()[0] == "M\t1\t1\t0|1|0|1\tSESSION"
    assert "\tapproved_not_applied\t" in tsv
    assert "\tblocked_not_written\t" in tsv
    assert "\tattempted_not_confirmed\t" in tsv


def test_audit_only_marks_success_after_sheet_applied_event():
    store = HistoryStore()
    store.append("proposal_created", proposal_id="p1", row=9,
                 changes=[{"cell": "J9", "value": "nuevo"}])
    store.append("proposal_approved", proposal_id="p1", row=9)
    store.append("sheet_apply_attempt", proposal_id="p1", row=9)
    assert store.recent()["summary"]["applied"] == 0
    store.append("sheet_applied", proposal_id="p1", row=9,
                 changes=[{"cell": "J9", "value": "nuevo"}])
    snap = store.recent()
    assert snap["summary"]["applied"] == 1
    assert len(snap["sheet_changes"]) == 1
    assert snap["sheet_activity"][0]["status"] == "applied"


def test_api_does_not_claim_applied_when_write_disabled(monkeypatch):
    from app import main as backend
    from app.review_store import ReviewStore
    from app.google_sheets import SheetsError
    from app.column_map import WRITE_COLUMNS, SHEET_HEADERS_A_AF
    monkeypatch.setattr(backend, "history_store", HistoryStore())
    monkeypatch.setattr(backend, "review_store", ReviewStore())
    monkeypatch.setattr(backend.gateway, "verify_template", lambda: {"ok": True})
    def forbid_write(changes):
        raise SheetsError("Writes disabled")
    monkeypatch.setattr(backend.gateway, "batch_update_cells", forbid_write)
    with TestClient(backend.app) as client:
        col = sorted(WRITE_COLUMNS)[0]
        p = client.post("/api/proposal", json={
            "row": 7, "column": col, "value": "periodicidad mensual"
        })
        assert p.status_code == 201
        proposal_id = p.json()["id"]
        a = client.post(f"/api/review/proposals/{proposal_id}/approve")
        assert a.status_code == 200
        blocked = client.post(f"/api/review/proposals/{proposal_id}/apply")
        assert blocked.status_code == 502
    counts = backend.history_store.recent()["summary"]
    assert counts["approved"] == 1
    assert counts["apply_attempts"] == 1
    assert counts["blocked"] == 1
    assert counts["applied"] == 0
    assert backend.history_store.recent()["sheet_changes"] == []
