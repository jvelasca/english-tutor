"""Tests de V3.21 (V20-17): carta lexicon con razón `transfer-gap`.

`sync_fsrs_cards` decide el `why` de una palabra `known` (reconocida y nunca
producida) mirando a su objetivo: si el objetivo YA tiene producción en otras
palabras, la palabra es un transfer gap real (`transfer-gap`) y no un simple
`recognition-only` (que se reserva para objetivos enteramente receptivos).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _seed_context(user_id: str, word: str, objective_id: str) -> None:
    vocabulary_repo.seed_curriculum_items(
        user_id,
        [
            {
                "word": word,
                "lemma": word,
                "cefr": "A1",
                "level_id": "a1",
                "objective_id": objective_id,
                "kind": "word",
            }
        ],
    )


def _lexicon_cards(user_id: str) -> list[dict]:
    return [
        c
        for c in academy_repo.list_fsrs_cards(user_id)
        if c["target_type"] == "lexicon"
    ]


def test_sync_marks_transfer_gap_when_objective_has_production(
    monkeypatch, tmp_path
):
    """Palabra conocida de un objetivo que YA produce -> `transfer-gap`."""
    uid = _setup(monkeypatch, tmp_path)
    objective = "obj-in-progress"
    # Otra palabra del mismo objetivo ya se produce en speaking.
    _seed_context(uid, "already-produced", objective)
    vocabulary_repo.record_exposures(uid, ["already-produced"])
    vocabulary_repo.record_production(
        uid, ["already-produced"], channel="speaking"
    )
    # La palabra objetivo: reconocida 2+ veces, nunca producida.
    _seed_context(uid, "gap-word", objective)
    vocabulary_repo.record_exposures(uid, ["gap-word"])
    vocabulary_repo.record_exposures(uid, ["gap-word"])

    from domain import academy as academy_service

    now = datetime.now(timezone.utc).isoformat()
    asyncio.run(academy_service.sync_fsrs_cards(uid, now=now))

    why = {
        c["target_id"]: c["why"] for c in _lexicon_cards(uid)
    }
    assert why["gap-word"] == "transfer-gap"
    # La palabra ya producida del objetivo no es un "gap": su carta refleja su
    # estado (learning o weak según la curva), nunca transfer-gap.
    assert why["already-produced"] in {"learning-lexicon", "weak-lexicon"}


def test_sync_keeps_recognition_only_when_objective_has_no_production(
    monkeypatch, tmp_path
):
    """Objetivo sin ninguna producción: la palabra known sigue siendo
    `recognition-only` (fase receptiva entera, sin gap que cerrar)."""
    uid = _setup(monkeypatch, tmp_path)
    _seed_context(uid, "fresh", "obj-receptive-only")
    vocabulary_repo.record_exposures(uid, ["fresh"])
    vocabulary_repo.record_exposures(uid, ["fresh"])

    from domain import academy as academy_service

    now = datetime.now(timezone.utc).isoformat()
    asyncio.run(academy_service.sync_fsrs_cards(uid, now=now))

    why = {c["target_id"]: c["why"] for c in _lexicon_cards(uid)}
    assert why["fresh"] == "recognition-only"


def test_why_for_lexicon_group_flag_pure():
    """Decisión pura de la razón según el flag de grupo (V20-17)."""
    from services import fsrs

    assert fsrs.why_for_lexicon("known", group_produced=True) == "transfer-gap"
    assert fsrs.why_for_lexicon("known", group_produced=False) == "recognition-only"
    assert fsrs.why_for_lexicon("known") == "recognition-only"
    assert fsrs.why_for_lexicon("learning") == "learning-lexicon"
    assert fsrs.why_for_lexicon("weak") == "weak-lexicon"
