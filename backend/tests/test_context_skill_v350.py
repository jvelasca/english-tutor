"""V3.50 — Context→Skill mapping + difficulty matching (transferencia).

Hasta V3.49 el banco de transferencia ya declaraba `cefr`, `difficulty_vector` y
una capa de variedad, pero la ELECCIÓN del contexto seguía ignorando esos datos:
`context_for` solo miraba «usados», «nivel alcanzable» y «novedad». Dos ítems del
mismo nivel recibían el mismo contexto aunque uno estuviera limitado en una
modalidad concreta (no produce por escrito, no recupera de memoria…).

V3.50 hace que esos datos decidan:

- cada contexto declara las competencias que ejercita (`skills`, vocabulario
  `CONTEXT_SKILLS`, espejo verificado de `services.evidence.LEXICAL_SKILLS`);
- `context_for` acepta la modalidad LIMITANTE (`skill`, la deriva el llamador con
  `planner.limiting_skill`) y la prefiere, y ajusta a la banda de dificultad
  alcanzable (`TRANSFER_DIFFICULTY_BAND`) para no servir el contexto más plano
  del banco a un alumno avanzado;
- el contexto servido lo expone de forma ADITIVA (`skills`).

Los dos filtros son PREFERENCIAS con degradación con gracia: sin coincidencias
se ignora el filtro, y sin `level`/`skill` reconocibles el resultado es idéntico
al de V3.49 (cero regresión). No se toca la escalera `transfer_state`, sus
umbrales, el scoring ni FSRS.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import evidence as evidence_svc
from services import transfer


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _seed_word(a: str, word: str, *, cefr: str = "B1") -> None:
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


def _get_context(client: TestClient, uid: str, word: str) -> dict:
    res = client.get(
        "/api/vocabulary/drill/transfer-context",
        params={"word": word, "user_id": uid},
    )
    assert res.status_code == 200, res.text
    return res.json()


# ------------------------------------------------------------- vocabulario


def test_context_skills_mirror_the_evidence_vocabulary():
    # Paridad por construcción: el espejo local no puede divergir del contrato.
    assert transfer.CONTEXT_SKILLS == evidence_svc.LEXICAL_SKILLS


def test_every_context_declares_non_empty_normalized_skills():
    for context in transfer.TRANSFER_CONTEXTS:
        declared = context.get("skills")
        assert declared, context["id"]
        skills = transfer.context_skills(context)
        assert skills, context["id"]
        assert set(skills) <= set(transfer.CONTEXT_SKILLS), context["id"]
        # Sin duplicados y en orden canónico.
        assert len(skills) == len(set(skills)), context["id"]
        assert list(skills) == [
            skill for skill in transfer.CONTEXT_SKILLS if skill in set(skills)
        ], context["id"]


def test_every_skill_in_the_vocabulary_is_exercised_by_some_context():
    exercised: set[str] = set()
    for context in transfer.TRANSFER_CONTEXTS:
        exercised.update(transfer.context_skills(context))
    assert exercised == set(transfer.CONTEXT_SKILLS)


def test_context_skills_accepts_ids_and_never_raises():
    first = transfer.TRANSFER_CONTEXTS[0]
    assert transfer.context_skills(first) == transfer.context_skills(
        "transfer:" + first["id"]
    )
    assert transfer.context_skills(first["id"]) == transfer.context_skills(
        "transfer:" + first["id"]
    )
    # Normaliza mayúsculas, deduplica e ignora valores fuera del vocabulario.
    assert transfer.context_skills(
        {"id": "x", "skills": ("SPOKEN_PRODUCTION", "spoken_production", "nope")}
    ) == ("spoken_production",)
    # Robustez: sin `skills` o con formas no iterables devuelve ().
    assert transfer.context_skills("no-existe") == ()
    assert transfer.context_skills(None) == ()
    assert transfer.context_skills({"id": "x", "skills": "spoken_production"}) == ()
    assert transfer.context_skills({"id": "x", "skills": 42}) == ()


def test_skills_are_the_only_addition_to_the_frozen_contexts():
    # V3.48 congela los seis contextos originales (mismos valores core); V3.50
    # solo AÑADE `skills`, así que la distancia contextual core no cambia y la
    # consigna del banco tampoco.
    assert transfer.context_distance("transfer:story", "transfer:work") == 5
    story = transfer.TRANSFER_CONTEXTS[0]
    assert story["id"] == "story"
    assert story["cefr"] == "A2"
    assert story["prompt"] == (
        "Tell a short story about something that happened to you recently."
    )
    assert transfer.context_skills("story") == (
        "written_production",
        "spoken_production",
        "spontaneous_use",
    )


# -------------------------------------------------------- selección (pura)


def test_without_level_or_skill_the_choice_is_unchanged():
    base = transfer.context_for("travel")["context_id"]
    assert transfer.context_for("travel", level="", skill="")["context_id"] == base
    assert transfer.context_for("travel", level=None, skill=None)["context_id"] == base


def test_unknown_level_or_skill_does_not_change_the_choice():
    base = transfer.context_for("travel")["context_id"]
    assert transfer.context_for("travel", level="Pre-A1")["context_id"] == base
    assert transfer.context_for("travel", skill="no-existe")["context_id"] == base
    assert (
        transfer.context_for(
            "travel", level="Pre-A1", skill="no-existe"
        )["context_id"]
        == base
    )


def test_skill_is_preferred_when_a_reachable_context_declares_it():
    for skill in transfer.CONTEXT_SKILLS:
        got = transfer.context_for("travel", level="C2", skill=skill)
        assert got["available"] is True
        # En C2 todo el banco está al alcance, así que la preferencia se cumple.
        assert skill in got["skills"], (skill, got["context_id"])
        assert transfer.cefr_index(got["cefr"]) <= transfer.cefr_index("C2")


def test_skill_filter_degrades_gracefully_when_no_context_declares_it():
    # Ningún contexto A1 declara `recall`: el filtro se ignora y se sirve A1.
    got = transfer.context_for("travel", level="A1", skill="recall")
    assert got["cefr"] == "A1"
    assert "recall" not in got["skills"]
    # Y sigue siendo el comportamiento sin skill (no se inventa un pool vacío).
    assert got["context_id"] == transfer.context_for("travel", level="A1")["context_id"]


def test_difficulty_band_avoids_the_flattest_context_for_b1():
    # Con V3.49 un ítem B1 podía recibir el contexto A1 más plano; con V3.50 la
    # banda (objetivo = posición del nivel − 1) lo excluye.
    got = transfer.context_for("travel", level="B1")
    assert got["cefr"] != "A1"
    assert got["difficulty"] >= 2
    a1 = {c["id"] for c in transfer.TRANSFER_CONTEXTS if c["cefr"] == "A1"}
    assert got["context_id"] not in {transfer.context_id_for(_id) for _id in a1}


def test_difficulty_band_reaches_the_hardest_tier_at_c2():
    hardest = max(
        transfer.difficulty_from_vector(c["difficulty_vector"])
        for c in transfer.TRANSFER_CONTEXTS
    )
    got = transfer.context_for("travel", level="C2")
    assert got["difficulty"] == hardest
    assert got["cefr"] in {"C1", "C2"}


def test_selection_is_deterministic_with_skill_and_level():
    first = transfer.context_for("travel", level="B2", skill="recall")
    assert first == transfer.context_for("travel", level="B2", skill="recall")
    assert "recall" in first["skills"]
    # El contexto servido declara exactamente las skills normalizadas del banco.
    assert first["skills"] == list(transfer.context_skills(first["context_id"]))


def test_skill_preference_beats_the_raw_hash_when_both_agree_on_level():
    # Dos palabras del MISMO nivel: con la misma modalidad limitante el contexto
    # servido declara esa modalidad (es una preferencia fuerte, no un desempate).
    for word in ("travel", "bank", "light"):
        got = transfer.context_for(word, level="C2", skill="written_production")
        assert "written_production" in got["skills"], (word, got["context_id"])


# ------------------------------------------------------------ contrato HTTP


def test_api_exposes_the_skills_of_the_served_context(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B1")

    with TestClient(app) as client:
        body = _get_context(client, uid, "travel")

    assert body["skills"]
    assert set(body["skills"]) <= set(transfer.CONTEXT_SKILLS)
    assert body["skills"] == list(transfer.context_skills(body["context_id"]))
    # Aditivo: los campos de V3.47 siguen presentes.
    assert body["cefr"] in {"A1", "A2", "B1", "B2", "C1", "C2"}
    assert body["difficulty"] == transfer.difficulty_from_vector(
        body["difficulty_vector"]
    )


def test_get_and_post_derive_the_same_context_with_skill_matching(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B2")
    # Evidencia por modalidad: la producción escrita falla (limitante) y el
    # recall acierta. El servidor debe derivar `written_production` y orientar el
    # contexto a esa modalidad, tanto en el GET como al registrar sin contexto.
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="travel",
        surface_form="travel",
        lexical_unit="travel",
        skill="written_production",
        task="write",
        activity="drill",
        activity_id="drill:write",
        context_id="",
        success=False,
        support_level="independent",
        error_type="missing_target",
    )
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="travel",
        surface_form="travel",
        lexical_unit="travel",
        skill="recall",
        task="recall",
        activity="drill",
        activity_id="drill:recall",
        context_id="",
        success=True,
        support_level="independent",
        error_type="correct",
    )

    with TestClient(app) as client:
        served = _get_context(client, uid, "travel")
        res = client.post(
            "/api/vocabulary/drill/transfer-attempt",
            params={"user_id": uid},
            json={
                "word": "travel",
                "text": "I travel to work by train every single day.",
            },
        )
    assert res.status_code == 200, res.text
    body = res.json()

    # Paridad GET↔POST: el servidor deriva el MISMO contexto en ambos caminos.
    assert body["context_id"] == served["context_id"]
    # Y la modalidad limitante orienta la elección cuando hay contexto que la
    # declara (B2 tiene contextos escritos dentro de la banda).
    assert "written_production" in served["skills"]
    rows = evidence_repo.list_evidence(uid, "travel")
    assert rows[0]["context_id"] == served["context_id"]
    assert rows[0]["skill"] == "spontaneous_use"
