from fastapi.testclient import TestClient

from app.column_map import WRITE_COLUMNS
from app.main import app, semantic_index

client = TestClient(app)


def test_health_is_cloud_safe_by_default():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["records_indexed"] == 360
    assert body["sheet_write_enabled"] is False
    assert body["human_confirmation_required"] is True


def test_index_has_360_records():
    assert len(semantic_index.records) == 360
    body = client.get("/api/index/status").json()
    assert body["records"] == 360
    assert body["authority"] == "retrieval_only"


def test_semantic_search_returns_evidence_not_authority():
    response = client.post(
        "/api/index/search",
        json={"query": "termografía punto caliente tablero", "top_k": 5},
    )
    assert response.status_code == 200
    matches = response.json()["matches"]
    assert matches
    assert all(item["authority"] == "retrieval_only" for item in matches)


def test_write_policy_is_asistente_3c_policy():
    assert WRITE_COLUMNS == {"B", "C", "H", "I", "J", "K", "L", "M", "N", "O"}


def test_search_column_f_is_not_writable():
    response = client.post(
        "/api/proposal",
        json={"row": 5, "column": "F", "value": "No modificar nombre"},
    )
    assert response.status_code == 409


def test_reviewable_j_can_be_proposed_but_not_applied_without_approval():
    proposed = client.post(
        "/api/proposal",
        json={"row": 5, "column": "J", "value": "Revisar desviación"},
    )
    assert proposed.status_code == 201
    proposal_id = proposed.json()["id"]

    blocked = client.post("/api/apply", json={"proposal_id": proposal_id})
    assert blocked.status_code == 409
