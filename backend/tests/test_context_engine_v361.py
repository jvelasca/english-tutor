"""V3.61 — Instance-aware Evidence + Anti-spoiler Guard.

La auditoría externa (`S`) aprobó la arquitectura de V3.60 (familia →
especificación → instancia) pero dejó P1 conceptuales abiertos, y la auditoría
interna (`T`) encontró **dos defectos funcionales reales** que esta release
cierra:

1. **La superficie servida podía NOMBRAR la unidad objetivo** (T-01): la familia
   `shopping` generaba «You are in a supermarket …» y `context_for` la servía
   tal cual, así que el alumno leía la respuesta y la evidencia acreditaba
   producción GUIADA en lugar de recuperación espontánea.
2. **La evidencia podía guardar la dificultad de OTRA instancia** (T-02):
   `TransferAttemptIn` no identificaba la superficie emitida y el POST
   recalculaba la rotación con el contador actual, de modo que dos respuestas
   simultáneas (o un reintento de red) persistían la carga de la siguiente
   superficie, no la de la consigna respondida.

Invariantes de la release (verificados aquí):

1. **Nunca se sirve una consigna que delate la unidad.** El guard es léxico y
   determinista (sin LLM ni WSD, premisa 21) y solo retira FAMILIAS del pool si
   queda alguna alternativa segura; si ninguna la tiene, se degrada a V3.60 y lo
   declara (`instance_guarded=False`).
2. **La identidad de la instancia es INMUTABLE de GET a POST.** El slug se
   deriva del contenido, y el POST persiste la carga de la superficie
   RESPONDIDA aunque el contador haya avanzado.
3. **La identidad pedagógica sigue siendo la FAMILIA.** `context_id` es
   `transfer:<id>`; `context_instance` es solo la SUPERFICIE, aditiva en el
   ledger y sin fragmentar `context_id`, `context_distance`,
   `context_diversity` ni el `transfer_state`.
4. **Degradación exacta.** Sin `target`, sin `unit` y sin slug, todo camino es
   byte a byte el de V3.60 (y los intentos 0/1/2 siguen sirviendo las
   superficies 0/1/2 de V3.59).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from schemas import vocabulary as schemas
from services import difficulty, transfer, transfer_audit

BANK = transfer.TRANSFER_CONTEXTS
BANK_IDS = tuple(transfer.context_id_for(context) for context in BANK)

# Palabras objeto PRECIOSAS para el guard: nombres comunes de los ejes de slot
# (lugares, objetos y periodos) que el alumno puede estar recuperando y que, si
# aparecen en la consigna, convierten la recuperación en producción guiada.
LEAK_PRONE_TARGETS = (
    "supermarket",
    "clothes shop",
    "bookshop",
    "shoe shop",
    "journey",
    "surprise",
    "coincidence",
    "holiday plans",
    "new manager",
    "workplace",
)


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


def _record_attempt(
    uid: str,
    word: str,
    context_id: str,
    *,
    success: bool,
    context_instance: str = "",
    served_difficulty: str = "",
) -> None:
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
        context_instance=context_instance,
        success=success,
        support_level="independent",
        error_type="correct" if success else "missing_target",
        served_difficulty=served_difficulty,
    )


def _isolate(context_id: str) -> list[str]:
    """Todos los `context_id` del banco MENOS el indicado (fuerza la familia)."""
    return [value for value in BANK_IDS if value != context_id]


def _other_than(context: dict) -> list[str]:
    return _isolate(transfer.context_id_for(context))


def _delta_family() -> str:
    """Familia del banco con superficies que declaran ajuste de carga."""
    for context in BANK:
        details = transfer.context_instance_details(context)
        if any(detail["difficulty_delta"] for detail in details):
            return transfer.context_id_for(context)
    raise AssertionError("el banco no declara ningún `difficulty_delta`")


def _served_vector(family: str, attempt: int) -> dict:
    """Carga de la superficie que la rotación sirve en ese intento (sin guard).

    El guard anti-spoiler es ORTOGONAL a la identidad de la instancia: aquí se
    compara el camino con `target` y el camino sin él, así que ninguno declara
    unidad objetivo.
    """
    index = transfer.context_instance_index(family, attempt, unit="travel")
    return transfer.context_instance_difficulty(family, index)


# ===========================================================================
# Bloque A — Guard anti-spoiler (defecto 1 de la auditoría `T`)
# ===========================================================================


def test_reveals_target_matches_the_unit_at_word_boundaries():
    assert transfer.reveals_target("You are in a supermarket.", "supermarket")
    assert transfer.reveals_target("We visited two supermarkets.", "supermarket")
    # Variantes inflexivas acotadas, sin lematizador: -s/-es/-ed/-ing/-er/-ers.
    assert transfer.reveals_target("She walked a long way.", "walk")
    assert transfer.reveals_target("He is walking home.", "walk")
    assert transfer.reveals_target("He walks home.", "walk")
    assert transfer.reveals_target("They booked a table.", "book")
    # Frontera de PALABRA: una subcadena dentro de OTRO token no delata nada
    # (`work` no casa con `homework` ni `art` con `start`). El guard es
    # CONSERVADOR: la variante inflexiva que sí genera (`walking` para `walk`)
    # solo puede retirar superficies de más, nunca dejar pasar la unidad.
    assert not transfer.reveals_target("The homework is done.", "work")
    assert not transfer.reveals_target("Start the car.", "art")
    assert not transfer.reveals_target("", "supermarket")
    assert not transfer.reveals_target("You are in a shop.", "shop window")
    # Expresiones de varias palabras: la coincidencia es de subcadena normalizada
    # (conservadora: acertar de más solo retira superficies, nunca delata).
    assert transfer.reveals_target("We met at the shoe shop.", "shoe shop")
    assert transfer.reveals_target("We met at the shoe shops.", "shoe shop")
    assert not transfer.reveals_target("We met at the shoe market.", "shoe shop")


def test_the_guard_ignores_units_too_short_to_be_a_signal():
    # Una unidad funcional no puede suprimir medio banco por ruido de tokens.
    for short in ("a", "an", "to", "is", "", None, 42):
        assert transfer.reveals_target("I want to go there.", short) is False
    assert transfer.reveals_target("I want to go there.", "go") is False
    assert transfer.reveals_target("I want to go there.", "there") is True


def test_without_a_target_the_available_space_is_the_whole_space():
    # Degradación EXACTA: sin unidad objetivo el guard no retira nada.
    for context in BANK:
        assert transfer.available_instance_details(
            context
        ) == transfer.context_instance_details(context)
        assert transfer.available_instance_details(context, "") == (
            transfer.context_instance_details(context)
        )


def test_the_shopping_family_never_serves_the_supermarket_surface():
    # Reproducción de la auditoría `T` (defecto T-01): la consigna con
    # `supermarket` estaba en el espacio y `context_for` la servía. Ningún
    # intento puede ya recibirla.
    family = "transfer:shopping"
    others = _isolate(family)
    suppressed = len(transfer.context_instance_details(family)) - len(
        transfer.available_instance_details(family, "supermarket")
    )
    assert suppressed == 12
    details = transfer.available_instance_details(family, "supermarket")
    for attempt in range(len(details) * 3):
        got = transfer.context_for(
            "supermarket",
            used_context_ids=others,
            attempts_by_context={family: {"attempts": attempt}},
        )
        assert got["context_id"] == family, attempt
        assert "supermarket" not in got["prompt"].lower(), (attempt, got["prompt"])
        assert got["instance_guarded"] is True
        assert got["instance_suppressed"] == suppressed
        assert got["instance_count"] == len(details)
        assert got["instance_index"] < got["instance_count"]
        # La consigna servida es la de la superficie que declara el guard.
        assert got["prompt"].startswith(details[got["instance_index"]]["prompt"])


def test_the_guard_covers_every_leak_prone_value_of_the_bank():
    for target in LEAK_PRONE_TARGETS:
        for context in BANK:
            got = transfer.context_for(
                target, used_context_ids=_other_than(context)
            )
            assert got["available"] is True, target
            if not got["instance_guarded"]:
                # Banco de una sola familia que delata la unidad: degradación
                # declarada, cubierta por su propio test.
                continue
            # La garantía del motor: ningún campo visible de la superficie
            # servida nombra la unidad (la misma comprobación que aplica el
            # guard, sobre la consigna REALMENTE servida y no sobre el espacio).
            assert not transfer.reveals_target(got["prompt"], target), (
                target,
                got["context_id"],
                got["prompt"],
            )
            if " " in target:
                assert target.lower() not in got["prompt"].lower(), target


def test_a_family_that_names_the_unit_is_dropped_only_with_an_alternative(
    monkeypatch,
):
    vector = {"lexical": 3, "syntax": 3, "discourse": 3, "interaction": 3}
    revealing = {
        "id": "revealing",
        "prompt": "You are in a supermarket and cannot find what you need.",
        "difficulty_vector": dict(vector),
    }
    safe = {
        "id": "safe",
        "prompt": "Tell me about a journey that did not go as planned.",
        "difficulty_vector": dict(vector),
    }
    monkeypatch.setattr(transfer, "TRANSFER_CONTEXTS", (revealing, safe))
    got = transfer.context_for("supermarket")
    # La familia que delata la unidad no se sirve: hay alternativa segura.
    assert got["context_id"] == "transfer:safe"
    assert got["instance_guarded"] is True
    assert "supermarket" not in got["prompt"].lower()
    # Y un objetivo que la familia no nombra no la retira del pool.
    assert transfer.context_for("holiday")["context_id"] == "transfer:revealing"


def test_a_bank_without_any_safe_surface_degrades_and_declares_it(monkeypatch):
    vector = {"lexical": 3, "syntax": 3, "discourse": 3, "interaction": 3}
    only = {
        "id": "only",
        "prompt": "You are in a supermarket and cannot find what you need.",
        "difficulty_vector": dict(vector),
    }
    monkeypatch.setattr(transfer, "TRANSFER_CONTEXTS", (only,))
    got = transfer.context_for("supermarket")
    # Banco patológico: degradación a V3.60 (nunca se deja al alumno sin tarea),
    # pero se DECLARA que el guard no pudo aplicarse.
    assert got["available"] is True
    assert got["context_id"] == "transfer:only"
    assert got["instance_guarded"] is False
    assert got["instance_suppressed"] == 0


def test_the_guard_does_not_change_the_family_identity_of_the_payload():
    guarded = transfer.context_for("supermarket", level="B1")
    plain = transfer.context_for("travel", level="B1")
    # El contrato no cambia por llevar guard (solo se añaden SUS claves).
    assert set(guarded) == set(plain)
    assert guarded["context_id"] in BANK_IDS
    assert guarded["context_id"] == transfer.context_id_for(guarded["context_id"])
    assert guarded["target_skill"] == plain["target_skill"]
    assert guarded["assessed_skill"] == plain["assessed_skill"]


def test_get_and_post_resolve_the_same_guarded_surface():
    family = "transfer:shopping"
    others = _isolate(family)
    details = transfer.available_instance_details(family, "supermarket")
    for attempt in range(len(details)):
        attempts = {family: {"attempts": attempt}}
        got = transfer.context_for(
            "supermarket", used_context_ids=others, attempts_by_context=attempts
        )
        index = got["instance_index"]
        assert index == transfer.context_instance_index(
            family, attempt, target="supermarket", unit="supermarket"
        )
        # El GET sirve la superficie `index` y el POST (misma rotación, mismo
        # guard) persistiría la carga de ESA superficie.
        assert got["prompt"].startswith(details[index]["prompt"])
        assert got["instance_difficulty_vector"] == transfer.served_difficulty(
            family, attempts, target="supermarket", unit="supermarket"
        )
        assert got["instance_difficulty_vector"] == (
            transfer.context_instance_difficulty(
                family, index, target="supermarket"
            )
        )


# ===========================================================================
# Bloque B — Identidad inmutable de instancia (defecto 2 de la auditoría `T`)
# ===========================================================================


def test_every_declared_slug_resolves_to_its_own_surface():
    for context in BANK:
        family = transfer.context_id_for(context)
        details = transfer.context_instance_details(family)
        for index, detail in enumerate(details):
            slug = str(detail["instance"])
            got = transfer.serve_instance(family, slug)
            assert got["count"] == len(details), family
            assert got["suppressed"] == 0, family
            if not slug:
                # La superficie histórica no tiene slug: sin identidad que
                # resolver se cae a la rotación y se declara no coincidente.
                assert got["matched"] is False, family
                continue
            assert got["matched"] is True, (family, slug)
            assert got["index"] == index, (family, slug)
            assert got["instance"] == slug
            assert got["difficulty"] == transfer.context_instance_difficulty(
                family, index
            )


def test_the_answered_surface_keeps_its_difficulty_when_the_counter_moves():
    # Corazón del defecto T-02: el contador avanza (otra respuesta simultánea, un
    # reintento de red) y el POST NO debe recalcular la superficie. Se busca una
    # superficie con ajuste cuya carga DIFIERA de la que la rotación sirve justo
    # después, para que la prueba discrimine de verdad.
    family = _delta_family()
    details = transfer.context_instance_details(family)
    attempt = 0
    while attempt <= len(details):
        index = transfer.context_instance_index(
            family, attempt, unit="travel"
        )
        vector = transfer.context_instance_difficulty(family, index)
        if (
            attempt >= 3
            and details[index]["difficulty_delta"]
            and vector != _served_vector(family, attempt + 1)
        ):
            break
        attempt += 1
    else:
        raise AssertionError("no se encontró una superficie discriminante")
    slug = str(details[index]["instance"])
    # El contador AVANZA (otra respuesta simultánea, un reintento de red): el
    # cálculo viejo —recalcular la rotación con el contador actual— habría
    # persistido OTRA carga.
    attempts = {family: {"attempts": attempt + 1}}
    assert transfer.served_difficulty(family, attempts, unit="travel") != vector
    assert transfer.context_instance_index(
        family, attempt, unit="travel"
    ) != transfer.context_instance_index(family, attempt + 1, unit="travel")
    # Y la superficie RESPONDIDA conserva su carga (el slug manda).
    got = transfer.serve_instance(family, slug, attempts, unit="travel")
    assert got["matched"] is True
    assert got["index"] == index
    assert got["difficulty"] == vector
    assert transfer.served_difficulty_for_instance(
        family, slug, attempts, unit="travel"
    ) == vector


def test_an_unknown_or_missing_slug_falls_back_to_the_current_rotation():
    family = _delta_family()
    for attempt in range(1, 8):
        attempts = {family: {"attempts": attempt}}
        expected_index = transfer.context_instance_index(
            family, attempt, unit="travel"
        )
        expected = transfer.served_difficulty(family, attempts, unit="travel")
        for slug in ("", "no-existe", "  ", None, 42):
            got = transfer.serve_instance(family, slug, attempts, unit="travel")
            assert got["matched"] is False, slug
            assert got["index"] == expected_index, (slug, attempt)
            assert got["difficulty"] == expected, (slug, attempt)
        # La fachada del ledger degrada exactamente igual.
        assert (
            transfer.served_difficulty_for_instance(
                family, "", attempts, unit="travel"
            )
            == expected
        )


def test_serve_instance_of_an_unknown_family_is_empty_and_never_raises():
    for value in (None, "", "no-existe", 42, [], {}):
        assert transfer.serve_instance(value, "cualquiera") == {
            "instance": "",
            "index": 0,
            "count": 0,
            "matched": False,
            "difficulty": {},
            "suppressed": 0,
        }, value
    # Familia reconocible pero sin slug conocido: la rotación, nunca vacío.
    got = transfer.serve_instance("transfer:story", "no-existe")
    assert got["matched"] is False
    assert got["count"] == len(transfer.context_instance_details("story"))
    assert got["difficulty"] == transfer.context_difficulty("story")


def test_the_guard_is_applied_when_resolving_the_answered_surface():
    family = "transfer:shopping"
    details = transfer.context_instance_details(family)
    leaked = next(
        detail
        for detail in details
        if transfer.surface_reveals_target(detail, "supermarket")
    )
    got = transfer.serve_instance(
        family, str(leaked["instance"]), target="supermarket"
    )
    # Una superficie retirada por el guard no es "respondible": no se declara
    # coincidente y se cae a la rotación de las superficies seguras.
    assert got["matched"] is False
    assert got["suppressed"] == 12
    assert got["index"] == transfer.context_instance_index(
        family, 0, target="supermarket"
    )


def test_the_api_persists_the_difficulty_of_the_answered_surface(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B1")
    # Se aísla una familia con ajuste de carga para que las superficies tengan
    # cargas distintas y la prueba discrimine de verdad.
    family = _delta_family()
    bank = tuple(
        context for context in BANK if transfer.context_id_for(context) == family
    )
    monkeypatch.setattr(transfer, "TRANSFER_CONTEXTS", bank)

    with TestClient(app) as client:
        attempt = 0
        body = _get_context(client, uid, "travel")
        while attempt <= body["instance_count"]:
            if (
                attempt >= 3
                and body["instance_difficulty_delta"]
                and body["instance_difficulty_vector"]
                != _served_vector(family, attempt + 1)
            ):
                break
            _record_attempt(uid, "travel", family, success=False)
            attempt += 1
            body = _get_context(client, uid, "travel")
        else:
            raise AssertionError("no se encontró una superficie discriminante")

        slug = body["context_instance"]
        answered_index = body["instance_index"]
        answered_vector = body["instance_difficulty_vector"]
        assert slug and body["instance_difficulty_delta"]
        # El contador AVANZA entre el GET y el POST (respuesta simultánea): la
        # superficie que el alumno respondió ya no es la que la rotación sirve.
        _record_attempt(uid, "travel", family, success=False)
        assert transfer.context_instance_index(
            family, attempt + 1, target="travel", unit="travel"
        ) != answered_index

        res = client.post(
            "/api/vocabulary/drill/transfer-attempt",
            params={"user_id": uid},
            json={
                "word": "travel",
                "text": "I would like to travel abroad with my family next spring.",
                "context_id": family,
                "context_instance": slug,
            },
        )
        assert res.status_code == 200, res.text
        out = res.json()

    assert out["context_instance"] == slug
    assert out["instance_index"] == answered_index
    assert out["instance_matched"] is True
    assert out["instance_count"] == len(
        transfer.available_instance_details(family, "travel")
    )
    rows = [
        row
        for row in evidence_repo.list_evidence(uid, "travel", target_type="lexicon")
        if row["served_difficulty"]
    ]
    assert len(rows) == 1
    # La dificultad persistida es la de la superficie RESPONDIDA, no la de la
    # siguiente rotación (regresión T-02).
    assert rows[0]["served_difficulty"] == difficulty.format_vector(answered_vector)
    assert rows[0]["context_instance"] == slug
    assert rows[0]["context_id"] == family


def test_the_api_degrades_without_a_slug_like_v3_60(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B1")
    family = _delta_family()
    bank = tuple(
        context for context in BANK if transfer.context_id_for(context) == family
    )
    monkeypatch.setattr(transfer, "TRANSFER_CONTEXTS", bank)

    with TestClient(app) as client:
        res = client.post(
            "/api/vocabulary/drill/transfer-attempt",
            params={"user_id": uid},
            json={
                "word": "travel",
                "text": "I would like to travel abroad with my family next spring.",
                "context_id": family,
                # Cliente legacy: sin `context_instance` (default "").
            },
        )
        assert res.status_code == 200, res.text
        out = res.json()

    assert out["instance_matched"] is False
    assert out["instance_index"] == 0
    assert out["instance_suppressed"] == 0
    expected = transfer.served_difficulty(
        family, {family: {"attempts": 0}}, target="travel", unit="travel"
    )
    rows = [
        row
        for row in evidence_repo.list_evidence(uid, "travel", target_type="lexicon")
        if row["served_difficulty"]
    ]
    assert rows[0]["served_difficulty"] == difficulty.format_vector(expected)
    assert rows[0]["context_instance"] == ""


# ===========================================================================
# Bloque C — Instance-aware Evidence (ledger aditivo)
# ===========================================================================


def test_the_ledger_schema_has_the_additive_instance_column(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    columns = {
        row[1] for row in db._conn().execute("PRAGMA table_info(learning_evidence)")
    }
    assert "context_instance" in columns
    assert "context_id" in columns


def test_evidence_without_a_surface_keeps_the_empty_instance(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")
    _record_attempt(uid, "travel", "transfer:story", success=True)
    rows = evidence_repo.list_evidence(uid, "travel", target_type="lexicon")
    assert len(rows) == 1
    # Fila legacy / drill sin banco: la columna aditiva queda vacía.
    assert rows[0]["context_instance"] == ""
    assert rows[0]["context_id"] == "transfer:story"


def test_the_surface_never_fragments_the_family_identity(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel")
    family = "transfer:debate"
    slug = str(transfer.context_instance_details(family)[12]["instance"])
    assert slug
    _record_attempt(uid, "travel", family, success=True, context_instance=slug)
    row = evidence_repo.list_evidence(uid, "travel", target_type="lexicon")[0]
    assert row["context_instance"] == slug
    # La identidad de evidencia es la FAMILIA: nunca `transfer:id:slug`.
    assert row["context_id"] == family
    assert row["context_id"] != f"{family}:{slug}"
    assert row["context_id"].count(":") == 1
    assert row["context_id"].endswith(transfer._bare_context_id(family))
    # El resumen sigue contando la FAMILIA (una sola entrada de contexto).
    summary = evidence_repo.summarize_by_target(uid, target_type="lexicon")["travel"]
    assert list(summary["contexts"]) == [family]


# ===========================================================================
# Bloque D — P1-01: espacio paramétrico no memorizable
# ===========================================================================


def test_the_cap_is_stratified_and_deterministic():
    total = 1000
    limit = transfer.CONTEXT_INSTANCE_SPACE_MAX
    indices = transfer._stratified_indices(total, limit)
    assert len(indices) == limit
    assert indices[0] == 0
    assert list(indices) == sorted(set(indices))
    assert indices == transfer._stratified_indices(total, limit)
    # Ningún eje queda hambriento: el muestreo equiespaciado reparte la
    # cobertura por TODO el producto, no por un prefijo.
    spec = transfer.context_instance_spec(
        {
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
    )
    axes = [(name, tuple(spec["slots"][name])) for name in spec["order"]]
    lengths = [len(values) for _name, values in axes]
    seen = {name: set() for name, _values in axes}
    for index in indices:
        partial = transfer._partial_at(axes, lengths, index)
        for name in seen:
            seen[name].add(partial["values"][name])
    for name, values in seen.items():
        assert len(values) >= 5, name
    # Y por debajo del techo el orden es EXACTAMENTE el de V3.60 (0..total-1).
    assert transfer._stratified_indices(7, limit) == tuple(range(7))
    # Sin espacio no hay posiciones (ni excepción).
    assert transfer._stratified_indices(0, limit) == ()
    assert transfer._stratified_indices(total, 0) == ()


def test_the_first_three_attempts_are_the_v3_59_surfaces():
    for context in BANK:
        for attempt in (0, 1, 2):
            assert transfer.context_instance_index(context, attempt) == attempt
            assert transfer.context_instance_index(
                context, attempt, unit="travel"
            ) == attempt
            assert transfer.context_instance_index(
                context, attempt, target="a journey", unit="travel"
            ) == attempt


def test_the_rotation_from_the_third_attempt_is_permuted_and_item_aware():
    permuted = 0
    item_aware = 0
    for context in BANK:
        family = transfer.context_id_for(context)
        count = len(transfer.context_instances(family))
        if count < 4:
            continue
        # Biyección: un ciclo completo visita TODO el espacio (no repite).
        for cycle in range(3):
            visited = {
                transfer.context_instance_index(context, cycle * count + attempt)
                for attempt in range(count)
            }
            assert visited == set(range(count)), family
        order = [
            transfer.context_instance_index(context, 3 + step)
            for step in range(count - 3)
        ]
        if order != list(range(3, count)):
            permuted += 1
        if any(
            transfer.context_instance_index(context, 3 + step, unit="a")
            != transfer.context_instance_index(context, 3 + step, unit="b")
            for step in range(count - 3)
        ):
            item_aware += 1
    # El ciclo ya no es el orden declarado y depende del ítem.
    assert permuted >= 1
    assert item_aware >= 1


def test_the_guarded_rotation_never_serves_a_retired_surface():
    family = "transfer:shopping"
    details = transfer.available_instance_details(family, "supermarket")
    for attempt in range(len(details) * 2):
        index = transfer.context_instance_index(
            family, attempt, target="supermarket", unit="supermarket"
        )
        assert 0 <= index < len(details)
        assert not transfer.surface_reveals_target(details[index], "supermarket")


# ===========================================================================
# Bloque E — P1-02: validación de contenido del espacio
# ===========================================================================


def test_the_real_bank_passes_the_content_validator():
    report = transfer_audit.validate_bank()
    assert report["families"] == len(BANK) == 20
    assert report["ok"] is True
    assert report["errors"] == []
    assert report["surfaces"] >= 20 * transfer.CONTEXT_INSTANCE_SPACE_MIN
    for family_report in report["reports"]:
        assert family_report["surfaces"] >= transfer.CONTEXT_INSTANCE_SPACE_MIN
        assert family_report["surfaces"] <= transfer.CONTEXT_INSTANCE_SPACE_MAX


def test_the_validator_checks_the_unit_has_a_servable_surface():
    report = transfer_audit.validate_bank(BANK, target="supermarket")
    # El banco real conserva tarea para la unidad aunque una familia la delate.
    assert report["ok"] is True
    assert report["errors"] == []
    assert {entry["code"] for entry in report["warnings"]} <= {
        "guarded_surfaces",
        "demand_spread",
    }
    shopping = transfer_audit.validate_instance_space(
        "shopping", "supermarket"
    )
    guarded = next(
        entry
        for entry in shopping["advisories"]
        if entry["code"] == "guarded_surfaces"
    )
    assert "12" in guarded["detail"]


def _synthetic(**overrides) -> dict:
    base = {
        "id": "syn",
        "prompt": "Base prompt.",
        "register": "formal",
        "difficulty_vector": {
            "lexical": 3,
            "syntax": 3,
            "discourse": 3,
            "interaction": 3,
        },
        "instance_space": {
            "template": "Do {a} with {b}.",
            "slots": {
                "a": tuple(f"a{index}" for index in range(4)),
                "b": tuple(f"b{index}" for index in range(4)),
            },
        },
    }
    base.update(overrides)
    return base


def _codes(family: dict, target: str = "") -> tuple[set[str], set[str]]:
    report = transfer_audit.validate_instance_space(family, target)
    return (
        {entry["code"] for entry in report["violations"]},
        {entry["code"] for entry in report["advisories"]},
    )


def test_the_validator_accepts_a_coherent_synthetic_family():
    errors, advisories = _codes(_synthetic())
    assert errors == set()
    assert advisories == set()


def test_the_validator_flags_the_space_size_invariants():
    errors, _advisories = _codes(
        _synthetic(
            instance_space={"template": "Do {a}.", "slots": {"a": ("only",)}}
        )
    )
    assert "below_min" in errors
    errors, _advisories = _codes(
        _synthetic(
            instance_space={
                "template": "Do {a} {b}.",
                "slots": {
                    "a": tuple(f"a{index}" for index in range(12)),
                    "b": tuple(f"b{index}" for index in range(12)),
                },
            }
        )
    )
    assert "above_max" in errors


def test_the_validator_flags_unresolved_placeholders_and_slug_problems():
    errors, _advisories = _codes(
        _synthetic(
            instances=(
                {"instance": "uno", "prompt": "Do {left} today."},
                {"instance": "dos", "prompt": "Do the other thing."},
                {"instance": "dos", "prompt": "Do a third thing."},
                {"prompt": "Do a fourth thing."},
            )
        )
    )
    assert {"unresolved_placeholder", "duplicate_instance_slug"} <= errors
    assert "missing_instance_slug" in errors


def test_the_validator_flags_deltas_without_a_coherent_justification():
    errors, _advisories = _codes(
        _synthetic(
            instance_space={
                "template": "Do {a}.",
                "difficulty_delta": {"discourse": 1},
                "slots": {
                    "a": (
                        {"value": "a", "difficulty_delta": {"discourse": 1}},
                        {"value": "b", "difficulty_delta": {"discourse": 3}},
                        {"value": "c", "difficulty_delta": {"discourse": 1.5}},
                        {"value": "d", "difficulty_delta": {"nonsense": 1}},
                        {
                            "value": "e",
                            "scenario": "A scene.",
                            "difficulty_delta": {"lexical": 1},
                        },
                    )
                },
            }
        )
    )
    assert {
        "delta_without_justification",
        "delta_out_of_range",
        "delta_not_integer",
        "delta_unknown_dimension",
    } <= errors


def test_the_validator_flags_register_and_skill_declarations():
    errors, _advisories = _codes(
        _synthetic(
            instance_space={
                "template": "Do {a}.",
                "slots": {
                    "a": (
                        {
                            "value": "a",
                            "register": "casual",
                            "skill_delta": ("pronunciation",),
                        },
                    )
                },
            }
        )
    )
    assert "register_mismatch" in errors
    assert "skill_delta_unknown" in errors
    # La MISMA declaración con el registro coherente y competencias del
    # vocabulario deja de violar el invariante: `family.register` es la
    # identidad y `instance.register` su realización local.
    errors, _advisories = _codes(
        _synthetic(
            instance_space={
                "template": "Do {a}.",
                "slots": {
                    "a": (
                        {
                            "value": "a",
                            "register": "formal",
                            "skill_delta": ("written_production",),
                        },
                    )
                },
            }
        )
    )
    assert "register_mismatch" not in errors
    assert "skill_delta_unknown" not in errors


def test_the_validator_flags_families_without_a_usable_specification():
    errors, _advisories = _codes({"id": "x", "prompt": "Solo la familia."})
    assert {"no_instance_space", "below_min"} <= errors
    errors, _warnings = _codes(
        _synthetic(
            instance_space={
                # El placeholder no lo declara ningún slot: la especificación no
                # es utilizable y la familia no genera ninguna superficie.
                "template": "Missing {other}.",
                "slots": {"when": ("x",)},
            }
        )
    )
    assert "unusable_spec" in errors
    # Un slot declarado que la plantilla no interpola: aviso, no error.
    errors, warnings = _codes(
        _synthetic(
            instance_space={
                "template": "Do {a} with {b}.",
                "slots": {
                    "a": tuple(f"a{index}" for index in range(4)),
                    "b": tuple(f"b{index}" for index in range(4)),
                    "unused": ("u1", "u2"),
                },
            }
        )
    )
    assert "unused_slots" in warnings
    assert errors == set()
    # El delta BASE sin ninguna declaración que lo explique: aviso.
    errors, warnings = _codes(
        _synthetic(
            instance_space={
                "template": "Do {a} with {b}.",
                "difficulty_delta": {"discourse": 1},
                "slots": {
                    "a": tuple(f"a{index}" for index in range(4)),
                    "b": tuple(f"b{index}" for index in range(4)),
                },
            }
        )
    )
    assert "base_delta_without_justification" in warnings


def test_the_validator_requires_a_servable_surface_for_the_unit():
    family = _synthetic(prompt="You are in a supermarket.")
    family["instance_space"]["template"] = "In a supermarket, do {a} with {b}."
    errors, _advisories = _codes(family, "supermarket")
    assert "no_safe_surface" in errors
    # Y la misma familia sin unidad objetivo pasa: el invariante solo actúa
    # cuando hay una palabra que proteger.
    errors, _advisories = _codes(family)
    assert "no_safe_surface" not in errors


def test_the_validator_reports_unknown_families_instead_of_raising():
    for value in (None, "", "no-existe", 42, [], {}):
        report = transfer_audit.validate_instance_space(value)
        assert report["ok"] is False
        assert {entry["code"] for entry in report["violations"]} == {
            "unknown_family"
        }, value


def test_the_demand_profile_is_advisory_and_declared_heuristic():
    simple = transfer_audit.demand_profile("Sort the files.")
    dense = transfer_audit.demand_profile(
        "Explain and justify your opinion, because your manager disagreed, "
        "although you had prepared the figures."
    )
    assert simple["heuristic"] is True
    assert dense["heuristic"] is True
    assert 1 <= simple["score"] <= 5
    assert 1 <= dense["score"] <= 5
    assert dense["score"] > simple["score"]
    assert dense["signals"]["argumentation"] >= 1
    # El perfil NO es un invariante: una familia con demanda dispar solo AVISA.
    family = _synthetic(
        instance_space={
            "template": "{a}",
            "slots": {
                "a": (
                    "Sort the files.",
                    *(f"Sort shelf {index}." for index in range(11)),
                    "Explain and justify your opinion, because your manager "
                    "disagreed, although you had prepared the figures.",
                )
            },
        }
    )
    errors, advisories = _codes(family)
    assert errors == set()
    assert "demand_spread" in advisories


def test_the_validator_bank_facade_gates_on_errors_only():
    broken = _synthetic(
        instance_space={"template": "Do {a}.", "slots": {"a": ("only",)}}
    )
    report = transfer_audit.validate_bank((*BANK, broken))
    assert report["families"] == len(BANK) + 1
    assert report["ok"] is False
    assert any(entry["code"] == "below_min" for entry in report["errors"])


# ===========================================================================
# Bloque F — Contrato aditivo
# ===========================================================================


def test_the_schemas_expose_the_additive_instance_contract():
    context_keys = set(schemas.TransferContextOut.model_fields)
    assert {
        "context_instance",
        "instance_index",
        "instance_count",
        "instance_suppressed",
        "instance_guarded",
    } <= context_keys
    attempt_out_keys = set(schemas.TransferAttemptOut.model_fields)
    assert {
        "context_instance",
        "instance_index",
        "instance_count",
        "instance_matched",
        "instance_suppressed",
    } <= attempt_out_keys
    assert "context_instance" in schemas.TransferAttemptIn.model_fields
    # Opcional de verdad: el cliente legacy sigue siendo válido.
    legacy = schemas.TransferAttemptIn(word="travel", text="I travel.")
    assert legacy.context_instance == ""


def test_the_payload_matches_the_context_contract():
    got = transfer.context_for("travel")
    assert set(got) == set(schemas.TransferContextOut.model_fields)
    # El guard añade sus dos claves a las 36 de V3.60, sin tocar ninguna otra.
    assert got["instance_guarded"] is True
    assert got["instance_suppressed"] == 0
    assert set(got) - {"instance_suppressed", "instance_guarded"} == set(
        schemas.TransferContextOut.model_fields
    ) - {"instance_suppressed", "instance_guarded"}


def test_the_empty_bank_return_carries_the_guard_defaults(monkeypatch):
    monkeypatch.setattr(transfer, "TRANSFER_CONTEXTS", ())
    got = transfer.context_for("travel")
    assert got["available"] is False
    assert got["instance_suppressed"] == 0
    assert got["instance_guarded"] is False
    assert set(got) == set(schemas.TransferContextOut.model_fields)
