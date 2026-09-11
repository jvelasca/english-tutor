"""V3.52 — Difficulty Engine 2.0 (P1-02 de la auditoría de V3.51).

V3.50/V3.51 emparejaban la dificultad con un ESCALAR: comparaban el ordinal CEFR
(0..5) contra la media del `difficulty_vector` (1..6) y colapsaban las cuatro
dimensiones antes de decidir, de modo que un `(5,1,5,1)` y un `(3,3,3,3)` eran
indistinguibles. V3.52 introduce un motor PURO que compara vector contra vector
por dimensión:

- `CEFR_CAPACITY` declara la capacidad de reto por nivel y dimensión;
- `challenge_vector` combina ítem (techo) y alumno (suelo) con el máximo por
  dimensión;
- `fit` mide distancia y overshoot; `select_by_difficulty` conserva los contextos
  que no se pasan del reto y, entre ellos, los más cercanos, degradando por
  mínima distancia si ninguno encaja.

La preocupación explícita de la auditoría —una unidad A1 con un alumno C2— se
blinda aquí: el TECHO lingüístico del ítem (`_within_level`) sigue mandando.

Las guardias de regresión viven en las suites de V3.43/V3.47/V3.48/V3.50/V3.51;
aquí se cubre lo NUEVO.
"""

from __future__ import annotations

from contextlib import closing

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import profile as profile_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import difficulty, transfer
from services.cefr import CEFR_LEVELS


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


# ---------------------------------------------------------- tabla de capacidad


def test_dimensions_are_the_canonical_bank_vocabulary():
    assert difficulty.DIFFICULTY_DIMENSIONS == (
        "lexical",
        "syntax",
        "discourse",
        "interaction",
    )
    # Paridad por construcción con el vocabulario del banco de transferencia.
    assert transfer.TRANSFER_DIFFICULTY_KEYS == difficulty.DIFFICULTY_DIMENSIONS


def test_capacity_table_is_complete_and_in_range():
    assert set(difficulty.CEFR_CAPACITY) == set(CEFR_LEVELS)
    for level, vector in difficulty.CEFR_CAPACITY.items():
        assert set(vector) == set(difficulty.DIFFICULTY_DIMENSIONS), level
        for dimension, value in vector.items():
            assert 1 <= value <= 5, (level, dimension, value)


def test_capacity_is_monotonic_non_decreasing_per_dimension():
    # Un nivel superior nunca tiene menos capacidad: la tabla debe ser un suelo
    # de reto creíble, no una colección arbitraria.
    ordered = [difficulty.CEFR_CAPACITY[level] for level in CEFR_LEVELS]
    for index in range(len(ordered) - 1):
        lower, upper = ordered[index], ordered[index + 1]
        for dimension in difficulty.DIFFICULTY_DIMENSIONS:
            assert upper[dimension] >= lower[dimension], dimension


def test_capacity_is_the_monotone_envelope_of_the_bank():
    # P2-01 de la auditoría Q de V3.52.1: la tabla declarada se quedaba corta en
    # la `interaction` de A1/A2 y larga en el léxico/sintaxis de B2/C1, y con la
    # tolerancia ESTRICTA excluía contextos del propio nivel (un alumno A2
    # demostrado no podía recibir `directions`/`shopping`, que el banco etiqueta
    # A2). La tabla es ahora el envelope monótono (máximo acumulado) de los
    # `difficulty_vector` reales: este test lo recalcula y falla si divergen.
    bank_max: dict[str, dict[str, int]] = {}
    for level in CEFR_LEVELS:
        vectors = [
            context["difficulty_vector"]
            for context in transfer.TRANSFER_CONTEXTS
            if context.get("cefr") == level
        ]
        assert vectors, level
        bank_max[level] = {
            dimension: max(vector[dimension] for vector in vectors)
            for dimension in difficulty.DIFFICULTY_DIMENSIONS
        }
    running = dict.fromkeys(difficulty.DIFFICULTY_DIMENSIONS, 0)
    for level in CEFR_LEVELS:
        running = {
            dimension: max(running[dimension], bank_max[level][dimension])
            for dimension in difficulty.DIFFICULTY_DIMENSIONS
        }
        assert difficulty.CEFR_CAPACITY[level] == running, level


