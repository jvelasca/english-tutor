"""V3.69 — E2E + Adaptive Engine Validation (batería E01–E19).

Release de **VALIDACIÓN**, no de capacidad: no añade motor, no migra, no toca el
banco ni `DECISION_POLICY_VERSION`. Lo que comprueba es que la cadena completa

    Evidence → Student State → Decision Projection → Task selection → Decision
    → Serving → Attempt → Outcome → Evidence

se sostiene **de punta a punta por HTTP** con escenarios controlados, y que el
provenance (FSM, idempotencia, propiedad) es honesto bajo abuso.

Cada escenario tiene su nombre literal (`test_e01_…` … `test_e19_…`) para que el
mapeo con la tabla de la auditoría sea 1:1. Los escenarios de integridad
(E09–E15) se apoyan en `GET /api/learning/decisions` (`transition_health`,
contadores y calibración) leído **después** de la acción; los contadores del
proceso son monotónicos, así que se afirma sobre **deltas**, nunca sobre valores
absolutos.

**Hallazgos que esta batería ya ha destapado** (declarados en la docstring de cada
escenario y en `release-notes-v3.69.0.md`):

- **E01(a) · el arranque en frío NO tiene provenance.** Con un alumno sin ninguna
  celda medible, `decision_projection.has_comparable_capacity` es `False`, así que
  la cola sirve la tarea de la cascada **sin** bloque `decision` y sin
  `decision_id`: el circuito no es observable hasta que hay estado. No es un bug
  (es la degradación declarada de V3.64), pero es un límite del contrato que la
  auditoría `Y` daba por cubierto.
- **E08 · `abandoned_count` no cuenta el abandono del ciclo de vida.** El informe
  de calibración solo carga filas `completed`, y su `abandoned_count` cuenta filas
  `completed` con `outcome = "abandoned"` (hoy inalcanzables por el camino
  público). El abandono del lifecycle (`decision_status = "abandoned"`) queda
  **fuera del denominador** (correcto) pero **invisible** en el informe (bucket a
  0). Asimetría de observabilidad, no de cálculo.
- **E15 · una servida caducada se REABRE, no queda `abandoned`.** El barrido la
  cierra como `abandoned` y la siguiente construcción de cola la reabre
  (`provenance_status = "reopened"`) porque la misma decisión se vuelve a servir.
  El test afirma la regla que de verdad importa: **nunca** acaba contando como
  `completed`.
- **E17 · el hueco de andamiaje es una SUMA al valor, no un descuento a la
  tarea.** `SCAFFOLDING_PENALTY` engorda el `gap` de la modalidad limitante
  (`decision_projection.skill_components`), de modo que el alumno con hueco
  recibe un valor esperado **MAYOR**, no menor. La aserción es diferencial, en la
  dirección real medida.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import decision_records as decision_records_repo
from repositories import dictionary as dictionary_repo
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs, observed_difficulty, planner

_MEASURED_SOURCES = (
    "task_empirical",
    "target_empirical",
    "skill_empirical",
    "margin",
)

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _setup(monkeypatch, tmp_path) -> str:
    """BD aislada + alumno A (mismo `_setup` canónico de la suite)."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _client() -> TestClient:
    return TestClient(app)


def _days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _seed_word(uid: str, word: str, *, cefr: str = "B1") -> None:
    vocabulary_repo.seed_curriculum_items(
        uid,
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
    vocabulary_repo.record_exposures(uid, [word])


def _dictionary_word(word: str, translation: str) -> None:
    """Caché global del diccionario: da CONTENIDO real al peldaño de recall."""
    dictionary_repo.save_entry(
        word,
        pos="noun",
        definition=f"definition of {word}",
        translation=translation,
        generator_version="test",
    )


def _matrix(uid: str, word: str, *, channel: str = "writing") -> None:
    """Matriz de competencia del ítem: habilita las candidatas de producción."""
    vocabulary_repo.record_production(uid, [word], channel=channel)
    vocabulary_repo.record_recalls(uid, [word])


def _due_lexicon_card(
    uid: str, word: str, *, stability: float = 5.0, days_ago: int = 3
) -> None:
    """Carta FSRS `lexicon` vencida (due ayer): es lo que puebla la cola."""
    card = {
        **fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
        "state": "review",
        "reps": 2,
        "stability": stability,
        "due_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "last_review_at": _days_ago(days_ago),
        "last_grade": fsrs.GRADE_GOOD,
    }
    assert academy_repo.upsert_fsrs_card(uid, card) is not None


def _evidence(
    uid: str,
    word: str,
    *,
    skill: str,
    days: list[int],
    success: bool,
    served: str = "lexical:3",
    credited: str = "",
    error: str = "",
    support: str = "independent",
) -> None:
    """Evidencia espaciada (un día distinto por fila) para el mismo ítem."""
    for days_ago in days:
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id=word,
            surface_form=word,
            lexical_unit=word,
            skill=skill,
            assessed_skill=skill,
            task="drill",
            activity="drill",
            success=success,
            support_level=support,
            error_type=error,
            served_difficulty=served,
            observed_task_difficulty=credited or served,
            occurred_at=_days_ago(days_ago),
        )


