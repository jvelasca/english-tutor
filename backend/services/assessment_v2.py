"""Assessment 2.0 — escalera de evaluación (V2.10).

Tipos canónicos (auditoría):

    Lesson  → formative (micro-assessment)
    Unit    → unit
    ~3 units → progress
    Level   → level (CEFR exam)
    Later   → retention (reassessment retardada)

También expone:
- `readiness` derivado de la escalera (no es un tipo de sesión).
- `mastery_evidence_gate`: MASTERED exige kinds emitibles
  (familiar×2 + transfer×2 + delayed); `novel` queda reservado sin emisor
  (F-K1, V3.24).

Motor puro y determinista: sin FastAPI ni BD.
"""

from __future__ import annotations

from datetime import datetime, timezone

from services.curriculum import Level, Objective, ObjectiveCheck, Unit

ASSESSMENT_VERSION = "2.0.0"

ASSESSMENT_KINDS: tuple[str, ...] = (
    "formative",
    "unit",
    "progress",
    "level",
    "retention",
)

# Umbral overall por tipo (0..1). El examen de nivel también exige min_per_skill
# en el scorer de exams; aquí el overall es la regla uniforme de la escalera.
PASS_THRESHOLDS: dict[str, float] = {
    "formative": 0.70,
    "unit": 0.75,
    "progress": 0.80,
    "level": 0.80,
    "retention": 0.70,
}

# Tope de ítems por tipo (None = sin tope; usa todos los checks disponibles).
ITEM_CAPS: dict[str, int | None] = {
    "formative": None,
    "unit": 12,
    "progress": 18,
    "level": None,
    "retention": None,
}

# Cada progress assessment cubre este número de unidades consecutivas.
PROGRESS_UNIT_SPAN = 3

# Días mínimos entre evaluación formal y retention reassessment.
RETENTION_MIN_DAYS = 7

# Ratio delayed/initial a partir del cual la retención se considera estable.
RETENTION_STABLE_RATIO = 0.9

# Certificación de nivel (H5): *completar ≠ certificar*. Completar el examen
# desbloquea el siguiente nivel; la certificación plena exige retención
# SOSTENIDA: ≥ este nº de reassessments estables por cada destreza del examen.
# Un reassessment estable es un evento `delayed` con ventana ≥
# RETENTION_MIN_DAYS desde su sesión formal origen Y ratio ≥
# RETENTION_STABLE_RATIO. F-A3 (V3.26, P2-02): un único delayed puntual ya no
# certifica — la retención longitudinal exige ≥ 2 puntos separados en el
# tiempo, y el escritor espacia cada reassessment nuevo ≥ RETENTION_MIN_DAYS
# desde el último del mismo origen (delayed_origin_anchors los ancla a su
# sesión formal real, no al examen más reciente).
CERTIFICATION_REQUIRED_DELAYED = 2

# V3.25 (fase 4, F-L8): ventanas de consolidación OPCIONALES para el informe
# longitudinal de retención sobre los eventos `delayed`. La certificación solo
# exige la ventana formal (§6.3, RETENTION_MIN_DAYS); estos intervalos permiten
# describir cuánto tiempo ha mantenido el alumno la retención estable después
# de cada reassessment (infraestructura, no gate nuevo).
RETENTION_INTERVALS: tuple[int, ...] = (1, 3, 7, 21)

# Regla MASTERED (auditoría §16): no basta con terminar.
# F-K1 (V3.24, dossier K): el kind `novel` no tiene emisor real, así que MASTERED
# exige solo kinds emitibles — familiar (initial/practice) + transfer×2 (unit/
# progress/level) + delayed (retention ≥7 días estable). `novel` queda reservado:
# requisito 0 hasta que exista una modalidad que lo emita de verdad.
#
# F-A1 (V3.26, P2-01): `initial` y `practice` dejan de ser dos umbrales sobre el
# mismo contador `familiar`. Con datos contextuales (context_id + created_at),
# `initial` = primer encuentro de cada contexto y `practice` = re-encuentros
# ESPACIADOS (≥ SPACED_PRACTICE_MIN_DAYS desde el primer encuentro) del MISMO
# contexto. Las filas legacy (sin contexto/fecha) conservan el fallback a
# filas/contextos (F-C4 las marcará como "experiencias no verificadas").
MASTERY_EVIDENCE_REQUIREMENTS: dict[str, int] = {
    "initial": 1,  # ≥1 contexto con primer encuentro
    "practice": 2,  # ≥2 re-encuentros espaciados del mismo contexto
    "transfer": 2,
    "delayed": 1,
}

