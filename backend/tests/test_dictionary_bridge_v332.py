"""Tests de aceptación de V3.32 — Dictionary → Learning Bridge (primer eslabón).

El puente convierte la consulta del diccionario (V3.30, D3: solo lectura) en
puerta a la práctica real: «Practicar esta palabra» reutiliza los endpoints de
drill existentes (`drill/attempt`, `drill/sentence-context|attempt`), que ya
aceptan palabras arbitrarias. Acceptance de integración HTTP (TestClient):

- mitad D3 del acceptance: la consulta de una palabra nueva sigue sin crear
  filas en `vocabulary` ni eventos en `vocabulary_events`;
- «practicar» tras consultar escribe EXACTAMENTE la misma evidencia que
  practicar esa palabra fuera del diccionario (mismos endpoints, mismas filas);
- evidencia por intento superado: `speaking_prod=1`, `production_count=1`,
  `exposure_count=0`, un evento `produced` (channel=speaking, activity=drill)
  en `vocabulary_events` y un `learning_events` `drill:<word>:ok` (o
  `drill:<word>:sentence:ok` para el paso frase);
- aislamiento entre usuarios: lo que hace A no toca el léxico de B;
- cierre D3 sin regresiones: tras consultar + practicar, una segunda consulta
  de la misma palabra no crea filas ni eventos adicionales.

Nota de diseño del dossier: cada test usa UN solo `with TestClient(app)` para
no re-ejecutar el lifespan (que llama `init_db()` y cuyo backfill V3.19 de
`chat_prod` re-etiquetaría filas modernas de speaking-only creadas antes de
abrir un bloque nuevo). Los tests del generador de contenido se aíslan con un
fetcher caído (offline): la caché `dictionary_entries` permanece vacía y las
consultas degradan a `definition_source="none"` de forma determinista.
"""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import learning as learning_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import dictionary_content


@pytest.fixture(autouse=True)
def _no_generator(monkeypatch):
    """Aísla las consultas del modelo local: el generador cae al instante."""

    async def _offline(_word: str, _model: str | None) -> str:
        raise dictionary_content.ContentUnavailableError("test: sin modelo")

    monkeypatch.setattr(dictionary_content, "_default_fetcher", _offline)


@pytest.fixture(autouse=True)
def _clear_generation_state():
    """Limpia el estado global de generación (vuelos, negative cache, cupos)."""
    from domain import vocabulary as vocabulary_domain

    vocabulary_domain._clear_generation_state()
    yield
    vocabulary_domain._clear_generation_state()


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    return a, b


def _fake_transcribe(text: str):
    def fake(_audio, _lang):
        return {"text": text, "duration": 2.0}

    return fake


