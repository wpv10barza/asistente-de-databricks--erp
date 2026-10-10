"""Databricks Apps UC volume adapter for verified OTA releases.

Apps do not mount /Volumes paths. Use WorkspaceClient.files to fetch into
a private temporary directory, then reuse FirmwareOtaStore SHA256 verification.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from .firmware_ota import (
    COMMIT_RE,
    FULL_COMMIT_RE,
    VERSION_RE,
    FirmwareOtaError,
    FirmwareOtaStore,
    FirmwareRelease,
)


def _missing(exc: Exception) -> bool:
    return (
        isinstance(exc, FileNotFoundError)
        or type(exc).__name__ in ("NotFound", "ResourceDoesNotExist")
        or str(getattr(exc, "error_code", "") or "") in (
            "RESOURCE_DOES_NOT_EXIST", "NOT_FOUND"
        )
    )


class UcVolumeFirmwareOtaStore(FirmwareOtaStore):
    """Read published UC files using the Databricks app service principal."""

    def __init__(
        self, volume_root: str, channel: str = "stable", *,
        files_client: Any | None = None,
    ) -> None:
        root = PurePosixPath(volume_root.strip().rstrip("/"))
        if not (root.is_absolute() and len(root.parts) == 5
                and root.parts[1] == "Volumes"):
            raise FirmwareOtaError(
                "OTA_VOLUME_PATH debe ser /Volumes/catalog/schema/volume."
            )
        self.volume_root = root
        self._files_client = files_client
        self._staging = tempfile.TemporaryDirectory(prefix="esp32-ota-")
        super().__init__(self._staging.name, channel)

    def _files(self) -> Any:
        if self._files_client is None:
            from databricks.sdk import WorkspaceClient
            self._files_client = WorkspaceClient().files
        return self._files_client

    def _remote(self, *segments: str) -> str:
        return str(self.volume_root.joinpath(*segments))

    def _fetch(
        self, relative: tuple[str, ...], *, allow_missing: bool = False
    ) -> Path | None:
        destination = self._require_root().joinpath(*relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, staged = tempfile.mkstemp(prefix=".uc-download-", dir=str(destination.parent))
        os.close(fd)
        try:
            self._files().download_to(self._remote(*relative), staged)
            os.replace(staged, destination)
            return destination
        except Exception as exc:
            if allow_missing and _missing(exc):
                return None
            if _missing(exc):
                raise FirmwareOtaError(
                    f"Archivo OTA no encontrado: {'/'.join(relative)}."
                ) from exc
            raise FirmwareOtaError(
                f"Files API no pudo leer el UC Volume ({type(exc).__name__})."
            ) from exc
        finally:
            if os.path.exists(staged):
                os.unlink(staged)

    def _versions(self) -> list[str]:
        try:
            entries = self._files().list_directory_contents(
                self._remote(self.channel)
            )
            return [
                PurePosixPath(str(e.path)).name for e in entries
                if e.path and e.is_directory is True
                and VERSION_RE.fullmatch(PurePosixPath(str(e.path)).name)
            ]
        except Exception as exc:
            if _missing(exc):
                raise FirmwareOtaError(
                    "El canal OTA no existe en el volumen de Unity Catalog."
                ) from exc
            raise FirmwareOtaError(
                f"Files API no pudo listar el UC Volume ({type(exc).__name__})."
            ) from exc

    def latest(self) -> FirmwareRelease:
        if not self._fetch((self.channel, "latest.json"), allow_missing=True):
            raise FirmwareOtaError("No existe latest.json en el canal OTA.")
        return super().latest()

    def release(self, version: str) -> FirmwareRelease:
        ver = self._validate_version(version)
        prefix = (self.channel, ver)
        if not self._fetch((*prefix, "manifest.json"), allow_missing=True):
            raise FirmwareOtaError(
                "Falta manifest.json de esta versión; se bloquea la descarga."
            )
        if not self._fetch((*prefix, "firmware.bin"), allow_missing=True):
            raise FirmwareOtaError("Firmware OTA no encontrado.")
        return super().release(ver)

    def release_for_commit(self, requested_sha: str) -> FirmwareRelease:
        prefix = requested_sha.strip().lower()
        if not COMMIT_RE.fullmatch(prefix):
            raise FirmwareOtaError(
                "Commit SHA inválido: use 8 a 40 caracteres hexadecimales."
            )

        matches = []
        for ver in self._versions():
            manifest_path = self._fetch(
                (self.channel, ver, "manifest.json"), allow_missing=True
            )
            if manifest_path is None:
                continue
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            sha = str(data.get("git_commit_sha", "")).strip().lower()
            if FULL_COMMIT_RE.fullmatch(sha) and sha.startswith(prefix):
                matches.append(ver)

        if not matches:
            raise FirmwareOtaError("No existe firmware OTA publicado para ese commit.")
        if len(matches) > 1:
            raise FirmwareOtaError("Commit ambiguo: ingrese el SHA completo.")
        return self.release(matches[0])