# Separación mínima (días) entre el primer encuentro de un contexto y su
# re-encuentro para que ese re-encuentro cuente como `practice` (F-A1, V3.26).
SPACED_PRACTICE_MIN_DAYS = 1


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def familiar_spaced_counts(
    rows: list[dict], *, min_gap_days: int = SPACED_PRACTICE_MIN_DAYS
) -> dict:
    """Separa la evidencia `familiar` en encuentros iniciales y re-encuentros
    espaciados (F-A1, V3.26/P2-01).

    - `initial_xp`: nº de contextos con al menos un encuentro `familiar`
      (primer encuentro de cada contexto).
    - `practice_xp`: nº de re-encuentros del MISMO contexto separados ≥
      `min_gap_days` desde su primer encuentro. Se cuenta un re-encuentro por
      día distinto posterior (una sesión que emite varias filas el mismo día no
      infla el contador).

    Solo cuentan filas con `context_id` no vacío y `created_at` parseable: las
    filas legacy (sin contexto o con fecha corrupta) no demuestran espaciado y
    no se incluyen (el llamador decide el fallback legacy a filas/contextos).
    """
    by_context: dict[str, list[datetime]] = {}
    for r in rows:
        if (r.get("evidence_kind") or "familiar") != "familiar":
            continue
        cid = (r.get("context_id") or "").strip()
        dt = _parse_iso(r.get("created_at") or "")
        if not cid or dt is None:
            continue
        by_context.setdefault(cid, []).append(dt)
    initial_xp = len(by_context)
    practice_xp = 0
    for dates in by_context.values():
        first = min(dates).date()
        # Cada día posterior distinto con gap suficiente = un re-encuentro.
        later_days = {d.date() for d in dates if d.date() > first}
        practice_xp += sum(
            1 for d in later_days if (d - first).days >= min_gap_days
        )
    return {"initial_xp": initial_xp, "practice_xp": practice_xp}


def ordered_units(level: Level) -> list[Unit]:
    """Unidades del nivel en orden curricular (módulo.order, unit.order)."""
    units: list[Unit] = []
    for module in sorted(level.modules, key=lambda m: m.order):
        for unit in sorted(module.units, key=lambda u: u.order):
            units.append(unit)
    return units


def find_unit(level: Level, unit_id: str) -> Unit | None:
    for unit in ordered_units(level):
        if unit.id == unit_id:
            return unit
    return None


def unit_objectives(unit: Unit) -> list[Objective]:
    return [o for lesson in unit.lessons for o in lesson.objectives]


def checks_from_objectives(objectives: list[Objective]) -> list[ObjectiveCheck]:
    """Concatena checks preservando orden curricular y sin duplicar ids."""
    seen: set[str] = set()
    out: list[ObjectiveCheck] = []
    for obj in objectives:
        for check in obj.checks:
            if check.id in seen:
                continue
            seen.add(check.id)
            out.append(check)
    return out


def _cap_items(
    items: list[ObjectiveCheck], kind: str
) -> list[ObjectiveCheck]:
    cap = ITEM_CAPS.get(kind)
    if cap is None or len(items) <= cap:
        return list(items)
    # Muestreo determinista: reparte por destreza (round-robin) hasta el tope.
    by_skill: dict[str, list[ObjectiveCheck]] = {}
    for it in items:
        by_skill.setdefault(it.skill, []).append(it)
    skills = list(by_skill.keys())
    picked: list[ObjectiveCheck] = []
    index = 0
    while len(picked) < cap and skills:
        skill = skills[index % len(skills)]
        bucket = by_skill[skill]
        if bucket:
            picked.append(bucket.pop(0))
        if not bucket:
            skills = [s for s in skills if by_skill[s]]
            if not skills:
                break
            index = index % len(skills)
            continue
        index += 1
    return picked


def item_payload(check: ObjectiveCheck) -> dict:
    """Ítem seguro para el cliente (sin correct_index)."""
    return {
        "id": check.id,
        "skill": check.skill,
        "prompt": check.prompt,
        "options": list(check.options),
    }


def build_formative(objective: Objective) -> dict:
    """Micro-assessment de una lección/objetivo."""
    items = list(objective.checks)
    return {
        "kind": "formative",
        "title": f"Formative · {objective.title}",
        "objective_id": objective.id,
        "unit_id": "",
        "unit_ids": [],
        "items": [item_payload(c) for c in items],
        "item_ids": [c.id for c in items],
        "threshold": PASS_THRESHOLDS["formative"],
        "assessment_version": ASSESSMENT_VERSION,
    }


