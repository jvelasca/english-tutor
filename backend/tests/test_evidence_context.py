"""V3.25 fase 1 — contexto del evento de evidencia (F-L6/F-L7).

Fija la infraestructura de eventos con contexto sobre `academy_evidence`
(`context_id`/`activity_id`/`task_type`/`support_level`): migración idempotente,
persistencia y lectura en el repositorio, escritura desde los builders y
enriquecimiento por el emisor en `_record_evidence_validated`, sin cambiar los
agregados actuales (`evidence_count`/`evidence_by_kind`).
"""

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import academy as academy_svc
from services.curriculum import ASSESSMENT_VERSION, load_level


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _assessable_objective():
    lv = load_level("a1")
    obj = next(o for o in lv.objectives() if o.checks)
    return lv, obj


# --- Migración idempotente ------------------------------------------------


def test_migration_adds_context_columns(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    from repositories.db import _conn

    with _conn() as conn:
        cols = {
            row[1] for row in conn.execute("PRAGMA table_info(academy_evidence)")
        }
    assert {"context_id", "activity_id", "task_type", "support_level"} <= cols
    # Segunda inicialización (idempotencia): no debe fallar ni duplicar columnas.
    db.init_db()
    rows = academy_repo.list_evidence(a)
    assert rows == []


def test_legacy_row_writes_default_empty_context(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    ok = academy_repo.record_evidence(
        a,
        "a1",
        "",
        "grammar",
        "i1",
        item_type="mcq",
        source="exam",
        result=1.0,
        curriculum_version="v1",
        assessment_version="exam-a1",
        evidence_kind="transfer",
    )
    assert ok is True
    rows = academy_repo.list_evidence(a)
    assert len(rows) == 1
    row = rows[0]
    assert row["context_id"] == ""
    assert row["activity_id"] == ""
    assert row["task_type"] == ""
    assert row["support_level"] == ""


def test_record_evidence_persists_context_fields(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    ok = academy_repo.record_evidence(
        a,
        "a1",
        "obj-1",
        "speaking",
        "overall",
        item_type="speaking",
        source="speaking",
        result=0.9,
        curriculum_version="v1",
        assessment_version="rubric-v1",
        evidence_kind="transfer",
        context_id="mission:m1",
        activity_id="speaking_mission",
        task_type="role_play",
        support_level="independent",
    )
    assert ok is True
    rows = academy_repo.list_evidence(a)
    assert len(rows) == 1
    row = rows[0]
    assert row["context_id"] == "mission:m1"
    assert row["activity_id"] == "speaking_mission"
    assert row["task_type"] == "role_play"
    assert row["support_level"] == "independent"


# --- Builders y validación ------------------------------------------------


def test_evidence_from_items_embeds_context():
    lv, obj = _assessable_objective()
    check = obj.checks[0]
    records = academy_svc.evidence_from_items(
        obj.checks,
        {check.id: check.correct_index},
        level_id="a1",
        objective_id=obj.id,
        source="objective_assessment",
        curriculum_version=lv.version,
        assessment_version=ASSESSMENT_VERSION,
        context_id="objective:o1",
        activity_id="objective_assessment",
        task_type="assessment",
        support_level="cued",
    )
    assert records
    for record in records:
        assert record["context_id"] == "objective:o1"
        assert record["activity_id"] == "objective_assessment"
        assert record["task_type"] == "assessment"
        assert record["support_level"] == "cued"


def test_support_level_unknown_is_invalid():
    lv, obj = _assessable_objective()
    check = obj.checks[0]
    record = academy_svc.evidence_from_items(
        obj.checks,
        {check.id: check.correct_index},
        level_id="a1",
        objective_id=obj.id,
        source="objective_assessment",
        curriculum_version=lv.version,
        assessment_version=ASSESSMENT_VERSION,
    )[0]
    record["support_level"] = "copy-paste"
    errors = academy_svc.evidence_record_errors(record, user_id="u1", level=lv)
    assert any("support_level" in e for e in errors)


def test_support_level_canonical_is_valid():
    lv, obj = _assessable_objective()
    check = obj.checks[0]
    record = academy_svc.evidence_from_items(
        obj.checks,
        {check.id: check.correct_index},
        level_id="a1",
        objective_id=obj.id,
        source="objective_assessment",
        curriculum_version=lv.version,
        assessment_version=ASSESSMENT_VERSION,
        support_level="independent",
    )[0]
    assert academy_svc.evidence_record_errors(record, user_id="u1", level=lv) == []


def test_support_level_absent_is_valid():
    lv, obj = _assessable_objective()
    check = obj.checks[0]
    record = academy_svc.evidence_from_items(
        obj.checks,
        {check.id: check.correct_index},
        level_id="a1",
        objective_id=obj.id,
        source="objective_assessment",
        curriculum_version=lv.version,
        assessment_version=ASSESSMENT_VERSION,
    )[0]
    assert academy_svc.evidence_record_errors(record, user_id="u1", level=lv) == []


# --- Enriquecimiento por el emisor (end-to-end) ---------------------------


def test_objective_assessment_writes_context_columns(monkeypatch, tmp_path):
    """El emisor de objective assessment declara contexto en el record funnel."""
    a = _setup(monkeypatch, tmp_path)
    lv, obj = _assessable_objective()
    checks = {c.id: c.correct_index for c in obj.checks}
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/assessment",
            params={"user_id": a},
            json={"level_id": "a1", "objective_id": obj.id, "answers": checks},
        )
    assert r.status_code == 200
    rows = academy_repo.list_evidence(a, "a1")
    assert rows
    for row in rows:
        assert row["context_id"] == f"objective:{obj.id}"
        assert row["activity_id"] == "objective_assessment"
        assert row["task_type"] == "assessment"
        # Fase 2: el emisor objective assessment declara apoyo `cued`
        # (reconocimiento con claves: MC/fill-blank del objetivo).
        assert row["support_level"] == "cued"


# --- V3.25 fase 2 — soporte por emisor y exposición en el perfil (F-L7) ---


def test_mission_evidence_declares_independent(monkeypatch, tmp_path):
    """La evidencia de speaking task/misión se declara `independent`."""
    from services import speaking as speaking_svc

    a = _setup(monkeypatch, tmp_path)
    lv = load_level("a1")
    result = speaking_svc.score_speaking("I am happy", "I am happy", 2.0)
    records = speaking_svc.evidence_from_speaking(
        result,
        level_id="a1",
        objective_id="",
        curriculum_version=lv.version,
    )
    # Se enriquece con el contexto que declara el emisor misión (fase 2).
    for r in records:
        r["support_level"] = "independent"
        assert academy_svc.evidence_record_errors(r, user_id=a, level=lv) == []


def test_profile_entry_exposes_support_levels():
    """`build_skill_profile` agrega `support_levels`/`independent_count` por
    destreza; las filas legacy (support vacío) no se cuentan."""
    lv = load_level("a1")
    skill = next(iter(lv.objectives())).skills[0]
    now = "2026-08-01T00:00:00+00:00"
    rows = [
        {
            "skill": skill,
            "evidence_kind": "familiar",
            "item_type": "mcq",
            "result": 1.0,
            "created_at": now,
            "support_level": "cued",
        },
        {
            "skill": skill,
            "evidence_kind": "familiar",
            "item_type": "speaking",
            "result": 1.0,
            "created_at": now,
            "support_level": "independent",
        },
        {
            "skill": skill,
            "evidence_kind": "familiar",
            "item_type": "speaking",
            "result": 1.0,
            "created_at": now,
            "support_level": "spontaneous",
        },
        {
            "skill": skill,
            "evidence_kind": "familiar",
            "item_type": "speaking",
            "result": 1.0,
            "created_at": now,
            "support_level": "",  # legacy: no se cuenta
        },
    ]
    profile = academy_svc.build_skill_profile(lv, {}, rows, now=now)
    entry = next(e for e in profile if e["skill"] == skill)
    assert entry["support_levels"]["cued"] == 1
    assert entry["support_levels"]["independent"] == 1
    assert entry["support_levels"]["spontaneous"] == 1
    assert entry["independent_count"] == 2
    assert entry["support_levels"]["guided"] == 0


# --- V3.25 fase 3 — transfer por contextos/tareas distintas (F-L6) --------


def test_evidence_context_count_distinct_only():
    """`evidence_context_count`: dos filas del mismo contexto cuentan 1;
    las filas legacy sin contexto no cuentan."""
    rows = [
        {
            "evidence_kind": "transfer",
            "context_id": "assessment_v2:unit:1",
            "activity_id": "assessment_v2:unit",
            "task_type": "unit",
        },
        {
            "evidence_kind": "transfer",
            "context_id": "assessment_v2:unit:1",
            "activity_id": "assessment_v2:unit",
            "task_type": "unit",
        },
        {
            "evidence_kind": "transfer",
            "context_id": "assessment_v2:unit:2",
            "activity_id": "assessment_v2:unit",
            "task_type": "unit",
        },
        {
            "evidence_kind": "transfer",
            "context_id": "",
            "activity_id": "",
            "task_type": "",
        },
        {
            "evidence_kind": "familiar",
            "context_id": "objective:o1",
            "activity_id": "objective_assessment",
            "task_type": "assessment",
        },
    ]
    assert academy_svc.evidence_context_count(rows, "transfer") == 2
    assert academy_svc.evidence_context_count(rows) == 3  # incluye familiar


def test_profile_entry_distinct_contexts_by_kind():
    """`build_skill_profile` agrega `distinct_contexts_by_kind` a la entrada."""
    lv = load_level("a1")
    skill = next(iter(lv.objectives())).skills[0]
    now = "2026-08-01T00:00:00+00:00"

    def _row(kind, cid):
        return {
            "skill": skill,
            "evidence_kind": kind,
            "item_type": "mcq",
            "result": 1.0,
            "created_at": now,
            "context_id": cid,
            "activity_id": "a",
            "task_type": "t",
        }

    rows = [
        _row("transfer", "c1"),
        _row("transfer", "c1"),  # mismo contexto: una experiencia
        _row("transfer", "c2"),
        _row("familiar", "c3"),
    ]
    profile = academy_svc.build_skill_profile(lv, {}, rows, now=now)
    entry = next(e for e in profile if e["skill"] == skill)
    assert entry["evidence_by_kind"]["transfer"] == 3  # filas
    assert entry["distinct_contexts_by_kind"]["transfer"] == 2  # experiencias
    assert entry["distinct_contexts_by_kind"]["familiar"] == 1


# --- V3.26 F-C4 — evidencia legacy sin `context_id` marcada por destreza ------


def test_profile_entry_reports_legacy_context_rows():
    """F-C4: `build_skill_profile` cuenta las filas sin `context_id`
    (`legacy_context_rows`) y marca `legacy_context_used` cuando algún kind con
    filas no tiene NINGÚN contexto conocido (el gate retrocede a filas)."""
    lv = load_level("a1")
    skill = next(iter(lv.objectives())).skills[0]
    now = "2026-08-01T00:00:00+00:00"

    def _row(kind, cid=""):
        return {
            "skill": skill,
            "evidence_kind": kind,
            "item_type": "mcq",
            "result": 1.0,
            "created_at": now,
            "context_id": cid,
            "activity_id": "",
            "task_type": "",
        }

    # Solo filas legacy (sin contexto): todas se cuentan y el kind retrocede.
    rows = [_row("familiar"), _row("familiar"), _row("transfer")]
    profile = academy_svc.build_skill_profile(lv, {}, rows, now=now)
    entry = next(e for e in profile if e["skill"] == skill)
    assert entry["legacy_context_rows"] == 3
    assert entry["legacy_context_used"] is True

    # Con contextos declarados en todos los kinds: sin filas legacy ni fallback.
    rows2 = [
        _row("familiar", "c1"),
        _row("transfer", "c2"),
        _row("transfer", "c3"),
    ]
    profile2 = academy_svc.build_skill_profile(lv, {}, rows2, now=now)
    entry2 = next(e for e in profile2 if e["skill"] == skill)
    assert entry2["legacy_context_rows"] == 0
    assert entry2["legacy_context_used"] is False

    # Mezcla: `familiar` con contexto y `transfer` solo legacy → el fallback se
    # dispara por el kind sin contextos (F-L6 no aplica a esas filas).
    rows3 = [_row("familiar", "c1"), _row("transfer"), _row("transfer")]
    profile3 = academy_svc.build_skill_profile(lv, {}, rows3, now=now)
    entry3 = next(e for e in profile3 if e["skill"] == skill)
    assert entry3["legacy_context_rows"] == 2
    assert entry3["legacy_context_used"] is True


def test_mastery_gate_requires_distinct_transfer_contexts():
    """F-L6: dos transfer del mismo contexto NO satisfacen el gate MASTERED
    cuando el perfil conoce los contextos; con contextos distintos, sí."""
    from services import assessment_v2 as av2

    counts = {"familiar": 2, "transfer": 2, "novel": 0, "delayed": 1}
    # Sin contextos (legacy): retrocede a filas → met, con fallback marcado.
    gate = av2.mastery_evidence_gate(counts)
    assert gate["met"] is True
    assert gate["legacy_fallback"] is True
    # Un solo contexto de transfer para 2 filas → bloqueado, sin fallback.
    gate = av2.mastery_evidence_gate(
        counts, context_counts={"familiar": 2, "transfer": 1, "delayed": 1}
    )
    assert gate["met"] is False
    assert "transfer" in gate["missing"]
    assert gate["counts"]["transfer_contexts"] == 1
    assert gate["legacy_fallback"] is False
    # Dos contextos distintos → met, sin fallback.
    gate2 = av2.mastery_evidence_gate(
        counts, context_counts={"familiar": 2, "transfer": 2, "delayed": 1}
    )
    assert gate2["met"] is True
    assert gate2["legacy_fallback"] is False


def test_mastery_gate_requires_distinct_familiar_contexts():
    """F-L6: familiar×2 exige dos experiencias distintas cuando se conocen."""
    from services import assessment_v2 as av2

    counts = {"familiar": 2, "transfer": 2, "novel": 0, "delayed": 1}
    gate = av2.mastery_evidence_gate(
        counts, context_counts={"familiar": 1, "transfer": 2, "delayed": 1}
    )
    assert gate["met"] is False
    assert "practice" in gate["missing"]


def test_readiness_uses_distinct_transfer_contexts_when_known():
    """F-L6: readiness B2 (transfer_required=2) no queda ready con 2 filas del
    mismo contexto; queda ready con 2 contextos distintos."""
    from services import adaptive

    def _entry(distinct_transfer):
        return {
            "skill": "listening",
            "score": 0.9,
            "confidence": 0.9,
            "evidence_count": 4,
            "evidence_by_kind": {"transfer": 2, "novel": 0},
            "distinct_contexts_by_kind": {
                "transfer": distinct_transfer,
                "novel": 0,
            },
        }

    blocked = adaptive.readiness([_entry(1)], "B2")
    by_skill = {s["skill"]: s for s in blocked["skills"]}
    assert by_skill["listening"]["ready"] is False
    assert by_skill["listening"]["transfer_count"] == 1
    assert blocked["blocking_skills"] == ["listening"]

    ready = adaptive.readiness([_entry(2)], "B2")
    by_skill2 = {s["skill"]: s for s in ready["skills"]}
    assert by_skill2["listening"]["ready"] is True
    assert by_skill2["listening"]["transfer_count"] == 2
    assert ready["blocking_skills"] == []


# --- V3.25 fase 4 — retención longitudinal y robustez del gate (F-L4/F-L8) -


def _delayed_row(skill, created_at, result=0.95, *, context_id="retention:test:1"):
    """Fila de un retention reassessment (Assessment 2.0, kind=retention):
    `evidence_kind="delayed"`, `task_type="retention"` y `context_id` de sesión."""
    return {
        "skill": skill,
        "evidence_kind": "delayed",
        "task_type": "retention",
        "item_type": "mcq",
        "result": result,
        "source": "assessment_v2",
        "created_at": created_at,
        "context_id": context_id,
        "curriculum_version": "v1",
        "assessment_version": "assessment-v2",
    }


def _exam_row(skill, created_at, result=1.0, *, context_id="exam:a1"):
    """Fila del EXAMEN formal (baseline): `task_type="exam"`, como la escribe
    la escalera Assessment 2.0 (kind=level) y submit_exam."""
    return {
        "skill": skill,
        "evidence_kind": "transfer",
        "task_type": "exam",
        "item_type": "mcq",
        "result": result,
        "source": "assessment_v2",
        "created_at": created_at,
        "context_id": context_id,
        "curriculum_version": "v1",
        "assessment_version": "assessment-v2",
    }


def test_certification_gate_verifies_delayed_rows():
    """F-L4 + F-A3 (V3.26): el gate certifica solo con ≥2 eventos `delayed`
    verificables y con ventana (≥ RETENTION_MIN_DAYS desde el examen formal) +
    ratio (≥ RETENTION_STABLE_RATIO) válidos; una sesión con `created_at`
    corrupto no puede certificar."""
    from services import assessment_v2 as av2

    formal = "2026-08-01T00:00:00+00:00"
    delayed_at = "2026-08-08T00:00:00+00:00"  # D+7
    g_ok = av2.certification_gate(
        ["listening"],
        [
            _exam_row("listening", formal),
            _delayed_row("listening", delayed_at, context_id="retention:1"),
            _delayed_row(  # punto 2: D+14, separado
                "listening", "2026-08-15T00:00:00+00:00", 0.95,
                context_id="retention:2",
            ),
        ],
    )
    assert g_ok["certified"] is True
    assert g_ok["retention_report"]["listening"]["verified"] is True
    assert g_ok["retention_report"]["listening"]["interval_days"] == [7, 14]
    assert g_ok["retention_report"]["listening"]["stable_points"] == 2

    g_bad = av2.certification_gate(
        ["reading"],
        [_exam_row("reading", formal), _delayed_row("reading", "nunca")],
    )
    assert g_bad["certified"] is False
    assert g_bad["retention_report"]["reading"]["verified"] is False
    assert "reading" in g_bad["pending_skills"]


def test_certification_gate_requires_delayed_per_skill():
    """Sin cambios de semántica (H5): hace falta retención validada para CADA
    destreza del examen. F-A3: listening acumula sus 2 puntos y speaking sigue
    sin ninguno → el nivel NO certifica."""
    from services import assessment_v2 as av2

    formal = "2026-08-01T00:00:00+00:00"
    delayed_at = "2026-08-08T00:00:00+00:00"  # D+7
    exam_rows = [_exam_row("listening", formal), _exam_row("speaking", formal)]
    rows = exam_rows + [
        _delayed_row("listening", delayed_at, context_id="retention:1"),
        _delayed_row("listening", "2026-08-15T00:00:00+00:00", 0.95,
                     context_id="retention:2"),
    ]
    g = av2.certification_gate(["listening", "speaking"], rows)
    assert g["certified"] is False
    assert g["delayed_by_skill"] == {"listening": 2, "speaking": 0}
    assert g["pending_skills"] == ["speaking"]


def test_retention_report_multi_interval():
    """F-L8: los eventos `delayed` derivan el intervalo formal→delayed más
    largo alcanzado y las ventanas opcionales D+1/D+3/D+7/D+21 superadas."""
    from services import assessment_v2 as av2

    formal = "2026-08-01T00:00:00+00:00"
    rows = [
        _exam_row("listening", formal),
        _delayed_row(  # D+7
            "listening", "2026-08-08T00:00:00+00:00", context_id="retention:1"
        ),
        _delayed_row(  # D+20
            "listening", "2026-08-21T00:00:00+00:00", context_id="retention:2"
        ),
    ]
    g = av2.certification_gate(["listening"], rows)
    report = g["retention_report"]["listening"]
    assert report["count"] == 2
    assert report["events"] == 2
    assert report["interval_days"] == [7, 20]
    assert report["longest_interval_days"] == 20
    # 20 días cubre D+1/D+3/D+7 pero todavía no D+21.
    assert report["intervals_reached"] == [1, 3, 7]
    assert g["certified"] is True


def test_student_model_endpoint_reports_legacy_context(monkeypatch, tmp_path):
    """F-C4 (V3.26): el Student Model agrega la marca legacy del perfil
    (`legacy_context_evidence`/`legacy_context_rows`) y cada destreza expone su
    desglose (`legacy_context_rows`/`legacy_context_used`)."""
    uid = _setup(monkeypatch, tmp_path)
    lv = load_level("a1")
    obj = lv.objectives()[0]
    skill = obj.skills[0]

    def _student_model(client):
        r = client.get("/api/academy/student-model", params={"user_id": uid})
        assert r.status_code == 200
        return r.json()

    with TestClient(app) as client:
        base = _student_model(client)
        assert base["legacy_context_evidence"] is False
        assert base["legacy_context_rows"] == 0
        assert base["skills"], "el perfil A1 incluye destrezas canónicas"
        for entry in base["skills"]:
            assert entry["legacy_context_rows"] == 0
            assert entry["legacy_context_used"] is False
        # Evidencia legacy (sin `context_id`) por vía directa del repositorio.
        for i in range(2):
            academy_repo.record_evidence(
                uid,
                lv.level_id,
                obj.id,
                skill,
                f"legacy:{i}",
                item_type="mcq",
                source="objective_assessment",
                result=1.0,
                evidence_kind="familiar",
            )
        body = _student_model(client)
    entry = next(e for e in body["skills"] if e["skill"] == skill)
    assert entry["legacy_context_rows"] == 2
    assert entry["legacy_context_used"] is True
    assert body["legacy_context_rows"] == 2
    assert body["legacy_context_evidence"] is True
