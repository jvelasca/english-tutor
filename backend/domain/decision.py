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
from services import skill_axis
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
            lexicon=lexicon,
            academy=academy,
            listening=listening,
            pronunciation=pronunciation,
            objectives=skill_axis.objective_competences_index(),
        ),
    }


def _seal_state(state: dict) -> str:
    """Serializa el estado con JSON determinista (el mismo del perfil)."""
    return json.dumps(state, ensure_ascii=False, sort_keys=True)


# Reintentos acotados del sellado estable (V3.64.1). El sello solo se acepta
# cuando la huella de las fuentes es IDÉNTICA antes y después de leer/calcular el
# estado: así el estado sellado describe EXACTAMENTE la evidencia del sello.
_SEAL_MAX_ATTEMPTS = 3


async def _recompute(user_id: str, *, level: str, now: str) -> tuple[dict, str]:
    """Recomputa el estado desde las cuatro fuentes y lo re-sella (V3.64).

    Devuelve `(estado, sello)`. El invariante de sellado es: el sello guardado
    debe ser ≤ (en evidencia) el estado, NUNCA mayor. Por eso la huella se toma
    ANTES y DESPUÉS de leer las fuentes: si entrara evidencia en medio (huella
    distinta), se reintenta; si tras agotar los reintentos siguen sin coincidir,
    se devuelve el sello ANTERIOR (más viejo que el estado), de modo que la caché
    se reportará NO fresca y se recomputará, en lugar de servir un estado viejo
    sellado con una huella nueva.
    """
    for _ in range(_SEAL_MAX_ATTEMPTS):
        seal_before = await run_in_threadpool(
            evidence_repo.evidence_fingerprint, user_id
        )
        sources = await canonical_sources(user_id)
        state = skill_state_service.skill_state(
            sources["state_rows"], level=level, now=now
        )
        seal_after = await run_in_threadpool(
            evidence_repo.evidence_fingerprint, user_id
        )
        if seal_before == seal_after:
            return state, seal_after
    return state, seal_before


def project_state(
    state: dict,
    *,
    source: str = "",
    sealed: bool = False,
    snapshot_fingerprint: str = "",
) -> dict:
    """Proyecta un estado YA calculado a un payload de decisión (V3.64, puro).

    Único punto donde el payload `{state, projection, capacity_by_skill,
    skill_values, drivers, source, sealed, snapshot_fingerprint}` se ensambla,
    para que el camino de la cola (`decision_projection`, con I/O) y el del perfil
    (que ya tiene el estado en la mano y no debe releerlo) no puedan divergir.

    `snapshot_fingerprint` (V3.64.1, P1-02) es la huella de las cuatro fuentes
    observada al INICIO de la decisión: identifica el snapshot de evidencia sobre
    el que se tomó. Es un token de trazabilidad, NO el sello de caché (que sigue
    gestionando `skill_state_is_fresh`). El camino del perfil lo deja vacío porque
    no es una decisión.
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
        "source": source,
        "sealed": sealed,
        "snapshot_fingerprint": snapshot_fingerprint,
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
    - `snapshot_fingerprint` — huella de las cuatro fuentes observada al INICIO de
      la decisión (V3.64.1, P1-02): la decisión se toma sobre el snapshot de
      evidencia vigente en ese instante, formalizado y trazable.

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
    if profile is not None:
        try:
            if await run_in_threadpool(profile_repo.skill_state_is_fresh, user_id):
                state = skill_state_service.normalize_skill_state(
                    profile.get("skill_state")
                )
                source = "cached"
            else:
                source = "recomputed"
        except Exception:  # noqa: BLE001 — preferencia no bloqueante
            source = "recomputed"
    else:
        state = skill_state_service.empty_skill_state()
        source = "recomputed"
    if source == "recomputed":
        try:
            state, seal = await _recompute(user_id, level=level, now=now)
        except Exception:  # noqa: BLE001 — sin estado la cola degrada a V3.63
            return None
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
    return project_state(
        state,
        source=source,
        sealed=sealed,
        snapshot_fingerprint=snapshot_fingerprint,
    )


def empty_projection() -> dict:
    """Proyección neutra con la MISMA forma (dict nuevo en cada llamada)."""
    return project_state(skill_state_service.empty_skill_state(), source="none")


def projection_now() -> str:
    """Marca temporal del recálculo (el llamador la lee UNA vez y la reutiliza)."""
    return datetime.now(timezone.utc).isoformat()