def build_unit(level: Level, unit_id: str) -> dict | None:
    unit = find_unit(level, unit_id)
    if unit is None:
        return None
    raw = checks_from_objectives(unit_objectives(unit))
    items = _cap_items(raw, "unit")
    return {
        "kind": "unit",
        "title": f"Unit assessment · {unit.title}",
        "objective_id": "",
        "unit_id": unit.id,
        "unit_ids": [unit.id],
        "items": [item_payload(c) for c in items],
        "item_ids": [c.id for c in items],
        "threshold": PASS_THRESHOLDS["unit"],
        "assessment_version": ASSESSMENT_VERSION,
    }


def build_progress(level: Level, anchor_unit_id: str) -> dict | None:
    """Progress assessment: la ancla y las (PROGRESS_UNIT_SPAN-1) anteriores."""
    units = ordered_units(level)
    ids = [u.id for u in units]
    if anchor_unit_id not in ids:
        return None
    end = ids.index(anchor_unit_id)
    start = max(0, end - (PROGRESS_UNIT_SPAN - 1))
    span = units[start : end + 1]
    if len(span) < 1:
        return None
    objs = [o for u in span for o in unit_objectives(u)]
    items = _cap_items(checks_from_objectives(objs), "progress")
    titles = " · ".join(u.title for u in span)
    return {
        "kind": "progress",
        "title": f"Progress assessment · {titles}",
        "objective_id": "",
        "unit_id": anchor_unit_id,
        "unit_ids": [u.id for u in span],
        "items": [item_payload(c) for c in items],
        "item_ids": [c.id for c in items],
        "threshold": PASS_THRESHOLDS["progress"],
        "assessment_version": ASSESSMENT_VERSION,
    }


def build_level(exam_items: list, *, exam_id: str, title: str) -> dict:
    """Envuelve el examen CEFR existente como peldaño `level`."""
    items = [
        {
            "id": it.id,
            "skill": it.skill,
            "prompt": it.prompt,
            "options": list(it.options),
        }
        for it in exam_items
    ]
    return {
        "kind": "level",
        "title": title or f"Level assessment · {exam_id}",
        "objective_id": "",
        "unit_id": "",
        "unit_ids": [],
        "exam_id": exam_id,
        "items": items,
        "item_ids": [it["id"] for it in items],
        "threshold": PASS_THRESHOLDS["level"],
        "assessment_version": ASSESSMENT_VERSION,
    }


def build_retention(previous: dict) -> dict:
    """Misma batería que una evaluación previa (reassessment retardada)."""
    return {
        "kind": "retention",
        "title": f"Retention · {previous.get('title') or previous.get('kind')}",
        "objective_id": previous.get("objective_id") or "",
        "unit_id": previous.get("unit_id") or "",
        "unit_ids": list(previous.get("unit_ids") or []),
        "source_kind": previous.get("kind") or "",
        "source_session_id": previous.get("session_id"),
        "items": list(previous.get("items") or []),
        "item_ids": list(previous.get("item_ids") or []),
        "threshold": PASS_THRESHOLDS["retention"],
        "assessment_version": ASSESSMENT_VERSION,
    }


def score_answers(
    checks: list[ObjectiveCheck] | list[dict],
    answers: dict[str, int],
) -> dict:
    """Puntúa respuestas. Acepta ObjectiveCheck o dicts con correct_index."""
    per_skill: dict[str, dict[str, int]] = {}
    correct = 0
    answered = 0
    for it in checks:
        item_id = it.id if hasattr(it, "id") else it["id"]
        skill = it.skill if hasattr(it, "skill") else it["skill"]
        correct_index = (
            it.correct_index if hasattr(it, "correct_index") else it["correct_index"]
        )
        if item_id not in answers:
            continue
        answered += 1
        bucket = per_skill.setdefault(skill, {"correct": 0, "total": 0})
        bucket["total"] += 1
        if answers[item_id] == correct_index:
            bucket["correct"] += 1
            correct += 1
    skills = {
        skill: {
            "correct": b["correct"],
            "total": b["total"],
            "score": round(b["correct"] / b["total"], 3) if b["total"] else 0.0,
        }
        for skill, b in per_skill.items()
    }
    overall = round(correct / answered, 3) if answered else 0.0
    return {
        "skills": skills,
        "correct": correct,
        "total": answered,
        "overall": overall,
    }


