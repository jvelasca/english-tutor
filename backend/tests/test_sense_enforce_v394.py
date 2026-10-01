"""SENSE-CONTEXT-01 (V3.94, ENFORCE): la evidencia de Listening DECIDE con la acepción.

V3.94 cierra el dark launch de V3.93: el Sense Resolver no solo registra su veredicto,
**decide**. La política es MÍNIMA y declarada (ver `allows_difficulty_evidence`): la
evidencia se suprime SOLO ante un `mismatch` PROBADO —el contexto usa una acepción
DISTINTA a la aprendida— y el suceso se registra como `new_sense_exposure`; todo lo
demás conserva la evidencia de V3.92.

Qué se fija aquí:

1. `listening_bridge.alternatives_index` reúne las acepciones de la caché (pura);
2. con alternativas, un `mismatch` es ALCANZABLE y, en producción, NO sube la carta:
   el intento queda registrado como exposición y la respuesta lo publica;
3. un `matched` conserva la evidencia y NO expone;
4. repetir el MISMO intento no vuelve a exponer (idempotencia por `attempt_id`);
5. `daily_plan.day_metrics` NO cuenta una exposición como dificultad.
"""
import json
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import listening as listening_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import daily_plan, fsrs
from services import listening as listening_svc
from services import listening_bridge as bridge
from services.listening import QUESTION_BANK


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _receptive_question() -> dict:
    for q in QUESTION_BANK:
        if q["skill"] not in ("dictation", "shadowing") and listening_svc.audio_text(q):
            return q
    raise AssertionError("banco sin ítems receptivos con texto")


def _wrong_index(q: dict) -> int:
    return (q["answer_index"] + 1) % len(q["options"])


def _phrase_word(q: dict) -> str:
    units = [
        u for u in bridge.phrase_units(listening_svc.audio_text(q)) if len(u) >= 4
    ]
    assert units, "frase demasiado corta para la sonda"
    return units[0]


def _fail(client, uid: str, q: dict, attempt: int = 1, attempt_id: str = ""):
    payload = {
        "question_id": q["id"],
        "answer_index": _wrong_index(q),
        "attempt_number": attempt,
    }
    if attempt_id:
        payload["attempt_id"] = attempt_id
    return client.post("/api/listening/answer", params={"user_id": uid}, json=payload)


def _seed_word(user_id: str, word: str, sense: dict) -> None:
    """Da de alta la palabra con su ACEPCIÓN declarada y una carta FSRS nueva."""
    vocabulary_repo.seed_study_items(
        user_id, [{"word": word, "lemma": word, "kind": "word"}], source="user"
    )
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "UPDATE vocabulary SET sense_json = ? WHERE user_id = ? AND word = ?",
            (json.dumps(sense), user_id, word),
        )
    academy_repo.upsert_fsrs_card(
        user_id, fsrs.empty_card(target_type="lexicon", target_id=word, label=word)
    )


def _seed_alternatives(word: str, senses: list[dict]) -> None:
    """Puebla la caché del diccionario con las acepciones conocidas de `word`."""
    dictionary_repo.save_entry(
        word, pos="noun", senses=senses, generator_version="1.7.0"
    )


def _difficulty(uid: str, word: str) -> float:
    return float(academy_repo.get_fsrs_card(uid, "lexicon", word)["difficulty"])


# --- El índice de alternativas del diccionario -------------------------------


def test_alternatives_index_gathers_known_senses():
    entries = [
        {"word": "Bank", "senses": [
            {"pos": "noun", "gloss": "money"},
            {"pos": "noun", "gloss": "river side"},
        ]},
        {"word": "anchor", "senses": []},
        {"word": "river", "senses": [{"pos": "noun", "gloss": "water"}]},
    ]
    index = bridge.alternatives_index(entries)
    assert set(index) == {"bank", "river"}
    assert len(index["bank"]) == 2


def test_alternatives_index_is_total_with_junk():
    assert bridge.alternatives_index(None) == {}
    assert bridge.alternatives_index(["bank", 7]) == {}
    assert bridge.alternatives_index([{"word": "", "senses": [{"pos": "noun"}]}]) == {}
    assert bridge.alternatives_index([{"word": "x", "senses": "nope"}]) == {}


# --- ENFORCE: el `mismatch` suprime la evidencia y expone --------------------