def _learner_with_state(
    uid: str,
    word: str,
    *,
    cefr: str = "B1",
    served: str = "lexical:3",
    credited: str = "",
    errors: bool = True,
) -> None:
    """Receta canónica: estado MEDIBLE que desbloquea la Decision Projection.

    La puerta declarada de V3.64 (`has_comparable_capacity`) exige una celda
    medida (2 muestras en 2 días): sin ella no hay bloque `decision` ni
    `decision_id`. La receta combina la matriz de competencia del ítem, la carta
    FSRS vencida y evidencia espaciada de recall con aciertos (capacidad) y
    errores `wrong_word` (candidata `error_prone`), que es lo que hace competir al
    argmax con margen comparable.
    """
    _seed_word(uid, word, cefr=cefr)
    _matrix(uid, word)
    _dictionary_word(word, f"translation of {word}")
    _due_lexicon_card(uid, word)
    _evidence(
        uid,
        word,
        skill="recall",
        days=[6, 4],
        success=True,
        served=served,
        credited=credited,
    )
    if errors:
        _evidence(
            uid,
            word,
            skill="recall",
            days=[3, 2],
            success=False,
            error="wrong_word",
            served=served,
            credited=credited,
        )


def _queue(client: TestClient, uid: str) -> dict:
    res = client.get("/api/learning/review", params={"user_id": uid})
    assert res.status_code == 200, res.text
    return res.json()


def _items(client: TestClient, uid: str) -> list[dict]:
    return _queue(client, uid)["items"]


def _item(items: list[dict], word: str) -> dict:
    found = next((item for item in items if item.get("word") == word), None)
    assert found is not None, f"{word} no está en la cola: {[i['word'] for i in items]}"
    return found


def _analytics(client: TestClient, uid: str, **params) -> dict:
    res = client.get("/api/learning/decisions", params={"user_id": uid, **params})
    assert res.status_code == 200, res.text
    return res.json()


def _rows(client: TestClient, uid: str, **params) -> list[dict]:
    return _analytics(client, uid, **params)["decisions"]


def _row(client: TestClient, uid: str, decision_id: str) -> dict:
    found = next(
        (r for r in _rows(client, uid) if r["decision_id"] == decision_id), None
    )
    assert found is not None, f"decisión {decision_id} ausente del ledger"
    return found


def _rejections(client: TestClient, uid: str) -> dict:
    """Contadores de rechazo de la FSM (monotónicos: se usan como delta)."""
    return _analytics(client, uid)["provenance_health"]["transition_health"][
        "rejections"
    ]


def _reject_delta(before: dict, after: dict, reason: str) -> int:
    return int(after.get(reason, 0)) - int(before.get(reason, 0))


def _calibration(client: TestClient, uid: str) -> dict:
    return _analytics(client, uid)["calibration"]


def _alternative(item: dict, skill: str) -> dict | None:
    """Candidata puntuada de esa modalidad (comparación manzana-con-manzana)."""
    decision = item.get("decision") or {}
    for alternative in decision.get("alternatives") or []:
        if alternative.get("skill") == skill:
            return alternative
    return None


def _serve(client: TestClient, uid: str, word: str, decision_id: str) -> dict:
    """GET del peldaño de recall: declara la decisión SERVIDA (round-trip)."""
    res = client.get(
        "/api/vocabulary/drill/recall",
        params={"user_id": uid, "word": word, "decision_id": decision_id},
    )
    assert res.status_code in (200, 422), res.text
    return res.json()


def _backdate_served(decision_id: str, *, hours: int) -> None:
    """Retrasa `served_at` (E15: la ventana de abandono son 24 h)."""
    stale = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "UPDATE decision_records SET served_at = ? WHERE decision_id = ?",
            (stale, decision_id),
        )


def _skill_sources(uid: str, word: str) -> list[dict]:
    """Filas canónicas del estado (la MISMA lectura que alimenta la proyección)."""
    from services import skill_state as skill_state_service

    return skill_state_service.skill_state_sources(
        lexicon=evidence_repo.list_evidence(uid, word, target_type="lexicon")
    )


# ---------------------------------------------------------------------------
# E01–E06 · El circuito pedagógico (estado → decisión → intento → evidencia)
# ---------------------------------------------------------------------------


