"""Restricted, deterministic Spanish frequency commands: proposal only, never write."""
from __future__ import annotations

import re
import unicodedata

from .column_map import SHEET_HEADERS_A_AF

_WORD_NUMBERS = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3,
    "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
}
_UNITS = {
    "mes": "Mes", "meses": "Mes",
    "ano": "año", "anos": "año",
    "dia": "Dia", "dias": "Dia",
    "semana": "Semana", "semanas": "Semana",
    "hora": "Hora", "horas": "Hora",
}
# Accept only direct, unambiguous commands targeting one immutable TareaId.
_COMMAND = re.compile(
    r"^(?:cambia|cambiar|modifica|modificar|actualiza|actualizar)\s+"
    r"(?:(?:la\s+)?(?:frecuencia|periodicidad)\s+(?:de\s+)?(?:la\s+)?)?"
    r"(?:tarea\s+)?(?:id\s*)?(?P<task>\d{3,12})\s+"
    r"(?:a|cada)\s+(?P<count>\d+|[a-z]+)\s+"
    r"(?P<unit>mes(?:es)?|ano(?:s)?|dia(?:s)?|semana(?:s)?|hora(?:s)?)\.?$"
)


def parse_frequency_command(text: str) -> tuple[str, int, str] | None:
    normalized = unicodedata.normalize("NFD", text.strip().lower())
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = " ".join(normalized.split())
    match = _COMMAND.fullmatch(normalized)
    if not match:
        return None
    raw = match.group("count")
    count = int(raw) if raw.isdecimal() else _WORD_NUMBERS.get(raw, 0)
    if not 1 <= count <= 1200:
        return None
    return match.group("task"), count, _UNITS[match.group("unit")]


def unique_task_row(values: list[list[object]], task_id: str, start_row: int = 5) -> int:
    positions = [
        start_row + index for index, row in enumerate(values)
        if row and str(row[0]).strip() == task_id
    ]
    if len(positions) != 1:
        raise ValueError(
            f"TareaId {task_id}: {len(positions)} coincidencias; "
            "se requiere revision manual, ninguna escritura realizada."
        )
    return positions[0]


def frequency_operations(count: int, unit: str) -> list[dict]:
    return [
        {
            "campo": "frecuencia", "columna_actualizar": "L",
            "encabezado": SHEET_HEADERS_A_AF["L"],
            "valor_actualizar": count, "razon": "Frecuencia solicitada por usuario",
        },
        {
            "campo": "unidad_tiempo", "columna_actualizar": "M",
            "encabezado": SHEET_HEADERS_A_AF["M"],
            "valor_actualizar": unit, "razon": "Unidad temporal solicitada por usuario",
        },
    ]
