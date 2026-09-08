"""Tests de vocabulario: extracción, persistencia, aislamiento y endpoints."""
import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.vocabulary import classify, extract_words


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def _fk_targets(table: str) -> set[tuple[str, str]]:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    finally:
        conn.close()
    return {(row[2], row[3]) for row in rows}


def test_vocabulary_table_has_user_fk(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert ("users", "user_id") in _fk_targets("vocabulary")


def test_extract_words_filters_and_sorts(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    words = extract_words("Hello, World! The cat sat on the mat.")
    assert words == ["cat", "hello", "mat", "sat", "world"]


def test_extract_words_deduplicates(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert extract_words("Cat cat CAT") == ["cat"]


def test_extract_words_removes_short_tokens(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    # "I", "a", "am" no cuentan como vocabulario.
    assert extract_words("I am a cat") == ["cat"]


def test_record_words_increments_appearances(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words(a, ["cat", "dog"]) is True
    assert vocabulary_repo.record_words(a, ["cat"]) is True
    vocab = {
        v["word"]: v["production_count"]
        for v in vocabulary_repo.get_vocabulary(a)
    }
    assert vocab["cat"] == 2
    assert vocab["dog"] == 1


def test_record_words_unknown_user_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_words("no-existe", ["cat"]) is False


def test_vocabulary_occurrences_migration(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    # Simula una BD legacy con la columna antigua `occurrences`.
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute(
        "ALTER TABLE vocabulary RENAME COLUMN production_count TO occurrences"
    )
    conn.commit()
    conn.close()

    # init_db debe volver a renombrar a `production_count` de forma idempotente
    # (V3.25/F-K7: la cadena histórica occurrences → appearances termina en el
    # nombre canónico `production_count`).
    db.init_db()
    conn = sqlite3.connect(db.DB_PATH)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(vocabulary)")}
    finally:
        conn.close()
    assert "production_count" in cols
    assert "occurrences" not in cols
    assert "appearances" not in cols


def test_vocabulary_legacy_appearances_exposures_rename(monkeypatch, tmp_path):
    """V3.25 (F-K7/P2-01): una BD V2.3 (columnas `appearances`/`exposures`) se
    migra a los nombres canónicos `production_count`/`exposure_count` y los
    datos se conservan."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    uid = users_repo.create_user("A")["id"]
    vocabulary_repo.record_words(uid, ["cat"])  # production_count = 1
    vocabulary_repo.record_exposures(uid, ["cat"])  # exposure_count = 1

    # Simula una instalación previa a V3.25.
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute(
        "ALTER TABLE vocabulary RENAME COLUMN production_count TO appearances"
    )
    conn.execute(
        "ALTER TABLE vocabulary RENAME COLUMN exposure_count TO exposures"
    )
    conn.commit()
    conn.close()

    db.init_db()
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}
    assert vocab["cat"]["production_count"] == 1
    assert vocab["cat"]["exposure_count"] == 1


def test_lexical_unit_declared_from_lemma_and_surface_fallback(monkeypatch, tmp_path):
    """V3.25 (P2-02): `lexical_unit` declara la unidad de análisis por ítem:
    el lemma cuando el currículo lo declara (seed) y la superficie normalizada
    en minúsculas cuando no hay lemma (producción libre)."""
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.seed_curriculum_items(
        a,
        [
            {
                "word": "Go",
                "lemma": "go",
                "cefr": "A1",
                "level_id": "a1",
                "objective_id": "o1",
                "kind": "word",
            }
        ],
    )
    vocabulary_repo.record_words(a, ["Traveling"])
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["Go"]["lemma"] == "go"
    assert vocab["Go"]["lexical_unit"] == "go"
    assert vocab["Traveling"]["lemma"] == ""
    assert vocab["Traveling"]["lexical_unit"] == "traveling"


def test_vocabulary_isolation(monkeypatch, tmp_path):
    a, b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_words(a, ["cat"])
    assert vocabulary_repo.get_vocabulary(b) == []


def test_get_vocabulary_ordered_by_appearances(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_words(a, ["zebra"])
    vocabulary_repo.record_words(a, ["apple", "apple"])
    vocab = vocabulary_repo.get_vocabulary(a)
    assert [v["word"] for v in vocab] == ["apple", "zebra"]


def test_vocabulary_endpoint_shape(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/vocabulary/analyze",
            params={"user_id": a},
            json={"text": "The cat sat on the mat."},
        )
        assert r.status_code == 200
        assert r.json()["words"] == ["cat", "mat", "sat"]

        got = client.get("/api/vocabulary", params={"user_id": a})
        assert got.status_code == 200
        assert {v["word"] for v in got.json()} == {"cat", "mat", "sat"}


def test_lexicon_endpoint_exposes_competence_matrix(monkeypatch, tmp_path):
    """V3.21 (V20-16) / V3.22: el léxico expone la matriz de competencia por ítem
    (con `production_gap`/`transfer_gap`) y los contadores del summary."""
    a, _b = _setup(monkeypatch, tmp_path)
    # Producida por chat (pero nunca expuesta por input).
    vocabulary_repo.record_words(a, ["hello"])
    # Reconocida (input) pero nunca producida: production gap.
    vocabulary_repo.record_exposures(a, ["world"])

    with TestClient(app) as client:
        got = client.get("/api/vocabulary/lexicon", params={"user_id": a})
        assert got.status_code == 200
        body = got.json()
        by_word = {i["word"]: i for i in body["items"]}
        assert by_word["hello"]["competence"]["recognition"] is False
        assert by_word["hello"]["competence"]["production"] is True
        assert by_word["hello"]["competence"]["production_gap"] is False
        assert by_word["hello"]["competence"]["transfer_gap"] is False
        assert by_word["world"]["competence"]["recognition"] is True
        assert by_word["world"]["competence"]["production"] is False
        assert by_word["world"]["competence"]["production_gap"] is True
        assert by_word["world"]["competence"]["transfer_gap"] is False
        s = body["summary"]
        assert s["recognized"] == 1
        assert s["produced"] == 1
        assert s["transfer"] == 0
        assert s["production_gap"] == 1
        assert s["transfer_gap"] == 0


def test_vocabulary_endpoint_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert (
            client.get("/api/vocabulary", params={"user_id": "no-existe"}).status_code
            == 404
        )
        assert (
            client.post(
                "/api/vocabulary/analyze",
                params={"user_id": "no-existe"},
                json={"text": "hello"},
            ).status_code
            == 404
        )


def test_classify_statuses(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert classify(0, 0) == "exposed"
    assert classify(1, 1) == "learning"
    assert classify(2, 3) == "learning"  # menos de 3 producciones
    assert classify(3, 1) == "learning"  # 3 producciones pero un solo día
    assert classify(3, 2) == "mastered"


def test_record_exposures_creates_exposed_rows(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_exposures(a, ["travel", "culture"]) is True
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["travel"]["exposure_count"] == 1
    assert vocab["travel"]["production_count"] == 0
    assert vocab["travel"]["production_days"] == 0
    assert vocab["travel"]["last_exposed_at"]


def test_record_exposures_accumulates(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["travel"])
    vocabulary_repo.record_exposures(a, ["travel"])
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["travel"]["exposure_count"] == 2
    assert vocab["travel"]["production_count"] == 0


def test_record_exposures_unknown_user_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_exposures("no-existe", ["travel"]) is False


def test_exposure_days_counts_distinct_days(monkeypatch, tmp_path):
    """V3.22: `exposure_days` suma una vez por día distinto y `first_exposed_at`
    se fija en la primera exposición."""
    a, _b = _setup(monkeypatch, tmp_path)
    times = iter(
        [
            "2026-08-20T10:00:00+00:00",
            "2026-08-20T11:00:00+00:00",  # mismo día → no suma
            "2026-08-21T10:00:00+00:00",  # día distinto → suma
            "2026-08-22T10:00:00+00:00",  # día distinto → suma
        ]
    )
    monkeypatch.setattr(vocabulary_repo, "_now", lambda: next(times))
    for _ in range(4):
        vocabulary_repo.record_exposures(a, ["sun"])
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["sun"]["exposure_count"] == 4
    assert vocab["sun"]["exposure_days"] == 3
    assert vocab["sun"]["first_exposed_at"]  # fijado en la primera exposición


def test_exposure_days_columns_migration_and_backfill(monkeypatch, tmp_path):
    """V3.22: una BD previa (sin `exposure_days`/`first_exposed_at`) se migra al
    re-ejecutar `init_db` y el histórico expuesto recibe backfill (1 día)."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    uid = users_repo.create_user("A")["id"]
    vocabulary_repo.record_exposures(uid, ["sun"])  # exposures = 1

    # Simula una BD previa a V3.22: elimina las columnas nuevas.
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute("ALTER TABLE vocabulary DROP COLUMN exposure_days")
    conn.execute("ALTER TABLE vocabulary DROP COLUMN first_exposed_at")
    conn.commit()
    conn.close()

    db.init_db()
    conn = sqlite3.connect(db.DB_PATH)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(vocabulary)")}
        row = conn.execute(
            "SELECT exposure_count, exposure_days, first_exposed_at "
            "FROM vocabulary WHERE word = 'sun'"
        ).fetchone()
    finally:
        conn.close()
    assert {"exposure_days", "first_exposed_at"} <= cols
    assert row[0] == 1  # exposure_count conservadas
    assert row[1] == 1  # exposure_days backfill
    assert row[2]  # first_exposed_at backfill


def test_production_days_counts_distinct_days(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    times = iter(
        [
            "2026-08-20T10:00:00+00:00",
            "2026-08-20T11:00:00+00:00",  # mismo día → no suma
            "2026-08-21T10:00:00+00:00",  # día distinto → suma
            "2026-08-22T10:00:00+00:00",  # día distinto → suma
        ]
    )
    monkeypatch.setattr(vocabulary_repo, "_now", lambda: next(times))
    for _ in range(4):
        vocabulary_repo.record_words(a, ["cat"])
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["cat"]["production_count"] == 4
    assert vocab["cat"]["production_days"] == 3


def test_vocabulary_endpoint_reports_status(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["travel"])  # exposed
    vocabulary_repo.record_words(a, ["cat"])  # learning (1 producción, 1 día)
    with TestClient(app) as client:
        got = client.get("/api/vocabulary", params={"user_id": a})
    assert got.status_code == 200
    by_word = {v["word"]: v for v in got.json()}
    assert by_word["travel"]["status"] == "exposed"
    assert by_word["travel"]["production_count"] == 0
    assert by_word["cat"]["status"] == "learning"


def test_vocabulary_p3_columns_migration(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    uid = users_repo.create_user("A")["id"]
    vocabulary_repo.record_words(uid, ["cat"])

    # Simula una BD previa a P3: elimina las columnas nuevas (canonical V3.25).
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute("ALTER TABLE vocabulary DROP COLUMN exposure_count")
    conn.execute("ALTER TABLE vocabulary DROP COLUMN last_exposed_at")
    conn.execute("ALTER TABLE vocabulary DROP COLUMN production_days")
    conn.commit()
    conn.close()

    db.init_db()
    conn = sqlite3.connect(db.DB_PATH)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(vocabulary)")}
        row = conn.execute(
            "SELECT production_count, production_days "
            "FROM vocabulary WHERE word = 'cat'"
        ).fetchone()
    finally:
        conn.close()
    assert {"exposure_count", "last_exposed_at", "production_days"} <= cols
    assert row[0] == 1  # production_count
    assert row[1] == 1  # production_days (backfill de producciones previas)


def test_lexicon_endpoint_shape(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.seed_curriculum_items(
        a,
        [
            {"word": "name", "lemma": "name", "cefr": "A1", "level_id": "a1",
             "objective_id": "o1", "kind": "word"},
            {"word": "i am", "lemma": "i am", "cefr": "A1", "level_id": "a1",
             "objective_id": "o1", "kind": "structure"},
        ],
    )
    vocabulary_repo.record_exposures(a, ["name"])
    vocabulary_repo.record_words(a, ["name"])
    with TestClient(app) as client:
        got = client.get("/api/vocabulary/lexicon", params={"user_id": a})
    assert got.status_code == 200
    body = got.json()
    assert body["summary"]["total"] == 2
    items = {i["word"]: i for i in body["items"]}
    assert set(items) == {"name", "i am"}
    assert items["name"]["cefr"] == "A1"
    assert items["name"]["source"] == "curriculum"
    assert items["name"]["kind"] == "word"
    assert items["i am"]["kind"] == "structure"
    assert items["name"]["status"] in {"mastered", "known", "learning", "weak"}
    assert 0 <= items["name"]["recall"] <= 1
    assert isinstance(items["name"]["next_review_days"], int)
    # V3.25 (F-K7/P2-02): contadores canónicos y unidad léxica en el API.
    assert items["name"]["production_count"] == 1
    assert items["name"]["exposure_count"] == 1
    assert items["name"]["lexical_unit"] == "name"


def test_lexicon_endpoint_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        resp = client.get(
            "/api/vocabulary/lexicon", params={"user_id": "no-existe"}
        )
        assert resp.status_code == 404


def test_record_production_by_channel_breaks_down(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_production(a, ["cat"], channel="chat") is True
    assert vocabulary_repo.record_production(a, ["cat"], channel="speaking") is True
    assert (
        vocabulary_repo.record_production(a, ["cat"], channel="writing") is True
    )
    assert (
        vocabulary_repo.record_production(a, ["dog"], channel="conversation")
        is True
    )
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    cat = vocab["cat"]
    # Semántica agregada intacta.
    assert cat["production_count"] == 3
    assert cat["chat_prod"] == 1
    assert cat["speaking_prod"] == 1
    assert cat["writing_prod"] == 1
    assert cat["conversation_prod"] == 0
    # Invariante de trazabilidad: suma de canales == appearances.
    assert (
        cat["chat_prod"] + cat["speaking_prod"]
        + cat["writing_prod"] + cat["conversation_prod"]
    ) == cat["production_count"]
    dog = vocab["dog"]
    assert dog["production_count"] == 1
    assert dog["conversation_prod"] == 1
    assert (
        dog["chat_prod"] + dog["speaking_prod"]
        + dog["writing_prod"] + dog["conversation_prod"]
    ) == dog["production_count"]


def test_record_production_unknown_channel_false(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_production(a, ["cat"], channel="typing") is False
    assert vocabulary_repo.get_vocabulary(a) == []


def test_record_production_unknown_user_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert (
        vocabulary_repo.record_production("no-existe", ["cat"], channel="chat")
        is False
    )


def test_production_days_distinct_day_single_channel_semantics(monkeypatch, tmp_path):
    """Un mismo día en dos canales suma una sola vez `production_days`."""
    a, _b = _setup(monkeypatch, tmp_path)
    times = iter(
        [
            "2026-08-20T10:00:00+00:00",
            "2026-08-20T11:00:00+00:00",  # mismo día, otro canal → no suma
            "2026-08-21T10:00:00+00:00",  # día distinto → suma
        ]
    )
    monkeypatch.setattr(vocabulary_repo, "_now", lambda: next(times))
    vocabulary_repo.record_production(a, ["cat"], channel="chat")
    vocabulary_repo.record_production(a, ["cat"], channel="speaking")
    vocabulary_repo.record_production(a, ["cat"], channel="chat")
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["cat"]["production_count"] == 3
    assert vocab["cat"]["production_days"] == 2
    assert vocab["cat"]["chat_prod"] == 2
    assert vocab["cat"]["speaking_prod"] == 1


def test_record_production_context_tags_merge(monkeypatch, tmp_path):
    """V3.23 (P1-04): `activity` etiqueta la producción con `channel:activity`
    en `context_tags`, fusionada de forma canónica, única y ordenada."""
    a, _b = _setup(monkeypatch, tmp_path)
    assert (
        vocabulary_repo.record_production(
            a, ["cat"], channel="speaking", activity="drill"
        )
        is True
    )
    # Misma actividad repetida: no duplica el tag.
    vocabulary_repo.record_production(
        a, ["cat"], channel="speaking", activity="drill"
    )
    # Segunda actividad del MISMO canal: tag adicional.
    vocabulary_repo.record_production(
        a, ["cat"], channel="speaking", activity="speaking_route"
    )
    # Canal distinto: chat libre.
    vocabulary_repo.record_production(
        a, ["cat"], channel="chat", activity="free_chat"
    )
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    # Orden canónico del repositorio: canales chat → speaking → writing →
    # conversation, luego actividad alfabética.
    assert (
        vocab["cat"]["context_tags"]
        == "chat:free_chat,speaking:drill,speaking:speaking_route"
    )
    # Semántica agregada intacta.
    assert vocab["cat"]["production_count"] == 4
    assert vocab["cat"]["speaking_prod"] == 3
    assert vocab["cat"]["chat_prod"] == 1


def test_record_production_without_activity_keeps_tags(monkeypatch, tmp_path):
    """Producción sin `activity` (callers legacy) no borra los tags existentes."""
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_production(
        a, ["cat"], channel="speaking", activity="drill"
    )
    vocabulary_repo.record_words(a, ["cat"])  # record_words: sin activity
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["cat"]["context_tags"] == "speaking:drill"


def test_record_retrievals_requires_interval_since_anchor(monkeypatch, tmp_path):
    """V3.23 (P1-02): una recuperación solo acredita retención si ocurre
    >= RETENTION_MIN_INTERVAL_DAYS después del ancla (primera exposición)."""
    a, _b = _setup(monkeypatch, tmp_path)
    times = iter(
        [
            "2026-08-20T10:00:00+00:00",  # exposición (ancla)
            "2026-08-20T11:00:00+00:00",  # retrieval mismo día: NO cuenta
            "2026-08-21T10:00:00+00:00",  # retrieval al día siguiente: cuenta
        ]
    )
    monkeypatch.setattr(vocabulary_repo, "_now", lambda: next(times))
    vocabulary_repo.record_exposures(a, ["sun"])
    assert vocabulary_repo.record_retrievals(a, ["sun"]) is True
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["sun"]["retrieval_successes"] == 0
    assert vocab["sun"]["retrieval_days"] == 0
    assert vocabulary_repo.record_retrievals(a, ["sun"]) is True
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["sun"]["retrieval_successes"] == 1
    assert vocab["sun"]["retrieval_days"] == 1
    assert vocab["sun"]["last_retrieval_at"]


def test_record_retrievals_dedupe_by_day_and_counts(monkeypatch, tmp_path):
    """`retrieval_successes` suma por recuperación; `retrieval_days` una vez por
    día distinto."""
    a, _b = _setup(monkeypatch, tmp_path)
    times = iter(
        [
            "2026-08-20T10:00:00+00:00",  # exposición (ancla)
            "2026-08-22T10:00:00+00:00",  # retrieval día +2
            "2026-08-22T11:00:00+00:00",  # retrieval mismo día → no suma días
            "2026-08-23T10:00:00+00:00",  # retrieval día +3 → suma día
        ]
    )
    monkeypatch.setattr(vocabulary_repo, "_now", lambda: next(times))
    vocabulary_repo.record_exposures(a, ["sun"])
    vocabulary_repo.record_retrievals(a, ["sun"])
    vocabulary_repo.record_retrievals(a, ["sun"])
    vocabulary_repo.record_retrievals(a, ["sun"])
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["sun"]["retrieval_successes"] == 3
    assert vocab["sun"]["retrieval_days"] == 2


def test_record_retrievals_without_anchor_ignored(monkeypatch, tmp_path):
    """Sin ancla (ni exposición ni producción) no hay retención medible: se
    ignora en silencio y no lanza."""
    a, _b = _setup(monkeypatch, tmp_path)
    # Palabra no sembrada: no existe fila.
    assert vocabulary_repo.record_retrievals(a, ["ghost"]) is True
    # Palabra sembrada del currículo (sin exposición ni producción): fila sin ancla.
    uid = users_repo.create_user("B")["id"]
    vocabulary_repo.seed_curriculum_items(uid, [{"word": "travel"}])
    assert vocabulary_repo.record_retrievals(uid, ["travel"]) is True
    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}
    assert vocab["travel"]["retrieval_successes"] == 0


def test_record_retrievals_unknown_user_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert vocabulary_repo.record_retrievals("no-existe", ["cat"]) is False


def test_vocabulary_v323_columns_migration(monkeypatch, tmp_path):
    """V3.23: una BD previa (sin retrieval/context_tags) se migra al re-ejecutar
    `init_db`. Los contadores de retrieval NO reciben backfill (la evidencia de
    recuperación demorada solo cuenta desde V3.23), pero `context_tags` existe."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    uid = users_repo.create_user("A")["id"]
    vocabulary_repo.record_exposures(uid, ["sun"])
    vocabulary_repo.record_words(uid, ["cat"])

    # Simula una BD previa a V3.23: elimina las columnas nuevas.
    conn = sqlite3.connect(db.DB_PATH)
    for col in (
        "retrieval_successes",
        "retrieval_days",
        "last_retrieval_at",
        "context_tags",
    ):
        conn.execute(f"ALTER TABLE vocabulary DROP COLUMN {col}")
    conn.commit()
    conn.close()

    db.init_db()
    conn = sqlite3.connect(db.DB_PATH)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(vocabulary)")}
        rows = {
            r[0]: r
            for r in conn.execute(
                "SELECT word, retrieval_successes, retrieval_days, "
                "context_tags FROM vocabulary"
            )
        }
    finally:
        conn.close()
    assert {
        "retrieval_successes",
        "retrieval_days",
        "last_retrieval_at",
        "context_tags",
    } <= cols
    # Sin backfill de retrieval: expuesta y producida, pero sin recuperación
    # demorada acreditada retrospectivamente.
    assert rows["sun"][1] == 0 and rows["sun"][2] == 0
    assert rows["cat"][1] == 0 and rows["cat"][2] == 0
    assert rows["sun"][3] == "" and rows["cat"][3] == ""


def test_vocabulary_v319_channels_migration_backfills_chat(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    uid = users_repo.create_user("A")["id"]
    vocabulary_repo.record_words(uid, ["cat"])

    # Simula una BD previa a V3.19: sin columnas de canal.
    conn = sqlite3.connect(db.DB_PATH)
    for col in (
        "chat_prod",
        "speaking_prod",
        "writing_prod",
        "conversation_prod",
    ):
        conn.execute(f"ALTER TABLE vocabulary DROP COLUMN {col}")
    conn.commit()
    conn.close()

    db.init_db()
    conn = sqlite3.connect(db.DB_PATH)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(vocabulary)")}
        row = conn.execute(
            "SELECT production_count, chat_prod, speaking_prod "
            "FROM vocabulary WHERE word = 'cat'"
        ).fetchone()
    finally:
        conn.close()
    assert {
        "chat_prod",
        "speaking_prod",
        "writing_prod",
        "conversation_prod",
    } <= cols
    # Backfill: el histórico previo solo pudo venir del chat libre.
    assert row[0] == 1  # production_count
    assert row[1] == 1  # chat_prod
    assert row[2] == 0  # speaking_prod


def test_lexicon_endpoint_exposes_channel_breakdown(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["name"])
    vocabulary_repo.record_production(a, ["name"], channel="chat")
    vocabulary_repo.record_production(a, ["name"], channel="speaking")
    with TestClient(app) as client:
        got = client.get("/api/vocabulary/lexicon", params={"user_id": a})
    assert got.status_code == 200
    items = {i["word"]: i for i in got.json()["items"]}
    item = items["name"]
    assert item["chat_prod"] == 1
    assert item["speaking_prod"] == 1
    assert item["writing_prod"] == 0
    assert item["conversation_prod"] == 0


def _fake_transcribe(text):
    def fake(_audio, _lang):
        return {"text": text, "duration": 2.0}

    return fake


def test_drill_candidates_endpoint_exposes_signal(monkeypatch, tmp_path):
    """La señal de candidatas al drill es determinista en servidor (premisa 21):
    expuestas y pendientes de consolidar la producción oral ESPACIADA (V3.21,
    V20-06). Las tecleadas en el chat (chat_prod) siguen siendo candidatas; una
    única producción oral del día no saca a la palabra (sigue pendiente)."""
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["travel", "culture", "music"])
    vocabulary_repo.record_production(a, ["culture"], channel="chat")
    vocabulary_repo.record_production(a, ["music"], channel="speaking")
    with TestClient(app) as client:
        got = client.get(
            "/api/vocabulary/drill/candidates", params={"user_id": a}
        )
    assert got.status_code == 200
    # music se produjo una sola vez (sin espaciar): sigue pendiente de drill.
    assert set(got.json()["words"]) == {"travel", "culture", "music"}


def test_drill_candidates_endpoint_limit(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["apple", "banana", "cherry"])
    with TestClient(app) as client:
        got = client.get(
            "/api/vocabulary/drill/candidates",
            params={"user_id": a, "limit": 2},
        )
    assert got.status_code == 200
    assert len(got.json()["words"]) == 2


def test_drill_attempt_endpoint_produces_word(monkeypatch, tmp_path):
    """Exponer → drill → producir: el intento transcribe (mock Whisper), puntúa y
    al producir la palabra la marca speaking_prod → sale de la lista."""
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["travel", "culture"])

    from routers import vocabulary as router_mod

    monkeypatch.setattr(
        router_mod, "transcribe_with_timing", _fake_transcribe("travel")
    )
    with TestClient(app) as client:
        ok = client.post(
            "/api/vocabulary/drill/attempt",
            params={"user_id": a},
            data={"word": "travel"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert ok.status_code == 200
        body = ok.json()
        assert body["produced"] is True
        assert body["score"] >= 80
        assert "travel" in body["breakdown"]["correct"]

        # Tras producirla, ya no es candidata (speaking_prod == 1).
        got = client.get(
            "/api/vocabulary/drill/candidates", params={"user_id": a}
        )
        assert got.json()["words"] == ["culture"]

    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["travel"]["speaking_prod"] == 1
    assert vocab["travel"]["production_count"] == 1
    # No declara dominio ni crea evidencia curricular: solo columna de canal.
    assert vocab["travel"]["chat_prod"] == 0
    assert vocab["culture"]["speaking_prod"] == 0


def test_drill_attempt_endpoint_ko_does_not_produce(monkeypatch, tmp_path):
    """Si la palabra no sale en la transcripción no se marca como producida y
    sigue siendo candidata."""
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["travel"])

    from routers import vocabulary as router_mod

    monkeypatch.setattr(
        router_mod, "transcribe_with_timing", _fake_transcribe("banana")
    )
    with TestClient(app) as client:
        ko = client.post(
            "/api/vocabulary/drill/attempt",
            params={"user_id": a},
            data={"word": "travel"},
            files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert ko.status_code == 200
        assert ko.json()["produced"] is False

        got = client.get(
            "/api/vocabulary/drill/candidates", params={"user_id": a}
        )
        assert got.json()["words"] == ["travel"]

    vocab = {v["word"]: v for v in vocabulary_repo.get_vocabulary(a)}
    assert vocab["travel"]["speaking_prod"] == 0