def test_mismatch_suppresses_the_card_and_exposes_a_new_sense(monkeypatch, tmp_path):
    """La frase usa OTRA acepción: la carta NO se toca y la respuesta expone.

    Antes de V3.94 esto subía la dificultad de la acepción aprendida (el defecto que
    SENSE-CONTEXT-01 midió). Ahora se registra como exposición y la carta queda
    intacta.
    """
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    text = listening_svc.audio_text(q)
    # La acepción declarada NO aparece en la frase (glosa ajena)...
    _seed_word(uid, word, {"lemma": word, "pos": "noun", "gloss": "zzz unrelated"})
    # ...y la caché conoce una alternativa que SÍ (su glosa es la propia frase).
    _seed_alternatives(word, [{"pos": "noun", "gloss": text}])
    with TestClient(app) as client:
        body = _fail(client, uid, q).json()
    assert body["difficulty_evidence"]["count"] == 0
    assert body["new_sense_exposure"]["words"] == [word]
    assert body["new_sense_exposure"]["count"] == 1
    assert _difficulty(uid, word) == pytest.approx(5.0, abs=0.001)  # NO se tocó
    rows = listening_repo.list_difficulty_evidence(uid)
    assert len(rows) == 1
    assert rows[0]["sense_match"] == "mismatch"
    # La fila NO aplicó dificultad: es el registro de la exposición, no un castigo.
    assert rows[0]["difficulty_before"] == rows[0]["difficulty_after"]


def test_matched_sense_keeps_evidence_and_does_not_expose(monkeypatch, tmp_path):
    """La frase usa la acepción aprendida: evidencia normal, sin exposición."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    text = listening_svc.audio_text(q)
    _seed_word(uid, word, {"lemma": word, "pos": "noun", "gloss": text})
    _seed_alternatives(word, [{"pos": "noun", "gloss": "zzz unrelated"}])
    with TestClient(app) as client:
        body = _fail(client, uid, q).json()
    assert body["difficulty_evidence"]["count"] == 1
    assert body["new_sense_exposure"]["count"] == 0
    assert _difficulty(uid, word) == pytest.approx(5.6, abs=0.001)


def test_repeating_the_same_attempt_does_not_double_expose(monkeypatch, tmp_path):
    """El mismo `attempt_id` no vuelve a exponer (idempotencia del ledger)."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    text = listening_svc.audio_text(q)
    _seed_word(uid, word, {"lemma": word, "pos": "noun", "gloss": "zzz unrelated"})
    _seed_alternatives(word, [{"pos": "noun", "gloss": text}])
    with TestClient(app) as client:
        first = _fail(client, uid, q, attempt_id="A1").json()
        second = _fail(client, uid, q, attempt_id="A1").json()
    assert first["new_sense_exposure"]["words"] == [word]
    assert second["new_sense_exposure"]["count"] == 0
    assert len(listening_repo.list_difficulty_evidence(uid)) == 1


# --- La métrica del día no cuenta una exposición como dificultad -------------


def test_day_metrics_separates_exposures_from_difficulty():
    day = "2026-09-29"
    bridge_rows = [
        {"word": "bank", "sense_match": "matched", "created_at": f"{day}T09:00:00"},
        {"word": "river", "sense_match": "", "created_at": f"{day}T09:05:00"},
        {"word": "bank", "sense_match": "mismatch", "created_at": f"{day}T09:10:00"},
    ]
    metrics = daily_plan.day_metrics([], [], [], day, bridge_rows)
    assert metrics["difficulty_evidence"] == 2
    assert metrics["words_flagged"] == 2
    assert metrics["sense_exposures"] == 1
    # V3.94.2: el split de una carta fuerte (dificultad intacta) no es dificultad
    # ni exposición. El de una carta débil sí subió y cuenta como dificultad.
    bridge_rows.append(
        {
            "word": "bank",
            "sense_match": "ambiguous",
            "sense_reason": "occurrence:split",
            "difficulty_before": 4.0,
            "difficulty_after": 4.0,
            "created_at": f"{day}T09:20:00",
        }
    )
    bridge_rows.append(
        {
            "word": "charge",
            "sense_match": "ambiguous",
            "sense_reason": "occurrence:split",
            "difficulty_before": 5.0,
            "difficulty_after": 5.6,
            "created_at": f"{day}T09:30:00",
        }
    )
    metrics = daily_plan.day_metrics([], [], [], day, bridge_rows)
    assert metrics["difficulty_evidence"] == 3
    assert metrics["words_flagged"] == 3
    assert metrics["sense_exposures"] == 1


# --- V3.94.1: el sentido se resuelve SIEMPRE, también en cartas fuertes ------


def _make_card_strong(user_id: str, word: str, difficulty: float = 4.0) -> None:
    """Convierte la carta de `word` en una carta DOMINADA (review, dificultad baja)."""
    card = academy_repo.get_fsrs_card(user_id, "lexicon", word)
    assert card is not None
    card["state"] = "review"
    card["difficulty"] = difficulty
    academy_repo.upsert_fsrs_card(user_id, card)


