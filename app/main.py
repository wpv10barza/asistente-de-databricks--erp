from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from .column_map import SHEET_HEADERS_A_AF, WRITE_COLUMNS
from .config import Settings
from .device_store import DeviceCommandStore, normalize_device_command, verify_device_token
from .firmware_ota import FirmwareOtaError, FirmwareOtaStore
from .firmware_uc_volume import UcVolumeFirmwareOtaStore
from .google_sheets import SheetsError, SheetsGateway
from .indexer import SemanticIndex
from .interpreter import interpret_command
from .review_store import ReviewStore
from .sheet_index import LiveSheetIndex


app = FastAPI(
    title="Asistente 3C + ERP Databricks",
    version="3.0.0",
    description="Edición Databricks-only: RAG, Device API, revisión humana y Google Sheets.",
)

settings = Settings()
gateway = SheetsGateway(settings)
semantic_index = SemanticIndex.load()
sheet_index = LiveSheetIndex()
device_commands = DeviceCommandStore()
review_store = ReviewStore()
firmware_ota = (
    UcVolumeFirmwareOtaStore(settings.ota_volume_path, settings.ota_channel)
    if settings.ota_volume_path.strip().startswith("/Volumes/")
    else FirmwareOtaStore(settings.ota_volume_path, settings.ota_channel)
)


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class SheetRebuildRequest(BaseModel):
    max_rows: int = Field(default=996, ge=1, le=996)


class DeviceCommandRequest(BaseModel):
    device_id: str
    request_id: str | None = None
    text: str


class ReviewOperation(BaseModel):
    campo: str = ""
    columna_actualizar: str
    encabezado: str
    valor_actualizar: Any
    razon: str = ""


class ReviewProposalRequest(BaseModel):
    row: int = Field(ge=5)
    matched: str = ""
    operations: list[ReviewOperation]
    external_command_id: str | None = None


class SingleProposalRequest(BaseModel):
    row: int = Field(ge=5)
    column: str
    value: Any


class ApplyRequest(BaseModel):
    proposal_id: str


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    detectedHeaders: dict[str, str] = Field(default_factory=dict)
    detectedCatalogs: dict[str, list[str]] = Field(default_factory=dict)


def _device_authorization(request: Request) -> None:
    configured = settings.esp32_api_token
    if not configured and not settings.allow_insecure_device_api:
        raise HTTPException(
            status_code=503,
            detail="ESP32_API_TOKEN no está configurado en el servidor.",
        )

    if configured:
        candidate = request.headers.get("x-3c-device-token", "")
        if not candidate:
            authorization = request.headers.get("authorization", "")
            if authorization.lower().startswith("bearer "):
                candidate = authorization[7:].strip()
        if not verify_device_token(configured, candidate):
            raise HTTPException(status_code=401, detail="Token del dispositivo inválido.")