def test_e01_new_learner_closes_the_loop(monkeypatch, tmp_path):
    """El circuito completo, con su límite de arranque en frío DECLARADO.

    (a) Alumno sin NINGUNA celda medida: la cola sirve la tarea (la cascada
        funciona) pero **sin** bloque `decision` y **sin** `decision_id` — el
        provenance no existe todavía. Es la degradación declarada de V3.64
        (`has_comparable_capacity`), no un fallo; se afirma para que quede escrito.
    (b) Con el estado mínimo medible: `decision` + `decision_id` → GET del peldaño
        (`served`) → POST del intento (`completed`, `outcome=ok`) → evidencia
        escrita → la reconstrucción de la cola NO reabre la medición.
    """
    uid = _setup(monkeypatch, tmp_path)

    # (a) Arranque en frío: hay tarea, pero no hay provenance.
    _seed_word(uid, "quokka", cefr="A1")
    _dictionary_word("quokka", "marsupial australiano")
    _due_lexicon_card(uid, "quokka")
    assert evidence_repo.list_evidence(uid, "quokka", target_type="lexicon") == []
    with _client() as client:
        cold = _item(_items(client, uid), "quokka")
        cold_rows = _rows(client, uid)

    assert cold["task"]["activity"] in planner.ACTIVITY_FOR_SKILL.values()
    assert not cold.get("decision")
    assert cold.get("decision_id", "") == ""
    assert cold_rows == []

    # (b) Con estado medible, el circuito entero se cierra por HTTP.
    _learner_with_state(uid, "river")
    with _client() as client:
        item = _item(_items(client, uid), "river")
        decision_id = item["decision_id"]
        assert decision_id

        _serve(client, uid, "river", decision_id)
        served = _row(client, uid, decision_id)
        assert served["decision_status"] == "served"
        assert served["executed_activity"] == "recall"

        attempt = client.post(
            "/api/vocabulary/drill/recall-attempt",
            params={"user_id": uid},
            json={"word": "river", "answer": "river", "decision_id": decision_id},
        )
        assert attempt.status_code == 200, attempt.text
        assert attempt.json()["correct"] is True

        completed = _row(client, uid, decision_id)
        assert completed["decision_status"] == "completed"
        assert completed["outcome"] == "ok"
        assert completed["outcome_measured"] is True
        assert completed["provenance_status"] == (
            decision_records_repo.PROVENANCE_RECORDED
        )

        evidence = evidence_repo.list_evidence(uid, "river", target_type="lexicon")
        assert evidence[-1]["success"] == 1

        # La siguiente construcción de cola no reescribe la medición ya hecha.
        _queue(client, uid)
        after = _row(client, uid, decision_id)

    assert after["decision_status"] == "completed"
    assert after["outcome"] == "ok"


def test_e02_weak_skill_raises_its_priority(monkeypatch, tmp_path):
    """La modalidad DÉBIL sube en el vector de prioridades (dirección, no valor)."""
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")
    _evidence(uid, "river", skill="written_production", days=[6, 4], success=True)
    _evidence(uid, "river", skill="spoken_production", days=[3, 2], success=False)

    with _client() as client:
        item = _item(_items(client, uid), "river")

    priorities = item["skill_priorities"]
    assert priorities["spoken_production"] > priorities["written_production"]
    assert item["limiting_skill"] == "spoken_production"
    assert item["limiting_skill"] == max(priorities, key=priorities.get)


def test_e03_retention_chooses_review(monkeypatch, tmp_path):
    """Ítem dominado y vencido: la cola lo cuenta como vencido y sirve repaso."""
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")

    with _client() as client:
        body = _queue(client, uid)
        item = _item(body["items"], "river")

    assert body["due_count"] >= 1
    assert item["activity"] in planner.ACTIVITY_FOR_SKILL.values()
    assert item["decision_id"]


def test_e04_transfer_gap_raises_production(monkeypatch, tmp_path):
    """Recuerdo fuerte + producción débil → el argmax elige PRODUCCIÓN.

    La candidata de producción solo compite si la modalidad tiene celda medida; la
    capacidad es del ALUMNO (por eso se mide en otro ítem) mientras que el hueco es
    del ÍTEM (`skill_gaps` mira la evidencia de este `word`). Con el recall ya sin
    errores, el argmax sirve la tarea oral (`sentence`) en vez de repetir recall.
    """
    uid = _setup(monkeypatch, tmp_path)
    # Sin errores de recall: la candidata `error_prone` desaparece.
    _learner_with_state(uid, "river", errors=False)
    _seed_word(uid, "ocean", cefr="B1")
    _dictionary_word("ocean", "translation of ocean")
    _evidence(uid, "ocean", skill="spoken_production", days=[6, 4], success=True)

    with _client() as client:
        item = _item(_items(client, uid), "river")
        decision = item["decision"]

    assert item["task"]["reason"] == "skill_gap"
    assert item["activity"] in {"sentence", "write", "transfer"}
    assert decision["source"] == "argmax"
    # La candidata de producción compite CON margen (deja de ser ciega).
    spoken = _alternative(item, "spoken_production")
    assert spoken is not None
    assert spoken["comparable"] is True
    assert item["task"]["activity"] == "sentence"


