"""Contratos del portal cloud: sin credenciales en HTML y con acciones reales, solo lectura."""

from fastapi.testclient import TestClient

from app.main import app
from app.student_portal import render_portal


client = TestClient(app)


def test_acceso_is_operational_and_passwordless():
    page = client.get("/acceso")
    assert page.status_code == 200
    assert page.text == client.get("/").text
    for marker in (
        "Conexión al backend",
        "Acceso del alumno",
        "Control docente",
        "Conectar con el backend",
        "Verificar conexión a los datos",
        "Buscar en Pocket",
        'requestJSON("/api/health")',
        'requestJSON("/api/sheet/verify")',
        'requestJSON("/api/index/search"',
        "alumno-cloud-control.yml",
    ):
        assert marker in page.text
    assert 'type="password"' not in page.text
    assert "polovaleriow@gmail.com" not in page.text
    assert "wpvbar11@gmail.com" not in page.text
    assert "ESP32_API_TOKEN" not in page.text


def test_portal_does_not_inline_any_tokens():
    page = render_portal()
    assert "DATABRICKS_CLIENT_SECRET" not in page
    assert "GEMINI_API_KEY" not in page
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" not in page


def test_pocket_search_is_a_real_read_only_api_call():
    response = client.post(
        "/api/index/search",
        json={"query": "mantenimiento preventivo", "top_k": 2},
    )
    assert response.status_code == 200
    assert "matches" in response.json()
