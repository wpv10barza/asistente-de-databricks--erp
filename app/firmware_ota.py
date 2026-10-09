from __future__ import annotations

import hashlib
import hmac
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
        if not hmac.compare_digest(release.sha256, sha256):
            raise FirmwareOtaError(
                "SHA-256 de latest.json no coincide con el firmware verificado."
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

        if not manifest_path.is_file():
            raise FirmwareOtaError(
                "Falta manifest.json de esta versión; se bloquea la descarga."
            )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise FirmwareOtaError("manifest.json de la versión es inválido.") from exc
        if not isinstance(manifest, dict):
            raise FirmwareOtaError("manifest.json debe contener un objeto JSON.")

        sha256 = str(manifest.get("sha256", "")).strip().lower()
        if not SHA256_RE.fullmatch(sha256):
            raise FirmwareOtaError("manifest.json contiene SHA-256 inválido.")
        if str(manifest.get("version", "")).strip() != candidate:
            raise FirmwareOtaError("La versión del manifiesto no coincide.")

        size = binary_path.stat().st_size
        if size <= 0:
            raise FirmwareOtaError("firmware.bin está vacío.")
        try:
            declared_size = int(manifest.get("size", 0))
        except (TypeError, ValueError) as exc:
            raise FirmwareOtaError("Tamaño del manifiesto inválido.") from exc
        if declared_size != size:
            raise FirmwareOtaError("Tamaño real del binario distinto de manifest.json.")

        actual = hashlib.sha256()
        try:
            with binary_path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(256 * 1024), b""):
                    actual.update(chunk)
        except OSError as exc:
            raise FirmwareOtaError("No se pudo leer firmware.bin.") from exc
        if not hmac.compare_digest(actual.hexdigest(), sha256):
            raise FirmwareOtaError(
                "SHA-256 real del firmware no coincide con manifest.json."
            )
        return FirmwareRelease(version=candidate, sha256=sha256, size=size, path=binary_path)
