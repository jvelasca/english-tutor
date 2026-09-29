import { useEffect, useState } from "react";
import { getGoal, getSession, getStudentModel, putGoal } from "../api/academy";
import type {
  DailyPlan,
  DailyPlanProgress,
  LearningGoal,
  LearningGoalType,
  PlanMode,
  Session as SessionData,
  SessionStep,
  SkillProfile,
  StudentModel,
} from "../types/api";
import { cefrLabel, levelClass } from "../utils/cefr";
import {
  SKILL_LABELS,
  SUBSKILL_LABELS,
  dimensionLabel,
  kindKey,
  stepTitle,
} from "../utils/learningLabels";
import { useI18n } from "../hooks/useI18n";

const GOAL_TYPE_LABELS: Record<LearningGoalType, string> = {
  general: "today.goalType.general",
  travel: "today.goalType.travel",
  work: "today.goalType.work",
  interview: "today.goalType.interview",
  exam: "today.goalType.exam",
};

const GOAL_TYPE_ORDER: LearningGoalType[] = [
  "general",
  "travel",
  "work",
  "interview",
  "exam",
];

/** V3.90: modos del objetivo del día, en el orden en que se ofrecen. */
const PLAN_MODE_ORDER: PlanMode[] = ["time", "units", "mixed"];

const PLAN_MODE_LABELS: Record<PlanMode, string> = {
  time: "today.planMode.time",
  units: "today.planMode.units",
  mixed: "today.planMode.mixed",
};

// F-C3 (V3.26): motivo de bloqueo de readiness por destreza (`blocked_by`).
const BLOCK_REASON_KEYS: Record<string, string> = {
  score: "today.blockReason.score",
  confidence: "today.blockReason.confidence",
  evidence: "today.blockReason.evidence",
  transfer: "today.blockReason.transfer",
  novel: "today.blockReason.novel",
};

const CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"] as const;

interface TodayPlanProps {
  userId: string | null;
  /** Plan diario (V3.90). Lo sirve Home: una sola lectura para la barra del
   *  encabezado y para la lista de pasos, de modo que no puedan divergir. */
  plan: DailyPlan | null;
  /** Estado de esa lectura. Solo con `"error"` se repliega a leer objetivo y
   *  sesión: mientras Home está cargando no se pide nada por duplicado. */
  planStatus?: "loading" | "ready" | "error";
  /** Recarga el plan (tras editar el objetivo o completar un paso). */
  onRefreshPlan?: () => void;
  onStep?: (step: SessionStep) => void;
}

