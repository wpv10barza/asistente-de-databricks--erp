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
        """Audit summary is for retained history, never an all-time guarantee.

        Only sheet_applied proves a successful Sheets API batch write.
        Approval, submission, attempt, and rejection are separate events.
        """
        limit = max(1, min(20, limit))
        with self._lock:
            events = list(self._events)
            persistent = self.persistent
        orders: dict[str, dict] = {}
        proposals: dict[str, dict] = {}
        sheet_changes: list[dict] = []
        activity: list[dict] = []
        attempts = 0
        blocked = 0
        for ev in events:
            typ = ev.get("type")
            cmd_id = ev.get("command_id")
            proposal_id = ev.get("proposal_id")
            if typ == "command_sent" and cmd_id:
                orders.setdefault(cmd_id, {
                    "command_id": cmd_id, "text": ev.get("text", ""),
                    "status": "pending_confirmation", "created_at": ev.get("at"),
                    "updated_at": ev.get("at"), "preview": [],
                })
            elif typ in ("command_applied", "command_rejected") and cmd_id:
                if cmd_id in orders:
                    orders[cmd_id]["status"] = (
                        "applied" if typ == "command_applied" else "rejected"
                    )
                    orders[cmd_id]["updated_at"] = ev.get("at")
            if typ == "proposal_preview" and cmd_id in orders:
                orders[cmd_id]["preview"] = ev.get("changes", [])
            if typ == "proposal_created" and proposal_id:
                proposals.setdefault(proposal_id, {
                    "id": proposal_id,
                    "status": "proposed", "row": ev.get("row"),
                    "command_id": cmd_id, "changes": ev.get("changes", []),
                    "created_at": ev.get("at"),
                })
            if typ in ("proposal_approved", "proposal_rejected", "sheet_applied") and proposal_id:
                proposal = proposals.setdefault(proposal_id, {
                    "id": proposal_id, "status": "proposed", "row": ev.get("row"),
                    "command_id": cmd_id, "changes": ev.get("changes", []),
                    "created_at": ev.get("at"),
                })
                proposal["status"] = {
                    "proposal_approved": "approved",
                    "proposal_rejected": "rejected",
                    "sheet_applied": "applied",
                }[typ]
                if typ == "proposal_approved" and cmd_id in orders:
                    orders[cmd_id]["status"] = "approved_not_applied"
                    orders[cmd_id]["updated_at"] = ev.get("at")
                elif typ == "proposal_rejected" and cmd_id in orders:
                    orders[cmd_id]["status"] = "rejected"
                    orders[cmd_id]["updated_at"] = ev.get("at")
            if typ == "sheet_apply_attempt":
                attempts += 1
            elif typ == "sheet_apply_blocked":
                blocked += 1
            elif typ == "sheet_applied":
                sheet_changes.append({
                    "at": ev.get("at"), "proposal_id": proposal_id,
                    "command_id": cmd_id, "row": ev.get("row"),
                    "changes": ev.get("changes", []), "status": "applied",
                })
            if typ in {
                "proposal_approved", "proposal_rejected",
                "sheet_apply_attempt", "sheet_apply_blocked", "sheet_applied",
            }:
                activity.append({
                    "at": ev.get("at"), "proposal_id": proposal_id,
                    "command_id": cmd_id, "row": ev.get("row"),
                    "status": {
                        "proposal_approved": "approved_not_applied",
                        "proposal_rejected": "rejected",
                        "sheet_apply_attempt": "attempted_not_confirmed",
                        "sheet_apply_blocked": "blocked_not_written",
                        "sheet_applied": "applied",
                    }[typ],
                    "changes": ev.get("changes", []) or
                               proposals.get(proposal_id, {}).get("changes", []),
                    "reason": _clean(ev.get("reason", ""), 100),
                })
        # Command history is per device. Sheet audit is global to this backend.
        # An all-time zero is never asserted if the audit store is not durable.
        filtered_orders = []
        commands_by_device = {
            ev.get("command_id") for ev in events
            if ev.get("type") == "command_sent" and (
                not device_id or ev.get("device_id") == device_id
            )
        }
        for cmd_id, item in orders.items():
            if cmd_id in commands_by_device:
                filtered_orders.append(item)
        filtered_orders.sort(key=lambda e: e["updated_at"] or "", reverse=True)
        summary = {
            "commands": len(filtered_orders),
            "approved": sum(p["status"] in ("approved", "applied") for p in proposals.values()),
            "rejected": sum(p["status"] == "rejected" for p in proposals.values()),
            "pending": sum(p["status"] == "proposed" for p in proposals.values()),
            "apply_attempts": attempts,
            "applied": len(sheet_changes),
            "blocked": blocked,
        }
        return {
            "orders": filtered_orders[:limit],
            "sheet_changes": sheet_changes[::-1][:limit],
            "sheet_activity": activity[::-1][:limit],
            "summary": summary,
            "persistent": persistent,
            "scope": "persistent_audit" if persistent else "current_backend_session",
            "sheet_activity_is_global": True,
            "sheet_changes_only_after_successful_batch_update": True,
        }


def panel_lines(data: dict) -> str:
    """Safe, compact 5-column TSV contract for the 480px panel.

    M row: approved, rejected, pending, attempts|applied|blocked,
    scope. O = per-device command; S = global review/Sheet audit.
    Approval/attempt are NEVER labelled as successful Sheets writes.
    """
    summary = data.get("summary", {})
    meta = "\t".join([
        "M", str(summary.get("approved", 0)), str(summary.get("rejected", 0)),
        str(summary.get("pending", 0)) + "|" +
        str(summary.get("apply_attempts", 0)) + "|" +
        str(summary.get("applied", 0)) + "|" +
        str(summary.get("blocked", 0)),
        "PERSIST" if data.get("persistent") else "SESSION",
    ])
    rows = [meta]
    for order in data["orders"]:
        preview = order.get("preview") or []
        preview_text = " | ".join(
            _clean(change.get("cell"), 12) + "=" + _clean(change.get("value"), 65)
            for change in preview[:2]
        )
        rows.append("\t".join([
            "O", _clean(order.get("updated_at"), 26),
            _clean(order.get("status"), 26),
            _clean(order.get("text"), 145), _clean(preview_text, 145),
        ]))
    for event in data.get("sheet_activity", []):
        details = " | ".join(
            _clean(change.get("cell"), 12) + "=" + _clean(change.get("value"), 65)
            for change in (event.get("changes") or [])[:2]
        )
        if not details:
            details = _clean(event.get("reason"), 100) or (
                "Propuesta " + _clean(event.get("proposal_id"), 24)
            )
        rows.append("\t".join([
            "S", _clean(event.get("at"), 26),
            _clean(event.get("status"), 26), _clean(details, 145),
            "Fila " + _clean(event.get("row"), 8) + " / " +
            _clean(event.get("proposal_id"), 38),
        ]))
    return "\n".join(rows) + "\n"