def test_every_bank_context_fits_its_own_level_under_strict_tolerance():
    # La consecuencia operativa del envelope: con la tolerancia ESTRICTA (suelo
    # demostrado) ningún contexto del banco puede quedar fuera del reto de su
    # propio nivel, que era el fallo medido en la auditoría.
    for context in transfer.TRANSFER_CONTEXTS:
        level = context["cefr"]
        fit = difficulty.fit(
            context["difficulty_vector"],
            difficulty.challenge_vector(level, level),
            tolerance=difficulty.DIFFICULTY_TOLERANCE,
        )
        assert fit["within"], (context["id"], fit)
        assert fit["max_overshoot"] == 0, context["id"]


def test_tolerance_bites_only_when_a_context_declares_above_the_envelope():
    # P2-02: sobre el banco actual (envelope) la tolerancia NO cambia ninguna
    # selección; es una red de seguridad para bancos que declaren por encima de
    # la envolvente. Este test documenta ambas cosas.
    levels = ("", *CEFR_LEVELS)
    for item in levels:
        for learner in levels:
            challenge = difficulty.challenge_vector(item, learner)
            if not challenge:
                continue
            pool = transfer._within_level(list(transfer.TRANSFER_CONTEXTS), item)
            strict = difficulty.select_by_difficulty(pool, challenge, tolerance=1)
            wide = difficulty.select_by_difficulty(pool, challenge, tolerance=2)
            assert strict == wide, (item, learner)

    # Y con un contexto SINTÉTICO que excede el reto, sí discrimina.
    challenge = {"lexical": 2, "syntax": 2, "discourse": 2, "interaction": 2}
    over = {
        "id": "over",
        "difficulty_vector": dict.fromkeys(difficulty.DIFFICULTY_DIMENSIONS, 4),
    }
    strict = difficulty.fit(over["difficulty_vector"], challenge, tolerance=1)
    wide = difficulty.fit(over["difficulty_vector"], challenge, tolerance=2)
    assert not strict["within"]
    assert wide["within"]


def test_capacity_for_returns_a_copy_and_unknown_is_empty():
    vector = difficulty.capacity_for("b1")
    assert vector == difficulty.CEFR_CAPACITY["B1"]
    vector["lexical"] = 99
    assert difficulty.CEFR_CAPACITY["B1"]["lexical"] != 99
    for unknown in ("", None, "Pre-A1", "no-existe", 42):
        assert difficulty.capacity_for(unknown) == {}


# ------------------------------------------------------------ challenge vector


def test_challenge_vector_is_the_max_per_dimension():
    item = difficulty.capacity_for("A1")
    learner = difficulty.capacity_for("C2")
    challenge = difficulty.challenge_vector("A1", "C2")
    for dimension in difficulty.DIFFICULTY_DIMENSIONS:
        assert challenge[dimension] == max(item[dimension], learner[dimension])
    # El techo del ítem no puede REDUCIR el reto del alumno avanzado.
    assert challenge == learner


def test_challenge_vector_without_levels_is_empty():
    assert difficulty.challenge_vector("", "") == {}
    assert difficulty.challenge_vector("Pre-A1", "no-existe") == {}
    # Un solo nivel reconocible basta: el otro lado no aporta dimensiones.
    assert difficulty.challenge_vector("B1", "") == difficulty.capacity_for("B1")
    assert difficulty.challenge_vector("", "A2") == difficulty.capacity_for("A2")


def test_challenge_vector_distinguishes_vectors_with_the_same_mean():
    # El motivo del P1-02: (5,1,5,1) y (3,3,3,3) comparten media (3) pero NO son
    # el mismo reto. El motor los distingue dimensión a dimensión.
    challenge = {"lexical": 3, "syntax": 3, "discourse": 3, "interaction": 3}
    spiky = {"lexical": 5, "syntax": 1, "discourse": 5, "interaction": 1}
    flat = {"lexical": 3, "syntax": 3, "discourse": 3, "interaction": 3}
    spiky_fit = difficulty.fit(spiky, challenge)
    flat_fit = difficulty.fit(flat, challenge)
    assert spiky_fit["distance"] == 8
    assert flat_fit["distance"] == 0
    assert spiky_fit["max_overshoot"] == 2
    assert flat_fit["max_overshoot"] == 0


