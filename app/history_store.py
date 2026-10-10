"""Read-only 3C and Google Sheets audit history.

An optional HISTORY_LOG_PATH on a persistent Databricks Volume makes records survive
application restarts. Without it, history is explicitly session-only.
Only a successful Google Sheets batch update produces a sheet_applied record.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: object, limit: int = 180) -> str:
    return " ".join(str(value if value is not None else "").split())[:limit]


@dataclass
class HistoryStore:
    path: str = ""
    limit: int = 500

    def __post_init__(self) -> None:
        self._lock = RLock()
        self._events: list[dict] = []
        self.persistence_error = ""
        if self.path:
            try:
                file = Path(self.path)
                if file.exists():
                    # Bound memory when reading a persisted audit (file itself is append-only).
                    with file.open("r", encoding="utf-8") as stream:
                        for line in stream:
                            try:
                                event = json.loads(line)
                                if isinstance(event, dict) and event.get("type"):
                                    self._events.append(event)
                                    self._events = self._events[-self.limit:]
                            except (ValueError, TypeError):
                                continue
            except OSError as exc:
                self.persistence_error = str(exc)

    @property
    def persistent(self) -> bool:
        return bool(self.path) and not self.persistence_error

    def append(self, event_type: str, **fields: object) -> dict:
        event = {"type": event_type, "at": _now(), **fields}
        with self._lock:
            self._events.append(event)
            self._events = self._events[-self.limit:]
            if self.path:
                try:
                    file = Path(self.path)
                    file.parent.mkdir(parents=True, exist_ok=True)
                    with file.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                    self.persistence_error = ""
                except OSError as exc:
                    # Sheet write may already be committed; never convert success to a failure.
                    self.persistence_error = str(exc)
        return event

    def recent(self, device_id: str = "", limit: int = 8) -> dict:
        limit = max(1, min(20, limit))
        with self._lock:
            events = list(self._events)
            persistent = self.persistent

        orders: dict[str, dict] = {}
        changes: list[dict] = []
        for event in events:
            kind = event.get("type")
            command_id = event.get("command_id")
            if kind in {"command_sent", "command_applied", "command_rejected"}:
                if device_id and event.get("device_id") != device_id:
                    continue
                item = orders.setdefault(command_id, {
                    "command_id": command_id,
                    "text": "",
                    "status": "pending_confirmation",
                    "created_at": event.get("at"),
                    "updated_at": event.get("at"),
                    "preview": [],
                })
                if kind == "command_sent":
                    item["text"] = event.get("text", "")
                    item["created_at"] = event.get("at")
                else:
                    item["status"] = "applied" if kind == "command_applied" else "rejected"
                item["updated_at"] = event.get("at")
            elif kind == "proposal_preview" and command_id:
                if command_id in orders:
                    orders[command_id]["preview"] = event.get("changes", [])
            elif kind == "sheet_applied":
                changes.append({
                    "at": event.get("at"),
                    "proposal_id": event.get("proposal_id"),
                    "command_id": command_id,
                    "row": event.get("row"),
                    "changes": event.get("changes", []),
                    "status": "applied",
                })
        selected = sorted(orders.values(), key=lambda e: e["updated_at"], reverse=True)[:limit]
        return {
            "orders": selected,
            "sheet_changes": list(reversed(changes))[:limit],
            "persistent": persistent,
            "scope": "persistent_audit" if persistent else "current_backend_session",
            "sheet_changes_only_after_successful_batch_update": True,
        }


def panel_lines(data: dict) -> str:
    """Small authenticated TSV contract for an ESP32 without JSON allocation.

    Type, UTC time, status/cell, summary and ID. All fields are one line.
    """
    rows = []
    for order in data["orders"]:
        preview = order.get("preview") or []
        preview_text = ""
        if preview:
            preview_text = " | ".join(
                _clean(change.get("cell"), 12) + "=" + _clean(change.get("value"), 65)
                for change in preview[:2]
            )
        rows.append("\t".join([
            "O", _clean(order.get("updated_at"), 26),
            _clean(order.get("status"), 26),
            _clean(order.get("text"), 145),
            _clean(preview_text, 145),
        ]))
    for applied in data["sheet_changes"]:
        details = " | ".join(
            _clean(change.get("cell"), 12) + "=" + _clean(change.get("value"), 90)
            for change in applied["changes"][:2]
        )
        rows.append("\t".join([
            "S", _clean(applied.get("at"), 26), "applied",
            _clean(details, 145), _clean(applied.get("command_id") or "web", 60),
        ]))
    return "\n".join(rows) + ("\n" if rows else "")