def test_strong_card_exposes_a_new_sense_without_touching_fsrs(monkeypatch, tmp_path):
    """P1 de V3.94.1: una palabra FUERTE con otra acepción ya no es invisible.

    Antes, `select_targets()` descartaba la carta fuerte ANTES de resolver el
    sentido, así que `palabra fuerte + sentido nuevo` daba FSRS intacto Y
    `new_sense_exposure = 0`. Ahora se resuelve siempre: la carta sigue intacta
    (no se castiga un dominio demostrado) pero la exposición SÍ se registra.
    """
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    text = listening_svc.audio_text(q)
    _seed_word(uid, word, {"lemma": word, "pos": "noun", "gloss": "zzz unrelated"})
    _seed_alternatives(word, [{"pos": "noun", "gloss": text}])
    _make_card_strong(uid, word, difficulty=4.0)
    with TestClient(app) as client:
        body = _fail(client, uid, q, attempt_id="strong-1").json()
    assert body["new_sense_exposure"]["words"] == [word]
    assert body["new_sense_exposure"]["count"] == 1
    assert body["difficulty_evidence"]["count"] == 0
    assert _difficulty(uid, word) == pytest.approx(4.0, abs=0.001)  # NO se tocó
    rows = listening_repo.list_difficulty_evidence(uid)
    assert len(rows) == 1
    assert rows[0]["sense_match"] == "mismatch"
    assert rows[0]["difficulty_before"] == rows[0]["difficulty_after"] == 4.0


def test_strong_card_with_the_learned_sense_is_not_touched(monkeypatch, tmp_path):
    """Una carta fuerte en su PROPIA acepción conserva su dominio (sin evidencia).

    Complemento del anterior: resolver SIEMPRE el sentido no puede convertirse en
    castigar una carta fuerte solo porque su palabra aparece en una frase fallada.
    """
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    text = listening_svc.audio_text(q)
    _seed_word(uid, word, {"lemma": word, "pos": "noun", "gloss": text})
    _seed_alternatives(word, [{"pos": "noun", "gloss": "zzz unrelated"}])
    _make_card_strong(uid, word, difficulty=4.0)
    with TestClient(app) as client:
        body = _fail(client, uid, q, attempt_id="strong-2").json()
    assert body["difficulty_evidence"]["count"] == 0
    assert body["new_sense_exposure"]["count"] == 0
    assert _difficulty(uid, word) == pytest.approx(4.0, abs=0.001)
    assert listening_repo.list_difficulty_evidence(uid) == []


def test_pedagogical_cycle_from_learning_to_a_second_sense(monkeypatch, tmp_path):
    """Secuencia completa de SENSE-CONTEXT-01 (V3.94.1).

    1. El alumno falla la frase en su ACEPCIÓN APRENDIDA → la carta sube y NO hay
       exposición (`matched`).
    2. La frase usa OTRA acepción → `mismatch` probado: la carta NO sube y se
       registra la exposición.
    3. Repetir el MISMO intento no vuelve a exponer (idempotencia).
    4. El alumno declara/APRENDE esa segunda acepción → la siguiente evidencia
       vuelve a ser de dificultad y deja de ser «sentido nuevo».
    """
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    text = listening_svc.audio_text(q)
    # La frase entera es la glosa que la representa (garantiza solape fuerte).
    matched_sense = {"lemma": word, "pos": "noun", "gloss": text}
    other_sense = {"lemma": word, "pos": "noun", "gloss": "zzz unrelated"}
    _seed_word(uid, word, matched_sense)  # 1) acepción aprendida = la de la frase
    _seed_alternatives(word, [{"pos": "noun", "gloss": "zzz unrelated"}])
    with TestClient(app) as client:
        first = _fail(client, uid, q, attempt_id="cyc-1").json()
        d1 = _difficulty(uid, word)
        # 2) La frase pasa a usarse en OTRA acepción (giro declarado del léxico).
        with closing(db._conn()) as conn, conn:
            conn.execute(
                "UPDATE vocabulary SET sense_json = ? WHERE user_id = ? AND word = ?",
                (json.dumps(other_sense), uid, word),
            )
        # La caché ahora conoce la acepción que la frase SÍ expresa.
        _seed_alternatives(word, [{"pos": "noun", "gloss": text}])
        second = _fail(client, uid, q, attempt_id="cyc-2").json()
        d2 = _difficulty(uid, word)
        # 3) Idempotencia: el mismo intento no reexpone.
        repeated = _fail(client, uid, q, attempt_id="cyc-2").json()
        # 4) El alumno aprende la segunda acepción → vuelve a ser dificultad.
        with closing(db._conn()) as conn, conn:
            conn.execute(
                "UPDATE vocabulary SET sense_json = ? WHERE user_id = ? AND word = ?",
                (json.dumps(matched_sense), uid, word),
            )
        fourth = _fail(client, uid, q, attempt_id="cyc-3").json()
        d4 = _difficulty(uid, word)

    # 1) Matched: evidencia normal, sin exposición.
    assert first["difficulty_evidence"]["count"] == 1
    assert first["new_sense_exposure"]["count"] == 0
    assert d1 == pytest.approx(5.6, abs=0.001)
    # 2) Mismatch PROBADO: la carta no sube y se expone.
    assert second["difficulty_evidence"]["count"] == 0
    assert second["new_sense_exposure"]["words"] == [word]
    assert d2 == pytest.approx(5.6, abs=0.001)
    # 3) Idempotente.
    assert repeated["new_sense_exposure"]["count"] == 0
    # 4) Declarada la segunda acepción: vuelve a ser dificultad, sin exposición.
    assert fourth["difficulty_evidence"]["count"] == 1
    assert fourth["new_sense_exposure"]["count"] == 0
    assert d4 == pytest.approx(6.2, abs=0.001)
    matches = [r["sense_match"] for r in listening_repo.list_difficulty_evidence(uid)]
    assert matches == ["matched", "mismatch", "matched"]


