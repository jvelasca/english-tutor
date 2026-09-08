"""Tests del servicio de léxico (V2.3 → P1): estado, recall, kinds y cobertura."""
from __future__ import annotations

import pytest

from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import lexicon
from services.curriculum import Level, Objective


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _level() -> Level:
    return Level(
        course_id="english-tutor-academy",
        level_id="a1",
        level="A1",
        title="A1 · Beginner",
        modules=[],
    )


def _objective(**kwargs) -> Objective:
    base = dict(
        id="a1-m01-u01-l01-o01",
        can_do="I can introduce myself.",
        title="Presentarme",
        skills=["speaking"],
        vocabulary=["Name", "Country"],
        concepts=["I am", "My name is"],
    )
    base.update(kwargs)
    return Objective(**base)


# --- items_from_objective ---------------------------------------------------


def test_items_from_objective_combines_vocabulary_and_concepts():
    obj = _objective()
    items = lexicon.items_from_objective(_level(), obj)
    by_word = {i["word"]: i for i in items}
    assert set(by_word) == {"name", "country", "i am", "my name is"}
    assert by_word["name"]["kind"] == "word"
    assert by_word["name"]["cefr"] == "A1"
    assert by_word["name"]["level_id"] == "a1"
    assert by_word["name"]["objective_id"] == obj.id
    # P1 (§3.2): oraciones con sujeto explícito se siembran como functional chunk.
    assert by_word["i am"]["kind"] == "functional_chunk"
    assert by_word["my name is"]["kind"] == "functional_chunk"


def test_items_from_objective_normalizes_and_dedupes():
    obj = _objective(vocabulary=["Name", "name"], concepts=["I am", "i am"])
    items = lexicon.items_from_objective(_level(), obj)
    assert len(items) == 2


def test_classify_kind_lexical_unit_taxonomy():
    """P1 (§3.2): la taxonomía de Lexical Unit va más allá de word/structure."""
    assert set(lexicon.LEXICAL_KINDS) == {
        "word",
        "collocation",
        "phrasal_verb",
        "expression",
        "sentence_frame",
        "functional_chunk",
        "structure",
    }
    # Palabra
    assert lexicon.classify_kind("train") == "word"
    # Verbo + partícula (dos tokens, partícula inequívoca)
    assert lexicon.classify_kind("get up", source="vocabulary") == "phrasal_verb"
    assert lexicon.classify_kind("wake up") == "phrasal_verb"
    # Frase fija declarada como vocabulary → collocation
    assert lexicon.classify_kind("living room", source="vocabulary") == "collocation"
    assert (
        lexicon.classify_kind("strong coffee", source="vocabulary") == "collocation"
    )
    # Huecos explícitos → sentence frame
    assert lexicon.classify_kind("How much is ...?") == "sentence_frame"
    assert lexicon.classify_kind("Where is …?") == "sentence_frame"
    # Interrogativa cerrada → functional chunk
    assert lexicon.classify_kind("How are you?") == "functional_chunk"
    assert lexicon.classify_kind("What is your name?") == "functional_chunk"
    # Petición funcional / oración con sujeto
    assert lexicon.classify_kind("Can I have") == "functional_chunk"
    assert lexicon.classify_kind("I would like") == "functional_chunk"
    # Etiquetas gramaticales/temáticas → structure (no se inventa tipo)
    assert lexicon.classify_kind("Present Simple") == "structure"
    assert lexicon.classify_kind("countable / uncountable") == "structure"
    assert lexicon.classify_kind("to be") == "structure"
    assert lexicon.classify_kind("family words") == "structure"


# --- seed_curriculum_items (repositorio) ------------------------------------


def test_seed_does_not_increment_appearances(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    items = lexicon.items_from_objective(_level(), _objective())
    assert vocabulary_repo.seed_curriculum_items(uid, items) is True
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}
    assert vocab["name"]["appearances"] == 0
    assert vocab["name"]["exposures"] == 0
    assert vocab["name"]["production_days"] == 0
    assert vocab["name"]["cefr"] == "A1"
    assert vocab["name"]["source"] == "curriculum"
    assert vocab["name"]["kind"] == "word"
    assert vocab["i am"]["kind"] == "functional_chunk"


