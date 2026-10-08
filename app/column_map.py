from __future__ import annotations

SHEET_HEADERS_A_AF = {
    "A": "EstrategiaId",
    "B": "ItemMantenible",
    "C": "ModoDeFalla",
    "D": "TipoEstrategia",
    "E": "TareaId",
    "F": "Nombre",
    "G": "TipoTarea",
    "H": "Restriccion",
    "I": "LimitesAceptables",
    "J": "ComentariosCondicionales",
    "K": "Origen",
    "L": "Frecuencia",
    "M": "UnidadTiempo",
    "N": "Especialidad",
    "O": "Labour1",
    "P": "Labour1Cantidad",
    "Q": "Labour1Horas",
    "R": "Labour2",
    "S": "Labour2Cantidad",
    "T": "Labour2Horas",
    "U": "Labour3",
    "V": "Labour3Cantidad",
    "W": "Labour3Horas",
    "X": "Labour4",
    "Y": "Labour4Cantidad",
    "Z": "Labour4Horas",
    "AA": "LabourOtras",
    "AB": "OrigTL1",
    "AC": "OrigTL2",
    "AD": "OrigTL3",
    "AE": "OrigTL4",
    "AF": "Eliminar",
}

# Canonical write policy for the integrated cloud system.
WRITE_COLUMNS = {"B", "C", "H", "I", "J", "K", "L", "M", "N", "O"}
SEARCH_COLUMNS = {"E", "F"}

# Pocket is retrieval/evidence only. These hints never expand WRITE_COLUMNS.
POCKET_HINT_COLUMNS = {"F", "I", "J", "L", "M", "N", "O", "P", "Q"}
SAFE_SEMANTIC_HINT_COLUMNS = tuple(sorted(WRITE_COLUMNS & POCKET_HINT_COLUMNS))

BLOCKED_COLUMNS = set(SHEET_HEADERS_A_AF) - WRITE_COLUMNS


def validate_header_row(values: list[str]) -> list[str]:
    mismatches: list[str] = []
    for index, (letter, expected) in enumerate(SHEET_HEADERS_A_AF.items()):
        actual = values[index] if index < len(values) else ""
        if str(actual).strip() != expected:
            mismatches.append(f"{letter}: expected {expected!r}, got {actual!r}")
    return mismatches


def assert_write_operation(column: str, header: str) -> None:
    column = column.strip().upper()
    if column not in WRITE_COLUMNS:
        raise ValueError(f"Columna bloqueada: {column}.")
    expected = SHEET_HEADERS_A_AF[column]
    if header.strip() != expected:
        raise ValueError(
            f"Encabezado no coincide para {column}: expected {expected!r}, got {header!r}."
        )
