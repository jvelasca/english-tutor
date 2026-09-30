"""V3.93.1: integridad transaccional e idempotencia del EVENTO pedagógico.

La reauditoría de V3.93 encontró tres fugas en el flujo completo del intento
(`attempt` → `review_queue` → `evidence` → `FSRS`) que esta release cierra:

- **P0-A · evidencia↔FSRS atómico.** El claim de la evidencia y el CAS de la carta
  eran dos transacciones; un CAS que agotaba los reintentos dejaba una fila de
  evidencia sin FSRS, y `evidence_key` impedía recuperarla. Ahora
  `claim_evidence_and_write_card` escribe ambas o ninguna, y revierte si el CAS
  no escribe (la clave se libera → el MISMO intento puede completarse después).
- **P0-B · intento idempotente.** `record_answer_event` deduplica por `attempt_id`
  (UUID del cliente) en UNA transacción: repetir el mismo intento no inserta otra
  fila ni re-cuenta la cola; un intento distinto sí.
- **P0-C · cola sin lost update.** El read-compute-write de `fail_count` queda
  serializado por el `BEGIN IMMEDIATE` (dos fallos concurrentes suman 2).
- **P1-D · CAS de fila completa.** `fsrs_cards.version` protege `reps`/`stability`
  frente a un repaso FSRS concurrente que no mueva `difficulty`.
- **P1-E · resolución de ocurrencia por discriminación.** El resolver elige la
  aparición MÁS DISCRIMINATIVA, no la de mayor solapamiento total.
"""
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs, sense_context
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
    units = [u for u in bridge.phrase_units(listening_svc.audio_text(q)) if len(u) >= 4]
    assert units, "frase demasiado corta para la sonda"
    return units[0]


def _seed_word_with_empty_card(user_id: str, word: str) -> None:
    vocabulary_repo.seed_study_items(
        user_id, [{"word": word, "lemma": word, "kind": "word"}], source="user"
    )
    academy_repo.upsert_fsrs_card(
        user_id,
        fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
    )


def _fail(client, uid: str, q: dict, attempt: int = 1, attempt_id: str = ""):
    payload = {
        "question_id": q["id"],
        "answer_index": _wrong_index(q),
        "attempt_number": attempt,
    }
    if attempt_id:
        payload["attempt_id"] = attempt_id
    return client.post("/api/listening/answer", params={"user_id": uid}, json=payload)


def _attempt_count(user_id: str, question_id: str) -> int:
    with closing(db._conn()) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM listening_attempts "
            "WHERE user_id = ? AND question_id = ?",
            (user_id, question_id),
        ).fetchone()
    return int(row["n"])


def _difficulty(user_id: str, word: str) -> float:
    card = academy_repo.get_fsrs_card(user_id, "lexicon", word)
    return float(card["difficulty"])


def _run_in_threads(work, n: int) -> list:
    results: list = []
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            results.append(work(i))
        except BaseException as exc:  # noqa: BLE001 - se re-lanza tras el join
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors, errors
    return results


# --- P0-A: evidencia ↔ FSRS atómico (rollback + recuperación) ---------------


def test_evidence_claim_rolls_back_when_fsrs_write_fails(monkeypatch, tmp_path):
    """Si el CAS no escribe, NO queda fila de evidencia y el mismo intento se recupera.

    Con la V3.93, el claim insertaba la fila y el fallo del CAS la dejaba huérfana:
    la evidencia contaba pero la carta no subía, y `evidence_key` bloqueaba el
    reintento. Aquí se fuerza el fallo del CAS, se comprueba que no queda NADA a
    medias, y que al restaurarlo el MISMO `attempt_id` completa lo que faltaba.
    """
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    _seed_word_with_empty_card(uid, word)
    real = academy_repo.write_fsrs_card_cas
    monkeypatch.setattr(academy_repo, "write_fsrs_card_cas", lambda *a, **k: False)
    with TestClient(app) as client:
        _fail(client, uid, q, attempt_id="A1")
    # Unidad 1 (intento + cola) sí quedó; la evidencia y el FSRS, no.
    assert _attempt_count(uid, q["id"]) == 1
    assert listening_repo.list_difficulty_evidence(uid) == []
    assert _difficulty(uid, word) == pytest.approx(5.0, abs=0.001)
    # Restaurado el CAS, el mismo intento completa la parte que faltaba.
    monkeypatch.setattr(academy_repo, "write_fsrs_card_cas", real)
    with TestClient(app) as client:
        _fail(client, uid, q, attempt_id="A1")
    assert _attempt_count(uid, q["id"]) == 1  # no se duplica el intento
    assert len(listening_repo.list_difficulty_evidence(uid)) == 1
    assert _difficulty(uid, word) == pytest.approx(5.6, abs=0.001)