def test_seed_preserves_production_and_fills_context(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_words(uid, ["name"])
    items = lexicon.items_from_objective(_level(), _objective())
    vocabulary_repo.seed_curriculum_items(uid, items)
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}
    assert vocab["name"]["appearances"] == 1  # no se reinicia la producción
    assert vocab["name"]["cefr"] == "A1"  # pero sí se rellena el contexto
    assert vocab["name"]["source"] == "curriculum"


def test_seed_unknown_user_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert (
        vocabulary_repo.seed_curriculum_items("no-existe", [{"word": "x"}]) is False
    )


# --- item_mastery / item_status ---------------------------------------------


def test_item_mastery_bounded():
    assert lexicon.item_mastery({"appearances": 0, "exposures": 0}) == 0.0
    # Evidencia completa: producida y expuesta en muchos días distintos.
    assert lexicon.item_mastery({"appearances": 100, "production_days": 100,
                                 "exposures": 100, "exposure_days": 100}) == 1.0


def test_item_mastery_recognition_requires_spaced_exposure_days():
    """V3.23 (P1-04): el reconocimiento pondera los DÍAS de exposición (0.6)
    más que el volumen (0.4). Cien exposiciones en un solo día ya no saturan la
    señal receptiva: 3 exposiciones en 3 días valen más que 100 en 1 día."""
    same_day = lexicon.item_mastery(
        {
            "appearances": 3,
            "production_days": 1,
            "exposures": 100,
            "exposure_days": 1,
        }
    )
    spaced = lexicon.item_mastery(
        {
            "appearances": 3,
            "production_days": 1,
            "exposures": 3,
            "exposure_days": 3,
        }
    )
    assert 0 < same_day < spaced <= 1.0


def test_item_status_deterministic():
    assert lexicon.item_status({"appearances": 0, "exposures": 0}) == "learning"
    assert lexicon.item_status({"appearances": 0, "exposures": 2}) == "known"
    assert (
        lexicon.item_status(
            {"appearances": 1, "production_days": 1, "exposures": 0}
        )
        == "weak"
    )
    # producido repetido pero no espaciado (mismo día) → aún en consolidación
    assert (
        lexicon.item_status(
            {"appearances": 3, "production_days": 1, "exposures": 3}
        )
        == "learning"
    )
    assert (
        lexicon.item_status({"appearances": 3, "production_days": 2}) == "mastered"
    )


# --- recall / next review ---------------------------------------------------


def test_item_recall_decays_over_time():
    row = {
        "appearances": 3,
        "production_days": 2,
        "exposures": 0,
        "last_seen": "2026-01-01T00:00:00+00:00",
        "last_exposed_at": "",
    }
    r0 = lexicon.item_recall(row, "2026-01-01T00:00:00+00:00")
    r1 = lexicon.item_recall(row, "2026-01-10T00:00:00+00:00")
    assert 0 <= r1 < r0 <= 1.0


def test_item_recall_uses_most_recent_activity():
    """V3.23 (P1-01): la curva de olvido se ancla a la actividad MÁS reciente.
    Antes se usaba `last_seen or last_exposed_at` (primero que exista): una
    producción antigua con exposición posterior hacía parecer el recuerdo en
    degradación, ignorando la exposición por completo."""
    base = {
        "appearances": 3,
        "production_days": 2,
        "exposures": 3,
        "exposure_days": 3,
    }
    now = "2026-09-09T00:00:00+00:00"
    # Producción antigua + exposición reciente: el ancla es la exposición.
    produced_old = {
        **base,
        "last_seen": "2026-06-01T00:00:00+00:00",
        "last_exposed_at": "2026-09-08T00:00:00+00:00",
    }
    exposed_only = {**produced_old, "last_seen": ""}
    assert lexicon.item_recall(produced_old, now) == lexicon.item_recall(
        exposed_only, now
    )
    # Producción reciente + exposición antigua: el ancla es la producción.
    exposed_old = {
        **base,
        "last_seen": "2026-09-08T00:00:00+00:00",
        "last_exposed_at": "2026-06-01T00:00:00+00:00",
    }
    produced_only = {**exposed_old, "last_exposed_at": ""}
    assert lexicon.item_recall(exposed_old, now) == lexicon.item_recall(
        produced_only, now
    )


