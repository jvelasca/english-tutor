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
from services.curriculum import load_assessments, load_level


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


def _fail_level_exam(
    monkeypatch, tmp_path, level_id: str = "a1"
) -> tuple[str, list[str]]:
    """Usuario nuevo que suspende el examen del nivel vía endpoint.

    Fallar deliberadamente todas las respuestas escribe evidencia mala sobre las
    destrezas del examen → `remediation_plan` real con debilidades (el camino
    que D1b declara reordenar y enriquecer con el nodo)."""
    uid = _setup(monkeypatch, tmp_path)
    data = load_assessments()
    exam = data.exams[level_id]
    answers = {it.id: (it.correct_index + 1) % len(it.options) for it in exam.items}
    with TestClient(app) as client:
        r = client.post(
            f"/api/academy/exam/{level_id}/submit",
            params={"user_id": uid},
            json={"answers": answers},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["passed"] is False
    assert body["failed_skills"]
    return uid, body["failed_skills"]


def test_session_weakness_step_is_enriched_with_real_remediation(
    monkeypatch, tmp_path
):
    """H1 (auditoría externa v3.17): camino REAL de remediación de D1b.

    Un usuario que suspende el examen A1 obtiene un paso `weakness` cuya
    destreza es una de las falladas y que está enriquecido con el nodo de su
    objetivo: `can_do` == can-do real del currículo, `graph_mastery` numérico y
    `because[]` no vacío (no solo el camino feliz de un usuario nuevo)."""
    uid, failed = _fail_level_exam(monkeypatch, tmp_path)
    lv = load_level("a1")
    body = _session(TestClient(app), uid)
    weak = [s for s in body["items"] if s["kind"] == "weakness"]
    assert weak, "la sesión de un examen suspendido tiene un paso `weakness`"
    step = weak[0]
    assert step["skill"] in failed, (
        f"la destreza del paso weakness ({step['skill']}) es una destreza fallada"
    )
    assert step["objective_id"]
    objective = _objective_by_id(lv, step["objective_id"])
    assert objective is not None
    assert step["can_do"] == objective.can_do
    assert isinstance(step["graph_mastery"], float)
    assert step["because"], "el nodo del objetivo explica la debilidad (because[])"


def test_next_best_never_diverges_when_first_step_has_node(monkeypatch, tmp_path):
    """H1 (auditoría externa v3.17): la no-divergencia `/next-best`==`/session`
    se fija también en el caso CON nodo (remediación real), no solo en el caso
    de usuario nuevo (listening sin objetivo → null==null).

    Se completan los pasos previos sin objetivo (repaso/listening) hasta que el
    primer paso de la sesión trae nodo, y se verifica que `/next-best` copia
    exactamente los campos del grafo."""
    uid, _failed = _fail_level_exam(monkeypatch, tmp_path)
    client = TestClient(app)
    body = _session(client, uid)
    first = body["items"][0]
    guard = 0
    while not (first.get("objective_id") and first.get("can_do")):
        r = client.post(
            "/api/academy/session/complete",
            params={"user_id": uid},
            json={"step_key": first["step_key"]},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["items"], "la sesión conserva pasos enriquecibles"
        first = body["items"][0]
        guard += 1
        assert guard < 12, "no se alcanzó un primer paso con nodo en la sesión"

    assert first["can_do"], "el primer paso de la sesión está enriquecido (nodo)"
    nb = client.get("/api/academy/next-best", params={"user_id": uid})
    assert nb.status_code == 200, nb.text
    best = nb.json()
    assert best is not None
    for field in ("can_do", "limiting_factor", "graph_mastery", "because"):
        assert best[field] == first[field], (
            f"el campo {field} de next-best divergió del primer paso enriquecido"
        )
