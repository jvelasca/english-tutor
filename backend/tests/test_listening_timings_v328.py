"""V3.28 (Listening Engine 4.0, Fase 2, Bloque D): timings gruesos de frase.

El backend calcula timings de frase heurísticos (reparto proporcional de
`duration` por peso textual, `sync="coarse_heuristic"`) y los sirve en el payload
cuando el ítem trae micro-flujo. NO son alineación acústica: los tests verifican
determinismo, cobertura completa de la duración y contrato en el endpoint (los
ítems con flow los exponen; el modo `mastered` compacto no)."""
import copy

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import listening as listening_repo
from repositories import users as users_repo
from services.listening import LEVEL_ORDER, QUESTION_BANK, coarse_sentence_timings


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _receptive_at(level: str) -> dict:
    """Primer ítem receptivo (no dictation/shadowing) del banco en `level`."""
    for q in QUESTION_BANK:
        if q["level"] == level and q["skill"] not in ("dictation", "shadowing"):
            return q
    raise AssertionError(f"banco sin ítems receptivos en {level}")


def _assert_timing_shape(entry: dict) -> None:
    assert set(entry) == {"index", "start", "end", "text", "sync"}
    assert entry["sync"] == "coarse_heuristic"
    assert entry["index"] >= 0
    assert entry["end"] >= entry["start"]
    assert entry["text"].strip()


# --- Pruebas puras de la función de timings ----------------------------------

def test_determinista_y_cubre_toda_la_duracion():
    q = {
        "clean_transcript": "First sentence here. Second sentence here.",
        "duration": 10.0,
        "repetition_policy": "none",
    }
    timings = coarse_sentence_timings(q)
    assert copy.deepcopy(timings) == coarse_sentence_timings(q)  # determinista
    assert len(timings) == 2
    assert timings[0]["start"] == 0.0
    # La última frase termina exactamente en `duration` (cobertura completa).
    assert timings[-1]["end"] == 10.0
    for idx in range(len(timings) - 1):
        a, b = timings[idx], timings[idx + 1]
        assert b["start"] >= a["end"]  # no solapan y guardan orden
        _assert_timing_shape(a)
    _assert_timing_shape(timings[-1])
    # Reparto proporcional al peso textual: la frase más larga ocupa más tiempo.
    span0 = timings[0]["end"] - timings[0]["start"]
    span1 = timings[1]["end"] - timings[1]["start"]
    assert span1 > span0  # "Second sentence here." pesa más que "First sentence here."


def test_repetition_twice_duplica_frases_y_acaba_en_duration():
    q = {
        "clean_transcript": "Go. Where?",
        "duration": 6.0,
        "repetition_policy": "twice",
    }
    timings = coarse_sentence_timings(q)
    assert len(timings) == 4
    assert [t["text"] for t in timings] == ["Go.", "Where?", "Go.", "Where?"]
    assert timings[0]["start"] == 0.0
    assert timings[-1]["end"] == 6.0
    # La segunda pasada arranca en la mitad exacta.
    assert timings[2]["start"] == 3.0
    for entry in timings:
        _assert_timing_shape(entry)


def test_sin_duration_o_sin_texto_no_hay_timings():
    assert coarse_sentence_timings({"clean_transcript": "Hello.", "duration": 0}) == []
    assert coarse_sentence_timings({"clean_transcript": "", "duration": 8.0}) == []
    assert coarse_sentence_timings({"transcript": "   ", "duration": 8.0}) == []


def test_fallback_de_texto_clean_transcript_a_transcript_a_script():
    q = {"transcript": "What I heard.", "script": "Ignored.", "duration": 3.0}
    timings = coarse_sentence_timings(q)
    assert [t["text"] for t in timings] == ["What I heard."]


def test_sin_duration_se_degrade_a_lista_vacia_en_payload_servido():
    """Un ítem sin `duration` (no sintetizado) sirve timings vacíos: la UI
    degrada a revelado sin resaltado, nunca a tiempos inventados."""
    q = {"clean_transcript": "Hello.", "duration": 0.0}
    assert coarse_sentence_timings(q) == []


# --- Contrato del endpoint ---------------------------------------------------

def test_level_route_exposes_sentence_timings_with_flow(monkeypatch, tmp_path):
    """Con micro-flujo el payload expone `sentence_timings` (lista, shape válida
    o vacía si el ítem no declara duración)."""
    uid = _setup(monkeypatch, tmp_path)
    level = LEVEL_ORDER[0]
    with TestClient(app) as client:
        r = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": level},
        )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["flow"], list) and body["flow"]
    assert isinstance(body["sentence_timings"], list)
    for entry in body["sentence_timings"]:
        _assert_timing_shape(entry)
    # Determinismo del banco: un ítem con duración sirve timings reproducibles.
    q = next(q for q in QUESTION_BANK if q["id"] == body["id"])
    if (q.get("duration") or 0) > 0:
        assert body["sentence_timings"] == coarse_sentence_timings(q)


def test_timings_sirven_en_drill_failed_para_item_con_duration(monkeypatch, tmp_path):
    """Drill (`mode=failed`) también lleva timings cuando el ítem declara duración."""
    uid = _setup(monkeypatch, tmp_path)
    q = next(
        q
        for q in QUESTION_BANK
        if q["skill"] not in ("dictation", "shadowing") and (q.get("duration") or 0) > 0
    )
    listening_repo.record_attempt(
        uid, q["id"], 0, False, skill=q["skill"], difficulty=3
    )
    with TestClient(app) as client:
        r = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": q["level"], "mode": "failed"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == q["id"]
    assert body["flow"]
    assert body["sentence_timings"] == coarse_sentence_timings(q)
    assert body["sentence_timings"]
    assert body["sentence_timings"][-1]["end"] == q["duration"]


def test_mastered_compact_no_sirve_timings(monkeypatch, tmp_path):
    """El modo compacto (`mastered`, sin flow) no expone timings: repaso de lo
    superado sin sync de transcript."""
    uid = _setup(monkeypatch, tmp_path)
    q = _receptive_at("A1")
    listening_repo.record_attempt(
        uid, q["id"], 1, True, skill=q["skill"], difficulty=3
    )
    with TestClient(app) as client:
        r = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": "A1", "mode": "mastered"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["flow"] == []
    assert body["sentence_timings"] == []
