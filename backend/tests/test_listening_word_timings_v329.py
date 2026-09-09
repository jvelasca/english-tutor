"""V3.29 (Fase 3): servir `word_timings` en el payload de ListeningQuestion.

Cubre `word_timings_for` (servicio): forma/orden de las palabras, asignación de
`index` de frase por intervalo de `coarse_sentence_timings`, degradación a `[]`
sin sidecar y sin `duration`, `repetition_policy="twice"` (dos pasadas) y el
ítem derivado `d-` reutilizando el sidecar del padre (`derived_from`); y el
contrato del endpoint (solo con audio TTS listo, `[]` sin sidecar, ausente en el
modo compacto `mastered`)."""
import copy
from pathlib import Path

from fastapi.testclient import TestClient

from config import PIPER_VOICE
from main import app
from repositories import db
from services import listening as listening_svc
from services.curriculum import LISTENING_BANK_VERSION
from services.listening import (
    LEVEL_ORDER,
    QUESTION_BANK,
    audio_digest,
    coarse_sentence_timings,
    word_timings_for,
)
from services.word_alignment_proxy import write_sidecar

_VOICE = PIPER_VOICE


_SPANS = [
    ("Hello", 0.0, 0.6),
    ("world", 0.7, 1.4),
    ("Nice", 3.0, 3.7),
    ("day", 3.8, 4.4),
    ("today", 4.5, 5.2),
]


def _setup(monkeypatch, tmp_path):
    from repositories import users as users_repo

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _tts_question(**overrides) -> dict:
    q = {
        "id": "l-test-w",
        "level": "A1",
        "skill": "word_recognition",
        "transcript": "Hello world. Nice day today.",
        "clean_transcript": "Hello world. Nice day today.",
        "script": "Hello world. Nice day today.",
        "duration": 8.0,
        "speech_rate": 150.0,
        "repetition_policy": "none",
    }
    q.update(overrides)
    return q


def _wav_path(question: dict) -> Path:
    cache_id = question.get("derived_from") or question["id"]
    digest = audio_digest(question, "normal")
    return (
        Path(listening_svc.DATA_DIR)
        / "listening"
        / LISTENING_BANK_VERSION
        / _VOICE
        / f"{cache_id}-{digest}.wav"
    )


def _sidecar_words(question: dict) -> list[dict]:
    """Palabras sintéticas cuyos inicios caen repartidos por todo el audio."""
    return [
        {"index": i, "text": text, "start": start, "end": end}
        for i, (text, start, end) in enumerate(_SPANS)
    ]


def _sentence_expected(start: float, sentences: list[dict]) -> int:
    for sentence in sentences:
        if sentence["start"] <= start < sentence["end"]:
            return int(sentence["index"])
    if sentences and start >= sentences[-1]["end"]:
        return int(sentences[-1]["index"])
    return -1


def _install_sidecar(question: dict) -> None:
    _wav_path(question).parent.mkdir(parents=True, exist_ok=True)
    write_sidecar(_wav_path(question), _sidecar_words(question), "x")


# --- Pruebas puras de word_timings_for ---------------------------------------

def test_word_timings_shape_order_y_frase(monkeypatch, tmp_path):
    monkeypatch.setattr(listening_svc, "DATA_DIR", tmp_path)
    question = _tts_question()
    _install_sidecar(question)
    result = word_timings_for(question)
    assert len(result) == 5
    texts = [w["text"] for w in result]
    assert texts == ["Hello", "world", "Nice", "day", "today"]
    for word in result:
        assert set(word) == {"index", "text", "start", "end", "sentence"}
        assert word["end"] >= word["start"]
        assert word["sentence"] >= -1
    # Orden por tiempo (monótono en `start`).
    starts = [w["start"] for w in result]
    assert starts == sorted(starts)
    # Determinista.
    assert copy.deepcopy(result) == word_timings_for(question)
    # `sentence` coherente con el intervalo que contiene cada `start`.
    sentences = coarse_sentence_timings(question)
    assert len(sentences) == 2
    for word in result:
        assert word["sentence"] == _sentence_expected(word["start"], sentences)


