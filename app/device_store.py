from __future__ import annotations

import hmac
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock


DEVICE_COMMAND_TTL_SECONDS = 15 * 60
DEVICE_COMMAND_LIMIT = 50


def _utc_now_iso(now: float | None = None) -> str:
    timestamp = time.time() if now is None else now
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def clean_single_line(value: object, max_length: int) -> str:
    text = str(value or "")
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]


def normalize_device_command(body: dict) -> dict:
    device_id = clean_single_line(body.get("device_id", body.get("deviceId")), 64)
    text = clean_single_line(body.get("text", body.get("command")), 1000)
    request_id = (
        clean_single_line(body.get("request_id", body.get("requestId")), 96)
        or str(uuid.uuid4())
    )

    if not device_id:
        raise ValueError("device_id es obligatorio.")
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", device_id):
        raise ValueError("device_id contiene caracteres no permitidos.")
    if not text:
        raise ValueError("text es obligatorio.")

    return {"device_id": device_id, "text": text, "request_id": request_id}


def verify_device_token(configured: str, candidate: str) -> bool:
    if not configured or not candidate:
        return False
    return hmac.compare_digest(configured.encode(), candidate.encode())


@dataclass
class DeviceCommandStore:
    ttl_seconds: int = DEVICE_COMMAND_TTL_SECONDS
    limit: int = DEVICE_COMMAND_LIMIT

    def __post_init__(self) -> None:
        self._commands: list[dict] = []
        self._lock = RLock()

    def _prune(self) -> None:
        cutoff = time.time() - self.ttl_seconds
        self._commands = [
            command
            for command in self._commands
            if command["_created_epoch"] >= cutoff
        ]

    def enqueue(self, input_data: dict) -> tuple[dict, bool]:
        with self._lock:
            self._prune()
            duplicate = next(
                (
                    command
                    for command in self._commands
                    if command["device_id"] == input_data["device_id"]
                    and command["request_id"] == input_data["request_id"]
                ),
                None,
            )
            if duplicate:
                return self._public(duplicate), True

            epoch = time.time()
            timestamp = _utc_now_iso(epoch)
            command = {
                "id": str(uuid.uuid4()),
                "request_id": input_data["request_id"],
                "device_id": input_data["device_id"],
                "text": input_data["text"],
                "status": "pending_confirmation",
                "created_at": timestamp,
                "updated_at": timestamp,
                "result": None,
                "changes_summary": "",
                "change_count": 0,
                "_created_epoch": epoch,
            }
            self._commands.append(command)
            if len(self._commands) > self.limit:
                self._commands = self._commands[-self.limit :]
            return self._public(command), False

    def get(self, command_id: str) -> dict | None:
        with self._lock:
            self._prune()
            command = next(
                (item for item in self._commands if item["id"] == command_id),
                None,
            )
            return self._public(command) if command else None

    def latest_pending(self, after_id: str | None = None) -> dict | None:
        with self._lock:
            self._prune()
            pending = [
                command
                for command in self._commands
                if command["status"] == "pending_confirmation"
            ]
            if not pending:
                return None
            if not after_id:
                return self._public(pending[-1])
            position = next(
                (i for i, item in enumerate(pending) if item["id"] == after_id),
                -1,
            )
            selected = pending[position + 1] if 0 <= position < len(pending) - 1 else pending[-1]
            return self._public(selected)

    def recent(self, device_id: str, offset: int = 0) -> dict:
        """Return a single recent record without exposing other devices.

        Ephemeral: this in-memory store expires after the configured TTL.
        It is a recent status viewer, not a permanent audit ledger.
        """
        with self._lock:
            self._prune()
            entries = [c for c in reversed(self._commands)
                       if c["device_id"] == device_id]
            total = len(entries)
            selected = self._public(entries[offset]) if offset < total else None
            if selected is None:
                return {"total": total, "offset": offset, "command_id": "",
                        "text": "", "status": "empty", "result": "",
                        "changes_summary": "", "change_count": 0,
                        "updated_at": ""}
            return {
                "total": total,
                "offset": offset,
                "command_id": selected["id"],
                "text": selected["text"],
                "status": selected["status"],
                "result": selected["result"] or "",
                "changes_summary": selected["changes_summary"],
                "change_count": selected["change_count"],
                "updated_at": selected["updated_at"],
            }

    def update(self, command_id: str, status: str, result: str = "",
               changes: list[tuple[str, object]] | None = None) -> dict | None:
        if status not in {"applied", "rejected"}:
            raise ValueError("status debe ser applied o rejected.")
        with self._lock:
            self._prune()
            command = next(
                (item for item in self._commands if item["id"] == command_id),
                None,
            )
            if not command:
                return None
            if command["status"] == "pending_confirmation":
                command["status"] = status
                command["result"] = clean_single_line(result, 300) or None
                if status == "applied" and changes:
                    command["change_count"] = len(changes)
                    parts = [
                        clean_single_line(f"{cell}: {value}", 90)
                        for cell, value in changes[:3]
                    ]
                    suffix = " ..." if len(changes) > 3 else ""
                    command["changes_summary"] = clean_single_line(
                        "; ".join(parts) + suffix, 180
                    )
                command["updated_at"] = _utc_now_iso()
            return self._public(command)

    @staticmethod
    def _public(command: dict) -> dict:
        return {key: value for key, value in command.items() if not key.startswith("_")}