def test_e05_same_task_two_contexts_are_two_instances(monkeypatch, tmp_path):
    """Misma DEFINICIÓN de tarea servida con contexto → INSTANCIA distinta.

    Por HTTP: la cola declara la definición (`task_key` + instancia vacía) y el
    GET de transferencia completa la instancia con el contexto SERVIDO sin tocar
    la definición. El respaldo puro fija que dos contextos de la misma definición
    son dos instancias.
    """
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")

    with _client() as client:
        item = _item(_items(client, uid), "river")
        decision_id = item["decision_id"]
        res = client.get(
            "/api/vocabulary/drill/transfer-context",
            params={"word": "river", "user_id": uid, "decision_id": decision_id},
        )
        assert res.status_code == 200, res.text
        context = res.json()
        row = _row(client, uid, decision_id)

    assert context["context_id"]
    # La DEFINICIÓN no cambia al servir un contexto…
    assert row["task_key"] == item["task_key"]
    # …pero la INSTANCIA sí: es definición + contexto, y declara el contexto.
    assert row["instance_known"] is True
    assert row["context_id"] == context["context_id"]
    assert row["task_instance_key"] != item["task_instance_key"]
    assert row["task_instance_key"] == (
        f"{row['task_key']}|{context['context_instance'] or context['context_id']}"
    )

    # Respaldo puro: dos contextos de la MISMA definición son dos instancias.
    base = dict(
        target_id="river",
        activity="transfer",
        support_level="spontaneous",
        served_difficulty={"lexical": 3},
        assessed_skill="spontaneous_use",
    )
    key = observed_difficulty.task_key_parts(**base)
    story = observed_difficulty.task_instance_key_parts(
        **base, context="transfer:story"
    )
    future = observed_difficulty.task_instance_key_parts(
        **base, context="transfer:future"
    )
    assert story != future
    assert story.startswith(key) and future.startswith(key)


def test_e06_failure_changes_p_success(monkeypatch, tmp_path):
    """`ok, ok, ko, ko` → `ko, ko` extra: el `p_success` del candidato BAJA.

    Se compara la MISMA alternativa (misma modalidad) antes y después del fallo,
    que es lo que hace honesta la comparación: comparar el ganador del argmax
    leería un cambio legítimo de tarea como un cambio de probabilidad.
    """
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")

    with _client() as client:
        before_item = _item(_items(client, uid), "river")
        before = _alternative(before_item, "recall")
        assert before is not None

        _evidence(
            uid, "river", skill="recall", days=[1], success=False, error="wrong_word"
        )
        after_item = _item(_items(client, uid), "river")
        after = _alternative(after_item, "recall")

    assert after is not None
    assert after["p_success"] < before["p_success"]
    assert after["p_success_source"] in _MEASURED_SOURCES
    assert before["p_success_source"] in _MEASURED_SOURCES
    # El cambio de predicción es EXPLICABLE, no un número suelto.
    assert "expected success" in after_item["why"]


# ---------------------------------------------------------------------------
# E07–E15 · Integridad del provenance (FSM, idempotencia, propiedad)
# ---------------------------------------------------------------------------


def test_e07_unclear_does_not_punish_mastery(monkeypatch, tmp_path):
    """`unclear` (el ASR no reconoció) NO es fallo de dominio: fuera del cómputo."""
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")

    with _client() as client:
        item = _item(_items(client, uid), "river")
        decision_id = item["decision_id"]
        _serve(client, uid, "river", decision_id)
        before_rows = len(evidence_repo.list_evidence(uid, "river"))

        assert decision_records_repo.mark_completed(
            uid, decision_id, "unclear", target_id="river", activity="recall"
        )
        row = _row(client, uid, decision_id)
        calibration = _calibration(client, uid)

    assert row["decision_status"] == "completed"
    assert row["outcome"] == "unclear"
    assert row["outcome_measured"] is False
    assert calibration["unclear_count"] == 1
    assert calibration["measured_count"] == 0
    assert calibration["bands"] == []
    # Dominio intacto: el ledger del que se deriva el estado no creció.
    assert len(evidence_repo.list_evidence(uid, "river")) == before_rows