def test_word_timings_sin_sidecar_degrada_a_vacio(monkeypatch, tmp_path):
    monkeypatch.setattr(listening_svc, "DATA_DIR", tmp_path)
    assert word_timings_for(_tts_question()) == []


def test_word_timings_sin_duration_sentence_a_menos_uno(monkeypatch, tmp_path):
    monkeypatch.setattr(listening_svc, "DATA_DIR", tmp_path)
    question = _tts_question(duration=0.0)
    _install_sidecar(question)
    assert coarse_sentence_timings(question) == []
    result = word_timings_for(question)
    assert len(result) == 5
    assert all(word["sentence"] == -1 for word in result)


def test_word_timings_twice_duplica_y_mapea_ambas_pasadas(monkeypatch, tmp_path):
    monkeypatch.setattr(listening_svc, "DATA_DIR", tmp_path)
    question = _tts_question(repetition_policy="twice", duration=8.0)
    # Dos pasadas: cada pasada cabe en su mitad (0-4 s y 4-8 s). Con reparto por
    # peso textual, la 1ª frase ocupa ~1.8 s y la 2ª el resto de la mitad.
    pass_words = [
        ("Hello", 0.0, 0.3),
        ("world", 0.35, 0.7),
        ("Nice", 2.0, 2.5),
        ("day", 2.6, 3.0),
        ("today", 3.1, 3.5),
    ]
    words = [
        {"index": i + half_index * len(pass_words), "text": text,
         "start": start + half, "end": end + half}
        for half_index, half in enumerate((0.0, 4.0))
        for i, (text, start, end) in enumerate(pass_words)
    ]
    _wav_path(question).parent.mkdir(parents=True, exist_ok=True)
    write_sidecar(_wav_path(question), words, "x")
    result = word_timings_for(question)
    assert len(result) == 10
    sentences = coarse_sentence_timings(question)
    assert len(sentences) == 4  # 2 frases × 2 pasadas
    first_half_texts = [w["text"] for w in result[:5]]
    second_half_texts = [w["text"] for w in result[5:]]
    assert first_half_texts == second_half_texts
    for word in result:
        assert word["sentence"] == _sentence_expected(word["start"], sentences)
    # Las palabras de la segunda mitad caen en frases de índice >= 2.
    assert all(word["sentence"] >= 2 for word in result[5:])
    assert all(word["sentence"] < 2 for word in result[:5])


def test_word_timings_derivado_reutiliza_sidecar_del_padre(monkeypatch, tmp_path):
    monkeypatch.setattr(listening_svc, "DATA_DIR", tmp_path)
    parent = _tts_question()
    derived = dict(parent)
    derived.update(
        {
            "id": "d-" + parent["id"],
            "derived": True,
            "derived_from": parent["id"],
            "task_type": "cloze",
        }
    )
    _install_sidecar(parent)
    # El WAV del derivado se cachea bajo el id del padre (mismo contenido).
    assert _wav_path(derived) == _wav_path(parent)
    assert word_timings_for(derived) == word_timings_for(parent)


# --- Contrato del endpoint ---------------------------------------------------

def test_route_con_flow_expone_word_timings_vacios_sin_sidecar(monkeypatch, tmp_path):
    """El payload con flow expone `word_timings` ([] aquí: DATA_DIR de test no
    tiene sidecar de la voz default; degradación controlada, nunca error)."""
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
    assert body.get("word_timings", []) == []


def test_mastered_compacto_no_expone_word_timings(monkeypatch, tmp_path):
    """Modo compacto (`mastered`, sin flow) no lleva word_timings, como hoy con
    `sentence_timings`."""
    from repositories import listening as listening_repo

    uid = _setup(monkeypatch, tmp_path)
    question = next(
        q for q in QUESTION_BANK if q["level"] == LEVEL_ORDER[0]
    )
    listening_repo.record_attempt(
        uid, question["id"], 1, True, skill=question["skill"], difficulty=3
    )
    with TestClient(app) as client:
        r = client.get(
            "/api/listening/question",
            params={"user_id": uid, "level": LEVEL_ORDER[0], "mode": "mastered"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["flow"] == []
    assert body.get("word_timings", []) == []