def evaluate(
    kind: str,
    scored: dict,
    *,
    min_per_skill: float | None = None,
) -> dict:
    """Decide pass/fail y lista destrezas fallidas."""
    if kind not in ASSESSMENT_KINDS:
        raise ValueError(f"kind desconocido: {kind}")
    threshold = PASS_THRESHOLDS[kind]
    skills = scored.get("skills") or {}
    failed: list[str] = []
    if min_per_skill is not None:
        for skill, block in skills.items():
            if block.get("score", 0.0) < min_per_skill:
                failed.append(skill)
        skill_ok = not failed if skills else False
    else:
        skill_ok = True
    overall = float(scored.get("overall") or 0.0)
    passed = bool(scored.get("total", 0) > 0) and overall >= threshold and skill_ok
    if not skill_ok and min_per_skill is None:
        failed = [
            s for s, b in skills.items() if b.get("score", 0.0) < threshold
        ]
    return {
        "kind": kind,
        "overall": overall,
        "threshold": threshold,
        "passed": passed,
        "correct": scored.get("correct", 0),
        "total": scored.get("total", 0),
        "skills": skills,
        "failed_skills": failed,
        "phase": "evaluation",
    }


def retention_delta(initial: dict, delayed: dict) -> dict:
    """Compara evaluación inicial vs retention reassessment."""
    first = float(initial.get("overall") or 0.0)
    later = float(delayed.get("overall") or 0.0)
    rate = round(later / first, 3) if first > 0 else None
    by_skill: list[dict] = []
    skills = set(initial.get("skills") or {}) | set(delayed.get("skills") or {})
    for skill in sorted(skills):
        a = (initial.get("skills") or {}).get(skill, {}).get("score")
        b = (delayed.get("skills") or {}).get(skill, {}).get("score")
        if a is None or b is None:
            delta = None
        else:
            delta = round(float(b) - float(a), 3)
        by_skill.append({"skill": skill, "initial": a, "delayed": b, "delta": delta})
    return {
        "initial_overall": first,
        "delayed_overall": later,
        "retention_rate": rate,
        "stable": rate is not None and rate >= RETENTION_STABLE_RATIO,
        "by_skill": by_skill,
        "phase": "retention",
    }


def _mean_score(rows: list[dict], skill: str = "") -> float | None:
    """Media de `result` numérico entre las filas (opcionalmente de `skill`)."""
    scores = [
        float(r["result"])
        for r in rows
        if (not skill or r.get("skill") == skill)
        and isinstance(r.get("result"), (int, float))
    ]
    return round(sum(scores) / len(scores), 3) if scores else None


def _latest_dt(rows: list[dict]) -> datetime | None:
    """`created_at` más reciente parseable entre las filas (None si ninguna)."""
    parsed = [
        dt for r in rows if (dt := _parse_iso(r.get("created_at") or "")) is not None
    ]
    return max(parsed) if parsed else None


def delayed_origin_anchors(sessions: list[dict]) -> dict[str, str]:
    """F-A2 (V3.26, P2-02): ancla de cada sesión de retención a su origen formal.

    Cada sesión `kind == "retention"` referencia en `source_session_id` la
    sesión formal que reevalúa (examen del nivel, `kind=level`/`unit`/
    `progress`). La evidencia `delayed` que escribe una sesión cerrada se
    etiqueta `context_id = "assessment_v2:retention:{session_id}"`; este helper
    resuelve para cada sesión de retención cerrada el `created_at` de su sesión
    formal origen, devolviendo un mapa `context_id → created_at` listo para
    `certification_gate(delayed_origins=...)`.

    Solo sesiones `status == "done"` (su evidencia ya está escrita) y con
    `source_session_id` resoluble y parseable producen ancla; el resto cae al
    ancla global del gate (fallback legacy).
    """
    by_id = {s.get("id"): s for s in sessions}
    out: dict[str, str] = {}
    for s in sessions:
        if s.get("kind") != "retention" or s.get("status") != "done":
            continue
        sid = s.get("id")
        origin = by_id.get(s.get("source_session_id"))
        created = (origin or {}).get("created_at")
        if sid is None or not created or _parse_iso(created) is None:
            continue
        out[f"assessment_v2:retention:{sid}"] = created
    return out


