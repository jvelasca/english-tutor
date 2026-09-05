"""Invariantes pedagógicas de V3.13 (Calibración de evidencia).

Suite que fija las reglas inmutables R1–R7 de la Constitución §1.1 y la lectura
honesta de los claims en verde:

- `practice_route_never_returns_demonstrated`  (R1/R2: práctica ≠ demostrado)
- `four_c2_questions_cannot_prove_c2`          (R7: muestra pequeña ≠ competencia)
- `vocab_alone_cannot_prove_cefr`              (R3: vocabulary ≠ nivel)
- `listening_practice_does_not_certify_level`  (R2: práctica no certifica)
- `mastery_requires_minimum_evidence`          (§6.4: suelo de muestras)
- `mc_recognition_alone_cannot_demonstrate`    (R5: reconocimiento ≠ producción)
- `current_level_is_material_not_student_level` (R4: sugerencia de material)
"""
from services import quiz_routes as engine
from services.competence import (
    PRODUCTION_SKILLS,
    SUPPORT_SKILLS,
    competence_state,
    competence_states,
)
from services.mastery import MASTERY_SKILLS


def _entry(
    *,
    score: float = 0.0,
    confidence: float = 0.0,
    evidence_count: int = 0,
    evidence_by_kind: dict | None = None,
    production_count: int = 0,
    routes: list[dict] | None = None,
) -> dict:
    entry = {
        "skill": "grammar",
        "score": score,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "evidence_by_kind": evidence_by_kind or {},
        "production_count": production_count,
        "review_due": False,
    }
    if routes is not None:
        entry["routes"] = routes
    return entry


# --- R1/R2: la práctica nunca devuelve demonstrated --------------------------


def test_practice_route_never_returns_demonstrated():
    for skill in ("grammar", "vocabulary"):
        rows: list[dict] = []
        for level in engine.LEVEL_ORDER:
            for c in engine.checks_for_level(skill, level):
                rows.append({"check_id": c["check_id"], "passed": True})
        comp = engine.route_competence(skill, rows)
        states = {c["level"]: c["state"] for c in comp}
        assert "demonstrated" not in set(states.values())
        # Todo dominado es material funcional a lo sumo.
        assert all(s in ("functional",) for s in states.values())


# --- R7: 4 preguntas de C2 no prueban C2 -------------------------------------


def test_four_c2_questions_cannot_prove_c2():
    """Dominar el banco corto de grammar C2 (4 MC + 4 CP = 8) pasa la puerta de
    la ruta (mide práctica sobre el banco disponible) pero queda en evidence
    depth LOW: la práctica no produce evidencia de competencia C2."""
    c2 = engine.checks_for_level("grammar", "C2")
    assert 0 < len(c2) < engine.QUIZ_SHORT_BANK
    rows = [{"check_id": c["check_id"], "passed": True} for c in c2]
    gate = engine.route_gate("grammar", "C2", rows)
    assert gate["passed"] is True
    assert gate["practice_depth"] == "low"
    # El Student Model no recibe esta práctica: la competencia formal sigue en
    # not_started sin evidencia, y jamás "C2 grammar demonstrated".
    record = competence_state(None, "grammar", "C2")
    assert record["state"] == "not_started"
    assert record["demonstrated"] is False


def test_short_bank_coverage_does_not_lift_to_medium():
    """Un banco corto dominado declara practice coverage con evidence depth LOW;
    la profundidad media exige un banco representativo (normal). C2 es hoy el
    único banco corto de grammar (4 MC + 4 CP = 8): B2 se normalizó en V3.13 P1
    al añadir la producción controlada al banco."""
    for level in ("C2",):
        bank = engine.checks_for_level("grammar", level)
        rows = [{"check_id": c["check_id"], "passed": True} for c in bank]
        gate = engine.route_gate("grammar", level, rows)
        assert gate["short_bank"] is True
        assert gate["passed"] is True
        assert gate["practice_depth"] == "low"
    # B2 ya no es corto: su banco (8 MC + 6 CP ≥ 12) alcanza la profundidad
    # media al dominarse, pero nunca demuestra el nivel (la ruta es práctica).
    b2 = engine.checks_for_level("grammar", "B2")
    rows = [{"check_id": c["check_id"], "passed": True} for c in b2]
    gate = engine.route_gate("grammar", "B2", rows)
    assert gate["short_bank"] is False
    assert gate["practice_depth"] == "medium"


# --- R3: Vocabulary no prueba CEFR -------------------------------------------


