import pytest

from app.review_store import ReviewStore


def operation(column="J", header="ComentariosCondicionales"):
    return {
        "campo": "comentarios_condicionales",
        "columna_actualizar": column,
        "encabezado": header,
        "valor_actualizar": "Texto completo",
        "razon": "",
    }


def test_review_approval_state_machine():
    store = ReviewStore()
    proposal = store.propose(row=5, matched="Tarea", operations=[operation()])
    assert proposal["status"] == "proposed"

    approved = store.approve(proposal["id"])
    assert approved["status"] == "approved"

    applied = store.mark_applied(proposal["id"])
    assert applied["status"] == "applied"


def test_review_blocks_column_f():
    store = ReviewStore()
    with pytest.raises(ValueError, match="Columna bloqueada"):
        store.propose(
            row=5,
            matched="Tarea",
            operations=[operation("F", "Nombre")],
        )


def test_row_lock_blocks_parallel_proposals():
    store = ReviewStore()
    store.propose(row=7, matched="A", operations=[operation()])
    with pytest.raises(ValueError, match="bloqueada"):
        store.propose(row=7, matched="B", operations=[operation()])