export function TodayPlan({
  userId,
  plan,
  planStatus,
  onRefreshPlan,
  onStep,
}: TodayPlanProps) {
  const { t } = useI18n();
  const [model, setModel] = useState<StudentModel | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<LearningGoal | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  // El Student Model depende del objetivo (`target_level`), así que al guardarlo
  // hay que volver a leerlo: `modelTick` es esa relectura.
  const [modelTick, setModelTick] = useState(0);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    void (async () => {
      try {
        const m = await getStudentModel(userId);
        if (!cancelled) setModel(m);
      } catch {
        /* backend no disponible */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, modelTick]);

  // V3.90: el plan diario lo sirve Home, pero si su lectura FALLA (endpoint
  // ausente o backend caído) el plan NO desaparece: se releen objetivo y sesión
  // —como en V3.89— y se pinta sin barra de progreso. Mientras Home sigue
  // cargando no se pregunta nada: la barra no se improvisa, necesita las
  // métricas que solo el plan trae.
  const degraded = !plan && (planStatus ?? "error") === "error";
  const [fallback, setFallback] = useState<{
    goal: LearningGoal | null;
    session: SessionData | null;
  }>({ goal: null, session: null });

  useEffect(() => {
    if (!userId || plan || !degraded) return;
    let cancelled = false;
    void (async () => {
      try {
        const [g, s] = await Promise.all([
          getGoal(userId),
          getSession(userId),
        ]);
        if (!cancelled) setFallback({ goal: g, session: s });
      } catch {
        /* backend no disponible */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, plan, degraded]);

  // `withPlanDefaults` cubre los planes guardados antes de V3.90, que no traen
  // las cinco claves nuevas: sin él, la cabecera del objetivo pintaría «NaN».
  const goal = plan ? withPlanDefaults(plan.goal) : fallback.goal;
  const session = plan?.session ?? fallback.session;

  function startEdit() {
    setDraft(goal);
    setSaved(false);
    setEditing(true);
  }

  function cancelEdit() {
    setDraft(goal);
    setEditing(false);
  }

  /**
   * Guarda el objetivo y RECARGA el plan. El borrador trae las cinco claves del
   * plan diario, pero si viniera de un plan antiguo sin ellas se rellenan con los
   * valores por defecto del backend antes de enviar (`putGoal` sustituye el
   * objetivo entero: lo que no se envíe, se pierde).
   */
  async function saveGoal() {
    if (!userId || !draft || saving) return;
    setSaving(true);
    try {
      const next = await putGoal(userId, withPlanDefaults(draft));
      setDraft(next);
      setEditing(false);
      setSaved(true);
      // El objetivo cambia el presupuesto y el nivel meta: recargar el plan…
      onRefreshPlan?.();
      // …y releer el Student Model (su nivel meta sale del objetivo).
      setModelTick((n) => n + 1);
    } catch {
      /* backend no disponible */
    } finally {
      setSaving(false);
    }
  }

  if (!model) {
    return (
      <section className="today-plan">
        <p className="progress-empty">{t("today.noModel")}</p>
      </section>
    );
  }

  const evidenced = model.skills.filter((s) => s.evidence_count > 0);

  return (
    <section className="today-plan">
      {goal && (
        <div className="goal-editor">
          {editing && draft ? (
            <div className="goal-form">
              <label className="goal-field">
                <span>{t("today.goal")}</span>
                <select
                  value={draft.goal_type}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      goal_type: e.target.value as LearningGoalType,
                    })
                  }
                >
                  {GOAL_TYPE_ORDER.map((gt) => (
                    <option key={gt} value={gt}>
                      {t(GOAL_TYPE_LABELS[gt])}
                    </option>
                  ))}
                </select>
              </label>
              <label className="goal-field">
                <span>{t("today.targetCefr")}</span>
                <select
                  value={draft.target_level}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      target_level: e.target.value as LearningGoal["target_level"],
                    })
                  }
                >
                  {CEFR_LEVELS.map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </select>
              </label>
              {/* V3.90: con qué se declara el objetivo del día. */}
              <label className="goal-field">
                <span>{t("today.planMode")}</span>
                <select
                  value={draft.plan_mode}
                  onChange={(e) =>
                    setDraft({ ...draft, plan_mode: e.target.value as PlanMode })
                  }
                >
                  {PLAN_MODE_ORDER.map((mode) => (
                    <option key={mode} value={mode}>
                      {t(PLAN_MODE_LABELS[mode])}
                    </option>
                  ))}
                </select>
              </label>
              <div className="goal-row">
                <label className="goal-field">
                  <span>{t("today.minPerDay")}</span>
                  <input
                    type="number"
                    min={5}
                    max={180}
                    step={5}
                    value={draft.minutes_per_day}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        minutes_per_day: Number(e.target.value),
                      })
                    }
                  />
                </label>
                <label className="goal-field">
                  <span>{t("today.daysPerWeek")}</span>
                  <input
                    type="number"
                    min={1}
                    max={7}
                    value={draft.days_per_week}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        days_per_week: Number(e.target.value),
                      })
                    }
                  />
                </label>
              </div>
              <div className="goal-row">
                {/* Las unidades solo se piden en los modos que las declaran. */}
                {draft.plan_mode !== "time" && (
                  <label className="goal-field">
                    <span>{t("today.targetUnits")}</span>
                    <input
                      type="number"
                      min={0}
                      max={12}
                      value={draft.target_units}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          target_units: Number(e.target.value),
                        })
                      }
                    />
                  </label>
                )}
                <label className="goal-field">
                  <span>{t("today.maxNew")}</span>
                  <input
                    type="number"
                    min={0}
                    max={5}
                    value={draft.max_new}
                    onChange={(e) =>
                      setDraft({ ...draft, max_new: Number(e.target.value) })
                    }
                  />
                </label>
              </div>
              <div className="goal-toggles">
                <label className="goal-toggle">
                  <input
                    type="checkbox"
                    checked={draft.include_listening}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        include_listening: e.target.checked,
                      })
                    }
                  />
                  <span>{t("today.includeListening")}</span>
                </label>
                <label className="goal-toggle">
                  <input
                    type="checkbox"
                    checked={draft.include_speaking}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        include_speaking: e.target.checked,
                      })
                    }
                  />
                  <span>{t("today.includeSpeaking")}</span>
                </label>
              </div>
              <div className="goal-actions">
                <button type="button" onClick={cancelEdit} disabled={saving}>
                  {t("common.cancel")}
                </button>
                <button
                  type="button"
                  className="goal-save"
                  onClick={saveGoal}
                  disabled={saving}
                >
                  {saving ? t("common.saving") : t("common.save")}
                </button>
              </div>
            </div>
          ) : (
            <div className="goal-summary">
              <div className="goal-summary-text">
                <strong>{t(GOAL_TYPE_LABELS[goal.goal_type])}</strong>
                <span>{goalSummary(goal, t)}</span>
              </div>
              <button type="button" onClick={startEdit}>
                {t("common.edit")}
              </button>
              {saved && <span className="goal-saved">{t("today.saved")}</span>}
            </div>
          )}
        </div>
      )}

      {plan && <GoalProgress plan={plan} />}

      <div className="today-milestone">
        <span className={`cefr-badge ${levelClass(model.current_level)}`}>
          {model.current_level}
        </span>
        <span className="today-arrow" aria-hidden="true">
          →
        </span>
        <span className={`cefr-badge ${levelClass(model.target_level)}`}>
          {model.target_level}
        </span>
        <span className="today-milestone-label">
          {cefrLabel(model.estimated_level)} · {t("today.nextMilestone")}{" "}
          {model.target_level}
        </span>
      </div>

      <div className="today-readiness">
        <div className="today-readiness-head">
          <span>
            {t("today.readyFor")} {model.target_level} ·{" "}
            {Math.round(model.readiness.overall)}%
          </span>
          <strong>{t(`readiness.${model.readiness.band}`)}</strong>
        </div>
        <div className="today-bar" role="progressbar" aria-valuenow={model.readiness.overall} aria-valuemin={0} aria-valuemax={100}>
          <span style={{ width: `${model.readiness.overall}%` }} />
        </div>
        {model.readiness.blocking_skills.length > 0 && (
          <p className="today-blocking">
            {t("today.blocking")}{" "}
            {model.readiness.blocking_skills
              .map((s) => {
                const r = model.readiness.skills.find((k) => k.skill === s);
                const reasons = (r?.blocked_by ?? []).filter(Boolean);
                const label = SKILL_LABELS[s] ?? s;
                // F-C3 (V3.26): el backend declara el motivo de bloqueo
                // (score/confidence/evidence/transfer/novel); la UI lo traduce.
                return reasons.length > 0
                  ? `${label} (${reasons
                      .map((reason) => t(BLOCK_REASON_KEYS[reason] ?? "today.blockReason.other"))
                      .join(", ")})`
                  : label;
              })
              .join(", ")}
          </p>
        )}
      </div>

      {evidenced.length > 0 && (
        <div className="today-skills">
          {evidenced.map((skill) => (
            <SkillBar key={skill.skill} skill={skill} />
          ))}
        </div>
      )}

      {model.reassessment && (
        <div className="today-reassessment">
          {t("today.readyToReassess")}{" "}
          {SKILL_LABELS[model.reassessment.skill] ?? model.reassessment.skill} (
          {model.reassessment.level})
        </div>
      )}

      {session && session.items.length > 0 ? (
        <>
          <div className="session-headline">
            <strong>{session.total_minutes} min</strong>
            <span>
              {t("today.review")} {session.review_count} · {t("today.practice")}{" "}
              {session.practice_count}
            </span>
          </div>
          <ol className="today-items">
            {session.items.map((item, i) => (
              <SessionStepRow
                key={`${item.kind}-${item.subskill ?? item.objective_id ?? item.title}-${i}`}
                item={item}
                onClick={onStep}
              />
            ))}
          </ol>
        </>
      ) : (
        plan && (
          <p className="today-goal-met" role="status">
            {t("today.goalMet")}
          </p>
        )
      )}

      {onStep && session && session.items.length > 0 && (
        <button
          type="button"
          className="today-start"
          onClick={() => onStep(session.items[0])}
        >
          {t("today.startSession")}
        </button>
      )}
    </section>
  );
}