# --- P0-B: idempotencia del intento COMPLETO por `attempt_id` ----------------


def test_double_submit_same_attempt_id_is_fully_idempotent(monkeypatch, tmp_path):
    """Repetir el MISMO `attempt_id` = 1 intento, 1 fallo, 1 evidencia, 5.6."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    _seed_word_with_empty_card(uid, word)
    with TestClient(app) as client:
        _fail(client, uid, q, attempt_id="A1")
        _fail(client, uid, q, attempt_id="A1")
    assert _attempt_count(uid, q["id"]) == 1
    assert listening_repo.get_queue_entry(uid, q["id"])["fail_count"] == 1
    assert len(listening_repo.list_difficulty_evidence(uid)) == 1
    assert _difficulty(uid, word) == pytest.approx(5.6, abs=0.001)


def test_two_real_attempts_distinct_attempt_ids(monkeypatch, tmp_path):
    """Dos INTENTOS (ids distintos) = 2 intentos, 2 fallos, 2 evidencias, 6.2."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    _seed_word_with_empty_card(uid, word)
    with TestClient(app) as client:
        _fail(client, uid, q, attempt=1, attempt_id="A1")
        _fail(client, uid, q, attempt=2, attempt_id="A2")
    assert _attempt_count(uid, q["id"]) == 2
    assert listening_repo.get_queue_entry(uid, q["id"])["fail_count"] == 2
    assert len(listening_repo.list_difficulty_evidence(uid)) == 2
    assert _difficulty(uid, word) == pytest.approx(6.2, abs=0.001)


def test_legacy_empty_attempt_id_keeps_v392_behaviour(monkeypatch, tmp_path):
    """Sin `attempt_id` (cliente antiguo) no hay dedup: cada envío es un intento."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    with TestClient(app) as client:
        _fail(client, uid, q)
        _fail(client, uid, q)
    assert _attempt_count(uid, q["id"]) == 2
    assert listening_repo.get_queue_entry(uid, q["id"])["fail_count"] == 2


# --- P0-C: la cola no pierde incrementos concurrentes -----------------------


def test_review_queue_concurrent_increments_do_not_lose_updates(monkeypatch, tmp_path):
    """Dos intentos distintos en paralelo → `fail_count == 2` (sin lost update)."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()

    def work(i: int) -> dict | None:
        return listening_repo.record_answer_event(
            uid,
            q["id"],
            _wrong_index(q),
            False,
            skill=q.get("skill", ""),
            attempt_id=f"thread-{i}",
            level=q.get("level", ""),
        )

    _run_in_threads(work, 2)
    assert _attempt_count(uid, q["id"]) == 2
    assert listening_repo.get_queue_entry(uid, q["id"])["fail_count"] == 2


