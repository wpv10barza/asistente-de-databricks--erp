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

def test_rejects_modified_firmware_even_when_size_matches(tmp_path: Path) -> None:
    make_release(tmp_path, payload=b"abcdefgh")
    (tmp_path / "stable" / "1.0.1" / "firmware.bin").write_bytes(b"ABCDEFGH")
    with pytest.raises(FirmwareOtaError, match="SHA-256 real"):
        FirmwareOtaStore(str(tmp_path)).latest()


def test_rejects_latest_hash_mismatch(tmp_path: Path) -> None:
    make_release(tmp_path)
    latest_path = tmp_path / "stable" / "latest.json"
    current = json.loads(latest_path.read_text(encoding="utf-8"))
    current["sha256"] = "a" * 64
    latest_path.write_text(json.dumps(current), encoding="utf-8")
    with pytest.raises(FirmwareOtaError, match="SHA-256 de latest"):
        FirmwareOtaStore(str(tmp_path)).latest()


def test_rejects_missing_release_manifest(tmp_path: Path) -> None:
    make_release(tmp_path)
    (tmp_path / "stable" / "1.0.1" / "manifest.json").unlink()
    with pytest.raises(FirmwareOtaError, match="Falta manifest.json"):
        FirmwareOtaStore(str(tmp_path)).release("1.0.1")


def test_rejects_manifest_version_mismatch(tmp_path: Path) -> None:
    make_release(tmp_path)
    path = tmp_path / "stable" / "1.0.1" / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = "1.0.9"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(FirmwareOtaError, match="versión del manifiesto"):
        FirmwareOtaStore(str(tmp_path)).release("1.0.1")

def test_find_published_release_by_full_sha_or_prefix(tmp_path: Path) -> None:
    sha = "a4b4144c6d96aedf8ca6a78f9b7adf7a436c0b0e"
    make_release(tmp_path)
    manifest_path = tmp_path / "stable" / "1.0.1" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["git_commit_sha"] = sha
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    store = FirmwareOtaStore(str(tmp_path))
    assert store.release_for_commit(sha).git_commit_sha == sha
    assert store.release_for_commit("a4b4144c").version == "1.0.1"
    assert store.release_for_commit("a4b4144c").public()["git_commit_sha"] == sha


def test_unknown_or_non_hex_commit_cannot_fallback_to_latest(tmp_path: Path) -> None:
    make_release(tmp_path)
    store = FirmwareOtaStore(str(tmp_path))
    with pytest.raises(FirmwareOtaError, match="No existe firmware"):
        store.release_for_commit("a4b4144c")
    with pytest.raises(FirmwareOtaError, match="SHA inválido"):
        store.release_for_commit("../../etc/passwd")


def test_ambiguous_prefix_fails_closed(tmp_path: Path) -> None:
    sha_one = "a4b4144c" + "1" * 32
    sha_two = "a4b4144c" + "2" * 32
    for version, sha in (("1.0.1", sha_one), ("1.0.2", sha_two)):
        make_release(tmp_path, version=version)
        path = tmp_path / "stable" / version / "manifest.json"
        obj = json.loads(path.read_text(encoding="utf-8"))
        obj["git_commit_sha"] = sha
        path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(FirmwareOtaError, match="ambiguo"):
        FirmwareOtaStore(str(tmp_path)).release_for_commit("a4b4144c")


def test_commit_lookup_also_checks_real_binary_digest(tmp_path: Path) -> None:
    make_release(tmp_path, payload=b"abcdefgh")
    path = tmp_path / "stable" / "1.0.1" / "manifest.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["git_commit_sha"] = "a4b4144c6d96aedf8ca6a78f9b7adf7a436c0b0e"
    path.write_text(json.dumps(obj), encoding="utf-8")
    (tmp_path / "stable" / "1.0.1" / "firmware.bin").write_bytes(b"abcdefgh"[:4] + b"ZZZZ")
    with pytest.raises(FirmwareOtaError, match="SHA-256 real"):
        FirmwareOtaStore(str(tmp_path)).release_for_commit("a4b4144c")