def certification_gate(
    exam_skills: list[str],
    evidence_rows: list[dict],
    *,
    now: str = "",
    delayed_origins: dict | None = None,
) -> dict:
    """Gate de certificación de un nivel (P1/H5): **completado ≠ certificado**.

    Aprobar el examen completa el nivel y desbloquea el siguiente; la
    certificación plena exige, por cada destreza del examen, retención
    retardada REAL y SOSTENIDA: ≥ `CERTIFICATION_REQUIRED_DELAYED` reassessment
    points estables — cada punto es un retention reassessment ocurrido ≥
    `RETENTION_MIN_DAYS` después de la evaluación formal del nivel y con ratio
    `delayed/initial ≥ RETENTION_STABLE_RATIO`. La presencia de filas `delayed`
    no basta: el gate reconstruye baseline y ratio desde las propias filas de
    `academy_evidence`.

    V3.25.1 (P1-01, auditoría externa V3.25): el gate ya no confía en que el
    emisor haya codificado la ventana. Verifica:

    - `formal_rows` — eventos de EXAMEN (`task_type == "exam"` con
      `evidence_kind != "delayed"`): cubre la escalera Assessment 2.0
      (`kind=level`) y el examen legacy (`submit_exam`). El ancla formal es el
      `created_at` más reciente entre ellos; `initial_score` por destreza es la
      media de `result` de esas filas. Sin filas de examen no hay baseline y
      ninguna destreza puede certificarse.
    - eventos `delayed` — filas con `evidence_kind == "delayed"` agrupadas por
      `context_id` (una sesión de retention emite una fila por ítem compartiendo
      contexto; las filas legacy sin `context_id` son cada una su propio evento).

    F-A3 (V3.26, P2-02): una destreza queda satisfecha cuando ≥
    `CERTIFICATION_REQUIRED_DELAYED` eventos `delayed` suyos son verificables
    (todos sus `created_at` parseables) con `interval_days >= RETENTION_MIN_DAYS`
    desde el ancla formal y `rate = delayed_score / initial_score >=
    RETENTION_STABLE_RATIO`. Un perfil con un único reassessment estable deja de
    certificar; el informe añade `stable_points` (eventos que cumplen ventana y
    ratio) por destreza.

    F-A2 (V3.26, P2-02, auditoría externa V3.25): cada evento `delayed` se ancla
    a la sesión formal que reevalúa cuando el llamador aporta `delayed_origins`
    (mapa `context_id → created_at` de la sesión origen, resuelto por
    `delayed_origin_anchors` desde `source_session_id`). El ancla global "examen
    más reciente del nivel" queda solo como fallback para eventos legacy sin
    contexto o sin origen resoluble. Así, un examen formal posterior (re-intento
    o review) no acorta el intervalo real de un evento previo.

    `retention_report` (informativo, no gate) expone por destreza `baseline_date`
    y `initial_score`, el intervalo formal→delayed en días de cada evento
    (`retention_interval_days`, alias retrocompatible `interval_days`), la edad
    real de cada evento respecto al momento de la consulta (`event_age_days`;
    ambos son conceptos distintos: la edad del evento no es el intervalo
    pedagógico), `longest_interval_days`, `longest_event_age_days`,
    `anchored_events`, `stable_points` (eventos que cumplen ventana y ratio),
    `intervals_reached` (RETENTION_INTERVALS) y el `rate` del mejor evento
    (`best_rate`).

    Devuelve conformidad global, conteo `delayed` por destreza y las destrezas
    pendientes de retención. Un nivel sin examen (sin destrezas exigidas) nunca
    puede quedar certificado.
    """
    # Baseline formal: eventos de examen de nivel (Assessment 2.0 kind=level y
    # submit_exam legacy). Nunca filas `delayed`.
    formal_rows = [
        r
        for r in evidence_rows
        if (r.get("task_type") or "") == "exam"
        and str(r.get("evidence_kind") or "familiar").lower() != "delayed"
    ]
    formal_anchor_dt = _latest_dt(formal_rows)
    initial_by_skill = {skill: _mean_score(formal_rows, skill) for skill in exam_skills}
    ev_now = _parse_iso(now) or datetime.now(timezone.utc)

    # Eventos `delayed`: filas agrupadas por `context_id` (una sesión de
    # retention emite una fila por ítem). Legacy sin `context_id`: cada fila es
    # su propio evento (contexto desconocido no demuestra experiencia conjunta).
    # Cada evento recuerda su `context_id` para resolver su ancla de origen.
    events: list[tuple[str, list[dict]]] = []
    by_context: dict[str, list[dict]] = {}
    for row in evidence_rows:
        if str(row.get("evidence_kind") or "").lower() != "delayed":
            continue
        if not row.get("skill"):
            continue
        cid = row.get("context_id") or ""
        if cid:
            by_context.setdefault(cid, []).append(row)
        else:
            events.append(("", [row]))
    events.extend((cid, rows) for cid, rows in by_context.items() if rows)

    delayed_by_skill: dict[str, int] = {}
    reports: dict[str, dict] = {}
    checks: dict[str, bool] = {}
    for skill in exam_skills:
        skill_events: list[dict] = []
        for cid, rows in events:
            own = [r for r in rows if r.get("skill") == skill]
            if not own:
                continue
            delayed_by_skill[skill] = delayed_by_skill.get(skill, 0) + len(own)
            ev_dt = _latest_dt(rows)
            verified = all(_parse_iso(r.get("created_at") or "") for r in own)
            # F-A2: ancla por origen real del evento (sesión formal que reevalúa)
            # con fallback al examen más reciente del nivel (legacy).
            anchor_dt = formal_anchor_dt
            anchored = bool(
                cid
                and delayed_origins is not None
                and cid in delayed_origins
                and _parse_iso(delayed_origins.get(cid) or "") is not None
            )
            if anchored:
                anchor_dt = _parse_iso(delayed_origins[cid])
            # Intervalo pedagógico formal→delayed (lo que el gate exige).
            interval_days = (
                max(0, (ev_dt - anchor_dt).days)
                if ev_dt is not None and anchor_dt is not None
                else None
            )
            # Edad del evento delayed respecto al momento de la consulta
            # (informativo; el intervalo pedagógico no depende de `now`).
            event_age_days = (
                max(0, (ev_now - ev_dt).days) if ev_dt is not None else None
            )
            delayed_score = _mean_score(own)
            initial_score = initial_by_skill.get(skill)
            rate = (
                round(delayed_score / initial_score, 3)
                if delayed_score is not None
                and initial_score not in (None, 0.0)
                else None
            )
            ok = (
                verified
                and interval_days is not None
                and interval_days >= RETENTION_MIN_DAYS
                and rate is not None
                and rate >= RETENTION_STABLE_RATIO
            )
            skill_events.append(
                {
                    "verified": verified,
                    "interval_days": interval_days,
                    "event_age_days": event_age_days,
                    "anchored": anchored,
                    "delayed_score": delayed_score,
                    "rate": rate,
                    "ok": ok,
                }
            )
        intervals = [
            e["interval_days"] for e in skill_events if e["interval_days"] is not None
        ]
        ages = [
            e["event_age_days"] for e in skill_events if e["event_age_days"] is not None
        ]
        longest = max(intervals) if intervals else 0
        longest_age = max(ages) if ages else 0
        # Mejor evento a efectos del informe: el de mayor intervalo formal→delayed
        # con ratio calculable (informativo, no gate: refleja la retención real
        # aunque no alcance el umbral de certificación).
        eligible = [
            e
            for e in skill_events
            if e["interval_days"] is not None and e["rate"] is not None
        ]
        best = max(eligible, key=lambda e: e["interval_days"]) if eligible else None
        # F-A3: la destreza certifica con ≥ CERTIFICATION_REQUIRED_DELAYED
        # reassessment points ESTABLES (eventos ok: ventana y ratio a la vez).
        stable_points = sum(1 for e in skill_events if e["ok"])
        reports[skill] = {
            "count": delayed_by_skill.get(skill, 0),
            "events": len(skill_events),
            "stable_points": stable_points,
            "verified": (
                all(e["verified"] for e in skill_events) if skill_events else True
            ),
            "baseline_date": (
                formal_anchor_dt.isoformat() if formal_anchor_dt is not None else None
            ),
            "initial_score": initial_by_skill.get(skill),
            "retention_interval_days": sorted(intervals),
            "interval_days": sorted(intervals),
            "event_age_days": sorted(ages),
            "longest_interval_days": longest,
            "longest_event_age_days": longest_age,
            "anchored_events": sum(1 for e in skill_events if e["anchored"]),
            "intervals_reached": [
                i for i in RETENTION_INTERVALS if longest >= i
            ],
            "best_rate": best["rate"] if best is not None else None,
        }
        checks[skill] = stable_points >= CERTIFICATION_REQUIRED_DELAYED

    return {
        "required": True,
        "window_min_days": RETENTION_MIN_DAYS,
        "min_delayed": CERTIFICATION_REQUIRED_DELAYED,
        "certified": bool(exam_skills) and all(checks.values()),
        "delayed_by_skill": {
            skill: delayed_by_skill.get(skill, 0) for skill in exam_skills
        },
        "retention_report": reports,
        "pending_skills": [s for s, ok in checks.items() if not ok],
        "checks": checks,
    }


