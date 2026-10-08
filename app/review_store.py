from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock

from .column_map import assert_write_operation


def utc_iso(epoch: float | None = None) -> str:
    value = time.time() if epoch is None else epoch
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


@dataclass
class ReviewStore:
    ttl_seconds: int = 5 * 60

    def __post_init__(self) -> None:
        self._proposals: dict[str, dict] = {}
        self._row_locks: dict[int, str] = {}
        self._lock = RLock()

    def propose(
        self,
        *,
        row: int,
        matched: str,
        operations: list[dict],
        external_command_id: str | None = None,
    ) -> dict:
        if row < 5:
            raise ValueError("La fila propuesta debe estar debajo de la cabecera.")
        if not operations:
            raise ValueError("La propuesta debe contener al menos una operación.")

        for operation in operations:
            assert_write_operation(
                str(operation.get("columna_actualizar", "")),
                str(operation.get("encabezado", "")),
            )

        with self._lock:
            existing_id = self._row_locks.get(row)
            if existing_id:
                existing = self._proposals.get(existing_id)
                if (
                    existing
                    and existing["status"] == "proposed"
                    and not self._expired(existing)
                ):
                    raise ValueError(
                        f"La fila {row} ya está bloqueada por otra propuesta."
                    )
                self._release(row, existing_id)

            now_epoch = time.time()
            proposal = {
                "id": str(uuid.uuid4()),
                "row": row,
                "matched": matched.strip(),
                "operations": operations,
                "external_command_id": external_command_id,
                "status": "proposed",
                "created_at": utc_iso(now_epoch),
                "updated_at": utc_iso(now_epoch),
                "expires_at": utc_iso(now_epoch + self.ttl_seconds),
                "_expires_epoch": now_epoch + self.ttl_seconds,
            }
            self._proposals[proposal["id"]] = proposal
            self._row_locks[row] = proposal["id"]
            return self._public(proposal)

    def get(self, proposal_id: str) -> dict:
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                raise ValueError("Propuesta no encontrada.")
            if proposal["status"] == "proposed" and self._expired(proposal):
                proposal["status"] = "rejected"
                proposal["updated_at"] = utc_iso()
                self._release(proposal["row"], proposal["id"])
                raise ValueError("La propuesta expiró y la fila fue desbloqueada.")
            return self._public(proposal)

    def approve(self, proposal_id: str) -> dict:
        with self._lock:
            proposal = self._require(proposal_id)
            if proposal["status"] != "proposed":
                raise ValueError(
                    f"La propuesta no está en estado proposed: {proposal['status']}."
                )
            if self._expired(proposal):
                proposal["status"] = "rejected"
                self._release(proposal["row"], proposal["id"])
                raise ValueError("La propuesta expiró.")
            proposal["status"] = "approved"
            proposal["updated_at"] = utc_iso()
            self._release(proposal["row"], proposal["id"])
            return self._public(proposal)

    def reject(self, proposal_id: str) -> dict:
        with self._lock:
            proposal = self._require(proposal_id)
            if proposal["status"] in {"proposed", "approved"}:
                proposal["status"] = "rejected"
                proposal["updated_at"] = utc_iso()
            self._release(proposal["row"], proposal["id"])
            return self._public(proposal)

    def require_approved(self, proposal_id: str) -> dict:
        proposal = self._require(proposal_id)
        if proposal["status"] != "approved":
            raise ValueError("La propuesta requiere aprobación humana previa.")
        return self._public(proposal)

    def mark_applied(self, proposal_id: str) -> dict:
        with self._lock:
            proposal = self._require(proposal_id)
            if proposal["status"] != "approved":
                raise ValueError("Solo una propuesta approved puede marcarse applied.")
            proposal["status"] = "applied"
            proposal["updated_at"] = utc_iso()
            return self._public(proposal)

    def _require(self, proposal_id: str) -> dict:
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Propuesta no encontrada.")
        return proposal

    @staticmethod
    def _expired(proposal: dict) -> bool:
        return time.time() >= proposal["_expires_epoch"]

    def _release(self, row: int, proposal_id: str) -> None:
        if self._row_locks.get(row) == proposal_id:
            self._row_locks.pop(row, None)

    @staticmethod
    def _public(proposal: dict) -> dict:
        return {key: value for key, value in proposal.items() if not key.startswith("_")}