# --- V3.94.2: ocurrencias en conflicto ---------------------------------------


def _split_question() -> dict:
    return {
        "id": "q-split",
        "transcript": (
            "On the river side, the bank was covered in mud, "
            "but I put my money in the bank."
        ),
    }


def test_strong_card_records_a_split_without_fsrs_or_exposure(monkeypatch, tmp_path):
    """Carta fuerte + dos sentidos: fila medible, sin castigo y sin exposición."""
    import asyncio

    from domain.listening import _apply_difficulty_evidence

    uid = _setup(monkeypatch, tmp_path)
    word = "bank"
    _seed_word(
        uid,
        word,
        {"lemma": word, "pos": "noun", "gloss": "a place where money is kept"},
    )
    _seed_alternatives(
        word,
        [
            {"pos": "noun", "gloss": "a place where money is kept"},
            {"pos": "noun", "gloss": "the side of a river"},
        ],
    )
    _make_card_strong(uid, word, difficulty=4.0)
    question = _split_question()

    async def _once(attempt_id: str) -> dict:
        return await _apply_difficulty_evidence(
            uid, question["id"], question, attempt_id=attempt_id
        )

    body = asyncio.run(_once("split-strong"))
    again = asyncio.run(_once("split-strong"))
    assert body["new_sense_exposure"]["count"] == 0
    assert body["count"] == 0
    assert again["new_sense_exposure"]["count"] == 0
    assert _difficulty(uid, word) == pytest.approx(4.0, abs=0.001)
    rows = listening_repo.list_difficulty_evidence(uid)
    assert len(rows) == 1
    assert rows[0]["sense_match"] == "ambiguous"
    assert rows[0]["sense_reason"] == "occurrence:split"
    assert rows[0]["difficulty_before"] == rows[0]["difficulty_after"] == 4.0


def test_weak_card_split_still_raises_difficulty(monkeypatch, tmp_path):
    """La duda no resta: una carta débil en conflicto sigue subiendo."""
    import asyncio

    from domain.listening import _apply_difficulty_evidence

    uid = _setup(monkeypatch, tmp_path)
    word = "bank"
    _seed_word(
        uid,
        word,
        {"lemma": word, "pos": "noun", "gloss": "a place where money is kept"},
    )
    _seed_alternatives(
        word,
        [
            {"pos": "noun", "gloss": "a place where money is kept"},
            {"pos": "noun", "gloss": "the side of a river"},
        ],
    )
    question = _split_question()
    body = asyncio.run(
        _apply_difficulty_evidence(
            uid, question["id"], question, attempt_id="split-weak"
        )
    )
    assert body["new_sense_exposure"]["count"] == 0
    assert body["count"] == 1
    assert body["words"] == [word]
    assert _difficulty(uid, word) == pytest.approx(5.6, abs=0.001)
    rows = listening_repo.list_difficulty_evidence(uid)
    assert len(rows) == 1
    assert rows[0]["sense_reason"] == "occurrence:split"
    assert rows[0]["difficulty_before"] != rows[0]["difficulty_after"]


