"""Tests de dominio/endpoint del plan diario enriquecido (V3.17, D1b/D7).

Invariantes cubiertos:
- `/api/academy/session` devuelve campos del Evidence Graph (`can_do`,
  `limiting_factor`, `graph_mastery`, `because[]`) SOLO en los pasos con
  objetivo y nodo construible (D1b); el `can_do` coincide con el can-do real
  del currículo para ese objetivo (mismo nodo → nunca diverge).
- D7: un paso sin `objective_id` (p. ej. listening) NO gana campos de grafo:
  el esquema los serializa vacíos/null y el paso se comporta como antes.
- `/api/academy/next-best` proyecta el primer paso de la sesión con los MISMOS
  campos de grafo que `/session` (mismo perfil + mismas filas → mismo nodo).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services.curriculum import load_level


def _setup(monkeypatch, tmp_path) -> str:
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _objective_by_id(lv, oid: str):
    for m in lv.modules:
        for u in m.units:
            for les in u.lessons:
                for o in les.objectives:
                    if o.id == oid:
                        return o
    return None


def _session(client, uid: str) -> dict:
    r = client.get("/api/academy/session", params={"user_id": uid})
    assert r.status_code == 200, r.text
    return r.json()


def test_session_new_step_carries_graph_fields_matching_curriculum(
    monkeypatch, tmp_path
):
    """D1b: el paso con objetivo del plan trae `can_do`/`limiting_factor`/
    `graph_mastery`/`because[]` y el can-do es el real del currículo."""
    uid = _setup(monkeypatch, tmp_path)
    lv = load_level("a1")
    body = _session(TestClient(app), uid)
    new_steps = [s for s in body["items"] if s["kind"] == "new"]
    assert new_steps, "un usuario nuevo tiene al menos un paso `new`"
    step = new_steps[0]
    assert step["objective_id"]
    objective = _objective_by_id(lv, step["objective_id"])
    assert objective is not None

    # Enriquecimiento presente: can-do textual del currículo y factor del nodo.
    assert step["can_do"] == objective.can_do
    assert isinstance(step["limiting_factor"], dict)
    assert isinstance(step["graph_mastery"], float)
    assert isinstance(step["because"], list)
    assert step["because"], "el nodo explica el can-do con al menos una viñeta"


def test_session_step_without_objective_stays_graph_silent(monkeypatch, tmp_path):
    """D7: un paso sin `objective_id` (listening, curva de olvido…) no trae
    campos de grafo; el esquema los serializa vacíos/null (fallback silencioso,
    nunca se bloquea la práctica por falta de nodo)."""
    uid = _setup(monkeypatch, tmp_path)
    body = _session(TestClient(app), uid)
    no_obj = [s for s in body["items"] if not s["objective_id"]]
    assert no_obj, "un usuario sin práctica de listening tiene pasos sin objetivo"
    for step in no_obj:
        assert step["can_do"] is None
        assert step["limiting_factor"] is None
        assert step["graph_mastery"] is None
        assert step["because"] == []


def test_next_best_graph_fields_never_diverge_from_session(monkeypatch, tmp_path):
    """D1b: `/next-best` y `/session` comparten nodo — los campos de grafo de la
    primera acción coinciden exactamente con los del primer paso de la sesión."""
    uid = _setup(monkeypatch, tmp_path)
    client = TestClient(app)
    body = _session(client, uid)
    nb = client.get("/api/academy/next-best", params={"user_id": uid})
    assert nb.status_code == 200, nb.text
    first = body["items"][0]
    best = nb.json()
    assert best is not None
    for field in ("can_do", "limiting_factor", "graph_mastery", "because"):
        assert best[field] == first[field], (
            f"el campo {field} de next-best divergió del primer paso de la sesión"
        )
