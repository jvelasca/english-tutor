"""V3.60 — Context Engine 4.0 (Instance Specification → Parameterized Instance).

La auditoría externa de V3.59 aprobó la separación FAMILIA/INSTANCIA pero dejó
tres P1 abiertos, y los tres primeros son los que cierra esta release:

1. **tres redacciones por familia siguen siendo memorizables**: agotada la
   familia en tres intentos, el alumno conoce las tres consignas;
2. **las instancias pueden cambiar la situación (y la dificultad) real sin poder
   declararlo**: `CONTEXT_INSTANCE_KEYS` era `("instance", "prompt")`;
3. **la dificultad observada no puede aprender de la instancia**: la superficie
   no dejaba rastro alguno de su carga.

V3.60 sustituye las consignas escritas a mano por un ESPACIO paramétrico por
familia: la familia declara `instance_space` (una `template` con slots y sus
valores) y el motor GENERA superficies deterministas de la MISMA identidad. Lo
que se genera es la COMBINACIÓN de valores declarados, no el texto: sigue sin
haber LLM ni aleatoriedad con estado en el camino de la evidencia.

Invariantes de la release (verificados aquí):

1. **La familia no se toca.** `context_id` sigue siendo la unidad de evidencia;
   ninguna clave nueva entra en `CONTEXT_DIMENSIONS`, `context_distance`,
   `context_diversity`, `_novelty_score` ni el `transfer_state`. La lista blanca
   de instancia y las claves de familia solo comparten `prompt`.
2. **Degradación exacta.** La superficie 0 es la consigna histórica y sin
   intentos la degradación es la de V3.59, con delta nulo.
3. **La rotación no cambia: se prolonga.** `space[:3]` reproduce byte a byte las
   tres superficies de V3.59.
4. **La dificultad de la superficie es explícita.** `difficulty_delta` es un
   ajuste sobre la carga de la familia, recortado al envelope 1..5, y
   `served_difficulty` es lo que el ledger persiste por evento.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import difficulty, transfer

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

# Contrato EXACTO del payload: 25 claves de V3.58 + 3 de V3.59 + 8 de V3.60.
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
V360_KEYS = V359_KEYS | {
    "instance_scenario",
    "instance_goal",
    "instance_register",
    "instance_difficulty_delta",
    "instance_difficulty_vector",
    "instance_difficulty",
    "instance_skills",
    "instance_generated",
}
# V3.61 (Instance-aware Evidence): guard anti-spoiler de la superficie servida y
# su explicabilidad. Aditivos: las 36 claves de V3.60 quedan intactas.
V361_KEYS = V360_KEYS | {"instance_suppressed", "instance_guarded"}

# Claves del payload que la rotación de superficie SÍ puede cambiar.
VOLATILE_KEYS = frozenset({"prompt", "context_instance", "instance_index"}) | {
    "instance_scenario",
    "instance_goal",
    "instance_register",
    "instance_difficulty_delta",
    "instance_difficulty_vector",
    "instance_difficulty",
    "instance_skills",
    "instance_generated",
}


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


# ------------------------------------------------------- frontera de identidad


def test_the_instance_whitelist_never_touches_the_family_identity():
    # La intersección con las claves de familia es EXACTAMENTE las dos claves que
    # son declaración de SUPERFICIE por naturaleza: la consigna y el registro de
    # la superficie (`register` es además una dimensión core, pero solo la lee la
    # FAMILIA: las instancias no entran en `context_distance`,
    # `context_diversity` ni `_novelty_score`, así que no puede fragmentar).
    assert set(transfer.CONTEXT_INSTANCE_KEYS) & set(FAMILY_KEYS) == {
        "prompt",
        "register",
    }
    # El resto de la identidad está PROHIBIDO en una instancia, clave a clave.
    identity_only = set(FAMILY_KEYS) - {"prompt", "register"}
    assert not (set(transfer.CONTEXT_INSTANCE_KEYS) & identity_only)
    # Y ninguna superficie del banco declara nada fuera de la lista blanca.
    for context in BANK:
        for raw in context["instances"]:
            assert set(raw) <= set(transfer.CONTEXT_INSTANCE_KEYS), context["id"]
        for name, values in (context.get("instance_space") or {}).get(
            "slots", {}
        ).items():
            for value in values:
                if isinstance(value, dict):
                    # `value` es el texto del SLOT (espacio de nombres del
                    # slot), no una clave de superficie.
                    assert set(value) - {"value"} <= set(
                        transfer.CONTEXT_INSTANCE_KEYS
                    ), (context["id"], name)


def test_a_surface_cannot_smuggle_the_family_identity():
    fake = {
        "id": "fake",
        "prompt": "Family prompt.",
        "instances": (
            {
                "instance": "a",
                "prompt": "Surface A.",
                "cefr": "C2",
                "topic": "hacked",
                "difficulty_vector": {"lexical": 5},
                "skills": ("written_production",),
            },
        ),
        "instance_space": {
            "template": "Surface {when}.",
            "slots": {
                "when": (
                    {
                        "value": "B",
                        "cefr": "C2",
                        "topic": "hacked",
                        "difficulty_delta": {"lexical": 5},
                    },
                ),
            },
        },
    }
    assert [
        surface["prompt"] for surface in transfer.context_instances(fake)
    ] == ["Family prompt.", "Surface A.", "Surface B."]
    # La especificación normalizada no tiene ninguna clave de identidad.
    spec = transfer.context_instance_spec(fake)
    assert set(spec) == {"template", "slots", "order", "difficulty_delta"}
    # Y sin familia reconocible no hay carga base que ajustar: `cefr` y
    # `difficulty_vector` declarados en la superficie son IGNORADOS.
    assert transfer.context_difficulty(fake) == {}
    assert transfer.context_instance_difficulty(fake, 2) == {}


# ------------------------------------------------------------------- el banco


def test_every_family_reaches_the_anti_memorisation_minimum():
    assert transfer.CONTEXT_INSTANCE_SPACE_MIN >= 12
    for context in BANK:
        space = transfer.context_instances(context)
        assert len(space) >= transfer.CONTEXT_INSTANCE_SPACE_MIN, context["id"]
        # Hay superficies GENERADAS de verdad: el espacio no son las tres de
        # V3.59 (el P1 que cierra esta release).
        assert len(space) > 1 + transfer.CONTEXT_INSTANCES_MIN, context["id"]
        assert any(
            detail["generated"]
            for detail in transfer.context_instance_details(context)
        ), context["id"]


def test_the_first_three_surfaces_are_v3_59_byte_for_byte():
    for context in BANK:
        space = transfer.context_instances(context)
        assert space[0] == {
            "instance": "",
            "prompt": context["prompt"],
        }, context["id"]
        for index, raw in enumerate(context["instances"], start=1):
            assert space[index] == {
                "instance": raw["instance"],
                "prompt": raw["prompt"],
            }, context["id"]


def test_generated_prompts_are_clean_and_distinct():
    for context in BANK:
        details = transfer.context_instance_details(context)
        prompts = [str(detail["prompt"]) for detail in details]
        assert len(set(prompts)) == len(prompts), context["id"]
        for prompt in prompts:
            assert prompt, context["id"]
            assert prompt.strip() == prompt, context["id"]
            # La consigna da un ESCENARIO: sin plantillas ni llaves sueltas.
            assert "{" not in prompt and "}" not in prompt, context["id"]


def test_the_bank_level_invariants_are_untouched():
    # El espacio NO añade familias ni toca la identidad de las que hay.
    assert len(BANK) == 20
    assert tuple(context["id"] for context in BANK) == tuple(
        context_id.removeprefix(transfer.TRANSFER_CONTEXT_PREFIX)
        for context_id in BANK_IDS
    )
    for context in BANK:
        assert set(context) <= set(FAMILY_KEYS) | {"instances", "instance_space"}


def test_pedagogical_equivalence_of_the_surfaces_of_a_family():
    """Test pedagógico de equivalencia (lo que la auditoría de V3.59 pedía).

    Todas las superficies de una familia sirven la MISMA identidad: se comprueba
    que, sirviendo cada índice del espacio, la familia entregada es idéntica en
    sus atributos pedagógicos (dimensiones core, CEFR, vector de familia,
    competencias de familia y modalidad evaluada) y solo cambian las claves
    declaradas de la superficie.
    """
    base = transfer.context_for("travel")
    family = base["context_id"]
    others = [context_id for context_id in BANK_IDS if context_id != family]
    # V3.61: el espacio SERVIDO (sin las superficies que delatan la unidad).
    count = len(transfer.available_instance_details(family, "travel"))
    assert count >= transfer.CONTEXT_INSTANCE_SPACE_MIN
    identity = (
        "context_id",
        "topic",
        "topic",
        "communicative_goal",
        "discourse_type",
        "cefr",
        "difficulty_vector",
        "skills",
        "target_skill",
        "assessed_skill",
        "assessment_mode",
        "item_level",
    )
    for attempt in range(count):
        got = transfer.context_for(
            "travel",
            used_context_ids=others,
            attempts_by_context={family: {"attempts": attempt}},
        )
        assert got["context_id"] == family
        # V3.61 (P1-01): la rotación deja de ser el orden declarado a partir del
        # tercer intento, así que la posición se resuelve con la MISMA función y
        # los mismos argumentos que el motor (unidad objetivo y unidad sembrada).
        assert got["instance_index"] == transfer.context_instance_index(
            family, attempt, target="travel", unit="travel"
        )
        for key in identity:
            assert got[key] == base[key], (attempt, key)
        # La superficie puede ajustar la carga, pero nunca salir del envelope.
        for load in got["instance_difficulty_vector"].values():
            assert 1 <= load <= 5
        assert set(got["instance_difficulty_vector"]) <= set(
            got["difficulty_vector"]
        )


# ------------------------------------------------------------------- el núcleo


def test_the_expansion_is_deterministic():
    for context in BANK:
        assert transfer.context_instance_details(
            context
        ) == transfer.context_instance_details(context)


def test_the_selection_sets_the_mix_order_and_the_cap_truncates_it():
    # `selection` decide qué slot se recorre PRIMERO (y por tanto qué entra
    # siempre si el techo recorta el producto cartesiano). El TEXTO sigue el
    # orden de la plantilla; lo que cambia es la SECUENCIA de combinaciones, que
    # se ve en la etiqueta de la superficie (slug en orden de mezcla).
    ordered = {
        "id": "s",
        "prompt": "Base.",
        "instance_space": {
            "template": "{a} {b}",
            "selection": ("b", "a"),
            "slots": {"a": ("a1", "a2", "a3"), "b": ("b1", "b2")},
        },
    }
    details = transfer.context_instance_details(ordered)
    assert [detail["prompt"] for detail in details] == [
        "Base.",
        "a1 b1",
        "a2 b1",
        "a3 b1",
        "a1 b2",
        "a2 b2",
        "a3 b2",
    ]
    assert [detail["instance"] for detail in details] == [
        "",
        "b1_a1",
        "b1_a2",
        "b1_a3",
        "b2_a1",
        "b2_a2",
        "b2_a3",
    ]
    # Sin `selection` se usa el orden de declaración de los slots (a primero).
    default_order = {
        "id": "s",
        "prompt": "Base.",
        "instance_space": {
            "template": "{a} {b}",
            "slots": {"a": ("a1", "a2"), "b": ("b1", "b2")},
        },
    }
    assert [
        detail["instance"]
        for detail in transfer.context_instance_details(default_order)
    ] == ["", "a1_b1", "a1_b2", "a2_b1", "a2_b2"]
    # V3.61 (P1-01): el techo ya NO corta un prefijo, sino que reparte el
    # producto completo de forma estratificada y determinista.
    huge = {
        "id": "huge",
        "prompt": "Base.",
        "instance_space": {
            "template": "{a} {b} {c}",
            "slots": {
                "a": tuple(f"a{index}" for index in range(10)),
                "b": tuple(f"b{index}" for index in range(10)),
                "c": tuple(f"c{index}" for index in range(10)),
            },
        },
    }
    details = transfer.context_instance_details(huge)
    generated = [detail for detail in details if detail["generated"]]
    assert len(generated) == transfer.CONTEXT_INSTANCE_SPACE_MAX
    assert generated[0]["prompt"] == "a0 b0 c0"
    # V3.61 (P1-01): el recorte es ESTRATIFICADO, no un PREFIJO. Con 10×10×10 y
    # techo 96, un prefijo habría fijado `a` en a0 (y en unas pocas más) dejando
    # `c` casi constante; el reparto equiespaciado da cobertura a los TRES ejes.
    prompts = [detail["prompt"].split() for detail in generated]
    for position in range(3):
        assert len({row[position] for row in prompts}) >= 5, position
    assert len({tuple(row) for row in prompts}) == len(prompts)


def test_the_specification_normalizes_slots_values_and_delta():
    context = {
        "id": "x",
        "prompt": "Base.",
        "instance_space": {
            "template": "{a} {b}",
            "selection": ("b", "unknown", "a"),
            "difficulty_delta": {"discourse": 9, "nonsense": 1},
            "slots": {
                # Deduplica por etiqueta, descarta basura y acepta dicts.
                "a": (
                    "a1",
                    "a1",
                    "",
                    7,
                    {"value": "a2", "difficulty_delta": {"lexical": 1}},
                ),
                "b": ("b1",),
                # La plantilla no lo interpola: no produciría consignas distintas.
                "unused": ("u1", "u2"),
            },
        },
    }
    spec = transfer.context_instance_spec(context)
    assert spec["order"] == ("b", "a")
    assert [value["value"] for value in spec["slots"]["a"]] == ["a1", "a2"]
    assert "unused" not in spec["slots"]
    # El delta base se recorta al rango declarado (±2) y descarta lo desconocido.
    assert spec["difficulty_delta"] == {"discourse": 2}
    details = transfer.context_instance_details(context)
    assert [detail["prompt"] for detail in details] == [
        "Base.",
        "a1 b1",
        "a2 b1",
    ]
    # La etiqueta sigue el orden de MEZCLA (`selection`), no el de la plantilla.
    assert [detail["instance"] for detail in details] == [
        "",
        "b1_a1",
        "b1_a2",
    ]
    # El delta de la superficie SUMA el del valor elegido al de la familia.
    assert details[2]["difficulty_delta"] == {"discourse": 2, "lexical": 1}


def test_an_unusable_specification_leaves_the_family_surfaces_only():
    base = {"id": "x", "prompt": "Only the family."}
    assert transfer.context_instance_spec(base) == {}
    for spec in (
        {"template": "No placeholders."},
        {"template": "Broken {", "slots": {}},
        {"template": "Missing {when}.", "slots": {"other": ("x",)}},
        {"template": "{when}.", "slots": {"when": ()}},
        {"template": "{when}.", "slots": {"when": ({"value": "  "}, 7)}},
        {"template": "{when}.", "slots": "not-a-mapping"},
        {"slots": {"when": ("x",)}},
        "not-a-mapping",
    ):
        assert transfer.context_instance_spec({**base, "instance_space": spec}) == {}
        assert transfer.context_instances(
            {**base, "instance_space": spec}
        ) == ({"instance": "", "prompt": "Only the family."},)


def test_the_index_rotates_over_the_whole_space():
    for context in BANK:
        space = len(transfer.context_instances(context))
        # V3.61 (P1-01): los tres primeros intentos son las superficies 0/1/2 y a
        # partir del tercero el ciclo se permuta con semilla `(familia, unidad)`;
        # la garantía es que sigue siendo una biyección del espacio completo.
        for attempt in range(3):
            assert transfer.context_instance_index(context, attempt) == attempt
        for cycle in range(3):
            visited = {
                transfer.context_instance_index(context, cycle * space + attempt)
                for attempt in range(space)
            }
            assert visited == set(range(space)), context["id"]
        for value in (None, "", "x", -1, -7, True, False, 0.5, [], {}):
            assert transfer.context_instance_index(context, value) == 0, value
        # Estabilidad: la misma evidencia produce siempre la misma superficie.
        assert transfer.context_instance_index(
            context, 5
        ) == transfer.context_instance_index(context, 5)
        # Determinismo entre ítems: la permutación depende de la unidad sembrada.
        assert transfer.context_instance_index(
            context, 5, unit="travel"
        ) == transfer.context_instance_index(context, 5, unit="travel")


def test_details_accept_ids_and_never_raise():
    assert transfer.context_instance_details(
        "transfer:story"
    ) == transfer.context_instance_details("story")
    assert transfer.context_instance_details("story") == (
        transfer.context_instance_details(BANK[0])
    )
    for value in (None, 42, "no-existe", [], {}, {"id": "x"}):
        assert transfer.context_instance_details(value) == (), value
    # Una familia sin espacio ni superficies declaradas: solo la histórica.
    single = {"id": "x", "prompt": "Only one."}
    assert transfer.context_instances(single) == (
        {"instance": "", "prompt": "Only one."},
    )
    assert transfer.context_instance_index(single, 9) == 0


def test_the_metadata_always_declares_the_same_keys():
    expected = set(transfer.CONTEXT_INSTANCE_DETAIL_KEYS) | {"skills"}
    for context in BANK:
        for index in range(len(transfer.context_instances(context))):
            metadata = transfer.context_instance_metadata(context, index)
            assert set(metadata) == expected, context["id"]
            assert set(metadata["skills"]) <= set(transfer.CONTEXT_SKILLS)
            assert set(transfer.context_skills(context)) <= set(metadata["skills"])
    # Índice fuera de rango: cae a la superficie 0 (degradación con gracia).
    assert transfer.context_instance_metadata(
        "story", 9999
    ) == transfer.context_instance_metadata("story", 0)
    assert transfer.context_instance_metadata(
        "story", -1
    ) == transfer.context_instance_metadata("story", 0)
    # Familia no reconocible: valores por defecto, nunca una excepción.
    empty = transfer.context_instance_metadata("no-existe")
    assert set(empty) == expected
    assert empty["skills"] == ()
    assert empty["instance"] == ""


# ------------------------------------------------------------- carga efectiva


def test_normalize_delta_keeps_the_canonical_vocabulary_and_clamps():
    assert difficulty.normalize_delta(
        {"lexical": 1, "discourse": -2}
    ) == {"lexical": 1, "discourse": -2}
    assert difficulty.normalize_delta({"lexical": 9}) == {"lexical": 2}
    assert difficulty.normalize_delta({"lexical": -9}) == {"lexical": -2}
    assert difficulty.normalize_delta({"lexical": 2.0}) == {"lexical": 2}
    assert difficulty.normalize_delta({"lexical": 2}, minimum=-1, maximum=1) == {
        "lexical": 1
    }
    for value in (
        None,
        {},
        {"lexical": 0},
        {"lexical": True},
        {"lexical": 0.5},
        {"nonsense": 1},
        {"lexical": float("nan")},
        [("lexical", 1)],
        "lexical:1",
    ):
        assert difficulty.normalize_delta(value) == {}, value


def test_apply_delta_without_a_delta_is_the_family_vector_exact():
    vector = {"lexical": 1, "syntax": 5, "discourse": 3, "interaction": 2}
    assert difficulty.apply_delta(vector, {}) == difficulty.normalize_vector(vector)
    assert difficulty.apply_delta(vector, None) == difficulty.normalize_vector(vector)
    assert difficulty.apply_delta(vector, {"lexical": 1}) == {
        "lexical": 2,
        "syntax": 5,
        "discourse": 3,
        "interaction": 2,
    }
    # Se recorta al envelope 1..5 y NO se inventan dimensiones.
    assert difficulty.apply_delta(
        vector, {"syntax": 1, "lexical": -1, "interaction": -2, "unknown": 1}
    ) == {"lexical": 1, "syntax": 5, "discourse": 3, "interaction": 1}


def test_served_difficulty_degrades_without_a_recognized_family():
    assert transfer.served_difficulty("") == {}
    assert transfer.served_difficulty(None) == {}
    assert transfer.served_difficulty("no-existe") == {}
    assert transfer.served_difficulty(42) == {}
    assert transfer.served_difficulty("story") == transfer.context_difficulty(
        "transfer:story"
    )
    assert transfer.served_difficulty(BANK[0]) == transfer.context_difficulty("story")
    for garbage in (42, "x", -3, [], {"attempts": "x"}):
        assert transfer.served_difficulty(
            "transfer:story", {"transfer:story": garbage}
        ) == transfer.context_difficulty("story")


def test_served_difficulty_matches_the_surface_that_context_for_serves():
    families_with_delta = 0
    for context in BANK:
        family = transfer.context_id_for(context)
        others = [context_id for context_id in BANK_IDS if context_id != family]
        space = len(transfer.context_instances(family))
        for attempt in range(space):
            attempts = {family: {"attempts": attempt}}
            got = transfer.context_for(
                "travel", used_context_ids=others, attempts_by_context=attempts
            )
            assert got["context_id"] == family, context["id"]
            assert got["instance_difficulty_vector"] == difficulty.apply_delta(
                got["difficulty_vector"], got["instance_difficulty_delta"]
            )
            assert got["instance_difficulty"] == transfer.difficulty_from_vector(
                got["instance_difficulty_vector"]
            )
            assert transfer.served_difficulty(
                family, attempts, unit="travel"
            ) == got["instance_difficulty_vector"], (context["id"], attempt)
            if got["instance_difficulty_delta"]:
                families_with_delta += 1
    # El ajuste de carga no es decorativo: hay superficies del banco que lo usan.
    assert families_with_delta >= 1


def test_instance_skills_are_the_family_skills_plus_the_declared_delta():
    family = "transfer:debate"
    others = [context_id for context_id in BANK_IDS if context_id != family]
    added = False
    for attempt in range(len(transfer.context_instances(family))):
        got = transfer.context_for(
            "travel",
            used_context_ids=others,
            attempts_by_context={family: {"attempts": attempt}},
        )
        assert set(got["skills"]) <= set(got["instance_skills"])
        assert set(got["instance_skills"]) <= set(transfer.CONTEXT_SKILLS)
        if "written_production" not in got["skills"]:
            added = "written_production" in got["instance_skills"] or added
    assert added


def test_the_family_choice_is_untouched_by_the_generated_space():
    base = transfer.context_for("travel", level="B2", skill="recall")
    for attempt in range(0, 30):
        got = transfer.context_for(
            "travel",
            level="B2",
            skill="recall",
            attempts_by_context={"transfer:story": {"attempts": attempt}},
        )
        assert got["context_id"] == base["context_id"]
        assert {
            key: value for key, value in got.items() if key not in VOLATILE_KEYS
        } == {
            key: value for key, value in base.items() if key not in VOLATILE_KEYS
        }


# ------------------------------------------------------------------- contrato


def test_the_payload_is_additive_over_v3_59():
    got = transfer.context_for("travel", level="B1")
    assert set(got) == set(V361_KEYS)
    # Degradación exacta: sin intentos, la superficie es la 0 y suelta delta nulo.
    assert got["context_instance"] == ""
    assert got["instance_index"] == 0
    assert got["instance_count"] == len(
        transfer.context_instances(got["context_id"])
    )
    assert got["prompt"] == transfer.context_instances(got["context_id"])[0]["prompt"]
    assert got["instance_difficulty_delta"] == {}
    assert got["instance_difficulty_vector"] == got["difficulty_vector"]
    assert got["instance_difficulty"] == got["difficulty"]
    assert got["instance_skills"] == got["skills"]
    assert got["instance_scenario"] == ""
    assert got["instance_goal"] == ""
    assert got["instance_register"] == ""
    assert got["instance_generated"] is False


def test_the_empty_bank_return_carries_the_surface_defaults(monkeypatch):
    monkeypatch.setattr(transfer, "TRANSFER_CONTEXTS", ())
    got = transfer.context_for("travel")
    assert got["available"] is False
    assert set(got) == set(V361_KEYS)
    assert got["instance_count"] == 0
    assert got["instance_difficulty_vector"] == {}
    assert got["instance_difficulty"] == 0
    assert got["instance_skills"] == []
    assert got["instance_generated"] is False


# --------------------------------------------------------------- contrato HTTP


def test_api_exposes_the_generated_surfaces(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B1")
    # Se AÍSLA una familia del banco para controlar su rotación sin depender del
    # hash estable de la palabra: `debate` es una de las que declaran ajuste.
    family = "transfer:debate"
    bank = tuple(
        context for context in BANK if transfer.context_id_for(context) == family
    )
    assert len(bank) == 1
    monkeypatch.setattr(transfer, "TRANSFER_CONTEXTS", bank)

    with TestClient(app) as client:
        # Se avanza hasta una superficie GENERADA con ajuste de carga declarado.
        attempts = 0
        body = _get_context(client, uid, "travel")
        while not body["instance_difficulty_delta"]:
            assert body["context_id"] == family
            # V3.61 (P1-01): el ciclo se permuta desde el tercer intento, así que
            # la posición se resuelve con la MISMA función que el motor.
            assert body["instance_index"] == transfer.context_instance_index(
                family, attempts, target="travel", unit="travel"
            )
            _record_attempt(uid, "travel", family, success=False)
            attempts += 1
            body = _get_context(client, uid, "travel")
        assert attempts < body["instance_count"]
        assert body["context_id"] == family
        assert body["instance_index"] == transfer.context_instance_index(
            family, attempts, target="travel", unit="travel"
        )
        # El 4º intento ya está en el espacio GENERADO (índices 0..2 son V3.59).
        assert body["instance_generated"] is True
        assert body["instance_index"] > transfer.CONTEXT_INSTANCES_MIN
        served = body["instance_difficulty_vector"]
        assert served == transfer.served_difficulty(
            family, {family: {"attempts": attempts}}, unit="travel"
        )

        # El POST persiste EXACTAMENTE la carga de la superficie servida.
        res = client.post(
            "/api/vocabulary/drill/transfer-attempt",
            params={"user_id": uid},
            json={
                "word": "travel",
                "text": "I would like to travel abroad with my family next spring.",
                "context_id": family,
            },
        )
        assert res.status_code == 200, res.text

    rows = [
        row
        for row in evidence_repo.list_evidence(uid, "travel", target_type="lexicon")
        if row["served_difficulty"]
    ]
    assert len(rows) == 1
    assert rows[0]["served_difficulty"] == difficulty.format_vector(served)
    # `observed_difficulty` sigue siendo la proyección legacy de lo servido.
    assert rows[0]["observed_difficulty"] == difficulty.format_vector(served)