def test_e08_abandon_does_not_contaminate_ko(monkeypatch, tmp_path):
    """Abandonar NO es fallar: sale del cómputo, sin `ko` fantasma.

    **Hallazgo (contrato real medido):** el abandono del ciclo de vida deja la fila
    en `decision_status = "abandoned"`, y esa fila **no entra** en el informe de
    calibración (que solo carga las `completed`). El contador `abandoned_count`
    cuenta otra cosa: filas `completed` con `outcome = "abandoned"`, hoy
    inalcanzables por el camino público. Consecuencia: el abandono queda fuera del
    denominador (correcto) pero **invisible** en el informe (el bucket queda a 0).
    El test fija el comportamiento real y registra la asimetría para el auditor.
    """
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")

    with _client() as client:
        item = _item(_items(client, uid), "river")
        decision_id = item["decision_id"]
        _serve(client, uid, "river", decision_id)
        for event in ("started", "abandoned"):
            res = client.post(
                "/api/vocabulary/drill/decision-lifecycle",
                params={"user_id": uid},
                json={
                    "decision_id": decision_id,
                    "event": event,
                    "target_id": "river",
                    "activity": "recall",
                },
            )
            assert res.status_code == 200, res.text
            assert res.json()["applied"] is True, event
        row = _row(client, uid, decision_id)
        calibration = _calibration(client, uid)

    assert row["decision_status"] == "abandoned"
    assert row["outcome"] == ""
    assert row["outcome_measured"] is False
    # Fuera del denominador: ni completa, ni medida, ni banda.
    assert calibration["completed_count"] == 0
    assert calibration["measured_count"] == 0
    assert calibration["unclear_count"] == 0
    assert calibration["bands"] == []
    # Y el bucket `abandoned_count` NO refleja el abandono del ciclo de vida.
    assert calibration["abandoned_count"] == 0


def test_e09_repeated_refresh_does_not_duplicate(monkeypatch, tmp_path):
    """Refrescar la cola ×3 no duplica el provenance: mismo `decision_id`."""
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")

    with _client() as client:
        ids = [_item(_items(client, uid), "river")["decision_id"] for _ in range(3)]
        rows = _rows(client, uid, target_id="river")

    assert len(set(ids)) == 1
    assert len(rows) == 1


def test_e10_double_submit_is_idempotent(monkeypatch, tmp_path):
    """El MISMO `completed(ok)` dos veces no duplica la medición.

    Nota de contrato: repetir el mismo outcome es la rama **idempotente**
    declarada de la FSM (la fila se reescribe con los mismos valores); el contador
    `duplicate_outcome` es para el outcome CONTRADICTORIO (E11). Lo que se exige
    aquí es que la medición no se duplique.
    """
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")

    with _client() as client:
        item = _item(_items(client, uid), "river")
        decision_id = item["decision_id"]
        _serve(client, uid, "river", decision_id)
        for _ in range(2):
            res = client.post(
                "/api/vocabulary/drill/recall-attempt",
                params={"user_id": uid},
                json={
                    "word": "river",
                    "answer": "river",
                    "decision_id": decision_id,
                },
            )
            assert res.status_code == 200, res.text
        row = _row(client, uid, decision_id)
        calibration = _calibration(client, uid)

    assert row["decision_status"] == "completed"
    assert row["outcome"] == "ok"
    assert calibration["measured_count"] == 1
    assert len(calibration["bands"]) == 1
    assert calibration["bands"][0]["count"] == 1


def test_e11_contradictory_submit_is_rejected(monkeypatch, tmp_path):
    """`completed(ok)` y después `completed(ko)`: la medición manda y no se pisa."""
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")

    with _client() as client:
        item = _item(_items(client, uid), "river")
        decision_id = item["decision_id"]
        _serve(client, uid, "river", decision_id)
        assert decision_records_repo.mark_completed(
            uid, decision_id, "ok", target_id="river", activity="recall"
        )
        before = _rejections(client, uid)
        rejected = decision_records_repo.mark_completed(
            uid, decision_id, "ko", target_id="river", activity="recall"
        )
        after = _rejections(client, uid)
        row = _row(client, uid, decision_id)
        calibration = _calibration(client, uid)

    assert rejected is False
    assert _reject_delta(before, after, "duplicate_outcome") == 1
    assert row["outcome"] == "ok"
    assert calibration["measured_count"] == 1


def test_e12_wrong_user_changes_nothing(monkeypatch, tmp_path):
    """El `decision_id` de A no lo puede cerrar B (propiedad de la fila)."""
    uid = _setup(monkeypatch, tmp_path)
    other = users_repo.create_user("B")["id"]
    _learner_with_state(uid, "river")

    with _client() as client:
        item = _item(_items(client, uid), "river")
        decision_id = item["decision_id"]
        _serve(client, uid, "river", decision_id)
        before = _rejections(client, uid)
        changed = decision_records_repo.mark_completed(
            other, decision_id, "ko", target_id="river", activity="recall"
        )
        after = _rejections(client, uid)
        row = _row(client, uid, decision_id)

    assert changed is False
    assert _reject_delta(before, after, "wrong_owner") == 1
    assert row["decision_status"] == "served"
    assert row["outcome"] == ""