def _count_rows(table: str) -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _lookup(client: TestClient, uid: str, word: str) -> dict:
    res = client.post(
        f"/api/vocabulary/dictionary?user_id={uid}",
        json={"word": word},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _drill_attempt(client: TestClient, uid: str, word: str) -> dict:
    """Paso Recall del drill: decir la palabra. Devuelve el body del scorer."""
    res = client.post(
        "/api/vocabulary/drill/attempt",
        params={"user_id": uid},
        data={"word": word},
        files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _sentence_context(client: TestClient, uid: str, word: str) -> dict:
    res = client.get(
        "/api/vocabulary/drill/sentence-context",
        params={"user_id": uid, "word": word},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _sentence_attempt(client: TestClient, uid: str, word: str) -> dict:
    res = client.post(
        "/api/vocabulary/drill/sentence-attempt",
        params={"user_id": uid},
        data={"word": word},
        files={"file": ("audio.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _row(uid: str, word: str) -> dict | None:
    rows = {v["word"]: v for v in vocabulary_repo.get_vocabulary(uid)}
    return rows.get(word)


# Claves de la fila que deben ser IDÉNTICAS al practicar desde el diccionario o
# directamente (misma evidencia, sin etiquetas de origen del puente).
_EVIDENCE_KEYS = (
    "word",
    "production_count",
    "production_days",
    "exposure_count",
    "chat_prod",
    "speaking_prod",
    "writing_prod",
    "conversation_prod",
    "lexical_unit",
    "context_tags",
)


# --- Acceptance: mitad D3 + práctica real -----------------------------------


def test_lookup_new_word_read_only_and_practice_writes_identical_evidence(
    monkeypatch, tmp_path
):
    """Lookup (D3) + practicar de A produce la MISMA evidencia que practicar esa
    misma palabra directamente (B), sin que A toque el léxico de B."""
    a, b = _setup(monkeypatch, tmp_path)
    assert _count_rows("vocabulary") == 0
    assert _count_rows("vocabulary_events") == 0

    from routers import vocabulary as router_mod

    monkeypatch.setattr(
        router_mod, "transcribe_with_timing", _fake_transcribe("quokka")
    )

    with TestClient(app) as client:
        # A consulta una palabra nueva: solo lectura (D3), tracked=false.
        data = _lookup(client, a, "quokka")
        assert data["usage"]["tracked"] is False
        assert data["definition_source"] == "none"
        assert _count_rows("vocabulary") == 0
        assert _count_rows("vocabulary_events") == 0

        # Botón «Practicar» simulado: A practica tras consultar; B practica la
        # misma palabra directamente (fuera del diccionario).
        assert _drill_attempt(client, a, "quokka")["produced"] is True
        assert _drill_attempt(client, b, "quokka")["produced"] is True

    row_a = _row(a, "quokka")
    row_b = _row(b, "quokka")
    assert row_a is not None and row_b is not None
    # Fila de producción pura: palabra sin historial previo de exposición.
    assert row_a["speaking_prod"] == 1
    assert row_a["production_count"] == 1
    assert row_a["exposure_count"] == 0
    assert row_a["chat_prod"] == 0
    # Evidencia IDÉNTICA a practicar fuera del diccionario.
    assert {k: row_a[k] for k in _EVIDENCE_KEYS} == {
        k: row_b[k] for k in _EVIDENCE_KEYS
    }
    # Aislamiento: la práctica de A no creó ninguna fila extra en B.
    assert len(vocabulary_repo.get_vocabulary(b)) == 1

    # Cada práctica dejó exactamente un evento produced (speaking + drill).
    events_a = vocabulary_repo.list_vocabulary_events(a, word="quokka")
    assert len(events_a) == 1
    ev = events_a[0]
    assert ev["event_type"] == "produced"
    assert ev["channel"] == "speaking"
    assert ev["activity"] == "drill"
    # Y su learning_event de éxito del drill (palabra suelta).
    learning_a = learning_repo.list_events(a, "exercise")
    assert [e["detail"] for e in learning_a] == ["drill:quokka:ok"]
    assert len(learning_repo.list_events(b, "exercise")) == 1


# --- Acceptance: paso Sentence equivalente -----------------------------------


def test_sentence_step_after_lookup_equivalent_evidence_and_d3_closure(
    monkeypatch, tmp_path
):
    """El paso frase tras consultar acredita la MISMA evidencia que el paso
    palabra (canal speaking, actividad drill, detalle :sentence:) y una segunda
    consulta no crea filas ni eventos adicionales (cierre D3)."""
    a, _b = _setup(monkeypatch, tmp_path)

    from routers import vocabulary as router_mod

    with TestClient(app) as client:
        assert _lookup(client, a, "quokka")["usage"]["tracked"] is False

        # El alumno repite la frase de contexto que el servidor sirvió.
        ctx = _sentence_context(client, a, "quokka")
        assert ctx["source"] == "template"
        monkeypatch.setattr(
            router_mod, "transcribe_with_timing", _fake_transcribe(ctx["phrase"])
        )
        body = _sentence_attempt(client, a, "quokka")
        assert body["passed"] is True
        assert body["phrase"] == ctx["phrase"]

        # Cierre D3 sin regresiones: la segunda consulta YA ve la palabra
        # trackeada, pero no crea filas ni eventos adicionales.
        again = _lookup(client, a, "quokka")
        assert again["usage"]["tracked"] is True
        assert again["usage"]["surface"]["production_count"] == 1

    row = _row(a, "quokka")
    assert row is not None
    assert row["speaking_prod"] == 1
    assert row["production_count"] == 1
    assert row["exposure_count"] == 0
    assert row["chat_prod"] == 0
    assert row["context_tags"] == "speaking:drill"

    # Un evento produced en el ledger léxico (igual que el paso palabra)…
    events = vocabulary_repo.list_vocabulary_events(a, word="quokka")
    assert len(events) == 1
    assert events[0]["event_type"] == "produced"
    assert events[0]["channel"] == "speaking"
    assert events[0]["activity"] == "drill"
    # …y el learning_event con el detalle del paso frase.
    learning = learning_repo.list_events(a, "exercise")
    assert [e["detail"] for e in learning] == ["drill:quokka:sentence:ok"]

    # Tras cerrar el TestClient no ha habido más startups: nada adicional.
    assert _count_rows("vocabulary") == 1
    assert _count_rows("vocabulary_events") == 1
    assert _count_rows("learning_events") == 1
    # Sin generador: la caché global de contenido sigue vacía.
    assert _count_rows("dictionary_entries") == 0


# --- Acceptance: aislamiento entre usuarios ----------------------------------


def test_lookup_and_practice_isolated_between_users(monkeypatch, tmp_path):
    """A consulta y practica; B no ve ningún rastro (ni la consulta ni la
    práctica de A tocan su léxico) hasta que practica por su cuenta."""
    a, b = _setup(monkeypatch, tmp_path)

    from routers import vocabulary as router_mod

    monkeypatch.setattr(
        router_mod, "transcribe_with_timing", _fake_transcribe("quokka")
    )

    with TestClient(app) as client:
        assert _lookup(client, a, "quokka")["usage"]["tracked"] is False
        assert _lookup(client, b, "quokka")["usage"]["tracked"] is False
        # Ni la consulta de A ni la de B han creado evidencia.
        assert _count_rows("vocabulary") == 0
        assert _count_rows("vocabulary_events") == 0

        assert _drill_attempt(client, a, "quokka")["produced"] is True

        # B sigue sin fila ni eventos: la práctica de A es estrictamente de A.
        assert _row(b, "quokka") is None
        assert vocabulary_repo.list_vocabulary_events(b, word="quokka") == []
        assert learning_repo.list_events(b, "exercise") == []

        # Cuando B practica, crea su propia fila (idéntica a la de A).
        assert _drill_attempt(client, b, "quokka")["produced"] is True

    row_b = _row(b, "quokka")
    row_a = _row(a, "quokka")
    assert {k: row_b[k] for k in _EVIDENCE_KEYS} == {
        k: row_a[k] for k in _EVIDENCE_KEYS
    }