def test_vocab_alone_cannot_prove_cefr():
    """Vocabulary es condición de apoyo (§3), nunca puerta de nivel: aunque la
    evidencia de vocabulario sea perfecta y con retención, la destreza se capa
    en FUNCTIONAL y ninguna otra destreza se enciende."""
    entry = _entry(
        score=1.0,
        confidence=1.0,
        evidence_count=8,
        evidence_by_kind={"familiar": 6, "delayed": 2},
        production_count=4,
    )
    record = competence_state(entry, "vocabulary", "B1")
    assert record["state"] == "functional"
    assert record["demonstrated"] is False

    vocab_model = dict(entry)
    vocab_model["skill"] = "vocabulary"
    records = competence_states([vocab_model], "B1")
    by_skill = {r["skill"]: r for r in records}
    assert by_skill["vocabulary"]["state"] == "functional"
    assert by_skill["vocabulary"]["demonstrated"] is False
    assert all(
        by_skill[s]["state"] == "not_started" for s in by_skill if s != "vocabulary"
    )


# --- R2: la práctica de listening no certifica el nivel -----------------------


def test_listening_practice_does_not_certify_level():
    """La práctica (ruta) de listening sin retención retardada deja la
    competencia en FUNCTIONAL; solo la ruta DEMONSTRATED (con su retención
    estable ≥ 7 días) la eleva."""
    record = competence_state(
        _entry(), "listening", "A1", route={"level": "A1", "state": "functional"}
    )
    assert record["state"] == "functional"
    assert record["demonstrated"] is False

    retained = competence_state(
        _entry(), "listening", "A1", route={"level": "A1", "state": "demonstrated"}
    )
    assert retained["state"] == "demonstrated"
    assert retained["demonstrated"] is True


# --- §6.4: el dominio exige mínimo de muestras -------------------------------


def test_mastery_requires_minimum_evidence():
    """DEMONSTRATED exige el mínimo de muestras de la matriz: en C2 listening el
    suelo es 6; con 3 muestras retenidas el estado queda en FUNCTIONAL."""
    record = competence_state(
        _entry(
            score=0.9,
            confidence=0.9,
            evidence_count=3,
            evidence_by_kind={"familiar": 2, "delayed": 1},
        ),
        "listening",
        "C2",
    )
    assert record["state"] == "functional"
    assert record["demonstrated"] is False
    assert record["gate"]["matrix_min_ok"] is False
    assert record["evidence_depth"] == "low"


# --- R5: solo reconocimiento no demuestra ------------------------------------


def test_mc_recognition_alone_cannot_demonstrate():
    """Para las destrezas productivas (grammar/speaking/writing), la evidencia
    de solo reconocimiento (MC, `production_count` = 0) jamás alcanza
    DEMONSTRATED aunque exista retención retardada."""
    assert "grammar" in PRODUCTION_SKILLS
    assert "speaking" in PRODUCTION_SKILLS
    assert "writing" in PRODUCTION_SKILLS
    for skill in PRODUCTION_SKILLS:
        record = competence_state(
            _entry(
                score=0.9,
                confidence=0.9,
                evidence_count=6,
                evidence_by_kind={"familiar": 5, "delayed": 1},
            ),
            skill,
            "B1",
        )
        assert record["state"] == "functional"
        assert record["demonstrated"] is False
        assert record["gate"]["production_ok"] is False


def test_support_skills_never_demonstrate():
    assert "vocabulary" in SUPPORT_SKILLS


# --- R4: current_level es sugerencia de material -----------------------------


def test_current_level_is_material_not_student_level():
    """`current_level` devuelve siempre una sugerencia de material dentro del
    orden CEFR de práctica, nunca una banda del alumno ni 'Pre-A1'."""
    # Sin intentos: el material a practicar empieza en A1.
    assert engine.current_level("grammar", []) == "A1"
    assert engine.current_level("vocabulary", []) == "A1"
    # Con bancos dominados devuelve otro nivel del orden (repaso pendiente).
    rows: list[dict] = []
    for level in engine.LEVEL_ORDER:
        for c in engine.checks_for_level("grammar", level):
            rows.append({"check_id": c["check_id"], "passed": True})
    suggested = engine.current_level("grammar", rows)
    assert suggested in engine.LEVEL_ORDER
    # Nunca un nivel de alumno: dominar solo el banco corto de C2 no sugiere
    # "seguir en C2" — el material pendiente (A1) vuelve a ser el primero.
    c2 = engine.checks_for_level("grammar", "C2")
    rows_c2 = [{"check_id": c["check_id"], "passed": True} for c in c2]
    assert engine.current_level("grammar", rows_c2) == "A1"


def test_route_competence_never_demonstrated_for_all_mastery_skills():
    """Las rutas de práctica declaran a lo sumo FUNCTIONAL; la demostración vive
    en el Student Model (competence_state), no en la práctica."""
    comp = engine.route_competence("grammar", [])
    assert {c["state"] for c in comp} == {"not_started"}


# --- Coherencia estructural --------------------------------------------------


def test_mastery_skills_alignment():
    """Las destrezas con producción obligatoria y las de apoyo son destrezas
    canónicas del registro (coherencia del modelo de competencias)."""
    assert PRODUCTION_SKILLS and SUPPORT_SKILLS
    assert set(PRODUCTION_SKILLS).isdisjoint(SUPPORT_SKILLS)
    assert set(PRODUCTION_SKILLS) | set(SUPPORT_SKILLS) <= set(MASTERY_SKILLS)
