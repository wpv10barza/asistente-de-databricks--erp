from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_portal_landing_is_same_as_root_and_does_not_embed_credentials():
    root = client.get("/")
    portal = client.get("/acceso")
    assert root.status_code == portal.status_code == 200
    assert root.text == portal.text
    assert "Conexión al backend" in portal.text
    assert "Acceso del alumno" in portal.text
    assert "Control docente" in portal.text
    assert "alumno-cloud-control.yml" in portal.text
    assert 'type="password"' not in portal.text
    assert "polovaleriow@gmail.com" not in portal.text
    assert "wpvbar11@gmail.com" not in portal.text