def test_next_review_days_bounded_and_monotonic():
    weak_row = {"appearances": 1, "production_days": 1, "exposures": 0}
    strong_row = {"appearances": 3, "production_days": 2, "exposures": 0}
    d_weak = lexicon.next_review_days(weak_row)
    d_strong = lexicon.next_review_days(strong_row)
    assert 1 <= d_weak <= d_strong <= 30


# --- distribución CEFR / resumen / señal micro-drill ------------------------


def test_cefr_distribution_orders_and_counts():
    rows = [
        {"cefr": "B1"},
        {"cefr": "A1"},
        {"cefr": "A1"},
        {"cefr": ""},
    ]
    assert lexicon.cefr_distribution(rows) == [
        {"cefr": "A1", "count": 2},
        {"cefr": "B1", "count": 1},
    ]


def test_summary_counts_statuses_and_cefr():
    rows = [
        {"appearances": 0, "exposures": 0, "cefr": "A1"},
        {"appearances": 0, "exposures": 1, "cefr": "A1"},
        {"appearances": 3, "production_days": 2, "exposures": 0, "cefr": "A2"},
    ]
    s = lexicon.summary(rows)
    assert s["total"] == 3
    assert s["learning"] == 1
    assert s["known"] == 1
    assert s["mastered"] == 1
    assert s["weak"] == 0
    assert s["by_cefr"] == [
        {"cefr": "A1", "count": 2},
        {"cefr": "A2", "count": 1},
    ]


def test_recognized_not_produced():
    rows = [
        {"word": "travel", "appearances": 0, "exposures": 3},
        {"word": "cat", "appearances": 1, "exposures": 0},
        {"word": "culture", "appearances": 0, "exposures": 0},
    ]
    assert lexicon.recognized_not_produced(rows) == ["travel"]


def test_recognized_not_produced_is_oral_semantics():
    """V3.19: la señal es 'expuestas y nunca producidas hablando', no 'nunca
    tecleadas'. Una palabra tecleada en el chat (chat_prod > 0) pero nunca dicha
    (speaking_prod == 0) sigue siendo candidata a speaking micro-drill."""
    rows = [
        {"word": "travel", "exposures": 3, "chat_prod": 2, "speaking_prod": 0},
        {"word": "culture", "exposures": 3, "chat_prod": 0, "speaking_prod": 1},
        {"word": "music", "exposures": 0, "chat_prod": 1, "speaking_prod": 0},
    ]
    assert lexicon.recognized_not_produced(rows) == ["travel"]


def test_drill_candidates_orders_by_recall_and_limits():
    """Candidatos (V3.21/F6-V20-06): expuestas pendientes de consolidar la
    producción oral espaciada, ordenadas por recuerdo ascendente y acotadas a
    `limit`. Una única producción del día no las elimina."""
    rows = [
        {
            "word": "oldest",
            "exposures": 3,
            "speaking_prod": 0,
            "appearances": 0,
            "production_days": 0,
            "first_seen": "",
            "last_seen": "",
            "last_exposed_at": "2020-01-01",
        },
        {
            "word": "newest",
            "exposures": 3,
            "speaking_prod": 0,
            "appearances": 0,
            "production_days": 0,
            "first_seen": "",
            "last_seen": "",
            "last_exposed_at": "2026-09-01",
        },
        {
            # Dicha una sola vez (sin éxito espaciado): sigue pendiente.
            "word": "spoken_once",
            "exposures": 3,
            "speaking_prod": 1,
            "appearances": 1,
            "production_days": 1,
            "first_seen": "",
            "last_seen": "2026-09-01",
            "last_exposed_at": "",
        },
        {
            # Dicha en dos días distintos (señal espaciada sin drill): sale.
            "word": "spoken_spaced",
            "exposures": 3,
            "speaking_prod": 2,
            "appearances": 2,
            "production_days": 2,
            "first_seen": "2026-08-01",
            "last_seen": "2026-09-01",
            "last_exposed_at": "",
        },
        {
            "word": "unexposed",
            "exposures": 0,
            "speaking_prod": 0,
            "appearances": 0,
            "production_days": 0,
            "first_seen": "",
            "last_seen": "",
            "last_exposed_at": "",
        },
    ]
    got = lexicon.drill_candidates(rows, limit=10)
    assert set(got) == {"oldest", "newest", "spoken_once"}
    assert "unexposed" not in got
    assert "spoken_spaced" not in got
    # Ordena por recuerdo ascendente y acota a `limit`.
    assert lexicon.drill_candidates(rows, limit=2) == got[:2]


