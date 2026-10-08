from __future__ import annotations

from .column_map import SAFE_SEMANTIC_HINT_COLUMNS, SHEET_HEADERS_A_AF

PRTS = [
    ("1YD PREV SRVC SCI", "SERV EXT SCI", "SCI", "Mantenimiento preventivo anual del sistema contra incendio SCI", ["red SCI", "panel de incendio", "detectores", "sirena", "bomba jockey", "válvula supervisada"]),
    ("1MO INS ELEC SEGURIDAD", "GACSA SISTEMA POTENCIA SERV EXT", "POTENCIA", "Inspección mensual eléctrica de seguridad en tableros y paneles", ["tablero DP", "panel LP", "puesta a tierra", "bloqueo eléctrico", "corriente estable", "señalización"]),
    ("1MO INS SRVC ELEC SALA", "GACSA SISTEMA POTENCIA SERV EXT", "SALA_ELECTRICA", "Inspección mensual del servicio eléctrico en sala eléctrica", ["sala eléctrica", "MCC", "celdas", "iluminación", "ventilación de sala", "orden y limpieza"]),
    ("1MO MBC PRED TERMOGRAFIA", "GACSA SISTEMA POTENCIA SERV EXT", "TERMOGRAFIA", "Termografía mensual predictiva en tableros, borneras y barras", ["imagen térmica", "punto caliente", "barra RST", "bornera", "interruptor principal", "delta térmico"]),
    ("1MO MBC PRED ULTRASONIDO", "GACSA SISTEMA POTENCIA SERV EXT", "ULTRASONIDO", "Ultrasonido mensual predictivo en componentes eléctricos energizados", ["descarga parcial", "ruido ultrasónico", "corona", "tracking", "aislador", "celda energizada"]),
    ("1MO PREV SRVC HVAC", "SERV EXT HVAC", "HVAC", "Servicio preventivo mensual HVAC en unidades de climatización", ["filtro HVAC", "evaporador", "condensador", "presión de refrigerante", "termostato", "drenaje"]),
    ("1MO PREV SRVC SALA ELEC SCI", "SERV EXT SCI", "SCI_SALA", "Preventivo mensual SCI asociado a sala eléctrica", ["sala eléctrica SCI", "detector de humo", "panel de alarma", "estación manual", "luz estroboscópica", "sirena"]),
    ("1YD PREV SRVC SALA", "GACSA SISTEMA POTENCIA SERV EXT", "SALA_ELECTRICA", "Servicio preventivo anual de sala eléctrica", ["sala eléctrica anual", "limpieza técnica", "tablero general", "barras", "aislamiento visual", "ajuste mecánico"]),
    ("1YO MBC SRVC EARTHING SALA", "GACSA SISTEMA POTENCIA SERV EXT", "EARTHING", "Servicio anual de medición y verificación de puesta a tierra de sala", ["malla a tierra", "resistencia de tierra", "pozo a tierra", "conductor verde amarillo", "barra equipotencial", "telurómetro"]),
    ("2YD PREV SRVC SALA", "GACSA SISTEMA POTENCIA SERV EXT", "SALA_ELECTRICA", "Servicio preventivo bienal de sala eléctrica", ["preventivo bienal", "sala de tableros", "celdas MT", "limpieza dieléctrica", "ajuste de puertas", "verificación de barras"]),
    ("3MD PREV SRVC HVAC", "SERV EXT HVAC", "HVAC", "Servicio preventivo trimestral HVAC de mayor alcance", ["mantenimiento trimestral HVAC", "serpentín", "compresor", "ventilador", "amperaje HVAC", "lavado químico"]),
    ("3MO INS SRVC BATTERY BANK", "GACSA SISTEMA POTENCIA SERV EXT", "BATERIAS", "Inspección trimestral del banco de baterías", ["banco de baterías", "voltaje por celda", "sulfatación", "UPS DC", "temperatura de batería", "bornes"]),
    ("3MO INS SRVC ELEC SALA", "GACSA SISTEMA POTENCIA SERV EXT", "SALA_ELECTRICA", "Inspección trimestral del servicio eléctrico de sala", ["inspección trimestral", "sala eléctrica", "alimentadores", "tablero de control", "estado de interruptores", "limpieza visual"]),
    ("3MO MBC PRED TERMOGRAFIA", "GACSA SISTEMA POTENCIA SERV EXT", "TERMOGRAFIA", "Termografía trimestral predictiva de mayor cobertura", ["termografía trimestral", "conexión caliente", "falso contacto", "barra de cobre", "breaker", "registro termográfico"]),
    ("3MO MBC PRED ULTRASONIDO", "GACSA SISTEMA POTENCIA SERV EXT", "ULTRASONIDO", "Ultrasonido trimestral predictivo en sala y equipos eléctricos", ["ultrasonido trimestral", "descarga interna", "arco incipiente", "ruido eléctrico", "aislamiento", "registro acústico"]),
    ("4YD PREV SRVC BANK CHARGER", "GACSA SISTEMA POTENCIA SERV EXT", "CARGADOR", "Servicio preventivo cuatrienal del cargador de baterías", ["cargador de baterías", "rectificador", "flotación DC", "ecualización", "ripple", "alarma charger"]),
    ("5YD PREV SRVC RELES", "GACSA SISTEMA POTENCIA SERV EXT", "RELES", "Servicio preventivo quinquenal de relés de protección", ["relé de protección", "inyección secundaria", "curva de disparo", "pickup", "trip", "prueba funcional"]),
    ("5YD PREV SRVC SALA", "GACSA SISTEMA POTENCIA SERV EXT", "SALA_ELECTRICA", "Servicio preventivo quinquenal integral de sala eléctrica", ["mantenimiento quinquenal", "sala eléctrica integral", "celdas completas", "torque general", "limpieza profunda", "prueba dieléctrica"]),
    ("6MD PREV SRVC HVAC", "SERV EXT HVAC", "HVAC", "Servicio preventivo semestral HVAC integral", ["semestral HVAC", "recuperación de refrigerante", "lavado de serpentines", "motor ventilador", "presostato", "temperatura de impulsión"]),
    ("6MD PREV SRVC SALA ELEC SCI", "SERV EXT SCI", "SCI_SALA", "Servicio preventivo semestral SCI para sala eléctrica", ["semestral SCI", "detectores de sala", "panel contra incendio", "prueba de alarma", "lazo supervisado", "batería de panel SCI"]),
]


def build_records() -> list[dict]:
    columns = list(SAFE_SEMANTIC_HINT_COLUMNS)
    rows: list[dict] = []
    for family_index, (code, specialty, family, feature, tokens) in enumerate(PRTS):
        for variant in range(18):
            token_a = tokens[variant % len(tokens)]
            token_b = tokens[(variant + 2) % len(tokens)]
            column = columns[(family_index + variant) % len(columns)]
            rows.append(
                {
                    "query": (
                        f"Reporte de mantenimiento: {token_a}; se observó {token_b}. "
                        f"Validar similitud con {feature} y proponer revisión controlada para {code}."
                    ),
                    "prt_code": code,
                    "family": family,
                    "specialty": specialty,
                    "matched_historical_feature": feature,
                    "suggested_column": column,
                    "suggested_column_name": SHEET_HEADERS_A_AF[column],
                    "requires_human_confirmation": True,
                }
            )
    assert len(rows) == 360
    return rows