# ------------------------------------------------------------------- fit


def test_fit_measures_distance_overshoot_and_tolerance():
    challenge = {"lexical": 3, "syntax": 3, "discourse": 3, "interaction": 3}
    assert difficulty.fit(challenge, challenge) == {
        "dimensions": 4,
        "dimensions_compared": 4,
        "dimensions_expected": 4,
        "coverage": 1.0,
        "distance": 0,
        "max_overshoot": 0,
        "within": True,
    }
    harder = {"lexical": 5, "syntax": 2, "discourse": 3, "interaction": 4}
    result = difficulty.fit(harder, challenge, tolerance=1)
    assert result["dimensions"] == 4
    assert result["distance"] == 2 + 1 + 0 + 1
    assert result["max_overshoot"] == 2
    assert result["within"] is False
    # Con la tolerancia amplia (suelo estimado/declarado) el mismo contexto entra.
    assert difficulty.fit(harder, challenge, tolerance=2)["within"] is True


def test_fit_with_empty_or_invalid_vectors_is_vacuous():
    # Reto VACÍO: encaje vacuo legítimo (no había nada que filtrar).
    assert difficulty.fit({}, {})["within"] is True
    assert difficulty.fit({}, {})["coverage"] == 1.0
    assert difficulty.fit({"lexical": 3}, {})["within"] is True
    # Reto DECLARADO sin dimensiones comunes: cobertura 0 y NO hay encaje
    # (V3.52.1, P1-01: antes devolvía within=True con distance=0).
    empty = difficulty.fit(None, {"lexical": 3})
    assert empty["dimensions"] == 0
    assert empty["dimensions_expected"] == 1
    assert empty["coverage"] == 0.0
    assert empty["within"] is False
    # Vector PARCIAL: se compara lo común, pero la cobertura incompleta no encaja.
    partial = difficulty.fit({"lexical": 5}, {"lexical": 3, "syntax": 3})
    assert partial["dimensions"] == 1
    assert partial["dimensions_expected"] == 2
    assert partial["coverage"] == 0.5
    assert partial["distance"] == 2
    assert partial["within"] is False


def test_normalize_vector_ignores_and_clamps():
    assert difficulty.normalize_vector(
        {"lexical": 3, "syntax": 0, "discourse": 9, "interaction": "x", "otra": 4}
    ) == {"lexical": 3, "syntax": 1, "discourse": 5}
    assert difficulty.normalize_vector(None) == {}
    assert difficulty.normalize_vector({"otra": 3}) == {}
    # Un bool no es una carga válida (evita tratar True como 1).
    assert difficulty.normalize_vector({"lexical": True}) == {}


# ------------------------------------------------------- select_by_difficulty


def _context(context_id: str, **vector: int) -> dict:
    return {"id": context_id, "difficulty_vector": dict(vector)}


def test_select_prefers_the_closest_within_tolerance():
    challenge = {"lexical": 3, "syntax": 3, "discourse": 3, "interaction": 3}
    pool = [
        _context("too_hard", lexical=5, syntax=5, discourse=5, interaction=5),
        _context("tolerated", lexical=4, syntax=4, discourse=4, interaction=4),
        _context("perfect", lexical=3, syntax=3, discourse=3, interaction=3),
        _context("flat", lexical=1, syntax=1, discourse=1, interaction=1),
    ]
    chosen = difficulty.select_by_difficulty(pool, challenge, tolerance=1)
    # `too_hard` excede el reto en 2 y queda fuera; entre los que entran gana el
    # de menor distancia (encaje perfecto).
    assert [context["id"] for context in chosen] == ["perfect"]


def test_select_degrades_by_minimum_distance_never_to_the_hardest():
    # Ningún contexto entra en la tolerancia (todos exceden): se degrada al MÁS
    # CERCANO, no al más difícil.
    challenge = {"lexical": 1, "syntax": 1, "discourse": 1, "interaction": 1}
    pool = [
        _context("hardest", lexical=5, syntax=5, discourse=5, interaction=5),
        _context("middle", lexical=3, syntax=3, discourse=3, interaction=3),
        _context("closest", lexical=2, syntax=2, discourse=2, interaction=2),
    ]
    chosen = difficulty.select_by_difficulty(pool, challenge, tolerance=0)
    assert [context["id"] for context in chosen] == ["closest"]