def test_e13_wrong_target_is_rejected(monkeypatch, tmp_path):
    """El intento de OTRO ítem no puede cerrar esta decisión."""
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")

    with _client() as client:
        item = _item(_items(client, uid), "river")
        decision_id = item["decision_id"]
        _serve(client, uid, "river", decision_id)
        before = _rejections(client, uid)
        changed = decision_records_repo.mark_completed(
            uid, decision_id, "ok", target_id="ocean", activity="recall"
        )
        after = _rejections(client, uid)
        row = _row(client, uid, decision_id)

    assert changed is False
    assert _reject_delta(before, after, "target_mismatch") == 1
    assert row["decision_status"] == "served"


def test_e14_invalid_transition_is_rejected(monkeypatch, tmp_path):
    """`computed → completed` no existe: la FSM lo rechaza y lo contabiliza."""
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")

    with _client() as client:
        item = _item(_items(client, uid), "river")
        decision_id = item["decision_id"]
        assert _row(client, uid, decision_id)["decision_status"] == "computed"
        before = _rejections(client, uid)
        changed = decision_records_repo.mark_completed(
            uid, decision_id, "ok", target_id="river", activity="recall"
        )
        after = _rejections(client, uid)
        row = _row(client, uid, decision_id)

    assert changed is False
    assert _reject_delta(before, after, "invalid_transition") == 1
    assert row["decision_status"] == "computed"


def test_e15_stale_serving_becomes_abandoned(monkeypatch, tmp_path):
    """Una servida de hace >24 h se cierra como `abandoned`, NUNCA como completed.

    (a) El barrido (`close_stale`, `DECISION_ABANDON_AFTER_HOURS = 24`) la cierra
        — se invoca con su `before_iso` explícito, que es la excepción declarada al
        «solo HTTP»: controlar el reloj del barrido sin inyectar un reloj nuevo.
    (b) La siguiente construcción de cola no la RESUCITA como medida: la reabre
        (`provenance_status = "reopened"`) porque la misma decisión vuelve a
        servirse, y sigue sin outcome. Lo que el contrato prohíbe —y aquí se
        afirma— es que una servida caducada acabe contando como `completed`.
    """
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")

    with _client() as client:
        item = _item(_items(client, uid), "river")
        decision_id = item["decision_id"]
        _serve(client, uid, "river", decision_id)
        _backdate_served(decision_id, hours=27)
        # La fila es ANTIGUA pero su huella sigue siendo la de este instante: el
        # barrido la ve caducada por `served_at`.
        swept = decision_records_repo.close_stale(uid, before_iso=_days_ago(1))
        abandoned = _row(client, uid, decision_id)
        assert abandoned["decision_status"] == "abandoned"
        assert abandoned["outcome"] == ""

        _queue(client, uid)
        reopened = _row(client, uid, decision_id)

    assert swept == 1
    assert reopened["decision_status"] != "completed"
    assert reopened["outcome"] == ""
    assert reopened["provenance_status"] == decision_records_repo.PROVENANCE_REOPENED


# ---------------------------------------------------------------------------
# E16 · Determinismo del Planner (puro + proyección HTTP)
# ---------------------------------------------------------------------------


def test_e16_planner_is_deterministic(monkeypatch, tmp_path):
    """Mismas entradas → misma tarea, `p_success`, ELV, `why` y `decision_id`."""
    # Nivel PURO: funciones sin estado ni reloj.
    matrix = {"production": True}
    evidence = {"error_types": {"wrong_word": 2}, "skill_successes": {"recall": 2}}
    signals = planner.planned_signals(evidence, matrix)
    kwargs = {
        "capacity_by_skill": {"recall": {"lexical": 3}},
        "task_difficulty": {"lexical": 3},
    }
    chosen = [
        planner.select_task_by_elv(matrix, evidence, signals, **kwargs)
        for _ in range(5)
    ]
    values = [
        planner.expected_learning_value(
            signals,
            skill="recall",
            task_difficulty={"lexical": 3},
            learner_capacity={"lexical": 3},
        )
        for _ in range(5)
    ]
    assert len({json.dumps(c, sort_keys=True) for c in chosen}) == 1
    assert len({json.dumps(v, sort_keys=True) for v in values}) == 1

    # Nivel HTTP: la MISMA cola repetida 5 veces, byte a byte en lo decisorio.
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")
    with _client() as client:
        snapshots = []
        for _ in range(5):
            item = _item(_items(client, uid), "river")
            row = _row(client, uid, item["decision_id"])
            snapshots.append(
                (
                    item["decision_id"],
                    item["task_key"],
                    json.dumps(item["task"], sort_keys=True),
                    json.dumps(item["why"], sort_keys=True),
                    item["expected_learning_value"],
                    row["decision_start_fingerprint"],
                    row["state_fingerprint"],
                )
            )

    assert len(set(snapshots)) == 1


