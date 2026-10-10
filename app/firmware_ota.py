from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class FirmwareOtaError(RuntimeError):
    pass


@dataclass(frozen=True)
class FirmwareRelease:
    version: str
    sha256: str
    size: int
    path: Path

    def public(self) -> dict:
        return {
            "version": self.version,
            "sha256": self.sha256.lower(),
            "size": self.size,
            "url": f"/api/device/v1/firmware/{self.version}.bin",
        }


class FirmwareOtaStore:
    """Read-only OTA release store backed by a Databricks UC Volume path."""

    def __init__(self, root: str, channel: str = "stable") -> None:
        self.root = Path(root.strip()) if root.strip() else None
        self.channel = channel.strip() or "stable"
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.channel):
            raise FirmwareOtaError("OTA_CHANNEL contiene caracteres no permitidos.")

    @property
    def configured(self) -> bool:
        return self.root is not None

    def _require_root(self) -> Path:
        if self.root is None:
            raise FirmwareOtaError(
                "OTA_VOLUME_PATH no está configurado. Agrega un UC volume a la App."
            )
        return self.root

    @staticmethod
    def _validate_version(version: str) -> str:
        candidate = version.strip()
        if not VERSION_RE.fullmatch(candidate):
            raise FirmwareOtaError("Versión OTA inválida.")
        return candidate

    def _channel_dir(self) -> Path:
        return self._require_root() / self.channel

    def latest(self) -> FirmwareRelease:
        manifest_path = self._channel_dir() / "latest.json"
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FirmwareOtaError("No existe latest.json en el canal OTA.") from exc
        except json.JSONDecodeError as exc:
            raise FirmwareOtaError("latest.json no contiene JSON válido.") from exc

        version = self._validate_version(str(raw.get("version", "")))
        sha256 = str(raw.get("sha256", "")).strip().lower()
        if not SHA256_RE.fullmatch(sha256):
            raise FirmwareOtaError("latest.json contiene SHA-256 inválido.")

        try:
            size = int(raw.get("size", 0))
        except (TypeError, ValueError) as exc:
            raise FirmwareOtaError("latest.json contiene tamaño inválido.") from exc
        if size <= 0:
            raise FirmwareOtaError("latest.json debe declarar size > 0.")

        release = self.release(version)
        if release.size != size:
            raise FirmwareOtaError(
                f"El tamaño del binario ({release.size}) no coincide con latest.json ({size})."
            )

        return FirmwareRelease(
            version=version,
            sha256=sha256,
            size=size,
            path=release.path,
        )

    def release(self, version: str) -> FirmwareRelease:
        candidate = self._validate_version(version)
        release_dir = self._channel_dir() / candidate
        binary_path = release_dir / "firmware.bin"
        manifest_path = release_dir / "manifest.json"

        if not binary_path.is_file():
            raise FirmwareOtaError("Firmware OTA no encontrado.")

        manifest: dict = {}
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise FirmwareOtaError("manifest.json de la versión es inválido.") from exc

        size = binary_path.stat().st_size
        sha256 = str(manifest.get("sha256", "")).strip().lower()
        if manifest and not SHA256_RE.fullmatch(sha256):
            raise FirmwareOtaError("manifest.json de la versión contiene SHA-256 inválido.")

        return FirmwareRelease(
            version=candidate,
            sha256=sha256,
            size=size,
            path=binary_path,
        )

    def by_commit(self, source_sha: str) -> tuple[FirmwareRelease, str]:
        """Select only an already published, immutable, matching firmware build.

        Never fetch, build or install an arbitrary GitHub commit on the device.
        A 7..40-character SHA prefix is accepted only when it uniquely identifies
        one published artifact. Never fall back to latest on a missing match.
        """
        candidate = source_sha.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{7,40}", candidate):
            raise FirmwareOtaError("Commit debe ser SHA hexadecimal de 7 a 40 caracteres.")
        directory = self._channel_dir()
        if not directory.is_dir():
            raise FirmwareOtaError("No hay firmware publicado en el canal OTA.")
        matches: list[tuple[FirmwareRelease, str]] = []
        for version_dir in directory.iterdir():
            if not version_dir.is_dir() or not VERSION_RE.fullmatch(version_dir.name):
                continue
            manifest_path = version_dir / "manifest.json"
            if not manifest_path.is_file():
                continue
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            # Only the primary 3C HMI, compiled for the dual-slot 16MB
            # layout with credential-preserving NVS, can be installed on it.
            if (data.get("source_repository") != "wpv10barza/erp-mantto-esp32" or
                data.get("hardware") != "ESP32-S3-4848S040" or
                data.get("partition_table") != "partitions_ota_16mb.csv" or
                data.get("credential_mode") != "ota3c-nvs"):
                continue
            full_sha = str(data.get("source_sha", "")).strip().lower()
            if not re.fullmatch(r"[0-9a-f]{40}", full_sha):
                continue
            if not full_sha.startswith(candidate):
                continue
            release = self.release(version_dir.name)
            declared_size = int(data.get("size", 0))
            if declared_size != release.size or not SHA256_RE.fullmatch(release.sha256):
                raise FirmwareOtaError("Metadatos de firmware publicado inconsistentes.")
            matches.append((release, full_sha))
        if not matches:
            raise FirmwareOtaError("El commit no tiene firmware OTA publicado.")
        if len(matches) > 1:
            raise FirmwareOtaError("Commit ambiguo: use el SHA completo de 40 caracteres.")
        return matches[0]
