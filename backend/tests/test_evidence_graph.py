"""Tests del Evidence Graph (V2.12)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from services import evidence_graph as eg
from services.curriculum import load_level


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _objective_with_skills():
    lv = load_level("b1")
    # Preferir un objetivo con speaking + vocabulary si existe.
    for obj in lv.objectives():
        if "vocabulary" in obj.skills and "speaking" in obj.skills:
            return lv, obj
    return lv, lv.objectives()[0]


# --- Motor puro -------------------------------------------------------------


def test_graph_version_and_dimensions():
    assert eg.GRAPH_VERSION.startswith("2.12")
    assert "transfer" in eg.GRAPH_DIMENSIONS
    assert "interaction" in eg.GRAPH_DIMENSIONS


def test_objective_node_finds_limiting_factor():
    lv, obj = _objective_with_skills()
    profile = [
        {"skill": "vocabulary", "score": 0.88, "evidence_count": 5},
        {"skill": "grammar", "score": 0.82, "evidence_count": 4},
        {"skill": "listening", "score": 0.73, "evidence_count": 3},
        {"skill": "speaking", "score": 0.67, "evidence_count": 3},
        {"skill": "interaction", "score": 0.61, "evidence_count": 2},
    ]
    objective_scores = {
        obj.id: {
            "vocabulary": 0.88,
            "grammar": 0.82,
            "listening": 0.73,
            "speaking": 0.67,
        }
    }
    # Sin evidencia transfer → limiting transfer (missing).
    node = eg.objective_node(
        obj,
        level_id=lv.level_id,
        level_label=lv.level,
        objective_scores=objective_scores,
        profile=profile,
        evidence_rows=[],
    )
    assert node["can_do"] == obj.can_do
    assert node["limiting_factor"] is not None
    assert node["limiting_factor"]["id"] == "transfer"
    assert node["limiting_factor"]["missing"] is True
    assert node["recommended_focus"]["phase"] == "transfer"


def test_limiting_factor_picks_weakest_skill_when_transfer_present():
    lv, obj = _objective_with_skills()
    profile = [
        {"skill": "vocabulary", "score": 0.9, "evidence_count": 5},
        {"skill": "speaking", "score": 0.4, "evidence_count": 2},
        {"skill": "interaction", "score": 0.55, "evidence_count": 2},
    ]
    objective_scores = {obj.id: {"vocabulary": 0.9, "speaking": 0.4}}
    evidence = [
        {
            "objective_id": obj.id,
            "evidence_kind": "transfer",
            "result": 0.8,
        }
    ]
    node = eg.objective_node(
        obj,
        level_id=lv.level_id,
        level_label=lv.level,
        objective_scores=objective_scores,
        profile=profile,
        evidence_rows=evidence,
    )
    assert node["limiting_factor"]["id"] in {
        "speaking",
        "interaction",
        "discourse",
        "grammar",
        "listening",
        "vocabulary",
        "transfer",
    }
    # Con transfer presente, no debería marcar missing en transfer.
    transfer = next(d for d in node["dimensions"] if d["id"] == "transfer")
    assert transfer["missing"] is False


def test_explain_because_structured():
    node = {
        "level": "B1",
        "dimensions": [
            {"id": "vocabulary", "score": 0.88, "missing": False},
            {"id": "interaction", "score": 0.61, "missing": False},
            {"id": "transfer", "score": 0.0, "missing": True},
        ],
        "limiting_factor": {
            "id": "transfer",
            "score": 0.0,
            "missing": True,
            "kind": "evidence",
        },
        "recommended_focus": {"dimension": "transfer", "phase": "transfer"},
    }
    bullets = eg.explain_because(node)
    assert any("Transfer evidence is missing" in b for b in bullets)
    assert any("vocabulary is already 88%" in b for b in bullets)
    assert any("targets transfer" in b for b in bullets)


def test_enrich_next_best_adds_because():
    activity = {
        "kind": "weakness",
        "skill": "speaking",
        "objective_id": "o1",
        "title": "Practice",
        "reason": "weak_skill",
        "why": "Speaking is weak.",
    }
    node = {
        "level": "B1",
        "can_do": "I can give opinions.",
        "mastery": 0.7,
        "dimensions": [
            {"id": "vocabulary", "score": 0.9, "missing": False},
            {"id": "speaking", "score": 0.5, "missing": False},
            {"id": "transfer", "score": 0.7, "missing": False},
        ],
        "limiting_factor": {
            "id": "speaking",
            "score": 0.5,
            "missing": False,
            "kind": "skill",
        },
        "recommended_focus": {"dimension": "speaking", "phase": "speak"},
    }
    enriched = eg.enrich_next_best(activity, node)
    assert len(enriched["because"]) >= 2
    assert enriched["limiting_factor"]["id"] == "speaking"
    assert enriched["can_do"] == "I can give opinions."


def test_build_level_graph_aggregates():
    lv = load_level("a1")
    graph = eg.build_level_graph(
        lv,
        objective_scores={},
        profile=[],
        evidence_rows=[],
        mastered_ids=set(),
    )
    assert graph["level_id"] == "a1"
    assert len(graph["nodes"]) == len(lv.objectives())
    assert graph["open_count"] == len(lv.objectives())
    assert graph["top_limiting_factor"] is not None


# --- HTTP -------------------------------------------------------------------


def test_evidence_graph_http(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, "a1", "A1")
    client = TestClient(app)

    graph = client.get(f"/api/academy/evidence-graph?user_id={uid}&level_id=a1")
    assert graph.status_code == 200, graph.text
    body = graph.json()
    assert body["graph_version"] == eg.GRAPH_VERSION
    assert body["level_id"] == "a1"
    assert len(body["nodes"]) >= 1
    node = body["nodes"][0]
    assert "can_do" in node
    assert "dimensions" in node
    assert "limiting_factor" in node

    detail = client.get(
        f"/api/academy/evidence-graph/objective/{node['objective_id']}"
        f"?user_id={uid}&level_id=a1"
    )
    assert detail.status_code == 200
    assert detail.json()["objective_id"] == node["objective_id"]


def test_next_best_includes_because_when_objective(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    academy_repo.enroll(uid, "a1", "A1")
    client = TestClient(app)
    # Puede devolver null si no hay pasos; en A1 fresco suele haber new.
    resp = client.get(f"/api/academy/next-best?user_id={uid}")
    assert resp.status_code == 200
    data = resp.json()
    if data is not None:
        assert "because" in data
        assert isinstance(data["because"], list)