def test_real_concurrency_two_answers(monkeypatch, tmp_path):
    """Dos peticiones HTTP simultáneas con ids distintos → 2 filas y 6.2."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_question()
    word = _phrase_word(q)
    _seed_word_with_empty_card(uid, word)

    def work(i: int) -> None:
        with TestClient(app) as client:
            _fail(client, uid, q, attempt_id=f"conc-{i}")

    _run_in_threads(work, 2)
    assert _attempt_count(uid, q["id"]) == 2
    assert listening_repo.get_queue_entry(uid, q["id"])["fail_count"] == 2
    assert len(listening_repo.list_difficulty_evidence(uid)) == 2
    assert _difficulty(uid, word) == pytest.approx(6.2, abs=0.001)


# --- P1-D: CAS de FILA COMPLETA por `version` -------------------------------


def test_full_row_cas_protects_reps_and_stability(monkeypatch, tmp_path):
    """Un repaso FSRS que cambia `reps`/`stability` (no `difficulty`) bloquea el CAS.

    Con el CAS de V3.93 (solo `difficulty`) esta escritura habría pasado y habría
    pisado `reps`/`stability` con los valores obsoletos de la carta leída antes del
    repaso. Con la versión de fila, no.
    """
    uid = _setup(monkeypatch, tmp_path)
    base = fsrs.empty_card(target_type="lexicon", target_id="bank", label="bank")
    academy_repo.upsert_fsrs_card(uid, base)
    stale = academy_repo.get_fsrs_card(uid, "lexicon", "bank")
    assert stale["version"] == 0
    # Repaso FSRS legítimo: cambia reps/stability, deja difficulty en 5.0.
    academy_repo.upsert_fsrs_card(uid, {**stale, "reps": 3, "stability": 12.0})
    now = datetime.now(timezone.utc).isoformat()
    updated = fsrs.apply_difficulty_evidence(
        stale, source="listening-evidence", now=now
    )
    assert updated["difficulty"] == pytest.approx(5.6, abs=0.001)
    assert (
        academy_repo.upsert_fsrs_card_cas(
            uid, updated, expected_version=stale["version"]
        )
        is False
    )
    card = academy_repo.get_fsrs_card(uid, "lexicon", "bank")
    assert card["difficulty"] == pytest.approx(5.0, abs=0.001)  # no se pisó
    assert card["reps"] == 3
    assert card["stability"] == pytest.approx(12.0, abs=0.001)
    assert card["version"] == 1  # cada escritura incrementa la versión


# --- Migración y filas legacy ----------------------------------------------


def test_migration_keeps_legacy_rows_and_partial_index_dedups(
    monkeypatch, tmp_path
):
    """Las filas legacy (`attempt_id`/`evidence_key` en '') conviven; el índice
    único PARCIAL dedup por `attempt_id` solo en las claves no vacías."""
    uid = _setup(monkeypatch, tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    with closing(db._conn()) as conn, conn:
        for _ in range(2):
            conn.execute(
                "INSERT INTO listening_difficulty_evidence "
                "(user_id, question_id, word, fail_count, difficulty_before, "
                "difficulty_after, due_at, created_at, evidence_key, sense_key, "
                "sense_match, sense_reason, attempt_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (uid, "q-legacy", "bank", 1, 5.0, 5.6, now, now, "", "", "", "", ""),
            )
            conn.execute(
                "INSERT INTO listening_attempts "
                "(user_id, question_id, answer_index, correct, created_at, "
                "attempt_id) VALUES (?, ?, ?, ?, ?, ?)",
                (uid, "q-legacy", 0, 0, now, ""),
            )
    db.init_db()  # idempotente: ni destruye ni duplica
    with closing(db._conn()) as conn:
        evidence = conn.execute(
            "SELECT COUNT(*) AS n FROM listening_difficulty_evidence "
            "WHERE user_id = ? AND evidence_key = ''",
            (uid,),
        ).fetchone()["n"]
        attempts = conn.execute(
            "SELECT COUNT(*) AS n FROM listening_attempts "
            "WHERE user_id = ? AND attempt_id = ''",
            (uid,),
        ).fetchone()["n"]
    assert evidence == 2
    assert attempts == 2  # dos '' no colisionan (índice PARCIAL)
    # El índice único parcial SÍ dedup por `attempt_id` no vacío.
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "INSERT INTO listening_attempts "
            "(user_id, question_id, answer_index, correct, created_at, attempt_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "q-new", 0, 0, now, "race"),
        )
    with pytest.raises(sqlite3.IntegrityError):
        with closing(db._conn()) as conn, conn:
            conn.execute(
                "INSERT INTO listening_attempts "
                "(user_id, question_id, answer_index, correct, created_at, "
                "attempt_id) VALUES (?, ?, ?, ?, ?, ?)",
                (uid, "q-other", 0, 0, now, "race"),
            )


# --- P1-E: el resolver elige la ocurrencia por discriminación ---------------


def test_sense_resolver_selects_occurrence_by_discrimination():
    """Con una aparición ambigua y otra inequívoca, gana la inequívoca.

    `river bank water money loan and later the river bank` tiene dos usos de
    `bank`: el primero está rodeado por la acepción declarada Y la alternativa
    (margen 0 → ambiguo); el segundo solo por la declarada (margen 1 → matched).
    El peso viejo (`declared + other`) elegía el primero por sumar 4 y devolvía
    `ambiguous`; el nuevo (margen) elige el segundo y devuelve `matched`.
    """
    declared = {"lemma": "bank", "pos": "noun", "gloss": "river water"}
    alternative = {"lemma": "bank", "pos": "noun", "gloss": "money loan"}
    text = "river bank water money loan and later the river bank"
    verdict = sense_context.classify_sense_evidence(
        "bank", text, declared, senses=[declared, alternative]
    )
    assert verdict["match"] == sense_context.SENSE_MATCHED
    assert verdict["reason"] == sense_context.REASON_GLOSS_DECLARED
    assert verdict["declared_overlap"] == 1
    assert verdict["best_other_overlap"] == 0