/** Rellena las claves del plan diario que un borrador antiguo no traiga. */
export function withPlanDefaults(goal: LearningGoal): LearningGoal {
  return {
    ...goal,
    plan_mode: goal.plan_mode ?? "time",
    target_units: goal.target_units ?? 0,
    max_new: goal.max_new ?? 1,
    include_listening: goal.include_listening ?? true,
    include_speaking: goal.include_speaking ?? true,
  };
}

/** Resumen textual del objetivo: en `mixed` se declaran los dos objetivos. */
function goalSummary(goal: LearningGoal, t: (k: string) => string): string {
  const parts = [`${t("today.targetCefr")} ${goal.target_level}`];
  const units = `${goal.target_units} ${t("today.unitsShort")}`;
  if (goal.plan_mode === "units") {
    parts.push(units);
  } else if (goal.plan_mode === "mixed") {
    parts.push(`${goal.minutes_per_day} ${t("today.minPerDay")}`);
    parts.push(units);
  } else {
    parts.push(`${goal.minutes_per_day} ${t("today.minPerDay")}`);
  }
  parts.push(`${goal.days_per_week} ${t("today.daysPerWeek")}`);
  return ` · ${parts.join(" · ")}`;
}

/**
 * V3.90: barra «OBJETIVO DE HOY».
 *
 * Publica tres cosas distintas y no las mezcla: lo HECHO (barras, con los minutos
 * que el motor había asignado a las unidades completadas), lo PENDIENTE (repasos
 * por origen: FSRS y cola de Listening) y el resultado de hoy (`accuracy`, media
 * observada, no una nota). En `mixed` el porcentaje es el mínimo de los objetivos
 * declarados, porque el día se cumple con ambos.
 *
 * Los minutos del plan son una **estimación del motor**, no tiempo de reloj: la
 * etiqueta lo dice y no se presenta como cronómetro.
 */
