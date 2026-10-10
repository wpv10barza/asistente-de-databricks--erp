from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.firmware_ota import FirmwareOtaError, FirmwareOtaStore


def make_release(root: Path, version: str = "1.0.1", payload: bytes = b"firmware") -> tuple[str, int]:
    stable = root / "stable"
    release = stable / version
    release.mkdir(parents=True)
    binary = release / "firmware.bin"
    binary.write_bytes(payload)
    sha256 = hashlib.sha256(payload).hexdigest()
    manifest = {
        "version": version,
        "sha256": sha256,
        "size": len(payload),
        "channel": "stable",
    }
    (release / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (stable / "latest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return sha256, len(payload)


def test_latest_release(tmp_path: Path) -> None:
    sha256, size = make_release(tmp_path)
    store = FirmwareOtaStore(str(tmp_path))
    release = store.latest()
    assert release.version == "1.0.1"
    assert release.sha256 == sha256
    assert release.size == size
    assert release.public()["url"] == "/api/device/v1/firmware/1.0.1.bin"


def test_rejects_path_traversal_version(tmp_path: Path) -> None:
    store = FirmwareOtaStore(str(tmp_path))
    with pytest.raises(FirmwareOtaError):
        store.release("../../etc/passwd")


def test_rejects_latest_size_mismatch(tmp_path: Path) -> None:
    make_release(tmp_path)
    latest = tmp_path / "stable" / "latest.json"
    data = json.loads(latest.read_text())
    data["size"] += 1
    latest.write_text(json.dumps(data))
    store = FirmwareOtaStore(str(tmp_path))
    with pytest.raises(FirmwareOtaError):
        store.latest()


def test_unconfigured_volume_fails_closed() -> None:
    store = FirmwareOtaStore("")
    with pytest.raises(FirmwareOtaError):
        store.latest()


def test_missing_manifest_is_ota_error_not_404(tmp_path: Path) -> None:
    store = FirmwareOtaStore(str(tmp_path))
    with pytest.raises(FirmwareOtaError, match="latest.json"):
        store.latest()


def test_http_ota_routes_never_mask_missing_manifest_as_404(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from fastapi.testclient import TestClient
    from app import main as backend

    monkeypatch.setattr(backend.settings, "esp32_api_token", "local-test-token")
    monkeypatch.setattr(backend, "firmware_ota", FirmwareOtaStore(str(tmp_path)))
    client = TestClient(backend.app)
    headers = {"X-3C-Device-Token": "local-test-token"}

    health = client.get("/api/device/v1/health")
    assert health.status_code == 200
    assert health.json()["firmware_latest_path"] == "/api/device/v1/firmware/latest"

    status = client.get("/api/device/v1/firmware/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["route_ok"] is True
    assert status.json()["status"] == "release_not_ready"
    assert status.json()["ready"] is False

    latest = client.get("/api/device/v1/firmware/latest", headers=headers)
    assert latest.status_code == 503
    assert "latest.json" in latest.json()["detail"]

    unauthorized = client.get("/api/device/v1/firmware/status")
    assert unauthorized.status_code == 401

    make_release(tmp_path, "1.0.1")
    ready = client.get("/api/device/v1/firmware/status", headers=headers)
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
    assert ready.json()["version"] == "1.0.1"
    manifest = client.get("/api/device/v1/firmware/latest", headers=headers)
    assert manifest.status_code == 200
    assert manifest.json()["url"] == "/api/device/v1/firmware/1.0.1.bin"
