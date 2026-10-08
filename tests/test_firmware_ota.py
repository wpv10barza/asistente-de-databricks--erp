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
