from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from .config import Settings

FIELD_RULES = {
    "item_mantenible": {"column": "B", "header": "ItemMantenible", "type": "catalog"},
    "modo_falla": {"column": "C", "header": "ModoDeFalla", "type": "catalog"},
    "restriccion": {"column": "H", "header": "Restriccion", "type": "text"},
    "limites_aceptables": {"column": "I", "header": "LimitesAceptables", "type": "long_text"},
    "comentarios_condicionales": {"column": "J", "header": "ComentariosCondicionales", "type": "long_text"},
    "origen": {"column": "K", "header": "Origen", "type": "text"},
    "frecuencia": {"column": "L", "header": "Frecuencia", "type": "positive_integer"},
    "unidad_tiempo": {"column": "M", "header": "UnidadTiempo", "type": "time_unit"},
    "especialidad": {"column": "N", "header": "Especialidad", "type": "catalog"},
    "labour1": {"column": "O", "header": "Labour1", "type": "catalog"},
}


def normalize_comparable(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(char for char in text if unicodedata.category(char) != "Mn")


def normalize_operation_value(
    field: str,
    raw_value: object,
    detected_catalogs: dict[str, list[str]],
) -> str | int:
    if field not in FIELD_RULES:
        raise ValueError(f"Campo no permitido: {field}")
    rule = FIELD_RULES[field]
    text = str(raw_value or "").strip()

    if rule["type"] == "positive_integer":
        try:
            number = int(text)
        except ValueError as exc:
            raise ValueError(f"{rule['header']} debe ser un entero.") from exc
        if number < 1:
            raise ValueError(f"{rule['header']} debe ser >= 1.")
        return number

    if rule["type"] == "time_unit":
        aliases = {
            "mensual": "Mes",
            "mes": "Mes",
            "meses": "Mes",
            "anual": "año",
            "ano": "año",
            "año": "año",
            "anos": "año",
            "años": "año",
            "semanal": "Semana",
            "semana": "Semana",
            "semanas": "Semana",
            "diario": "Dia",
            "diaria": "Dia",
            "dia": "Dia",
            "dias": "Dia",
            "hora": "Hora",
            "horas": "Hora",
        }
        mapped = aliases.get(normalize_comparable(text))
        if not mapped:
            raise ValueError(f"Unidad de tiempo no válida: {text}.")
        return mapped

    if not text:
        raise ValueError(f"{rule['header']} no puede quedar vacío.")

    if rule["type"] == "long_text" and re.search(r"(\.\.\.|…|\betc\.?\b)", text, re.I):
        raise ValueError(
            f"{rule['header']} debe contener texto completo sin elipsis ni etcétera."
        )

    if rule["type"] == "catalog":
        catalog = detected_catalogs.get(field, [])
        match = next(
            (
                value
                for value in catalog
                if normalize_comparable(value) == normalize_comparable(text)
            ),
            None,
        )
        if match is None:
            raise ValueError(
                f"{rule['header']} debe coincidir con un valor existente en el catálogo."
            )
        return match

    return text


def build_prompt(
    text: str,
    detected_headers: dict[str, str],
    detected_catalogs: dict[str, list[str]],
) -> str:
    allowed = ", ".join(
        f"{field}={rule['column']}:{rule['header']}"
        for field, rule in FIELD_RULES.items()
    )
    return f"""Eres el parser de comandos del Asistente 3C desplegado en Databricks.
No ejecutas cambios. Produces JSON que será validado por un backend determinístico.

REGLAS INMUTABLES:
- La tarea se localiza por Nombre en F o por TareaId en E si fue indicado.
- No inventes columnas, encabezados, IDs ni valores.
- Solo puedes proponer: {allowed}.
- E y F son búsqueda; nunca se escriben.
- mensual => frecuencia=1 y unidad_tiempo=Mes salvo valor explícito.
- anual => frecuencia=1 y unidad_tiempo=año salvo valor explícito.
- cada N meses => frecuencia=N y unidad_tiempo=Mes.
- cada N años => frecuencia=N y unidad_tiempo=año.
- límites/criterio aceptable => limites_aceptables.
- comentario/instrucción/procedimiento condicional => comentarios_condicionales.
- No trunques texto con ..., … ni etc.
- Los campos catalog deben coincidir exactamente con catálogos existentes.
- Si falta tarea, valor o existe ambigüedad: requiere_revision=true.
- Nunca marques una operación como aplicada.

Devuelve JSON con:
tarea_buscada, tarea_id, operaciones[], requiere_revision, motivo_revision.
Cada operación: campo, valor, razon.

ENCABEZADOS:
{json.dumps(detected_headers, ensure_ascii=False)}

CATALOGOS:
{json.dumps(detected_catalogs, ensure_ascii=False)}

COMANDO:
{json.dumps(text, ensure_ascii=False)}
"""


def validate_model_output(
    parsed: dict[str, Any],
    detected_headers: dict[str, str],
    detected_catalogs: dict[str, list[str]],
) -> dict:
    validated: list[dict] = []
    for operation in parsed.get("operaciones", []) or []:
        field = str(operation.get("campo", "")).strip()
        if field not in FIELD_RULES:
            raise ValueError(f"Campo no permitido: {field}")
        rule = FIELD_RULES[field]
        detected = detected_headers.get(rule["column"])
        if detected and detected != rule["header"]:
            raise ValueError(
                f"La columna {rule['column']} no coincide con {rule['header']}."
            )
        validated.append(
            {
                "campo": field,
                "columna_actualizar": rule["column"],
                "encabezado": rule["header"],
                "valor_actualizar": normalize_operation_value(
                    field,
                    operation.get("valor"),
                    detected_catalogs,
                ),
                "razon": str(operation.get("razon", "")).strip(),
            }
        )

    task_id = str(parsed.get("tarea_id", "") or "").strip()
    return {
        "tarea_buscada": str(parsed.get("tarea_buscada", "") or "").strip(),
        "tarea_id": task_id,
        "columna_busqueda": "E" if task_id else "F",
        "operaciones": validated,
        "requiere_revision": bool(parsed.get("requiere_revision")) or not validated,
        "motivo_revision": str(
            parsed.get("motivo_revision")
            or ("" if validated else "No se detectaron cambios válidos.")
        ).strip(),
        "authority": "proposal_only",
    }


def interpret_command(
    settings: Settings,
    text: str,
    detected_headers: dict[str, str],
    detected_catalogs: dict[str, list[str]],
) -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY no está configurada.")

    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=build_prompt(text, detected_headers, detected_catalogs),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
    except errors.ClientError as exc:
        status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if status in {400, 401, 403}:
            raise RuntimeError(
                f"Gemini rechazó credencial/autorización o acceso al modelo (HTTP {status})."
            ) from exc
        if status == 404:
            raise RuntimeError(
                "El modelo Gemini configurado no está disponible para este proyecto."
            ) from exc
        raise RuntimeError(
            f"Gemini rechazó la solicitud (HTTP {status or 'desconocido'})."
        ) from exc
    except errors.APIError as exc:
        raise RuntimeError("Gemini API no está disponible temporalmente.") from exc
    parsed = json.loads(response.text or "{}")
    if not isinstance(parsed, dict):
        raise ValueError("La respuesta del modelo no es un objeto JSON.")
    return validate_model_output(parsed, detected_headers, detected_catalogs)
