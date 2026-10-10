"""OTA fixed-length response contract for ESP32-S3 TLS updater."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main


def test_ota_response_is_raw_binary_with_fixed_length(monkeypatch, tmp_path: Path):
    body = b"\xe9" + bytes(range(256)) * 4030
    image = tmp_path / "firmware.bin"
    image.write_bytes(body)
    sha256 = hashlib.sha256(body).hexdigest()

    class FakeStore:
        def release(self, version: str):
            assert version == "2.5.1"
            return SimpleNamespace(
                version=version, path=image, sha256=sha256, size=len(body)
            )

    monkeypatch.setattr(main, "firmware_ota", FakeStore())
    monkeypatch.setattr(main, "_device_authorization", lambda _request: None)
    resp = TestClient(main.app).get("/api/device/v1/firmware/2.5.1.bin")
    assert resp.status_code == 200
    assert resp.content == body
    assert resp.headers["content-length"] == str(len(body))
    assert resp.headers["content-type"] == "application/octet-stream"
    assert resp.headers.get("transfer-encoding") is None
    assert resp.headers["x-firmware-sha256"] == sha256
    assert resp.headers["cache-control"] == "private, no-store"


def test_ota_response_rejects_tampered_byte_stream(monkeypatch, tmp_path: Path):
    image = tmp_path / "firmware.bin"
    image.write_bytes(b"\xe9" + b"A" * 3000)

    class FakeStore:
        def release(self, version: str):
            return SimpleNamespace(
                version=version, path=image,
                sha256=hashlib.sha256(b"\xe9" + b"B" * 3000).hexdigest(),
                size=image.stat().st_size
            )

    monkeypatch.setattr(main, "firmware_ota", FakeStore())
    monkeypatch.setattr(main, "_device_authorization", lambda _request: None)
    resp = TestClient(main.app).get("/api/device/v1/firmware/2.5.1.bin")
    assert resp.status_code == 503
    assert "SHA-256" in resp.json()["detail"]


def test_ota_response_rejects_oversized_release(monkeypatch, tmp_path: Path):
    class FakeStore:
        def release(self, version: str):
            return SimpleNamespace(
                version=version, path=tmp_path / "never-read.bin",
                sha256="a" * 64, size=0x400001
            )

    monkeypatch.setattr(main, "firmware_ota", FakeStore())
    monkeypatch.setattr(main, "_device_authorization", lambda _request: None)
    resp = TestClient(main.app).get("/api/device/v1/firmware/2.5.1.bin")
    assert resp.status_code == 503
    assert "4 MiB" in resp.json()["detail"]