def test_select_keeps_all_tied_at_the_minimum_distance_preserving_order():
    challenge = {"lexical": 3, "syntax": 3, "discourse": 3, "interaction": 3}
    pool = [
        _context("b", lexical=4, syntax=2, discourse=3, interaction=3),
        _context("a", lexical=2, syntax=4, discourse=3, interaction=3),
        _context("c", lexical=1, syntax=1, discourse=1, interaction=1),
    ]
    chosen = difficulty.select_by_difficulty(pool, challenge, tolerance=1)
    # `b` y `a` empatan en distancia 2; se conserva el orden de entrada.
    assert [context["id"] for context in chosen] == ["b", "a"]


def test_select_without_challenge_or_pool_is_the_identity():
    pool = [_context("a", lexical=1, syntax=1, discourse=1, interaction=1)]
    assert difficulty.select_by_difficulty(pool, {}) == pool
    assert difficulty.select_by_difficulty([], {"lexical": 3}) == []
    assert difficulty.select_by_difficulty(pool, None) == pool


def test_select_accepts_a_raw_vector_or_a_context_dict():
    challenge = {"lexical": 3, "syntax": 3, "discourse": 3, "interaction": 3}
    raw = [{"lexical": 3, "syntax": 3, "discourse": 3, "interaction": 3}]
    assert difficulty.select_by_difficulty(raw, challenge, tolerance=1) == raw


def test_select_never_rewards_a_context_without_declared_vector():
    # V3.52.1 (P1-01): antes la intersección vacía daba within=True y distance=0,
    # así que un contexto sin `difficulty_vector` ganaba siempre la selección.
    challenge = {"lexical": 3, "syntax": 3, "discourse": 3, "interaction": 3}
    pool = [
        {"id": "sin_vector"},
        _context("declarado", lexical=2, syntax=2, discourse=2, interaction=2),
    ]
    chosen = difficulty.select_by_difficulty(pool, challenge, tolerance=1)
    assert [context["id"] for context in chosen] == ["declarado"]


def test_select_degrades_by_coverage_before_distance():
    # Ningún contexto entra en la tolerancia: se prefiere COBERTURA completa
    # aunque su distancia sea mucho mayor que la de un vector parcial.
    challenge = {"lexical": 1, "syntax": 1, "discourse": 1, "interaction": 1}
    pool = [
        _context("parcial", lexical=2, syntax=2),
        _context("completo", lexical=5, syntax=5, discourse=5, interaction=5),
    ]
    chosen = difficulty.select_by_difficulty(pool, challenge, tolerance=0)
    assert [context["id"] for context in chosen] == ["completo"]


def test_tolerance_for_is_strict_only_for_demonstrated():
    assert difficulty.tolerance_for("demonstrated") == difficulty.DIFFICULTY_TOLERANCE
    assert (
        difficulty.tolerance_for("estimated")
        == difficulty.DIFFICULTY_TOLERANCE_ESTIMATED
    )
    for source in ("practice", "none", "", None):
        assert (
            difficulty.tolerance_for(source)
            == difficulty.DIFFICULTY_TOLERANCE_ESTIMATED
        )
    assert difficulty.DIFFICULTY_TOLERANCE == 1
    assert difficulty.DIFFICULTY_TOLERANCE_ESTIMATED == 2


# ------------------------------------------- integración con el banco real


def test_a1_item_with_c2_learner_never_exceeds_the_item_ceiling():
    # La preocupación explícita de la auditoría: el TECHO del ítem manda aunque
    # el alumno sea mucho más avanzado.
    got = transfer.context_for("travel", level="A1", learner_level="C2")
    assert transfer.cefr_index(got["cefr"]) <= transfer.cefr_index("A1")
    # El reto objetivo sí refleja la capacidad del alumno C2.
    assert got["difficulty_fit"]["challenge"] == difficulty.capacity_for("C2")


