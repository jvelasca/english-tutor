"""V3.59 — Context Engine 3.0 (Context Bank Family/Instance).

La auditoría externa de V3.43 dejó abierto que el banco curado se queda corto:
un banco finito de consignas fijas se MEMORIZA. V3.48 lo amplió a 20 contextos
(seis de ellos congelados), pero cada uno seguía teniendo UNA sola superficie: al
agotar el banco el alumno repite literalmente la misma consigna y puede reciclar
una respuesta aprendida en lugar de transferir la unidad.

V3.59 separa las dos cosas que hasta ahora eran la misma:

- **FAMILIA**: la identidad pedagógica (sus seis dimensiones core, su `cefr`, su
  `difficulty_vector`, sus `skills` y su `id`). Es la unidad de EVIDENCIA: el
  `id` es el `context_id` del ledger, así que el banco NO se fragmenta y no
  cambian los umbrales, la escalera `transfer_state`, `context_distance`,
  `context_diversity`, la novedad ni el ajuste de dificultad.
- **INSTANCIA**: una superficie DECLARADA de la misma familia (misma identidad,
  otra redacción). La superficie 0 es la consigna histórica de la familia, byte
  a byte; las demás son superficies nuevas que se sirven por ROTACIÓN: el intento
  N sobre esa familia recibe la superficie `N % nº_superficies`.

Invariantes de la release (verificados aquí):

1. **Identidad intacta.** Una instancia solo puede declarar
   `CONTEXT_INSTANCE_KEYS` (`instance`, `prompt`): no puede tocar la familia.
2. **Degradación exacta.** Sin evidencia (0 intentos) el payload es el de V3.58
   salvo los tres campos aditivos, y la consigna es la histórica de la familia.
3. **La elección no cambia.** La familia servida es función de la misma evidencia
   que en V3.58: la rotación de superficie no entra en el pool, la novedad, la
   distancia ni la dificultad.
4. **Rotación real.** Con el banco agotado, la segunda estancia en la misma
   familia sirve OTRA superficie (el objetivo anti-memorización).
"""

from __future__ import annotations

import collections

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import transfer

BANK = transfer.TRANSFER_CONTEXTS
BANK_IDS = tuple(transfer.context_id_for(context) for context in BANK)

# Claves de IDENTIDAD de una familia (unidad de evidencia + atributos de los que
# dependen `context_distance`/`context_diversity`/`context_skills`/
# `context_difficulty`). Una INSTANCIA no puede declararlas.
FAMILY_KEYS = (
    "id",
    "skills",
    "topic",
    "communicative_goal",
    "discourse_type",
    "social_relation",
    "time_reference",
    "register",
    "interaction_type",
    "cefr",
    "difficulty_vector",
    "lexical_environment",
    "syntactic_focus",
    "prompt",
)

# Contrato EXACTO del payload de `context_for` en V3.58 (25 claves) más los tres
# campos aditivos de V3.59 y los ocho de V3.60. Fija por escrito que las releases
# no quitan ni renombran nada (contrato aditivo, premisa 9).
V358_KEYS = frozenset(
    {
        "word",
        "context_id",
        "topic",
        "prompt",
        "available",
        "exhausted",
        "communicative_goal",
        "discourse_type",
        "condition",
        "required_target",
        "unscaffolded",
        "cefr",
        "difficulty_vector",
        "difficulty",
        "skills",
        "target_skill",
        "assessed_skill",
        "assessment_mode",
        "item_level",
        "learner_level",
        "learner_level_source",
        "learner_capacity",
        "capacity_skill",
        "difficulty_fit",
        "skill_priorities",
    }
)
V359_KEYS = V358_KEYS | {"context_instance", "instance_index", "instance_count"}