def test_drill_candidates_no_limit_when_large_limit():
    rows = [
        {
            "word": w,
            "exposures": 1,
            "speaking_prod": 0,
            "appearances": 0,
            "first_seen": "",
            "last_seen": "",
            "last_exposed_at": "",
        }
        for w in ("a", "b", "c")
    ]
    assert set(lexicon.drill_candidates(rows, limit=10)) == {"a", "b", "c"}


def test_coverage_indicator_receptive_productive_by_level():
    """P1 (§3.1): el Vocabulary Coverage Indicator distingue receptivo
    (encontrado: input o producción) de productivo (producido ≥1 vez), por
    nivel y frente a las bandas objetivo. Es indicador, no puerta."""
    rows = [
        {"cefr": "Pre-A1", "appearances": 0, "exposures": 0},
        {"cefr": "Pre-A1", "appearances": 0, "exposures": 2},
        {"cefr": "A1", "appearances": 3, "production_days": 2, "exposures": 0},
        {"cefr": "A1", "appearances": 0, "exposures": 1},
        {"cefr": "A2", "appearances": 0, "exposures": 0},
        {"cefr": "C2", "appearances": 0, "exposures": 1},
        {"cefr": "nivel-raro", "appearances": 5, "exposures": 0},  # sin banda
    ]
    cov = lexicon.coverage_indicator(rows)
    # Totales: receptivo suma los niveles con banda declarada (no "nivel-raro").
    assert cov["receptive"] == 4  # Pre-A1(1) + A1(2) + C2(1)
    assert cov["productive"] == 1  # solo la fila mastered A1
    assert cov["mastered"] == 1

    by_level = {lvl["cefr"]: lvl for lvl in cov["by_level"]}
    assert [lvl["cefr"] for lvl in cov["by_level"]] == [
        "Pre-A1",
        "A1",
        "A2",
        "C2",
    ]
    a1 = by_level["A1"]
    assert a1["total"] == 2
    assert a1["receptive"] == 2
    assert a1["productive"] == 1
    assert a1["mastered"] == 1
    assert a1["known"] == 1
    assert a1["learning"] == 0
    # Ratio frente al extremo superior de la banda objetivo (A1 receptivo
    # 700–1000; productivo 400–600).
    assert a1["receptive_pct"] == pytest.approx(round(2 / 1000, 3), rel=1e-6)
    assert a1["productive_pct"] == pytest.approx(round(1 / 600, 3), rel=1e-6)

    assert by_level["Pre-A1"]["receptive"] == 1
    # C2 no declara banda numérica: el ratio es None.
    assert by_level["C2"]["receptive"] == 1
    assert by_level["C2"]["receptive_pct"] is None
    assert by_level["C2"]["productive_pct"] is None
    assert "nivel-raro" not in by_level


# --- V3.21 (V20-16/V20-17) / V3.22 / V3.23: matriz de competencia -----------

def _row(**overrides) -> dict:
    row = {
        "word": "w",
        "appearances": 0,
        "first_seen": "",
        "last_seen": "",
        "exposures": 0,
        "last_exposed_at": "",
        "exposure_days": 0,
        "first_exposed_at": "",
        "production_days": 0,
        "chat_prod": 0,
        "speaking_prod": 0,
        "writing_prod": 0,
        "conversation_prod": 0,
        # V3.23: evidencia de recuperación demorada y contexto por actividad.
        "retrieval_successes": 0,
        "retrieval_days": 0,
        "last_retrieval_at": "",
        "context_tags": "",
    }
    row.update(overrides)
    return row