def mastery_evidence_gate(
    by_kind: dict | None,
    *,
    context_counts: dict[str, int] | None = None,
    familiar_spaced: dict | None = None,
) -> dict:
    """¿Se puede considerar MASTERED? (familiar×2 + transfer×2 + delayed).

    F-K1 (V3.24, dossier K): el gate exige solo kinds **emitibles**
    (familiar de formatives/objetivos, transfer de unit/progress/level, delayed
    de retention estable). `novel` sigue en `counts` como señal (kind válido y
    reservado, sin emisor real) pero no forma parte de `checks`/`missing`.

    V3.25 (fase 3, F-L6): cuando `context_counts` se pasa (contextos distintos
    por kind derivados de los eventos), el check `transfer` exige experiencias
    distintas, no filas repetidas del mismo contexto. Si el conteo de contextos
    es 0 (legacy sin contexto declarado), retrocede al conteo de filas para no
    bloquear datos previos a V3.25. `delayed` se mide por filas: la ventana ≥7
    días ya impone separación real.

    F-A1 (V3.26, P2-01): cuando `familiar_spaced` se pasa (resultado de
    `familiar_spaced_counts` sobre las filas), `initial` y `practice` dejan de
    ser dos umbrales sobre el mismo contador `familiar`: `initial` exige ≥1
    contexto con primer encuentro y `practice` exige ≥2 re-encuentros ESPACIADOS
    del mismo contexto. Sin `familiar_spaced` (llamadas puras por conteos o
    datos legacy), se conserva el fallback legacy (filas/contextos) — F-C4 lo
    marcará como "experiencias no verificadas" en el perfil.
    """
    kinds = by_kind or {}
    familiar = int(kinds.get("familiar", 0))
    transfer = int(kinds.get("transfer", 0))
    novel = int(kinds.get("novel", 0))
    delayed = int(kinds.get("delayed", 0))

    def _experiences(kind: str, rows: int) -> int:
        if context_counts:
            ctx = int(context_counts.get(kind, 0) or 0)
            if ctx > 0:
                return ctx
        return rows

    familiar_xp = _experiences("familiar", familiar)
    transfer_xp = _experiences("transfer", transfer)

    if familiar_spaced is not None:
        initial_xp = int(familiar_spaced.get("initial_xp", 0))
        practice_xp = int(familiar_spaced.get("practice_xp", 0))
    else:
        initial_xp = familiar_xp
        practice_xp = familiar_xp

    checks = {
        "initial": initial_xp >= MASTERY_EVIDENCE_REQUIREMENTS["initial"],
        "practice": practice_xp >= MASTERY_EVIDENCE_REQUIREMENTS["practice"],
        "transfer": transfer_xp >= MASTERY_EVIDENCE_REQUIREMENTS["transfer"],
        "delayed": delayed >= MASTERY_EVIDENCE_REQUIREMENTS["delayed"],
    }
    missing = [name for name, ok in checks.items() if not ok]

    def _ctx(kind: str) -> int:
        if context_counts:
            return int(context_counts.get(kind, 0) or 0)
        return 0

    # F-C4 (V3.26): el gate retrocede al conteo de filas cuando un kind con filas
    # no tiene ningún contexto conocido (`familiar`/`transfer`). Con contextos el
    # conteo es de experiencias distintas (las filas legacy no se cuentan ni
    # inflan). La UI marca este estado como "experiencias no verificadas".
    legacy_fallback = (familiar > 0 and _ctx("familiar") == 0) or (
        transfer > 0 and _ctx("transfer") == 0
    )

    return {
        "met": not missing,
        "checks": checks,
        "missing": missing,
        "legacy_fallback": legacy_fallback,
        "counts": {
            "familiar": familiar,
            "familiar_contexts": familiar_xp,
            "familiar_initial_xp": initial_xp,
            "familiar_practice_xp": practice_xp,
            "transfer": transfer,
            "transfer_contexts": transfer_xp,
            "novel": novel,
            "delayed": delayed,
        },
    }