function GoalProgress({ plan }: { plan: DailyPlan }) {
  const { t } = useI18n();
  const p: DailyPlanProgress = plan.progress;
  const pct = Math.round(p.percent * 100);
  const metrics = plan.metrics;
  return (
    <div className="goal-progress">
      <div className="goal-progress-head">
        <span>{t("today.goalProgress")}</span>
        <strong data-testid="goal-progress-pct">{pct}%</strong>
      </div>
      <div
        className="today-bar goal-progress-bar"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={t("today.goalProgress")}
      >
        <span style={{ width: `${pct}%` }} />
      </div>
      <p className="goal-progress-detail">
        <span>
          {t("today.progressUnits")}: {p.units_done}
          {p.units_target > 0 ? ` / ${p.units_target}` : ""}
        </span>
        <span>
          {t("today.progressMinutes")}: {p.minutes_done}
          {p.minutes_ratio !== null ? ` / ${p.minutes_target}` : ""}{" "}
          <span className="goal-progress-note">{t("today.estimated")}</span>
        </span>
      </p>
      <p className="goal-progress-detail">
        <span>
          {t("today.pendingReviews")}: {plan.pending.total}
          {plan.pending.total > 0 && (
            <span className="goal-progress-note">
              {" "}
              ({t("today.pendingBreakdown")
                .replace("{fsrs}", String(plan.pending.fsrs))
                .replace("{listening}", String(plan.pending.listening))})
            </span>
          )}
        </span>
        <span>
          {t("today.todayAccuracy")}:{" "}
          {metrics.accuracy === null
            ? t("today.noData")
            : `${Math.round(metrics.accuracy * 100)}%`}
          <span className="goal-progress-note">
            {" "}
            ({metrics.units} {t("today.unitsShort")})
          </span>
        </span>
      </p>
    </div>
  );
}