def test_matrix_never_seen_is_all_false_no_gap():
    m = lexicon.item_competence_matrix(_row())
    assert m["recognition"] is False
    assert m["production"] is False
    assert m["transfer"] is False
    assert m["retention"] is False
    assert m["spaced_exposure"] is False
    assert m["spaced_production"] is False
    assert m["production_gap"] is False  # sin reconocimiento no hay gap
    assert m["transfer_gap"] is False
    assert m["production_channels"] == []
    assert m["transfer_contexts"] == 0


def test_matrix_recognition_only_is_production_gap():
    m = lexicon.item_competence_matrix(_row(exposures=3))
    assert m["recognition"] is True
    assert m["production"] is False
    assert m["transfer"] is False
    assert m["retention"] is False
    # Reconocida y nunca producida: el gap que cierra el speaking micro-drill.
    assert m["production_gap"] is True
    assert m["transfer_gap"] is False


def test_matrix_produced_once_single_channel_is_transfer_gap():
    # Producida una sola vez en un solo canal y un solo día: ni transfer ni
    # retention; es un transfer gap real (producida en ejercicios pero nunca
    # usada en otro contexto).
    m = lexicon.item_competence_matrix(
        _row(
            exposures=2,
            appearances=1,
            speaking_prod=1,
            production_days=1,
            first_seen="2026-01-01T10:00:00+00:00",
            last_seen="2026-01-01T11:00:00+00:00",
        )
    )
    assert m["production"] is True
    assert m["production_channels"] == ["speaking"]
    assert m["transfer"] is False
    assert m["retention"] is False
    assert m["production_gap"] is False
    assert m["transfer_gap"] is True


def test_matrix_transfer_by_two_channels_same_day_no_retention():
    # Dos canales el MISMO día: transfer (contextos distintos) pero sin
    # recuperación demorada -> retention False. Sin context_tags explícitos, el
    # fallback por canal produce `speaking:other` + `writing:other` (2
    # contextos).
    m = lexicon.item_competence_matrix(
        _row(appearances=2, exposures=2, speaking_prod=1, writing_prod=1)
    )
    assert set(m["production_channels"]) == {"speaking", "writing"}
    assert m["transfer_contexts"] == 2
    assert m["transfer"] is True
    assert m["retention"] is False
    assert m["spaced_production"] is False  # mismo día: sin espaciado productivo
    assert m["transfer_gap"] is False


def test_matrix_spaced_production_is_not_retention():
    # Un solo canal, producción espaciada (>= 2 días, hueco >= 1 día): señal de
    # `spaced_production` PERO no retención (V3.23: requiere recuperación
    # demorada, no exposición/producción repetida).
    m = lexicon.item_competence_matrix(
        _row(
            appearances=2,
            exposures=1,
            speaking_prod=2,
            production_days=2,
            first_seen="2026-01-01T10:00:00+00:00",
            last_seen="2026-01-03T10:00:00+00:00",
        )
    )
    assert m["production_channels"] == ["speaking"]
    assert m["transfer_contexts"] == 1
    assert m["transfer"] is False
    assert m["spaced_production"] is True
    assert m["spaced_exposure"] is False
    assert m["retention"] is False
    assert m["transfer_gap"] is True


def test_matrix_spaced_receptive_exposure_is_not_retention():
    # Exposición espaciada (días distintos) sin producción: señal de
    # `spaced_exposure` receptiva PERO no retención (V3.23: ver la palabra dos
    # veces no demuestra que se recuerda; falta la recuperación demorada).
    m = lexicon.item_competence_matrix(
        _row(
            exposures=3,
            exposure_days=2,
            first_exposed_at="2026-01-01T10:00:00+00:00",
            last_exposed_at="2026-01-03T10:00:00+00:00",
        )
    )
    assert m["recognition"] is True
    assert m["production"] is False
    assert m["retention"] is False
    assert m["spaced_exposure"] is True
    assert m["spaced_production"] is False
    assert m["transfer"] is False
    assert m["production_gap"] is True  # sigue pendiente de producción


