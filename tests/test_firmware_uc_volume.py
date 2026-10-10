from __future__ import annotations
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

from app.firmware_ota import FirmwareOtaError
from app.firmware_uc_volume import UcVolumeFirmwareOtaStore

VOLUME = "/Volumes/workspace/default/esp32_firmware"
COMMIT = "2d6b9e0ef43e521015996cdffdea38a67cd37f92"


class FakeFiles:
    def __init__(self, root):
        self.root = root
        self.calls = []

    def _path(self, remote):
        assert remote.startswith(VOLUME + "/")
        return self.root / remote[len(VOLUME) + 1:]

    def list_directory_contents(self, directory_path):
        path = self._path(directory_path)
        if not path.is_dir():
            raise FileNotFoundError(directory_path)
        return [
            SimpleNamespace(path=directory_path + "/" + p.name, is_directory=p.is_dir())
            for p in path.iterdir()
        ]

    def download_to(self, remote, local):
        self.calls.append(remote)
        src = self._path(remote)
        if not src.is_file():
            raise FileNotFoundError(remote)
        Path(local).write_bytes(src.read_bytes())


def published(root, payload=b"esp32"):
    folder = root / "stable" / "2.5.1"
    folder.mkdir(parents=True)
    sha = hashlib.sha256(payload).hexdigest()
    (folder / "firmware.bin").write_bytes(payload)
    (folder / "manifest.json").write_text(json.dumps({
        "version": "2.5.1", "size": len(payload),
        "sha256": sha, "git_commit_sha": COMMIT,
    }))
    return sha


def test_uc_commit_uses_sdk_not_local_volume_path(tmp_path):
    sha = published(tmp_path)
    sdk = FakeFiles(tmp_path)
    store = UcVolumeFirmwareOtaStore(VOLUME, files_client=sdk)
    actual = store.release_for_commit("2d6b9e0e")
    assert actual.git_commit_sha == COMMIT
    assert actual.sha256 == sha
    assert actual.path.read_bytes() == b"esp32"
    assert len(sdk.calls) == 3


def test_uc_missing_channel_fails_closed(tmp_path):
    store = UcVolumeFirmwareOtaStore(VOLUME, files_client=FakeFiles(tmp_path))
    with pytest.raises(FirmwareOtaError, match="canal OTA"):
        store.release_for_commit("2d6b9e0e")


def test_uc_invalid_sha_avoids_network(tmp_path):
    sdk = FakeFiles(tmp_path)
    store = UcVolumeFirmwareOtaStore(VOLUME, files_client=sdk)
    with pytest.raises(FirmwareOtaError, match="SHA inválido"):
        store.release_for_commit("../badsha")
    assert not sdk.calls


def test_uc_unknown_sha_has_no_latest_fallback(tmp_path):
    published(tmp_path)
    store = UcVolumeFirmwareOtaStore(VOLUME, files_client=FakeFiles(tmp_path))
    with pytest.raises(FirmwareOtaError, match="No existe firmware"):
        store.release_for_commit("ffffffff")


def test_uc_tampered_image_sha_fails_closed(tmp_path):
    published(tmp_path)
    (tmp_path / "stable" / "2.5.1" / "firmware.bin").write_bytes(b"XXXXX")
    store = UcVolumeFirmwareOtaStore(VOLUME, files_client=FakeFiles(tmp_path))
    with pytest.raises(FirmwareOtaError, match="SHA-256 real"):
        store.release_for_commit("2d6b9e0e")


def test_uc_latest_requires_manifest(tmp_path):
    published(tmp_path)
    store = UcVolumeFirmwareOtaStore(VOLUME, files_client=FakeFiles(tmp_path))
    with pytest.raises(FirmwareOtaError, match="latest.json"):
        store.latest()


def test_uc_latest_when_published(tmp_path):
    sha = published(tmp_path)
    (tmp_path / "stable" / "latest.json").write_text(json.dumps({
        "version": "2.5.1", "size": 5, "sha256": sha,
    }))
    store = UcVolumeFirmwareOtaStore(VOLUME, files_client=FakeFiles(tmp_path))
    assert store.latest().version == "2.5.1"


def test_uc_missing_bin_fails_closed(tmp_path):
    published(tmp_path)
    (tmp_path / "stable" / "2.5.1" / "firmware.bin").unlink()
    store = UcVolumeFirmwareOtaStore(VOLUME, files_client=FakeFiles(tmp_path))
    with pytest.raises(FirmwareOtaError, match="Firmware OTA no encontrado"):
        store.release_for_commit("2d6b9e0e")


def test_uc_volume_requires_absolute_resource_path():
    with pytest.raises(FirmwareOtaError, match="OTA_VOLUME_PATH"):
        UcVolumeFirmwareOtaStore("dbfs:/Volumes/workspace/default/esp32_firmware")


def test_uc_access_denied_is_not_misidentified_as_missing(tmp_path):
    class Denied(FakeFiles):
        def list_directory_contents(self, p):
            raise PermissionError("denied")
    store = UcVolumeFirmwareOtaStore(VOLUME, files_client=Denied(tmp_path))
    with pytest.raises(FirmwareOtaError, match="PermissionError"):
        store.release_for_commit("2d6b9e0e")
