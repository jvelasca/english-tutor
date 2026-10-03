"""Sonda de telemetría del Sense Resolver sobre una base temporal.

Siembra las frases del corpus de polisemia como fallos de Listening: cada
lema entra en el léxico con su acepción declarada, el diccionario guarda las
alternativas, y el puente real (`_apply_difficulty_evidence`) escribe el
ledger. No abre `backend/data/tutor.db`: esas filas medirían alumnos, y una
sonda no puede fabricarlas.

El umbral de 30 filas con veredicto es el de la sonda, no el de producción.
"""
import asyncio
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from repositories import academy as academy_repo
from repositories import db
from repositories import dictionary as dictionary_repo
from repositories import listening as listening_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs
from services import sense_context as sc

CORPUS = Path(__file__).resolve().parent / "fixtures" / "sense_regression_corpus.json"
REPORT = Path(__file__).resolve().parents[2] / "scripts" / "sense_shadow_report.py"
MIN_VERDICT_ROWS = 30
# Mismatch probado que el gold humano no confirma. Son las glosas genéricas
# ya declaradas en el corpus; si el conjunto cambia, la heurística se movió.
PROVEN_MISMATCH_FALSE_POSITIVES = frozenset({"bank-10", "run-07"})


def _load_items() -> list[dict]:
    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert payload["version"] == "3.94.2"
    return payload["items"]


def _setup(monkeypatch, tmp_path) -> str:
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "probe.db")
    db.init_db()
    return users_repo.create_user("Probe")["id"]


def _seed_only_this_word(user_id: str, word: str, sense: dict) -> None:
    """Deja en el léxico solo `word`, con la acepción de este ítem.

    Una frase puede nombrar otro lema del corpus. Si ese otro lema siguiera
    en el léxico, el fallo escribiría una fila de más y el veredicto de esta
    frase dejaría de ser el del ítem.
    """
    vocabulary_repo.seed_study_items(
        user_id,
        [{"word": word, "lemma": word, "kind": "word", "sense": sense}],
        source="user",
    )
    with closing(db._conn()) as conn, conn:
        conn.execute(
            "DELETE FROM vocabulary WHERE user_id = ? AND word != ?",
            (user_id, word),
        )
    if academy_repo.get_fsrs_card(user_id, "lexicon", word) is None:
        academy_repo.upsert_fsrs_card(
            user_id,
            fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
        )


def _question(item: dict) -> dict:
    return {
        "id": item["id"],
        "transcript": item["sentence"],
        "skill": "detail",
        "answer_index": 0,
        "options": ["no", "yes"],
    }


def _report_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("sense_shadow_report", REPORT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_ledger_matches_the_corpus_and_clears_thirty_rows(monkeypatch, tmp_path):
    """95 fallos reales del puente, un veredicto por frase, informe incluido."""
    from domain.listening import _apply_difficulty_evidence

    uid = _setup(monkeypatch, tmp_path)
    items = _load_items()
    assert len(items) >= MIN_VERDICT_ROWS

    async def _fail_all() -> None:
        for item in items:
            word = item["lemma"]
            _seed_only_this_word(uid, word, item["declared"])
            dictionary_repo.save_entry(
                word,
                senses=item["alternatives"],
                generator_version="1.7.0",
            )
            question = _question(item)
            body = await _apply_difficulty_evidence(
                uid,
                question["id"],
                question,
                attempt_id=item["id"],
            )
            expected = item["resolver_expected"]
            proven = expected["match"] == sc.SENSE_MISMATCH
            if proven:
                assert body["new_sense_exposure"]["words"] == [word], item["id"]
                assert body["count"] == 0, item["id"]
            else:
                assert body["new_sense_exposure"]["count"] == 0, item["id"]
                assert body["words"] == [word], item["id"]

    asyncio.run(_fail_all())

    rows = listening_repo.list_difficulty_evidence(uid)
    by_id = {row["question_id"]: row for row in rows}
    assert len(by_id) == len(items)
    proven_false_positives = set()
    for item in items:
        row = by_id[item["id"]]
        expected = item["resolver_expected"]
        assert row["word"] == item["lemma"], item["id"]
        assert row["sense_match"] == expected["match"], item["id"]
        assert row["sense_reason"] == expected["reason"], item["id"]
        assert row["sense_key"], item["id"]
        if expected["match"] == sc.SENSE_MISMATCH:
            assert row["difficulty_before"] == row["difficulty_after"], item["id"]
            if item["gold"] != sc.SENSE_MISMATCH:
                proven_false_positives.add(item["id"])
        else:
            assert row["difficulty_after"] >= row["difficulty_before"], item["id"]
    assert proven_false_positives == PROVEN_MISMATCH_FALSE_POSITIVES

    report_mod = _report_module()
    transcripts = {item["id"]: item["sentence"] for item in items}
    conn = sqlite3.connect(tmp_path / "probe.db")
    try:
        report = report_mod._report(conn, examples=10, transcripts=transcripts)
    finally:
        conn.close()

    assert report["total"] == len(items)
    assert report["with_verdict"] >= MIN_VERDICT_ROWS
    assert report["without_verdict"] == 0
    assert report["declared_sense"] == len(items)
    assert report["enforce_suppressed"] == report["by_match"]["mismatch"]
    assert report["enforce_kept"] == (
        report["with_verdict"] - report["enforce_suppressed"]
    )
    def _reason_count(reason: str) -> int:
        return sum(
            1
            for item in items
            if item["resolver_expected"]["reason"] == reason
        )

    reasons = report["by_reason"]
    assert reasons.get(sc.REASON_GLOSS_OTHER, 0) == _reason_count(
        sc.REASON_GLOSS_OTHER
    )
    assert reasons.get(sc.REASON_ROLE_OTHER, 0) == _reason_count(
        sc.REASON_ROLE_OTHER
    )
    assert report["possible_mismatch"] == reasons.get(sc.REASON_GLOSS_OTHER_WEAK, 0)
    assert report["occurrence_split"] == reasons.get(sc.REASON_OCCURRENCE_SPLIT, 0)

    reviewed = []
    for reason in (sc.REASON_GLOSS_OTHER, sc.REASON_ROLE_OTHER):
        for example in report["examples"][reason]:
            assert example["transcript"], example["question_id"]
            assert example["sense_match"] == sc.SENSE_MISMATCH
            reviewed.append(example["question_id"])
    assert set(reviewed) >= PROVEN_MISMATCH_FALSE_POSITIVES