function SessionStepRow({
  item,
  onClick,
}: {
  item: SessionStep;
  onClick?: (step: SessionStep) => void;
}) {
  const { t } = useI18n();
  const kindKeyLabel = kindKey(item.kind);
  const label = kindKeyLabel ? t(kindKeyLabel) : item.kind;
  const reason =
    item.kind === "listening" && item.subskill
      ? `${t("today.subskill")} ${SUBSKILL_LABELS[item.subskill] ?? item.subskill}`
      : item.reason;
  const limit = item.limiting_factor;
  return (
    <li className="today-item">
      <button
        type="button"
        className="today-item-action"
        onClick={() => onClick?.(item)}
        disabled={!onClick}
      >
        <span className={`today-dot kind-${item.kind}`} aria-hidden="true" />
        <span className="today-item-body">
          <span className="today-item-title">{stepTitle(item, t)}</span>
          <span className="today-item-reason">{reason}</span>
          {/* V3.17 (D6): micro-líneas del can-do con su nodo del grafo. Son
              informativas (estáticas) dentro de la fila-botón: can-do en
              itálica y chip del factor limitante; el because[] completo solo
              vive en NextBestCard. Sin can_do o sin nodo (D7) no se dibujan. */}
          {item.can_do && limit && (
            <span className="today-item-graph">
              <span className="today-item-can-do">{item.can_do}</span>
              <span className="today-item-limit" role="note">
                {dimensionLabel(limit.id)}
                {limit.missing
                  ? ` · ${t("home.missing")}`
                  : ` · ${Math.round(limit.score * 100)}%`}
              </span>
            </span>
          )}
        </span>
        <span className="today-item-kind">{label}</span>
        <span className="today-item-minutes">{item.minutes} min</span>
      </button>
    </li>
  );
}

function SkillBar({ skill }: { skill: SkillProfile }) {
  const { t } = useI18n();
  const label = SKILL_LABELS[skill.skill] ?? skill.skill;
  const scorePct = Math.round(skill.score * 100);
  const stabilityPct = Math.round(skill.stability * 100);
  const trend = skill.trend;
  return (
    <div className="today-skill">
      <div className="today-skill-head">
        <span>{label}</span>
        <span className="today-skill-meta">
          {trend !== null && (
            <span className={trend >= 0 ? "trend-up" : "trend-down"}>
              {trend >= 0 ? "↗" : "↘"} {Math.abs(trend)}%
            </span>
          )}
          <span className="today-skill-stability">
            {t("today.stability").replace("{pct}", String(stabilityPct))}
          </span>
        </span>
      </div>
      <div className="today-bar">
        <span style={{ width: `${scorePct}%` }} />
      </div>
    </div>
  );
}
