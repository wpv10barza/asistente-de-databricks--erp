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

    from dataclasses import replace
    monkeypatch.setattr(backend, "settings", replace(backend.settings, esp32_api_token="local-test-token"))
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

def test_by_commit_only_uses_published_release(tmp_path: Path) -> None:
    sha = "a" * 40
    make_release(tmp_path, "2.7.0", b"real_ota_bytes")
    manifest = tmp_path / "stable" / "2.7.0" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["source_sha"] = sha
    data.update(source_repository="wpv10barza/erp-mantto-esp32",
                hardware="ESP32-S3-4848S040",
                partition_table="partitions_ota_16mb.csv",
                credential_mode="ota3c-nvs")
    manifest.write_text(json.dumps(data), encoding="utf-8")
    store = FirmwareOtaStore(str(tmp_path))
    release, resolved = store.by_commit("aaaaaaa")
    assert resolved == sha and release.version == "2.7.0"
    with pytest.raises(FirmwareOtaError, match="no tiene firmware"):
        store.by_commit("bbbbbbb")
    with pytest.raises(FirmwareOtaError, match="SHA hexadecimal"):
        store.by_commit("../latest")


def test_commit_route_is_authorized_and_does_not_fall_back_to_latest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from dataclasses import replace
    from fastapi.testclient import TestClient
    from app import main as backend

    make_release(tmp_path, "2.7.0", b"example")
    manifest = tmp_path / "stable" / "2.7.0" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["source_sha"] = "a" * 40
    data.update(source_repository="wpv10barza/erp-mantto-esp32",
                hardware="ESP32-S3-4848S040",
                partition_table="partitions_ota_16mb.csv",
                credential_mode="ota3c-nvs")
    manifest.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(backend, "settings",
                        replace(backend.settings, esp32_api_token="ci-device-token"))
    monkeypatch.setattr(backend, "firmware_ota", FirmwareOtaStore(str(tmp_path)))
    client = TestClient(backend.app)
    route = "/api/device/v1/firmware/by-commit/" + "a" * 40
    assert client.get(route).status_code == 401
    authorized = {"X-3C-Device-Token": "ci-device-token"}
    found = client.get(route, headers=authorized)
    assert found.status_code == 200
    assert found.json()["source_sha"] == "a" * 40
    assert found.json()["version"] == "2.7.0"
    not_published = client.get(
        "/api/device/v1/firmware/by-commit/" + "b" * 40, headers=authorized)
    assert not_published.status_code == 404

def test_wrong_firmware_family_cannot_be_installed_by_commit(tmp_path: Path) -> None:
    make_release(tmp_path, "2.9.0")
    release_manifest = tmp_path / "stable" / "2.9.0" / "manifest.json"
    data = json.loads(release_manifest.read_text(encoding="utf-8"))
    data["source_sha"] = "a" * 40
    data["source_repository"] = "wpv10barza/firmware-demo"
    data["hardware"] = "ESP32-S3-4848S040"
    data["partition_table"] = "partitions_ota_16mb.csv"
    data["credential_mode"] = "ota3c-nvs"
    release_manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(FirmwareOtaError, match="no tiene firmware"):
        FirmwareOtaStore(str(tmp_path)).by_commit("aaaaaaa")