def test_e16b_decisions_endpoint_reports_calibration_and_health(monkeypatch, tmp_path):
    """Contrato completo del endpoint huérfano `GET /api/learning/decisions`.

    `{decisions, calibration, provenance_health}` con los contadores, las bandas
    predicted vs observed, la salud del registro y los filtros/paginación
    declarados. Es también el test que cierra el tramo `outcome → calibración`
    **por HTTP** (hoy solo se probaba a nivel de repositorio).
    """
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")

    with _client() as client:
        empty = _analytics(client, uid)
        assert set(empty) == {"decisions", "calibration", "provenance_health"}
        assert empty["decisions"] == []
        assert set(empty["calibration"]) >= {
            "completed_count",
            "measured_count",
            "unclear_count",
            "abandoned_count",
            "bands",
            "calibration_error",
        }
        health = empty["provenance_health"]
        assert set(health) >= {"record_failures", "transition_health"}
        assert set(health["transition_health"]) == {
            "ok",
            "reopened",
            "closed_decision",
            "rejections",
        }

        item = _item(_items(client, uid), "river")
        decision_id = item["decision_id"]
        _serve(client, uid, "river", decision_id)
        client.post(
            "/api/vocabulary/drill/recall-attempt",
            params={"user_id": uid},
            json={"word": "river", "answer": "river", "decision_id": decision_id},
        )

        report = _analytics(client, uid)
        row = _row(client, uid, decision_id)
        # Filtros: `target_id` y `status` se aplican de verdad.
        assert len(_rows(client, uid, target_id="river")) == 1
        assert len(_rows(client, uid, target_id="ocean")) == 0
        assert len(_rows(client, uid, status="completed")) == 1
        assert len(_rows(client, uid, status="computed")) == 0
        # Paginación: `offset` recorta, `limit` acota.
        assert _rows(client, uid, offset=1) == []
        assert len(_rows(client, uid, limit=1)) == 1

    assert row["decision_status"] == "completed"
    assert report["calibration"]["measured_count"] == 1
    band = report["calibration"]["bands"][0]
    assert band["count"] == 1
    assert band["observed_success_rate"] == 1.0
    assert {
        "band",
        "count",
        "mean_predicted_p_success",
        "observed_success_rate",
        "error",
    } <= set(band)


# ---------------------------------------------------------------------------
# E17–E19 · Casos de la auditoría `X` (apoyo, TOCTOU, concurrencia)
# ---------------------------------------------------------------------------


def test_e17_scaffolding_gap_penalizes_the_task(monkeypatch, tmp_path):
    """El hueco servido − acreditado MUEVE la decisión (aserción DIFERENCIAL).

    Dos alumnos idénticos salvo por la dependencia de apoyo: A recibe
    `lexical:5` y acredita `lexical:2` (hueco 3), B recibe y acredita `lexical:2`
    (hueco 0). La aserción es diferencial porque el hueco gobierna la decisión pero
    NO se expone en el ítem (`served_load` publica la carga servida, no el bloque
    `load` de la proyección): verificarlo por HTTP obliga a comparar dos gemelos.

    **Dirección REAL medida (hallazgo):** el hueco SUMA al valor de la modalidad
    limitante (`SCAFFOLDING_PENALTY` engorda el `gap` en
    `decision_projection.skill_components`), así que el alumno con hueco recibe un
    ELV MAYOR y un `why` que declara el hueco grande. No es un descuento a la
    tarea; es perjuicio en el diagnóstico, no en la puntuación. Se registra para el
    auditor: ¿es la dirección querida, o el hueco debería penalizar la tarea?
    """
    uid_a = _setup(monkeypatch, tmp_path)
    uid_b = users_repo.create_user("B")["id"]
    _learner_with_state(uid_a, "mountain", served="lexical:5", credited="lexical:2")
    _learner_with_state(uid_b, "mountain", served="lexical:2", credited="lexical:2")

    # Respaldo PURO: el hueco se mide, y solo lo tiene A.
    assert observed_difficulty.scaffolding_gap(_skill_sources(uid_a, "mountain")) == {
        "lexical": 3
    }
    assert observed_difficulty.scaffolding_gap(_skill_sources(uid_b, "mountain")) == {}

    with _client() as client:
        item_a = _item(_items(client, uid_a), "mountain")
        item_b = _item(_items(client, uid_b), "mountain")

    # Diferencial observable: la memoria de apoyo cambia la valoración de la tarea.
    assert item_a["decision"]["source"] == "argmax"
    assert item_b["decision"]["source"] == "argmax"
    assert item_a["expected_learning_value"] > item_b["expected_learning_value"]
    assert item_a["why"] != item_b["why"]


