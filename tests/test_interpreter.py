import pytest

from app.interpreter import normalize_operation_value, validate_model_output


def test_frequency_must_be_positive_integer():
    assert normalize_operation_value("frecuencia", "3", {}) == 3
    with pytest.raises(ValueError):
        normalize_operation_value("frecuencia", "0", {})


def test_time_unit_is_canonicalized():
    assert normalize_operation_value("unidad_tiempo", "mensual", {}) == "Mes"
    assert normalize_operation_value("unidad_tiempo", "anual", {}) == "año"


def test_catalog_must_match_existing_value():
    catalogs = {"especialidad": ["ELEC", "MEC"]}
    assert normalize_operation_value("especialidad", "elec", catalogs) == "ELEC"
    with pytest.raises(ValueError):
        normalize_operation_value("especialidad", "INVENTADA", catalogs)


def test_model_output_is_proposal_only():
    parsed = {
        "tarea_buscada": "Inspección",
        "tarea_id": "",
        "operaciones": [
            {"campo": "comentarios_condicionales", "valor": "Texto completo", "razon": ""}
        ],
        "requiere_revision": False,
    }
    result = validate_model_output(
        parsed,
        {"J": "ComentariosCondicionales"},
        {},
    )
    assert result["authority"] == "proposal_only"
    assert result["operaciones"][0]["columna_actualizar"] == "J"
