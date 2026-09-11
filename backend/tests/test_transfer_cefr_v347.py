"""V3.47 — CEFR y `difficulty_vector` del contexto de transferencia (P1 sección 7).

La auditoría de V3.46.0 señaló que el motor de transferencia sabía QUÉ contexto
tocaba (`work`, `future`…) pero no CUÁNTO exigía: no es lo mismo «Tell your friend
about your weekend» que «Explain to a colleague how you would handle a problem
and justify your decision». Faltaba la dimensión de dificultad para que el futuro
planner pueda ajustar la tarea al alumno.

V3.47 etiqueta cada contexto del banco con:

- `cefr` — nivel del Marco (`services.cefr.CEFR_LEVELS`);
- `difficulty_vector` — carga `lexical`/`syntax`/`discourse`/`interaction`
  (enteros 1..5), la misma convención que listening/speaking;
- `difficulty` — escalar derivado (media redondeada, clamp 1..6).

`context_for` acepta un `level` opcional (retrocompatible: sin él el
comportamiento es idéntico al de V3.46) y no sirve contextos por encima del
alcance del alumno si hay un candidato alcanzable; si no lo hay, cae al nivel
más cercano. El contrato HTTP expone los tres campos de forma aditiva.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import transfer
from services.cefr import CEFR_LEVELS


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _seed_word(a: str, word: str, *, cefr: str = "A1") -> None:
    vocabulary_repo.seed_curriculum_items(
        a,
        [
            {
                "word": word,
                "lemma": word,
                "cefr": cefr,
                "level_id": "a1",
                "objective_id": "o1",
                "kind": "word",
            }
        ],
    )
    vocabulary_repo.record_exposures(a, [word])


# ------------------------------------------------------------- banco etiquetado


def test_every_context_declares_a_valid_cefr_and_difficulty_vector():
    assert transfer.TRANSFER_DIFFICULTY_KEYS == (
        "lexical",
        "syntax",
        "discourse",
        "interaction",
    )
    for context in transfer.TRANSFER_CONTEXTS:
        assert context["cefr"] in CEFR_LEVELS, context["id"]
        vector = context["difficulty_vector"]
        assert set(vector) == set(transfer.TRANSFER_DIFFICULTY_KEYS), context["id"]
        for key, value in vector.items():
            assert 1 <= value <= 5, (context["id"], key, value)


def test_difficulty_from_vector_is_the_rounded_mean_with_clamp():
    assert transfer.difficulty_from_vector({}) == 1
    assert transfer.difficulty_from_vector({"lexical": 1, "syntax": 1}) == 1
    assert transfer.difficulty_from_vector({"lexical": 4, "syntax": 4}) == 4
    # Clamp al rango canónico 1..6 (misma regla que listening/speaking).
    assert transfer.difficulty_from_vector({"lexical": 9}) == 6
    assert transfer.difficulty_from_vector({"lexical": 0}) == 1


# ----------------------------------------------------------- selección con nivel


def test_context_for_without_level_is_unchanged():
    # Retrocompatibilidad estricta: `level=""` (y omitirlo) da el mismo contexto
    # que V3.46, sin filtrar por CEFR.
    assert (
        transfer.context_for("travel")["context_id"]
        == transfer.context_for("travel", level="")["context_id"]
    )


def test_context_for_respects_the_student_level():
    # A1 solo alcanza el contexto de nivel A1 del banco.
    got = transfer.context_for("travel", level="A1")
    assert got["available"] is True
    assert got["cefr"] == "A1"
    assert transfer.cefr_index(got["cefr"]) <= transfer.cefr_index("A1")
    # Determinista y estable entre llamadas.
    assert got["context_id"] == transfer.context_for("travel", level="A1")["context_id"]
    # El contexto servido trae su dificultad declarada.
    assert got["difficulty"] == transfer.difficulty_from_vector(
        got["difficulty_vector"]
    )


def test_context_for_falls_back_to_the_closest_level_when_none_is_reachable():
    # Si no queda ningún contexto del nivel del alumno sin usar, cae al nivel
    # alcanzable más cercano (A2), no a uno arbitrario (B1).
    a1_ids = [
        transfer.context_id_for(context)
        for context in transfer.TRANSFER_CONTEXTS
        if context["cefr"] == "A1"
    ]
    got = transfer.context_for("travel", used_context_ids=a1_ids, level="A1")
    assert got["cefr"] == "A2"
    assert got["exhausted"] is False


def test_context_for_serves_any_context_above_an_unknown_level():
    # Un nivel desconocido ("" o Pre-A1) no filtra: comportamiento histórico.
    assert (
        transfer.context_for("travel", level="Pre-A1")["context_id"]
        == transfer.context_for("travel")["context_id"]
    )


def test_context_for_ignores_level_when_every_candidate_is_within_reach():
    # Con nivel C2 todos los contextos son alcanzables: la elección debe ser la
    # misma que sin nivel (la novedad y el hash estable deciden).
    assert (
        transfer.context_for("travel", level="C2")["context_id"]
        == transfer.context_for("travel")["context_id"]
    )


# ------------------------------------------------------------ contrato HTTP


def test_api_exposes_cefr_and_difficulty_of_the_served_context(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="A1")

    with TestClient(app) as client:
        res = client.get(
            "/api/vocabulary/drill/transfer-context",
            params={"word": "travel", "user_id": uid},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["cefr"] in CEFR_LEVELS
    assert set(body["difficulty_vector"]) == set(transfer.TRANSFER_DIFFICULTY_KEYS)
    assert body["difficulty"] == transfer.difficulty_from_vector(
        body["difficulty_vector"]
    )
    # El ítem declara A1, así que el contexto servido no excede su nivel.
    assert transfer.cefr_index(body["cefr"]) <= transfer.cefr_index("A1")