def test_matrix_retention_requires_delayed_retrieval_days():
    # V3.23 (P1-02): la retención exige recuperación correcta DEMORADA. Un ítem
    # con `retrieval_days >= umbral` (días distintos con éxito de micro-drill
    # fuera del intervalo) es `retention`, con independencia del espaciado
    # receptivo/productivo.
    m = lexicon.item_competence_matrix(
        _row(
            exposures=3,
            exposure_days=2,
            first_exposed_at="2026-01-01T10:00:00+00:00",
            last_exposed_at="2026-01-03T10:00:00+00:00",
            retrieval_successes=3,
            retrieval_days=2,
            last_retrieval_at="2026-03-01T10:00:00+00:00",
        )
    )
    assert m["retention"] is True
    assert m["spaced_exposure"] is True  # señal independiente, no es retención
    assert m["retrieval_successes"] == 3
    assert m["retrieval_days"] == 2


def test_matrix_retention_zero_retrieval_days():
    # retrieval_days = 0 (o ausente): nunca retención, aunque haya producciones
    # y exposiciones espaciadas.
    m = lexicon.item_competence_matrix(
        _row(appearances=3, production_days=2, speaking_prod=3, exposures=5)
    )
    assert m["retention"] is False
    assert m["retrieval_days"] == 0


def test_production_contexts_explicit_tags_and_fallback():
    # V3.23 (P1-04): los contextos se derivan de `context_tags` (channel:activity)
    # y, para canales legacy sin etiqueta, del fallback `channel:other`.
    assert lexicon.production_contexts(_row()) == []
    m = lexicon.production_contexts(
        _row(speaking_prod=1, writing_prod=1)
    )
    assert m == ["speaking:other", "writing:other"]
    m = lexicon.production_contexts(
        _row(
            speaking_prod=2,
            context_tags="speaking:drill,speaking:speaking_route",
        )
    )
    assert m == ["speaking:drill", "speaking:speaking_route"]


def test_matrix_transfer_by_two_activities_same_channel():
    # V3.23 (P1-04): dos actividades DISTINTAS dentro del MISMO canal (drill +
    # ruta speaking) son 2 contextos de producción => transfer True, aunque haya
    # un solo canal.
    m = lexicon.item_competence_matrix(
        _row(
            exposures=2,
            appearances=2,
            speaking_prod=2,
            context_tags="speaking:drill,speaking:speaking_route",
        )
    )
    assert m["production_channels"] == ["speaking"]
    assert m["transfer_contexts"] == 2
    assert m["transfer"] is True
    assert m["transfer_gap"] is False


def test_matrix_spaced_requires_one_day_gap():
    # production_days == 2 pero mismas fechas (datos raros): no hay hueco real.
    m = lexicon.item_competence_matrix(
        _row(
            appearances=2,
            speaking_prod=2,
            production_days=2,
            first_seen="2026-01-01T10:00:00+00:00",
            last_seen="2026-01-01T11:00:00+00:00",
        )
    )
    assert m["retention"] is False
    assert m["spaced_production"] is False
    assert m["transfer"] is False


def test_summary_counts_matrix_competence():
    rows = [
        _row(word="never", exposures=0),
        _row(word="recog", exposures=2),
        _row(word="produced-1", exposures=1, appearances=1, speaking_prod=1),
        _row(
            word="transfer",
            exposures=2,
            appearances=2,
            speaking_prod=1,
            writing_prod=1,
        ),
        _row(
            word="retained",
            exposures=3,
            exposure_days=2,
            first_exposed_at="2026-01-01T10:00:00+00:00",
            last_exposed_at="2026-01-03T10:00:00+00:00",
            retrieval_days=1,
        ),
        _row(
            word="spaced-only",
            exposures=3,
            exposure_days=2,
            first_exposed_at="2026-01-01T10:00:00+00:00",
            last_exposed_at="2026-01-03T10:00:00+00:00",
        ),
    ]
    s = lexicon.summary(rows)
    # recognized: recog + produced-1 + transfer + retained + spaced-only.
    assert s["recognized"] == 5
    assert s["produced"] == 2
    assert s["transfer"] == 1  # solo "transfer" (2 canales)
    assert s["retention"] == 1  # solo "retained" (recuperación demorada)
    assert s["spaced_exposure"] == 2  # retained + spaced-only (señal receptiva)
    assert s["production_gap"] == 3  # recog + retained + spaced-only
    assert s["transfer_gap"] == 1  # solo "produced-1"
