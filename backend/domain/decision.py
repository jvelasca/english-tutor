"""Decision Projection del alumno: de las filas canónicas a la DECISIÓN (V3.64).

Cierra el **P1-01** de la auditoría de V3.62: hasta V3.63 el Student Skill State
era **descriptivo** (se construía, se persistía y se exponía, pero la decisión de
tareas seguía leyendo el estado de V3.54). Aquí vive el puente declarado:

    Student Skill State  →  DECISION PROJECTION  →  Planner 3.0

**Nunca** `skill_state → planner`. El planner sigue siendo puro y ciego al estado
persistido: recibe `capacity_by_skill`/`skill_values`/`drivers`, que son
proyecciones calculadas por `services.decision_projection`.

Invariantes de este módulo (I/O, no puro):

- La proyección se deriva de las **filas canónicas** (las MISMAS cuatro fuentes
  que alimentan el estado), nunca de la caché como fuente de verdad.
- La caché sellada (`learning_profile.skill_state` + `skill_state_source`, V3.63)
  es **solo** la optimización O(1) y **siempre** se valida con
  `evidence_fingerprint`/`skill_state_is_fresh` antes de usarse.
- Si la caché está VIEJA, está vacía o es legacy sin sello, se **recomputa UNA
  vez** desde las cuatro fuentes y se vuelve a sellar. `source` declara cuál de
  los dos caminos se siguió (`cached`/`recomputed`), para que el comportamiento
  sea auditable y comprobable.
- Sin fila de perfil no se inventa caché: se recomputa y se proyecta sin
  persistir (la degradación es exacta al camino de V3.63, que no usa proyección).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from starlette.concurrency import run_in_threadpool

from repositories import academy as academy_repo
from repositories import evidence as evidence_repo
from repositories import listening as listening_repo
from repositories import profile as profile_repo
from repositories import pronunciation as pronunciation_repo
from services import decision_projection as projection_service
from services import observed_difficulty, skill_axis
from services import skill_state as skill_state_service
from services.evidence import LEXICAL_SKILLS


async def canonical_sources(user_id: str) -> dict:
    """Lee las CUATRO fuentes canónicas y ensambla las filas del estado (V3.62).

    Helper COMPARTIDO con `domain.profile`: la secuencia "leer las cuatro fuentes
    → `skill_state_sources`" vive aquí UNA sola vez, para que el recálculo bajo
    demanda de V3.64 no la duplique (y no pueda divergir del perfil).

    Devuelve `{lexicon, academy, listening, pronunciation, state_rows}`: las filas
    crudas (que el perfil necesita además para el estado observado de V3.53/V3.54)
    y las filas canónicas ya ensambladas del estado unificado.
    """
    lexicon = await run_in_threadpool(evidence_repo.list_observed_rows, user_id)
    # V3.65: telemetría COMPLETA (éxitos Y fallos, con identidad de ítem) para el
    # estado unificado. `lexicon` (solo éxitos) sigue alimentando el estado legacy
    # de V3.53/V3.54 (`observed_signals`); el fallo es un INTENTO del estado nuevo.
    lexicon_attempts = await run_in_threadpool(
        evidence_repo.list_attempt_rows, user_id
    )
    academy = await run_in_threadpool(academy_repo.list_evidence, user_id)
    listening = await run_in_threadpool(listening_repo.list_attempts, user_id)
    pronunciation = await run_in_threadpool(
        pronunciation_repo.list_attempts, user_id
    )
    return {
        "lexicon": lexicon,
        "academy": academy,
        "listening": listening,
        "pronunciation": pronunciation,
        "state_rows": skill_state_service.skill_state_sources(
            lexicon=lexicon_attempts,
            academy=academy,
            listening=listening,
            pronunciation=pronunciation,
            objectives=skill_axis.objective_competences_index(),
        ),
    }


async def _empirical_maps(user_id: str) -> tuple[dict, dict]:
    """Mapas EMPÍRICOS por TAREA y por ITEM desde el ledger léxico (V3.67, I/O).

    Lee `list_attempt_rows` (éxitos Y fallos con identidad de ítem y contexto) y
    deriva las filas canónicas léxicas con `skill_state_sources`, para aplicar
    después las DOS granularidades de V3.67:

    - `empirical_success_by_task` — por `task_signature` (la TAREA completa);
    - `empirical_success_by_target` — por `target_id` (el ITEM; Nivel A).

    Es una lectura INDEPENDIENTE de la caché del estado (un read por construcción
    de la proyección): el mapa describe el ledger del candidato, no la celda
    agregada. Devuelve `(by_task, by_target)`.
    """
    attempts = await run_in_threadpool(evidence_repo.list_attempt_rows, user_id)
    rows = skill_state_service.skill_state_sources(lexicon=attempts)
    return (
        observed_difficulty.empirical_success_by_task(rows),
        observed_difficulty.empirical_success_by_target(rows),
    )


def _seal_state(state: dict) -> str:
    """Serializa el estado con JSON determinista (el mismo del perfil)."""
    return json.dumps(state, ensure_ascii=False, sort_keys=True)


# Reintentos acotados del sellado estable (V3.64.1). El sello solo se acepta
# cuando la huella de las fuentes es IDÉNTICA antes y después de leer/calcular el
# estado: así el estado sellado describe EXACTAMENTE la evidencia del sello.
_SEAL_MAX_ATTEMPTS = 3


async def _recompute(
    user_id: str, *, level: str, now: str
) -> tuple[dict, str, dict, dict]:
    """Recomputa el estado desde las cuatro fuentes y lo re-sella (V3.64 → V3.67).

    Devuelve `(estado, sello, by_task, by_target)`. El invariante de sellado es:
    el sello guardado debe ser ≤ (en evidencia) el estado, NUNCA mayor. Por eso la
    huella se toma ANTES y DESPUÉS de leer las fuentes: si entrara evidencia en
    medio (huella distinta), se reintenta; si tras agotar los reintentos siguen
    sin coincidir, se devuelve el sello ANTERIOR (más viejo que el estado), de
    modo que la caché se reportará NO fresca y se recomputará, en lugar de servir
    un estado viejo sellado con una huella nueva.

    V3.67 (P2, snapshot coherente): los mapas empíricos (`by_task`/`by_target`) se
    derivan de las MISMAS filas canónicas que el estado, DENTRO del mismo lazo de
    sellado. Así `state_fingerprint` y el mapa empírico describen el MISMO
    snapshot de evidencia (la decisión es válida contra `state_fingerprint`).
    """
    for _ in range(_SEAL_MAX_ATTEMPTS):
        seal_before = await run_in_threadpool(
            evidence_repo.evidence_fingerprint, user_id
        )
        sources = await canonical_sources(user_id)
        rows = sources["state_rows"]
        state = skill_state_service.skill_state(rows, level=level, now=now)
        by_task = observed_difficulty.empirical_success_by_task(rows)
        by_target = observed_difficulty.empirical_success_by_target(rows)
        seal_after = await run_in_threadpool(
            evidence_repo.evidence_fingerprint, user_id
        )
        if seal_before == seal_after:
            return state, seal_after, by_task, by_target
    return state, seal_before, by_task, by_target


def project_state(
    state: dict,
    *,
    source: str = "",
    sealed: bool = False,
    snapshot_fingerprint: str = "",
    state_fingerprint: str = "",
    empirical_success_by_task: dict[str, dict] | None = None,
    empirical_success_by_target: dict[str, dict] | None = None,
) -> dict:
    """Proyecta un estado YA calculado a un payload de decisión (V3.64, puro).

    Único punto donde el payload `{state, projection, capacity_by_skill,
    skill_values, drivers, source, sealed, snapshot_fingerprint}` se ensambla,
    para que el camino de la cola (`decision_projection`, con I/O) y el del perfil
    (que ya tiene el estado en la mano y no debe releerlo) no puedan divergir.

    V3.66 (P1-02) separa DOS huellas en vez de una sola mal etiquetada:

    - `snapshot_fingerprint` / `decision_start_fingerprint` — la huella de las
      cuatro fuentes observada al INICIO de la decisión (lo que V3.64.1 llamaba
      `snapshot_fingerprint`). Es el token de trazabilidad del snapshot sobre el
      que se empezó a decidir.
    - `state_fingerprint` — la huella que DESCRIBE el estado efectivamente
      proyectado (el sello de la caché fresca validada, o el sello del recálculo).
      El invariante es que `state_fingerprint` representa el MISMO conjunto de
      evidencia que `state`.

    El camino del perfil (no es una decisión) deja ambas huellas vacías.

    `empirical_success_by_task` (V3.67, P1-01) es el mapa `{task_signature:
    estimación empírica}` POR TAREA (la granularidad `P(éxito | alumno, tarea)`
    con la FIRMA completa, que V3.66 aún colapsaba a `target_id`).
    `empirical_success_by_target` es el mapa `{target_id: estimación}` POR ITEM
    (Nivel A de la jerarquía). El camino del perfil los deja vacíos porque no es
    una decisión.
    """
    projection = projection_service.project(state)
    return {
        "state": state,
        "projection": projection,
        "capacity_by_skill": projection_service.capacity_by_skill(projection),
        "skill_values": projection_service.skill_values(projection),
        "drivers": {
            skill: projection_service.drivers(projection, skill)
            for skill in LEXICAL_SKILLS
        },
        # V3.65 (aditivo): la estimación EMPÍRICA de P(éxito) por eje léxico,
        # derivada de la `confidence` de la celda. Sin celda la clave por eje es
        # `{}` y el planner degrada exactamente a V3.64.
        "empirical_success": projection_service.empirical_success_by_skill(
            projection
        ),
        # V3.67 (aditivo): DOS mapas empíricos con nombres honestos — por TAREA
        # (firma completa) y por ITEM (target_id). Sin mapa la clave es `{}` y el
        # planner degrada a la granularidad por skill de V3.65.
        "empirical_success_by_task": (
            dict(empirical_success_by_task)
            if isinstance(empirical_success_by_task, dict)
            else {}
        ),
        "empirical_success_by_target": (
            dict(empirical_success_by_target)
            if isinstance(empirical_success_by_target, dict)
            else {}
        ),
        "source": source,
        "sealed": sealed,
        "snapshot_fingerprint": snapshot_fingerprint,
        # V3.66 (P1-02): las DOS huellas explícitas. `snapshot_fingerprint` se
        # conserva como alias retrocompatible de `decision_start_fingerprint`.
        "decision_start_fingerprint": snapshot_fingerprint,
        "state_fingerprint": state_fingerprint,
    }


async def decision_projection(
    user_id: str, *, level: str = "", now: str = ""
) -> dict | None:
    """Proyección de decisión del alumno (V3.64, I/O; nunca lanza).

    Devuelve `{state, projection, capacity_by_skill, skill_values, drivers,
    source, sealed, snapshot_fingerprint}`:

    - `state` — el estado unificado `{modalidad: {competencia: entry}}` desde el
      que se proyecta (caché fresca validada o recálculo sellado);
    - `projection` — la proyección completa por celda (`services.decision_projection`);
    - `capacity_by_skill` — capacidad por CANAL evaluado (reemplazo directo de
      `lexicon._capacity_by_skill`, con el filtro de comparabilidad);
    - `skill_values` — valor pedagógico proyectado por eje (el `value` del
      Planner 3.0);
    - `drivers` — `{skill: drivers}` explicables;
    - `source` — `"cached"` si la caché sellada era fresca, `"recomputed"` si hubo
      que recalcular desde las filas canónicas;
    - `sealed` — si el recálculo se persistió (una caché legible por O(1));
    - `snapshot_fingerprint` / `decision_start_fingerprint` — huella de las cuatro
      fuentes observada al INICIO de la decisión (V3.64.1 → V3.66 P1-02): la
      decisión se toma sobre el snapshot de evidencia vigente en ese instante;
    - `state_fingerprint` — huella que describe el estado efectivamente proyectado
      (sello de la caché fresca validada o sello del recálculo; V3.66 P1-02).

    `level`/`now` los aporta el llamador: este módulo NO lee el reloj (el camino
    caliente ya lo lee una vez) ni recalcula el Student Model.
    """
    snapshot_fingerprint = await run_in_threadpool(
        evidence_repo.evidence_fingerprint, user_id
    )
    try:
        profile = await run_in_threadpool(profile_repo.get_profile, user_id)
    except Exception:  # noqa: BLE001 — la proyección nunca rompe la cola
        return None
    sealed = False
    state_fingerprint = ""
    empirical_by_task: dict = {}
    empirical_by_target: dict = {}
    if profile is not None:
        try:
            if await run_in_threadpool(profile_repo.skill_state_is_fresh, user_id):
                state = skill_state_service.normalize_skill_state(
                    profile.get("skill_state")
                )
                source = "cached"
                # V3.66 (P1-02): la huella del estado proyectado es el sello de la
                # caché fresca validada — describe EXACTAMENTE el estado servido.
                state_fingerprint = str(profile.get("skill_state_source") or "")
            else:
                source = "recomputed"
        except Exception:  # noqa: BLE001 — preferencia no bloqueante
            source = "recomputed"
    else:
        state = skill_state_service.empty_skill_state()
        source = "recomputed"
    if source == "recomputed":
        try:
            # V3.67 (P2, snapshot coherente): el estado y los mapas empíricos
            # salen del MISMO lazo de sellado, de modo que `state_fingerprint` y
            # el mapa empírico describen el MISMO snapshot de evidencia.
            state, seal, empirical_by_task, empirical_by_target = await _recompute(
                user_id, level=level, now=now
            )
        except Exception:  # noqa: BLE001 — sin estado la cola degrada a V3.63
            return None
        # V3.66 (P1-02): la huella del estado proyectado es el sello del
        # recálculo (el que describe el estado devuelto), NO la huella inicial.
        state_fingerprint = seal
        # Solo se persiste si hay fila de perfil: sin ella no se inventa caché.
        if profile is not None:
            try:
                await run_in_threadpool(
                    profile_repo.set_skill_state,
                    user_id,
                    _seal_state(state),
                    seal,
                )
                sealed = True
            except Exception:  # noqa: BLE001 — el sello es una optimización
                sealed = False
    else:
        # Caché fresca: los mapas se derivan del ledger ACTUAL (coherente con el
        # sello que validó la frescura). Best-effort: sin mapa se degrada a skill.
        try:
            empirical_by_task, empirical_by_target = await _empirical_maps(user_id)
        except Exception:  # noqa: BLE001 — sin mapa se degrada a skill
            empirical_by_task = empirical_by_target = {}
    return project_state(
        state,
        source=source,
        sealed=sealed,
        snapshot_fingerprint=snapshot_fingerprint,
        state_fingerprint=state_fingerprint,
        empirical_success_by_task=empirical_by_task,
        empirical_success_by_target=empirical_by_target,
    )


def empty_projection() -> dict:
    """Proyección neutra con la MISMA forma (dict nuevo en cada llamada)."""
    return project_state(skill_state_service.empty_skill_state(), source="none")


def projection_now() -> str:
    """Marca temporal del recálculo (el llamador la lee UNA vez y la reutiliza)."""
    return datetime.now(timezone.utc).isoformat()