# V3.60 (Context Engine 4.0): los ocho campos de la superficie parametrizada.
V360_INSTANCE_KEYS = frozenset(
    {
        "instance_scenario",
        "instance_goal",
        "instance_register",
        "instance_difficulty_delta",
        "instance_difficulty_vector",
        "instance_difficulty",
        "instance_skills",
        "instance_generated",
    }
)
V360_KEYS = V359_KEYS | V360_INSTANCE_KEYS

# Campos del payload que la rotación SÍ puede cambiar (el resto debe ser idéntico).
VOLATILE_KEYS = frozenset(
    {"prompt", "context_instance", "instance_index"}
) | V360_INSTANCE_KEYS


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _seed_word(uid: str, word: str, *, cefr: str = "B1") -> None:
    vocabulary_repo.seed_curriculum_items(
        uid,
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
    vocabulary_repo.record_exposures(uid, [word])


def _get_context(client: TestClient, uid: str, word: str) -> dict:
    res = client.get(
        "/api/vocabulary/drill/transfer-context",
        params={"word": word, "user_id": uid},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _record_attempt(uid: str, word: str, context_id: str, *, success: bool) -> None:
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id=word,
        surface_form=word,
        lexical_unit=word,
        skill="spontaneous_use",
        task="transfer",
        activity="drill",
        activity_id="drill:transfer",
        context_id=context_id,
        success=success,
        support_level="independent",
        error_type="correct" if success else "missing_target",
    )


# ------------------------------------------------------------------ el banco


def test_every_family_declares_the_minimum_number_of_extra_surfaces():
    assert transfer.CONTEXT_INSTANCES_MIN >= 1
    for context in BANK:
        surfaces = transfer.context_instances(context)
        assert len(surfaces) >= 1 + transfer.CONTEXT_INSTANCES_MIN, context["id"]
        # La superficie 0 es SIEMPRE la consigna histórica de la familia.
        assert surfaces[0] == {
            "instance": "",
            "prompt": context["prompt"],
        }, context["id"]


def test_the_family_surface_keeps_the_historical_prompt_byte_identical():
    story = transfer.context_instances("story")
    assert story[0] == {
        "instance": "",
        "prompt": (
            "Tell a short story about something that happened to you recently."
        ),
    }
    # Los seis contextos congelados conservan su consigna como superficie 0.
    for context in BANK[:6]:
        surfaces = transfer.context_instances(context)
        assert surfaces[0]["prompt"] == context["prompt"], context["id"]


def test_an_instance_cannot_declare_the_family_identity():
    for context in BANK:
        # V3.60: la familia declara además su ESPACIO paramétrico (`instance_space`).
        assert set(context) <= set(FAMILY_KEYS) | {
            "instances",
            "instance_space",
        }, context["id"]
        for raw in context["instances"]:
            assert set(raw) <= set(transfer.CONTEXT_INSTANCE_KEYS), context["id"]


def test_instance_prompts_are_clean_and_distinct():
    for context in BANK:
        surfaces = transfer.context_instances(context)
        prompts = [surface["prompt"] for surface in surfaces]
        assert len(set(prompts)) == len(prompts), context["id"]
        for surface in surfaces:
            prompt = surface["prompt"]
            assert prompt, context["id"]
            assert prompt.strip() == prompt, context["id"]
            # La consigna da un ESCENARIO: sin plantillas ni llaves sueltas.
            assert "{" not in prompt and "}" not in prompt, context["id"]


def test_instances_do_not_change_the_distance_or_the_variety():
    story = BANK[0]
    same_family = dict(story)
    same_family["instances"] = ()
    # La distancia y la variedad leen la FAMILIA: la superficie no puntúa.
    assert transfer.context_distance(story, same_family) == 0
    assert transfer.context_distance("transfer:story", "transfer:work") == 5
    assert set(transfer.context_variety(list(BANK_IDS))) == {
        "dimensions",
        "varied_dimensions",
        "score",
    }


def test_the_bank_level_invariants_are_untouched():
    assert len(BANK) == 20
    counts = collections.Counter(context["cefr"] for context in BANK)
    assert counts == {"A1": 3, "A2": 4, "B1": 4, "B2": 3, "C1": 3, "C2": 3}
    pairs = [
        transfer.context_distance(first, second)
        for index, first in enumerate(BANK)
        for second in BANK[index + 1 :]
    ]
    assert min(pairs) >= transfer.CONTEXT_DIVERSITY_MIN
    diversity = transfer.context_diversity(list(BANK_IDS))
    assert diversity["diverse_dimensions"] >= transfer.CONTEXT_DIVERSITY_MIN
    assert "variety" in diversity


# ------------------------------------------------------------- núcleo puro


def test_context_instances_accepts_ids_and_never_raises():
    assert transfer.context_instances("transfer:story") == transfer.context_instances(
        "story"
    )
    assert transfer.context_instances("no-existe") == ()
    assert transfer.context_instances(None) == ()
    assert transfer.context_instances(42) == ()
    assert transfer.context_instances({"id": "x"}) == ()
    # Normaliza, descarta superficies vacías o no-dict y nunca lanza.
    assert transfer.context_instances(
        {
            "id": "x",
            "prompt": " p ",
            "instances": (
                {"instance": "a", "prompt": " q "},
                "basura",
                {},
                {"prompt": ""},
                7,
                {"instance": "b"},
            ),
        }
    ) == (
        {"instance": "", "prompt": "p"},
        {"instance": "a", "prompt": "q"},
    )


def test_context_instance_index_advances_one_surface_per_attempt():
    count = len(transfer.context_instances("story"))
    # V3.60: el espacio de la familia ya no son solo las declaradas (1 + MIN),
    # así que la cota es inferior: lo que se fija aquí es la ROTACIÓN exacta.
    assert count >= 1 + transfer.CONTEXT_INSTANCES_MIN
    assert transfer.context_instance_index("story", 0) == 0
    for attempt in range(2 * count):
        assert transfer.context_instance_index("story", attempt) == attempt % count
    # Estabilidad: la misma evidencia produce siempre la misma superficie.
    assert transfer.context_instance_index("story", 2) == (
        transfer.context_instance_index("story", 2)
    )


def test_context_instance_index_degrades_to_the_family_surface():
    assert transfer.context_instance_index("story") == 0
    for value in (None, "", "x", -1, -7, True, False, 0.5, [], {}):
        assert transfer.context_instance_index("story", value) == 0, value
    # El bucket `{"attempts": n}` del resumen de evidencia también vale.
    count = len(transfer.context_instances("story"))
    assert transfer.context_instance_index("story", {"attempts": 4}) == 4 % count
    # Una familia con una sola superficie no rota nunca.
    single = {"id": "x", "prompt": "Only one."}
    assert transfer.context_instances(single) == (
        {"instance": "", "prompt": "Only one."},
    )
    assert transfer.context_instance_index(single, 9) == 0


def test_the_family_choice_is_untouched_by_the_surface_rotation():
    base = transfer.context_for("travel", level="B2", skill="recall")
    for attempt in range(0, 9):
        got = transfer.context_for(
            "travel",
            level="B2",
            skill="recall",
            attempts_by_context={"transfer:story": {"attempts": attempt}},
        )
        assert got["context_id"] == base["context_id"]
        assert {
            key: value
            for key, value in got.items()
            if key not in VOLATILE_KEYS
        } == {
            key: value
            for key, value in base.items()
            if key not in VOLATILE_KEYS
        }


def test_context_for_never_raises_with_garbage_attempts():
    for value in (None, 42, "x", [], {"transfer:story": "x"}, {"transfer:story": -5}):
        got = transfer.context_for("travel", attempts_by_context=value)
        assert got["instance_index"] == 0, value
    got = transfer.context_for(
        "travel", attempts_by_context={"transfer:story": {"attempts": "x"}}
    )
    assert got["instance_index"] == 0


# ------------------------------------------------------------------ contrato


def test_without_evidence_the_payload_is_v3_58_plus_three_additive_fields():
    got = transfer.context_for("travel", level="B1")
    surfaces = transfer.context_instances(got["context_id"])
    assert set(got) == set(V360_KEYS)
    assert got["context_instance"] == ""
    assert got["instance_index"] == 0
    assert got["instance_count"] == len(surfaces)
    assert got["prompt"] == surfaces[0]["prompt"]
    # V3.60: sin intentos la superficie es la 0, así que sus metadatos y su
    # ajuste de carga son NULOS y la carga efectiva es la de la FAMILIA.
    assert got["instance_difficulty_delta"] == {}
    assert got["instance_generated"] is False
    assert got["instance_difficulty_vector"] == got["difficulty_vector"]


def test_the_served_surface_matches_the_index_and_the_attempts():
    surfaces = transfer.context_instances("story")
    # Se fuerza la familia `story` como única no usada.
    others = [context_id for context_id in BANK_IDS if context_id != "transfer:story"]
    got = transfer.context_for(
        "travel",
        used_context_ids=others,
        attempts_by_context={"transfer:story": 2},
    )
    assert got["context_id"] == "transfer:story"
    assert got["available"] is True
    assert got["exhausted"] is False
    assert got["instance_index"] == 2
    assert got["context_instance"] == surfaces[2]["instance"]
    # Con la condición por defecto (`cued_context`) la consigna es el escenario.
    assert got["prompt"] == surfaces[2]["prompt"]


def test_the_empty_bank_return_carries_the_instance_defaults(monkeypatch):
    monkeypatch.setattr(transfer, "TRANSFER_CONTEXTS", ())
    got = transfer.context_for("travel")
    assert got["available"] is False
    assert set(got) == set(V360_KEYS)
    assert got["context_instance"] == ""
    assert got["instance_index"] == 0
    assert got["instance_count"] == 0
    assert got["instance_difficulty_vector"] == {}
    assert got["instance_skills"] == []
    assert got["instance_generated"] is False


# --------------------------------------------------------------- contrato HTTP


def test_api_exposes_the_served_surface(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B1")

    with TestClient(app) as client:
        body = _get_context(client, uid, "travel")

    surfaces = transfer.context_instances(body["context_id"])
    assert body["instance_count"] == len(surfaces)
    assert body["instance_index"] == 0
    assert body["context_instance"] == surfaces[0]["instance"]
    assert body["prompt"] == surfaces[0]["prompt"]


def test_a_second_visit_to_the_same_family_serves_a_new_surface(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B1")
    # Se "gasta" el banco entero para que la familia se RE-sirva (pool agotado):
    # es justo el escenario en el que el alumno memorizaría la consigna.
    for context_id in BANK_IDS:
        _record_attempt(uid, "travel", context_id, success=False)

    with TestClient(app) as client:
        first = _get_context(client, uid, "travel")
        assert first["exhausted"] is True
        family = first["context_id"]
        surfaces = transfer.context_instances(family)
        # Cada familia tiene ya un intento: superficie 1 (no la histórica).
        assert first["instance_index"] == 1 % len(surfaces)
        # La condición servida añade su instrucción DETRÁS: la superficie va
        # siempre delante (V3.46).
        assert first["prompt"].startswith(
            surfaces[first["instance_index"]]["prompt"]
        )

        _record_attempt(uid, "travel", family, success=False)
        second = _get_context(client, uid, "travel")

    assert second["context_id"] == family
    assert second["instance_index"] == (
        (first["instance_index"] + 1) % len(surfaces)
    )
    assert second["prompt"].startswith(surfaces[second["instance_index"]]["prompt"])
    # Superficies distintas: la segunda estancia NO repite la redacción.
    assert surfaces[second["instance_index"]]["prompt"] != (
        surfaces[first["instance_index"]]["prompt"]
    )
    assert second["prompt"] != first["prompt"]
    assert second["context_instance"] != first["context_instance"]
