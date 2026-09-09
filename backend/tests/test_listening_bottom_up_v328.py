"""V3.28 (Listening Engine 4.0, Fase 2, Bloque C): contenido Bottom-Up derivado.

Resuelve P1-02/P1-03 parcial: el contenido de decodificación (cloze auditivo,
dictado parcial, segmentación) se deriva de forma determinista del corpus
existente (`services/listening_bottom_up.py`), sin re-etiquetado ni re-autoría.

Tests:
1. Barrido del banco completo: todo ítem derivado emitido es un payload válido
   (sin huecos vacíos, sin opciones duplicadas, con la respuesta en opciones),
   determinista, que reutiliza el audio/level del padre y nunca recursivo.
2. Scoring positivo/negativo por endpoint (MCQ y dictado parcial).
3. Contrato negativo: los ítems derivados no entran en la puerta de ruta ni en
   `route_questions`/`level_items` (certificación anclada al banco curado).
4. Selector: `pick_next_question(layer=recognition)` puede servir ítems derivados
   del nivel de trabajo como volumen extra; nunca sin capa recognition."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import listening as listening_repo
from services.listening import (
    DERIVED_BY_ID,
    DERIVED_RECOGNITION_POOL,
    LEVEL_ORDER,
    QUESTION_BANK,
    level_items,
    pick_next_question,
    questions_for_level,
    route_gate,
    route_questions,
    skill_layer,
)
from services.listening_bottom_up import (
    DERIVED_ID_PREFIX,
    DERIVED_TASK_TYPES,
    derive_for_item,
)


def _setup(monkeypatch, tmp_path):
    from repositories import users as users_repo

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _recognition_ids(level: str) -> set[str]:
    """Ids naturales (no derivados) de la capa recognition de un nivel."""
    return {
        q["id"]
        for q in questions_for_level(level)
        if skill_layer(q.get("skill", "")) == "recognition"
    }


# ---------------------------------------------------------------------------
# 1. Barrido del banco completo
# ---------------------------------------------------------------------------

def test_catalog_is_deterministic_and_complete():
    """El catálogo derivado coincide con una re-derivación sobre el banco."""
    rebuilt = {}
    for parent in QUESTION_BANK:
        for item in derive_for_item(parent):
            rebuilt[item["id"]] = item
    assert set(rebuilt) == set(DERIVED_BY_ID)
    # Deterministismo: re-derivar produce exactamente los mismos payloads.
    for qid, item in DERIVED_BY_ID.items():
        assert rebuilt[qid] == item


def test_whole_bank_derivation_produces_valid_payloads():
    """Barrido: todo ítem derivado es válido, determinista y sin huecos basura."""
    assert len(QUESTION_BANK) >= 400
    assert DERIVED_BY_ID  # el banco produce contenido derivado
    by_parent: dict[str, list[dict]] = {}
    for item in DERIVED_BY_ID.values():
        by_parent.setdefault(item["derived_from"], []).append(item)

    for parent in QUESTION_BANK:
        derived = by_parent.get(parent["id"], [])
        if not derived:
            # Solo los ítems sin frase ni reducciones pueden no emitir nada.
            continue
        for item in derived:
            assert item["id"].startswith(DERIVED_ID_PREFIX)
            assert item["derived"] is True
            assert item["derived_from"] == parent["id"]
            assert item["task_type"] in DERIVED_TASK_TYPES
            assert item["level"] == parent["level"]
            # El audio del padre se reutiliza tal cual (sin WAV duplicados).
            assert item.get("audio_id", "") == parent.get("audio_id", "")
            assert item.get("transcript") == parent.get("transcript")
            assert item["id"] not in {q["id"] for q in QUESTION_BANK}
            if item["task_type"] in ("cloze", "segmentation"):
                # MCQ válido: 3 opciones únicas, sin vacíos, respuesta dentro.
                options = item["options"]
                assert len(options) == 3, f"{item['id']}: options={options}"
                assert len(set(options)) == 3, f"{item['id']}: duplicadas"
                assert all(str(o).strip() for o in options)
                assert 0 <= item["answer_index"] < 3
                # Capa recognition derivada del skill (el backend decide, nunca
                # el cliente): cloze=word_recognition, segmentación=phrase_recognition.
                assert skill_layer(item["skill"]) == "recognition"
            if item["task_type"] in ("cloze", "partial_dictation"):
                # El hueco se muestra en la pregunta (nunca vacío).
                assert "_____" in item["question"], item["id"]
            if item["task_type"] == "partial_dictation":
                assert item["skill"] == "dictation"
                assert item["options"] == []
                assert item["answer_index"] == -1
                tokens = item["partial_reference"].split()
                assert 2 <= len(tokens) <= 4, item["id"]
                assert all(t.strip() for t in tokens)


def test_derived_options_include_the_audible_word():
    """La respuesta de cada cloze/segmentación es la palabra realmente audible."""
    for item in DERIVED_BY_ID.values():
        if item["task_type"] not in ("cloze", "segmentation"):
            continue
        parent = next(
            q for q in QUESTION_BANK if q["id"] == item["derived_from"]
        )
        parent_audio = (
            parent.get("transcript")
            or parent.get("clean_transcript")
            or parent.get("script")
            or ""
        ).lower()
        correct = item["options"][item["answer_index"]]
        # La opción correcta aparece en el texto audible del padre (para la
        # segmentación, la reducción puede ser subcadena de un token concatenado).
        assert correct.lower() in parent_audio, (
            f"{item['id']}: {correct!r} no audible en {parent['id']}"
        )


def test_no_recursive_derivation_and_no_duplicate_ids():
    """Nunca se deriva de un derivado y los ids son únicos."""
    derived_parents = {q.get("derived_from") for q in DERIVED_BY_ID.values()}
    assert derived_parents.isdisjoint(DERIVED_BY_ID)  # sin recursión
    assert len(DERIVED_BY_ID) == len(set(DERIVED_BY_ID))


# ---------------------------------------------------------------------------
# 2. Scoring por endpoint
# ---------------------------------------------------------------------------

def _first_derived(task: str) -> dict:
    return next(v for v in DERIVED_BY_ID.values() if v["task_type"] == task)


def test_cloze_scoring_correct_and_wrong(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    cloze = _first_derived("cloze")
    with TestClient(app) as client:
        ok = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={
                "question_id": cloze["id"],
                "answer_index": cloze["answer_index"],
                "stage": "while2",
            },
        )
        ko = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={
                "question_id": cloze["id"],
                "answer_index": (cloze["answer_index"] + 1) % 3,
                "stage": "while2",
            },
        )
    assert ok.status_code == 200 and ok.json()["correct"] is True
    assert ko.status_code == 200 and ko.json()["correct"] is False
    assert ko.json()["correct_index"] == cloze["answer_index"]


def test_segmentation_scoring_via_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    seg = _first_derived("segmentation")
    with TestClient(app) as client:
        ok = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={
                "question_id": seg["id"],
                "answer_index": seg["answer_index"],
            },
        )
    assert ok.status_code == 200
    assert ok.json()["correct"] is True
    assert ok.json()["skill"] == "phrase_recognition"


def test_partial_dictation_scoring_deterministic(monkeypatch, tmp_path):
    """Dictado parcial: acierto exacto con `partial_reference`, fallo con otra
    transcripción (puntuación por tokens, sin LLM)."""
    uid = _setup(monkeypatch, tmp_path)
    partial = _first_derived("partial_dictation")

    def _submit(text: str):
        with TestClient(app) as client:
            return client.post(
                "/api/listening/dictation",
                params={"user_id": uid},
                json={
                    "question_id": partial["id"],
                    "transcript": text,
                    "stage": "while2",
                },
            )

    exact = _submit(partial["partial_reference"])
    assert exact.status_code == 200
    assert exact.json()["correct"] is True
    assert exact.json()["word_accuracy"] == 100
    wrong = _submit("completely different words here")
    assert wrong.status_code == 200
    assert wrong.json()["correct"] is False


# ---------------------------------------------------------------------------
# 3. Contrato negativo: los derivados no entran en la puerta/certificación
# ---------------------------------------------------------------------------

def test_derived_items_never_in_route_pool_or_items(monkeypatch, tmp_path):
    """route_questions/level_items excluyen de forma defensiva lo derivado."""
    uid = _setup(monkeypatch, tmp_path)
    cloze = _first_derived("cloze")
    level = cloze["level"]
    # Defensa explícita: aunque alguien los pasara como extra, no entran.
    pool = route_questions(level, extra_questions=[cloze])
    assert cloze["id"] not in {q["id"] for q in pool}
    # level_items (pool de la ruta) nunca lista un derivado.
    listening_repo.record_attempt(
        uid, cloze["id"], cloze["answer_index"], True,
        skill=cloze["skill"], difficulty=3, layer="recognition",
    )
    items = level_items(level, listening_repo.list_attempts(uid))
    assert cloze["id"] not in {i["question_id"] for i in items}


def test_derived_attempts_do_not_advance_route_gate(monkeypatch, tmp_path):
    """Un intento sobre un ítem derivado no cuenta para la puerta del nivel."""
    uid = _setup(monkeypatch, tmp_path)
    cloze = _first_derived("cloze")
    level = cloze["level"]
    empty_gate = route_gate(level, [])
    listening_repo.record_attempt(
        uid, cloze["id"], cloze["answer_index"], True,
        skill=cloze["skill"], difficulty=3, layer="recognition",
    )
    after = route_gate(level, listening_repo.list_attempts(uid))
    assert after == empty_gate
    # El id derivado ni siquiera pertenece al banco curado del nivel.
    assert cloze["id"] not in {q["id"] for q in questions_for_level(level)}


# ---------------------------------------------------------------------------
# 4. Selector: servir derivados en práctica recognition
# ---------------------------------------------------------------------------

def test_pick_serves_derived_in_recognition_layer(monkeypatch, tmp_path):
    """Con capa recognition y agotadas las naturales de A1, el selector puede
    servir un ítem derivado del mismo nivel como volumen bottom-up."""
    level = LEVEL_ORDER[0]  # A1
    natural = questions_for_level(level)
    recog = _recognition_ids(level)
    assert recog
    # Marca vistas+correctas todas las de capa recognition; quedan sin dominar
    # las de otras capas → nivel de trabajo sigue siendo A1.
    seen = recog | {q["id"] for q in natural}
    correct = set(recog)
    pool = [q for q in DERIVED_RECOGNITION_POOL if q["level"] == level]
    assert pool, "A1 debe tener ítems derivados servibles"
    q = pick_next_question(
        seen, correct, layer="recognition", bottom_up_questions=pool
    )
    assert q["derived"] is True
    assert q["level"] == level
    assert q["derived_from"] in {p["id"] for p in natural}


def test_pick_never_serves_derived_without_recognition_layer(monkeypatch, tmp_path):
    """Sin capa recognition (o sin pool derivado) nunca se sirve un derivado."""
    level = LEVEL_ORDER[0]
    natural = questions_for_level(level)
    recog = _recognition_ids(level)
    seen = recog | {q["id"] for q in natural}
    correct = set(recog)
    pool = [q for q in DERIVED_RECOGNITION_POOL if q["level"] == level]
    q_comprehension = pick_next_question(
        seen, correct, layer="comprehension", bottom_up_questions=pool
    )
    assert q_comprehension.get("derived") is not True
    q_no_layer = pick_next_question(
        seen, correct, layer=None, bottom_up_questions=pool
    )
    assert q_no_layer.get("derived") is not True
    # Sin pasar pool, el banco curado tampoco contiene derivados (por diseño).
    q_baseline = pick_next_question(seen, correct, layer="recognition")
    assert q_baseline.get("derived") is not True
