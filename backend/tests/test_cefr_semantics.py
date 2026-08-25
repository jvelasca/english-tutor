"""Tests de la semántica del perfil CEFR (V1.5.2).

Cubre el overall ponderado con mínimos críticos (sustituye a la media aritmética)
y la exposición de sub-destrezas de listening dentro del perfil.
"""

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services import academy as academy_svc
from services.curriculum import load_level
from services.listening import QUESTION_BANK


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _entry(skill, score, evidence_count):
    return {"skill": skill, "score": score, "evidence_count": evidence_count}


def test_overall_cefr_score_empty():
    assert academy_svc.overall_cefr_score([]) == 0.0


def test_overall_cefr_score_is_weighted_not_arithmetic():
    profile = [
        _entry("vocabulary", 1.0, 3),
        _entry("grammar", 1.0, 3),
        _entry("pronunciation", 0.0, 0),
        _entry("listening", 0.0, 0),
        _entry("speaking", 0.0, 0),
        _entry("reading", 0.0, 0),
        _entry("writing", 0.0, 0),
    ]
    # Ponderado: 0.15*1 + 0.20*1 = 0.35 (≠ media aritmética 2/7 ≈ 0.286).
    assert academy_svc.overall_cefr_score(profile) == 0.35


def test_overall_cefr_score_critical_minimum_caps():
    profile = [
        _entry("grammar", 0.2, 3),  # crítica y débil
        _entry("vocabulary", 1.0, 3),
        _entry("pronunciation", 1.0, 3),
        _entry("listening", 1.0, 3),
        _entry("speaking", 1.0, 3),
        _entry("reading", 1.0, 3),
        _entry("writing", 1.0, 3),
    ]
    # Ponderado ≈ 0.84, pero la gramática (crítica) cae bajo 0.4 → cap en 0.4.
    assert academy_svc.overall_cefr_score(profile) == 0.4


def test_overall_cefr_score_critical_min_ignored_without_evidence():
    profile = [
        _entry("grammar", 0.0, 0),  # sin evidencia: no penaliza
        _entry("vocabulary", 1.0, 3),
        _entry("pronunciation", 1.0, 3),
        _entry("listening", 1.0, 3),
        _entry("speaking", 1.0, 3),
        _entry("reading", 1.0, 3),
        _entry("writing", 1.0, 3),
    ]
    # Ponderado = 0.15+0.10+0.15+0.15+0.10+0.15 = 0.80 (grammar sin evidencia no resta
    # ni activa el mínimo crítico).
    assert academy_svc.overall_cefr_score(profile) == 0.80


def test_critical_skills_empty_when_none_below_minimum():
    profile = [
        _entry("grammar", 0.9, 3),
        _entry("vocabulary", 0.9, 3),
    ]
    assert academy_svc.critical_skills(profile) == []


def test_critical_skills_flags_weak_critical():
    profile = [
        _entry("grammar", 0.2, 3),  # crítica y débil
        _entry("vocabulary", 1.0, 3),
    ]
    assert academy_svc.critical_skills(profile) == ["grammar"]


def test_critical_skills_ignored_without_evidence():
    profile = [
        _entry("grammar", 0.0, 0),  # sin evidencia: no es crítica todavía
        _entry("vocabulary", 1.0, 3),
    ]
    assert academy_svc.critical_skills(profile) == []


def test_profile_exposes_listening_subskills(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        client.post(
            "/api/listening/answer",
            params={"user_id": a},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
        r = client.get(
            "/api/academy/profile", params={"user_id": a, "level_id": "a1"}
        )
    assert r.status_code == 200
    skills = {s["skill"]: s for s in r.json()["skills"]}
    listening = skills["listening"]
    assert listening["subskills"], "la destreza 'listening' no expone subskills"
    by_sub = {s["skill"]: s for s in listening["subskills"]}
    assert by_sub[q["skill"]]["attempts"] == 1


def test_profile_exposes_critical_skills(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    lv = load_level("a1")
    obj = next(
        o for o in lv.objectives() if any(c.skill == "grammar" for c in o.checks)
    )
    wrong = {c.id: (c.correct_index + 1) % len(c.options) for c in obj.checks}
    with TestClient(app) as client:
        r = client.post(
            "/api/academy/objective/assessment",
            params={"user_id": a},
            json={"level_id": "a1", "objective_id": obj.id, "answers": wrong},
        )
        assert r.status_code == 200
        prof = client.get(
            "/api/academy/profile", params={"user_id": a, "level_id": "a1"}
        )
    assert prof.status_code == 200
    body = prof.json()
    assert "critical_skills" in body
    assert "grammar" in body["critical_skills"]