def retention_due(
    last_formal_at: str,
    *,
    now: str = "",
    min_days: int = RETENTION_MIN_DAYS,
) -> bool:
    """True si ya pasó la ventana de retención desde la última formal."""
    if not last_formal_at:
        return False
    now_dt = _parse_iso(now) or datetime.now(timezone.utc)
    last_dt = _parse_iso(last_formal_at)
    if last_dt is None:
        return False
    return (now_dt - last_dt).days >= min_days


def retention_spacing_due(
    sessions: list[dict],
    *,
    origin_session_id: int | None,
    now: str = "",
    min_days: int = RETENTION_MIN_DAYS,
) -> bool:
    """F-A3 (V3.26, P2-02): espaciado longitudinal entre reassessments del
    MISMO origen formal.

    Un retention reassessment nuevo cuyo origen es `origin_session_id` debe
    separarse ≥ `min_days` del ÚLTIMO reassessment ya cerrado (`status ==
    "done"`, el punto cuya evidencia `delayed` ya existe) de ese mismo origen;
    sin reassessment previo del origen la condición es transparente (True).

    El gate exige ≥ `CERTIFICATION_REQUIRED_DELAYED` puntos estables; este
    espaciado es el que hace que >1 punto sea REAL y separado (dos submits el
    mismo día o en días consecutivos no generan puntos longitudinales). Devuelve
    True si ya pasó el espaciado o no hay un punto previo que respetar.
    """
    last_at = ""
    for s in sessions:
        if s.get("kind") != "retention" or s.get("status") != "done":
            continue
        if (s.get("source_session_id") or None) != origin_session_id:
            continue
        created = s.get("created_at") or ""
        if created and created > last_at:
            last_at = created
    if not last_at:
        return True
    return retention_due(last_at, now=now, min_days=min_days)