def _proposal_or_404(proposal_id: str) -> dict:
    try:
        return review_store.get(proposal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <!doctype html>
    <html lang="es">
      <head><meta charset="utf-8"><title>Asistente 3C Databricks</title></head>
      <body style="font-family:system-ui;max-width:900px;margin:40px auto;line-height:1.5">
        <h1>Asistente 3C + ERP — Databricks</h1>
        <p>API cloud activa. La IA propone; el backend valida; la persona confirma.</p>
        <ul>
          <li><a href="/docs">OpenAPI / revisión interactiva</a></li>
          <li><a href="/api/health">Health</a></li>
          <li><a href="/api/index/status">Índice Pocket</a></li>
          <li><a href="/api/device/v1/health">Device API</a></li>
        </ul>
        <p>Google Sheets escribe solo si existe aprobación humana y ALLOW_SHEET_WRITE=true.</p>
      </body>
    </html>
    """


@app.get("/api/health")
@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "service": "asistente-databricks-erp",
        "version": "3.0.0",
        "runtime": "databricks" if settings.databricks_runtime else "local-test",
        "records_indexed": len(semantic_index.records),
        "live_sheet_records_indexed": len(sheet_index.rows),
        "sheet_auth_mode": settings.sheet_auth_mode,
        "sheet_write_enabled": settings.allow_sheet_write,
        "gemini_configured": bool(settings.gemini_api_key),
        "device_api_configured": bool(settings.esp32_api_token),
        "ota_volume_configured": firmware_ota.configured,
        "ota_channel": settings.ota_channel,
        "human_confirmation_required": True,
    }


@app.get("/api/config")
def config() -> dict:
    return {
        "spreadsheet_id": settings.spreadsheet_id,
        "sheet_name": settings.sheet_name,
        "header_row": settings.header_row,
        "search_columns": ["E", "F"],
        "write_columns": sorted(WRITE_COLUMNS),
    }


@app.get("/api/index/status")
@app.get("/index/status")
def index_status() -> dict:
    return {
        "status": "ready",
        "records": len(semantic_index.records),
        "tokens": len(semantic_index.inverted),
        "source": "pocket_deterministic_dataset",
        "authority": "retrieval_only",
    }


@app.post("/api/index/search")
@app.post("/index/search")
def index_search(item: SearchRequest) -> dict:
    return {
        "query": item.query,
        "matches": semantic_index.search(item.query, item.top_k),
        "source": "pocket_deterministic_dataset",
        "authority": "retrieval_only",
    }


@app.get("/api/index/sheet/status")
def sheet_index_status() -> dict:
    return {
        "status": "ready" if sheet_index.rows else "empty",
        "records": len(sheet_index.rows),
        "tokens": len(sheet_index.inverted),
        "source": "google_sheet",
    }


@app.post("/api/index/sheet/rebuild")
def rebuild_sheet_index(item: SheetRebuildRequest) -> dict:
    try:
        verification = gateway.verify_template()
        if not verification["ok"]:
            raise HTTPException(status_code=409, detail=verification)
        end_row = settings.header_row + item.max_rows
        a1 = (
            f"'{settings.sheet_name}'!"
            f"A{settings.header_row + 1}:AF{end_row}"
        )
        values = gateway.read_values(a1)
        count = sheet_index.rebuild(values, start_row=settings.header_row + 1)
    except SheetsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "status": "ready",
        "records": count,
        "range": a1,
        "source": "google_sheet",
        "write_performed": False,
    }


@app.post("/api/index/sheet/search")
def search_sheet_index(item: SearchRequest) -> dict:
    if not sheet_index.rows:
        raise HTTPException(
            status_code=409,
            detail="Live Google Sheet index is empty. Rebuild it first.",
        )
    return {
        "query": item.query,
        "matches": sheet_index.search(item.query, item.top_k),
        "source": "google_sheet",
    }


@app.get("/api/sheet/verify")
@app.get("/sheet/verify")
def verify_sheet() -> dict:
    try:
        result = gateway.verify_template()
    except SheetsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result)
    return result


@app.post("/api/extract")
def extract(item: ExtractRequest) -> dict:
    try:
        return interpret_command(
            settings,
            item.text,
            item.detectedHeaders,
            item.detectedCatalogs,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, SheetsError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/review/proposals", status_code=201)
def create_review_proposal(item: ReviewProposalRequest) -> dict:
    try:
        return review_store.propose(
            row=item.row,
            matched=item.matched,
            operations=[operation.model_dump() for operation in item.operations],
            external_command_id=item.external_command_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/proposal", status_code=201)
@app.post("/proposal", status_code=201)
def create_single_proposal(item: SingleProposalRequest) -> dict:
    column = item.column.strip().upper()
    if column not in WRITE_COLUMNS:
        raise HTTPException(status_code=409, detail=f"Columna bloqueada: {column}.")
    operation = {
        "campo": "",
        "columna_actualizar": column,
        "encabezado": SHEET_HEADERS_A_AF[column],
        "valor_actualizar": item.value,
        "razon": "Propuesta API",
    }
    try:
        return review_store.propose(
            row=item.row,
            matched="",
            operations=[operation],
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/review/proposals/{proposal_id}")
def get_review_proposal(proposal_id: str) -> dict:
    return _proposal_or_404(proposal_id)


@app.post("/api/review/proposals/{proposal_id}/approve")
def approve_review_proposal(proposal_id: str) -> dict:
    try:
        return review_store.approve(proposal_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/review/proposals/{proposal_id}/reject")
def reject_review_proposal(proposal_id: str) -> dict:
    try:
        proposal = review_store.reject(proposal_id)
        command_id = proposal.get("external_command_id")
        if command_id:
            device_commands.update(command_id, "rejected", "Rechazado por revisión humana.")
        return proposal
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/review/proposals/{proposal_id}/apply")
def apply_review_proposal(proposal_id: str) -> dict:
    try:
        proposal = review_store.require_approved(proposal_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    verification = None
    try:
        verification = gateway.verify_template()
        if not verification["ok"]:
            raise HTTPException(status_code=409, detail=verification)

        changes = [
            (
                f"{operation['columna_actualizar']}{proposal['row']}",
                operation["valor_actualizar"],
            )
            for operation in proposal["operations"]
        ]
        google_result = gateway.batch_update_cells(changes)
        applied = review_store.mark_applied(proposal_id)

        command_id = applied.get("external_command_id")
        if command_id:
            device_commands.update(
                command_id,
                "applied",
                f"Propuesta {proposal_id} aplicada.",
            )

        return {
            "status": "applied",
            "proposal": applied,
            "google": google_result,
            "template_verification": verification,
        }
    except SheetsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/apply")
@app.post("/apply")
def apply_by_id(item: ApplyRequest) -> dict:
    return apply_review_proposal(item.proposal_id)


@app.get("/api/device/v1/health")
def device_health() -> dict:
    return {
        "ok": True,
        "service": "asistente-3c-device-api-databricks",
        "accepts_commands": bool(settings.esp32_api_token)
        or settings.allow_insecure_device_api,
        "requires_human_confirmation": True,
        "protocol_version": "1.0",
        "supports_status_polling": True,
        "supports_https_ota": True,
        "firmware_latest_path": "/api/device/v1/firmware/latest",
        "discovery": {
            "mode": "databricks_app_url",
            "mdns": False,
        },
    }


@app.get("/api/device/v1/firmware/latest")
def latest_device_firmware(request: Request) -> dict:
    _device_authorization(request)
    try:
        release = firmware_ota.latest()
    except FirmwareOtaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        **release.public(),
        "channel": settings.ota_channel,
        "transport": "https",
        "verification": "sha256",
    }


@app.get("/api/device/v1/firmware/commits/{commit_sha}")
def firmware_by_git_commit(commit_sha: str, request: Request) -> dict:
    _device_authorization(request)
    try:
        release = firmware_ota.release_for_commit(commit_sha)
    except FirmwareOtaError as exc:
        message = str(exc)
        lowered = message.lower()
        status = (400 if "sha inválido" in lowered
                  else 409 if "ambiguo" in lowered
                  else 404 if "no existe firmware" in lowered
                  else 503)
        raise HTTPException(status_code=status, detail=message) from exc
    return {
        **release.public(),
        "channel": settings.ota_channel,
        "transport": "https",
        "verification": "sha256",
        "selection": "git_commit",
    }


@app.get("/api/device/v1/firmware/{version}.bin")
def download_device_firmware(version: str, request: Request) -> Response:
    """Return one fully verified, fixed-length binary body.

    ESP32's HTTPClient.getStreamPtr reads the unframed TCP/TLS payload.
    A fixed Content-Length (and no chunked transfer framing) is needed for
    its firmware loader. FileResponse's multi-chunk ASGI streaming can
    interact poorly with an intermediate proxy, so buffer this bounded OTA
    image before beginning the HTTP response. The firmware is restricted to
    a 4 MiB application partition.
    """
    _device_authorization(request)
    try:
        release = firmware_ota.release(version)
        if release.size > 0x400000:
            raise FirmwareOtaError("Firmware OTA excede la partición de 4 MiB.")
        payload = release.path.read_bytes()
        if len(payload) != release.size:
            raise FirmwareOtaError("Tamaño del binario cambió durante la lectura.")
        if not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), release.sha256):
            raise FirmwareOtaError("SHA-256 de la respuesta OTA no coincide.")
    except FirmwareOtaError as exc:
        message = str(exc)
        status = (404 if "no encontrado" in message.lower()
                  else 400 if "versión ota inválida" in message.lower()
                  else 503)
        raise HTTPException(status_code=status, detail=message) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="No se pudo leer firmware OTA.") from exc

    return Response(
        content=payload,
        media_type="application/octet-stream",
        headers={
            "Content-Length": str(len(payload)),
            "X-Firmware-Version": release.version,
            "X-Firmware-SHA256": release.sha256,
            "Cache-Control": "private, no-store",
        },
    )

@app.post("/api/device/v1/commands")
def enqueue_device_command(item: DeviceCommandRequest, request: Request) -> dict:
    _device_authorization(request)
    try:
        normalized = normalize_device_command(item.model_dump())
        command, duplicate = device_commands.enqueue(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "command_id": command["id"],
        "request_id": command["request_id"],
        "status": command["status"],
        "duplicate": duplicate,
        "requires_human_confirmation": True,
        "status_path": f"/api/device/v1/commands/{command['id']}",
        "message": "Comando recibido para revisión humana.",
    }


@app.get("/api/device/v1/commands/pending")
def pending_device_command(after: str | None = None) -> dict:
    return {"command": device_commands.latest_pending(after)}


@app.get("/api/device/v1/commands/{command_id}")
def get_device_command(command_id: str, request: Request) -> dict:
    _device_authorization(request)
    command = device_commands.get(command_id)
    if not command:
        raise HTTPException(status_code=404, detail="Comando no encontrado o vencido.")
    return {"command": command}
