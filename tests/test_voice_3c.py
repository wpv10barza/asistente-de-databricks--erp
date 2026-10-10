"""No-cloud unit tests: real Sheets calls are stubbed, no cell is modified."""
from dataclasses import replace
import base64
import pytest
from fastapi.testclient import TestClient
import app.main as backend
from app.voice_3c import VoiceDraftStore, VoiceError, decode_audio, safe_command

AUTH = {"X-3C-Device-Token": "ci-token"}
DEVICE = "panel-4848s040-3c-01"


@pytest.fixture
def app_client(monkeypatch):
    monkeypatch.setattr(
        backend, "settings",
        replace(backend.settings, esp32_api_token="ci-token", allow_sheet_write=False),
    )
    monkeypatch.setattr(backend, "voice_drafts", VoiceDraftStore())
    return TestClient(backend.app)


def test_voice_drafts_are_for_editor_not_sheets(app_client):
    r = app_client.post("/api/device/v1/voice/drafts", headers=AUTH, json={
        "device_id": DEVICE, "text": "Actualizar tarea mensual", "request_id": "voice-ci-1"
    })
    assert r.status_code == 202
    assert r.json()["requires_local_review"] is True
    assert r.json()["sheets_modified"] is False

    repeat = app_client.post("/api/device/v1/voice/drafts", headers=AUTH, json={
        "device_id": DEVICE, "text": "Actualizar tarea mensual", "request_id": "voice-ci-1"
    })
    assert repeat.json()["duplicate"] is True
    draft = app_client.get("/api/device/v1/voice/inbox", headers=AUTH,
                           params={"device_id": DEVICE}).json()["draft"]
    assert draft["text"] == "Actualizar tarea mensual"
    assert app_client.get("/api/device/v1/voice/inbox/panel", headers=AUTH,
                           params={"device_id": DEVICE}).text == draft["id"] + "\tActualizar tarea mensual\n"

    assert app_client.post(f"/api/device/v1/voice/drafts/{draft['id']}/ack", headers=AUTH,
                           json={"device_id": "wrong-device"}).status_code == 404
    ack = app_client.post(f"/api/device/v1/voice/drafts/{draft['id']}/ack", headers=AUTH,
                          json={"device_id": DEVICE})
    assert ack.status_code == 200
    assert ack.json()["sheets_modified"] is False
    status = app_client.get(
        "/api/device/v1/voice/drafts/" + draft["id"], headers=AUTH,
        params={"device_id": DEVICE},
    )
    assert status.status_code == 200
    assert status.json()["status"] == "delivered_to_editor"
    assert status.json()["sheets_modified"] is False
    assert app_client.get(
        "/api/device/v1/voice/drafts/" + draft["id"], headers=AUTH,
        params={"device_id": "another-device"},
    ).status_code == 404
    assert app_client.get("/api/device/v1/voice/inbox/panel", headers=AUTH,
                          params={"device_id": DEVICE}).text == ""


def test_voice_requires_device_auth(app_client):
    for path in ("/api/device/v1/cloud/verify", "/api/device/v1/voice/health",
                 f"/api/device/v1/voice/inbox?device_id={DEVICE}"):
        assert app_client.get(path).status_code == 401
    assert app_client.post("/api/device/v1/voice/drafts",
                           json={"device_id": DEVICE, "text": "Hola", "request_id": "v-1"}).status_code == 401


def test_audio_contract_without_external_gemini(app_client, monkeypatch):
    sample = b"RIFF" + b"0" * 512
    assert decode_audio(base64.b64encode(sample).decode(), "audio/wav")[0] == sample
    with pytest.raises(VoiceError):
        decode_audio(base64.b64encode(b"fake").decode(), "audio/wav")

    def mock_transcribe(*args):
        return "Revisar la estrategia de mantenimiento"
    monkeypatch.setattr(backend, "transcribe_with_gemini", mock_transcribe)
    resp = app_client.post("/api/device/v1/voice/transcribe", headers=AUTH, json={
        "audio_base64": base64.b64encode(sample).decode(), "mime_type": "audio/wav",
    })
    assert resp.status_code == 200
    assert resp.json()["transcript"] == "Revisar la estrategia de mantenimiento"
    assert resp.json()["sent_to_esp32"] is False


def test_real_sheet_probe_is_not_just_configured(app_client, monkeypatch):
    monkeypatch.setattr(backend.gateway, "verify_template", lambda: {
        "ok": True,
        "spreadsheet_id": "test-sheet-id",
        "sheet_name": "Data",
        "header_row": 4,
        "auth_mode": "service_account",
        "mismatches": [],
    })
    resp = app_client.get("/api/device/v1/cloud/verify", headers=AUTH)
    assert resp.status_code == 200
    result = resp.json()
    assert result["google_sheets"]["connected"] is True
    assert result["google_sheets"]["verified_by"] == "live_google_sheets_api_read"
    assert result["sheet_write_enabled"] is False

    monkeypatch.setattr(backend.gateway, "verify_template", lambda: {
        "ok": False, "sheet_name": "Data", "mismatches": [{"col": "A"}],
    })
    assert app_client.get("/api/device/v1/cloud/verify", headers=AUTH).status_code == 409

    from app.google_sheets import SheetsError
    def offline():
        raise SheetsError("Google Sheets HTTP 403")
    monkeypatch.setattr(backend.gateway, "verify_template", offline)
    assert app_client.get("/api/device/v1/cloud/verify", headers=AUTH).status_code == 502


def test_invalid_editor_message_is_rejected():
    for text in ("", "x" * 231, "A\n" * 130):
        with pytest.raises(VoiceError):
            safe_command(text)