def ladder_status(
    *,
    completed_kinds: set[str],
    units_done: int,
    has_exam: bool,
    retention_ready: bool,
    mastery_gate: dict | None = None,
) -> dict:
    """Estado de la escalera + siguiente peldaño recomendado.

    `readiness.ladder_complete` marca el nivel *completado* (avance desbloqueado,
    la retención no bloquea el progreso); `readiness.level_certified` marca la
    certificación plena: exige el peldaño `level` (examen aprobado) **y** el
    retention reassessment (`retention`), porque la retención estable ≥7 días es
    requisito de la certificación, no una evaluación aparte (P1/H5).
    """
    steps = []
    for kind in ASSESSMENT_KINDS:
        available = True
        reason = "available"
        if kind == "unit" and units_done < 1:
            available = False
            reason = "complete-a-unit"
        elif kind == "progress" and units_done < PROGRESS_UNIT_SPAN:
            available = False
            reason = f"need-{PROGRESS_UNIT_SPAN}-units"
        elif kind == "level" and not has_exam:
            available = False
            reason = "no-exam"
        elif (
            kind == "level"
            and "progress" not in completed_kinds
            and units_done < PROGRESS_UNIT_SPAN
        ):
            # Nivel disponible si hay examen; se recomienda tras progress.
            reason = "recommended-after-progress"
        elif kind == "retention" and not retention_ready:
            available = False
            reason = "wait-retention-window"
        done = kind in completed_kinds
        steps.append(
            {
                "kind": kind,
                "available": available,
                "completed": done,
                "reason": "done" if done else reason,
            }
        )

    next_kind = None
    for step in steps:
        if step["available"] and not step["completed"]:
            next_kind = step["kind"]
            break

    gate = mastery_gate or mastery_evidence_gate({})
    non_retention_done = all(
        s["completed"] for s in steps if s["kind"] != "retention"
    )
    readiness = {
        "ladder_complete": non_retention_done
        or (
            "formative" in completed_kinds
            and "unit" in completed_kinds
            and (
                "progress" in completed_kinds or units_done < PROGRESS_UNIT_SPAN
            )
            and ("level" in completed_kinds or not has_exam)
        ),
        "mastery_eligible": gate["met"],
        "mastery_missing": list(gate.get("missing") or []),
        "next_kind": next_kind,
        "retention_due": retention_ready,
        # H5/P1: la retención no es un peldaño aparte que "suma puntos": el nivel
        # queda *certificado* solo cuando el peldaño `level` (examen aprobado) se
        # completa Y el retention reassessment (≥7 días, ratio estable) también.
        "level_certified": (
            "level" in completed_kinds and "retention" in completed_kinds
        ),
    }
    return {
        "steps": steps,
        "readiness": readiness,
        "assessment_version": ASSESSMENT_VERSION,
    }


def evidence_kind_for(kind: str) -> str:
    """Qué evidence_kind registrar al completar un peldaño."""
    if kind == "retention":
        return "delayed"
    if kind in ("unit", "progress", "level"):
        return "transfer"
    return "familiar"