def test_learner_level_source_selects_the_tolerance_in_the_payload():
    demonstrated = transfer.context_for(
        "travel", level="B1", learner_level="C1", learner_level_source="demonstrated"
    )
    estimated = transfer.context_for(
        "travel", level="B1", learner_level="C1", learner_level_source="estimated"
    )
    assert demonstrated["learner_level_source"] == "demonstrated"
    assert demonstrated["difficulty_fit"]["tolerance"] == 1
    assert estimated["difficulty_fit"]["tolerance"] == 2
    # Mismo reto objetivo: la fuente solo cambia el margen admitido.
    assert demonstrated["difficulty_fit"]["challenge"] == (
        estimated["difficulty_fit"]["challenge"]
    )


def test_unknown_source_degrades_to_the_wide_tolerance():
    got = transfer.context_for("travel", level="B1", learner_level="C1")
    assert got["learner_level_source"] == ""
    expected = difficulty.DIFFICULTY_TOLERANCE_ESTIMATED
    assert got["difficulty_fit"]["tolerance"] == expected


def test_difficulty_fit_shape_is_stable_across_returns():
    keys = {
        "challenge",
        "dimensions",
        "dimensions_compared",
        "dimensions_expected",
        "coverage",
        "distance",
        "max_overshoot",
        "within",
        "tolerance",
    }
    for got in (
        transfer.context_for("travel", level="B1"),
        transfer.context_for("travel", level="B1", learner_level="C2"),
        transfer.context_for("travel", used_context_ids=[
            transfer.context_id_for(context) for context in transfer.TRANSFER_CONTEXTS
        ]),
    ):
        assert keys <= set(got["difficulty_fit"])
        assert isinstance(got["difficulty_fit"]["within"], bool)


# ------------------------------------------------------------- contrato HTTP


def test_api_exposes_learner_level_source_and_difficulty_fit(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B1")
    # Nivel demostrado cacheado (A2) y estimado (C1): el suelo es el demostrado.
    profile_repo.set_level_state(
        uid, estimated_level="C1", demonstrated_level="A2"
    )
    with TestClient(app) as client:
        res = client.get(
            "/api/vocabulary/drill/transfer-context",
            params={"word": "travel", "user_id": uid},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["learner_level"] == "A2"
    assert body["learner_level_source"] == "demonstrated"
    assert body["difficulty_fit"]["tolerance"] == difficulty.DIFFICULTY_TOLERANCE
    expected_challenge = difficulty.challenge_vector("B1", "A2")
    assert body["difficulty_fit"]["challenge"] == expected_challenge
    # V3.52.1 (P1-01): la cobertura dimensional viaja en el payload. Los 20
    # contextos reales declaran las 4 dimensiones, así que aquí es completa.
    assert body["difficulty_fit"]["coverage"] == 1.0
    assert body["difficulty_fit"]["dimensions_expected"] == len(expected_challenge)
    assert body["difficulty_fit"]["dimensions_compared"] == len(expected_challenge)
    # Aditivo: los campos de V3.47/V3.50/V3.51 siguen presentes.
    assert body["cefr"] in CEFR_LEVELS
    assert body["difficulty"] == transfer.difficulty_from_vector(
        body["difficulty_vector"]
    )
    assert body["skills"]


def test_get_and_post_share_the_level_source(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B2")
    profile_repo.set_level_state(
        uid, estimated_level="B2", demonstrated_level=""
    )
    with TestClient(app) as client:
        served = client.get(
            "/api/vocabulary/drill/transfer-context",
            params={"word": "travel", "user_id": uid},
        ).json()
        attempt = client.post(
            "/api/vocabulary/drill/transfer-attempt",
            params={"user_id": uid},
            json={
                "word": "travel",
                "text": "I travel to work by train every single day.",
            },
        ).json()
    # Paridad GET↔POST: el contexto derivado usa el MISMO suelo y tolerancia.
    assert attempt["context_id"] == served["context_id"]
    assert served["learner_level_source"] == "estimated"


def test_legacy_profile_column_still_feeds_the_drill(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B1")
    # Fila migrada de V3.51: solo `cefr_level` tiene valor.
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "INSERT INTO learning_profile "
            "(user_id, cefr_level, estimated_level, demonstrated_level, updated_at) "
            "VALUES (?, 'C1', '', '', '2026-01-01T00:00:00+00:00')",
            (uid,),
        )
    got = transfer.context_for(
        "travel",
        level="B1",
        learner_level="C1",
        learner_level_source="practice",
    )
    assert got["learner_level"] == "C1"
    assert got["learner_level_source"] == "practice"