def _fingerprint(uid: str) -> str:
    return evidence_repo.evidence_fingerprint(uid)


def test_e18_evidence_arriving_during_the_decision_is_not_sealed_stale(
    monkeypatch, tmp_path
):
    """Evidencia que entra DURANTE la decisión no puede dejar un sello rancia.

    (a) Por HTTP: evidencia nueva entre dos lecturas CAMBIA la decisión y su sello
        (la huella de snapshot entra en el `decision_id`, así que un sello viejo no
        puede pasar por nuevo).
    (b) Invariante interno (el intercalado exacto de `_SEAL_MAX_ATTEMPTS` no es
        alcanzable por HTTP de forma determinista): la huella de frescura crece con
        la evidencia, así que «huella anterior ≠ huella posterior» es detectable y
        el sello nunca se declara fresco con huella desajustada.
    """
    uid = _setup(monkeypatch, tmp_path)
    _learner_with_state(uid, "river")

    with _client() as client:
        first = _item(_items(client, uid), "river")
        first_row = _row(client, uid, first["decision_id"])
        first_seal = first_row["decision_start_fingerprint"]
        assert first_seal

        # (b) La huella de frescura cambia cuando entra evidencia nueva.
        before = _fingerprint(uid)
        _evidence(uid, "river", skill="spoken_production", days=[3, 1], success=True)
        after = _fingerprint(uid)
        assert after != before

        second = _item(_items(client, uid), "river")
        second_row = _row(client, uid, second["decision_id"])

    # (a) Decisión y sello NUEVOS: el snapshot viejo no se reutiliza.
    assert second["decision_id"] != first["decision_id"]
    assert second_row["decision_start_fingerprint"] != first_seal
    assert second_row["decision_start_fingerprint"] == after
    assert second_row["state_fingerprint"]


def test_e19_two_active_learners_do_not_mix_state(monkeypatch, tmp_path):
    """Dos alumnos activos sobre la MISMA BD no se contaminan en ninguna dirección.

    Se intercalan las cuatro operaciones (`cola(A) → cola(B) → completo(A) →
    completo(B)`) para que cualquier mezcla de estado, cola o `decision_id` se
    manifieste, y se comprueba en AMBAS direcciones (B no ve a A y A sigue viendo
    lo suyo tras la actividad de B). Complementa a E12, que cubre el rechazo de la
    propiedad ajena: aquí la pregunta es la coexistencia.
    """
    uid_a = _setup(monkeypatch, tmp_path)
    uid_b = users_repo.create_user("B")["id"]
    _learner_with_state(uid_a, "river")
    _learner_with_state(uid_b, "mountain")

    with _client() as client:
        item_a = _item(_items(client, uid_a), "river")
        queue_b = _items(client, uid_b)
        item_b = _item(queue_b, "mountain")

        assert [i["word"] for i in queue_b] == ["mountain"]
        assert item_a["decision_id"]
        assert item_b["decision_id"]
        assert item_a["decision_id"] != item_b["decision_id"]

        # Cierre de A: no puede tocar la fila de B.
        _serve(client, uid_a, "river", item_a["decision_id"])
        assert (
            client.post(
                "/api/vocabulary/drill/recall-attempt",
                params={"user_id": uid_a},
                json={
                    "word": "river",
                    "answer": "river",
                    "decision_id": item_a["decision_id"],
                },
            ).status_code
            == 200
        )
        # Cierre de B: no puede tocar la fila de A.
        _serve(client, uid_b, "mountain", item_b["decision_id"])
        assert (
            client.post(
                "/api/vocabulary/drill/recall-attempt",
                params={"user_id": uid_b},
                json={
                    "word": "mountain",
                    "answer": "mountain",
                    "decision_id": item_b["decision_id"],
                },
            ).status_code
            == 200
        )

        rows_a = _rows(client, uid_a)
        rows_b = _rows(client, uid_b)
        calibration_a = _calibration(client, uid_a)
        calibration_b = _calibration(client, uid_b)
        queue_a_after = _items(client, uid_a)
        queue_b_after = _items(client, uid_b)

    # Cada ledger contiene SOLO lo suyo, y cada medición es de su alumno.
    assert [r["target_id"] for r in rows_a] == ["river"]
    assert [r["target_id"] for r in rows_b] == ["mountain"]
    assert rows_a[0]["decision_status"] == "completed"
    assert rows_b[0]["decision_status"] == "completed"
    assert calibration_a["measured_count"] == 1
    assert calibration_b["measured_count"] == 1
    # Y ninguna cola devuelve el ítem del otro (el repaso puede quedar vacío: la
    # carta se reprograma al completar, y eso no es contaminación).
    assert all(i["word"] == "river" for i in queue_a_after)
    assert all(i["word"] == "mountain" for i in queue_b_after)
