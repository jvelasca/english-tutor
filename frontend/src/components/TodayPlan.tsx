import { useEffect, useState } from "react";
import { getGoal, getSession, getStudentModel, putGoal } from "../api/academy";
import type {
  LearningGoal,
  LearningGoalType,
  Session as SessionData,
  SessionStep,
  SkillProfile,
  StudentModel,
} from "../types/api";
import { cefrLabel, cefrTone } from "../utils/cefr";
import {
  KIND_LABELS,
  SKILL_LABELS,
  SUBSKILL_LABELS,
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

const CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"] as const;

interface TodayPlanProps {
  userId: string | null;
  onStep?: (step: SessionStep) => void;
  refreshKey?: number;
}

export function TodayPlan({ userId, onStep, refreshKey = 0 }: TodayPlanProps) {
  const { t } = useI18n();
  const [model, setModel] = useState<StudentModel | null>(null);
  const [session, setSession] = useState<SessionData | null>(null);
  const [goal, setGoal] = useState<LearningGoal | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<LearningGoal | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    void (async () => {
      try {
        const [m, s, g] = await Promise.all([
          getStudentModel(userId),
          getSession(userId),
          getGoal(userId),
        ]);
        if (!cancelled) {
          setModel(m);
          setSession(s);
          setGoal(g);
          setDraft(g);
        }
      } catch {
        /* backend no disponible */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey]);

  function startEdit() {
    setDraft(goal);
    setSaved(false);
    setEditing(true);
  }

  function cancelEdit() {
    setDraft(goal);
    setEditing(false);
  }

  async function saveGoal() {
    if (!userId || !draft || saving) return;
    setSaving(true);
    try {
      const next = await putGoal(userId, draft);
      setGoal(next);
      setDraft(next);
      setEditing(false);
      setSaved(true);
      // El objetivo cambia el presupuesto diario y el nivel meta: recargar.
      const [m, s] = await Promise.all([
        getStudentModel(userId),
        getSession(userId),
      ]);
      setModel(m);
      setSession(s);
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
                <span>
                  {t("today.targetCefr")} {goal.target_level} ·{" "}
                  {goal.minutes_per_day} {t("today.minPerDay")} ·{" "}
                  {goal.days_per_week} {t("today.daysPerWeek")}
                </span>
              </div>
              <button type="button" onClick={startEdit}>
                {t("common.edit")}
              </button>
              {saved && <span className="goal-saved">{t("today.saved")}</span>}
            </div>
          )}
        </div>
      )}

      <div className="today-milestone">
        <span className={`cefr-badge ${cefrTone(model.current_level)}`}>
          {model.current_level}
        </span>
        <span className="today-arrow" aria-hidden="true">
          →
        </span>
        <span className={`cefr-badge ${cefrTone(model.target_level)}`}>
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
              .map((s) => SKILL_LABELS[s] ?? s)
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

      {session && session.items.length > 0 && (
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

function SessionStepRow({
  item,
  onClick,
}: {
  item: SessionStep;
  onClick?: (step: SessionStep) => void;
}) {
  const { t } = useI18n();
  const label = KIND_LABELS[item.kind] ?? item.kind;
  const reason =
    item.kind === "listening" && item.subskill
      ? `${t("today.subskill")} ${SUBSKILL_LABELS[item.subskill] ?? item.subskill}`
      : item.reason;
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
          <span className="today-item-title">{stepTitle(item)}</span>
          <span className="today-item-reason">{reason}</span>
        </span>
        <span className="today-item-kind">{label}</span>
        <span className="today-item-minutes">{item.minutes} min</span>
      </button>
    </li>
  );
}

function SkillBar({ skill }: { skill: SkillProfile }) {
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
          <span className="today-skill-stability">stability {stabilityPct}%</span>
        </span>
      </div>
      <div className="today-bar">
        <span style={{ width: `${scorePct}%` }} />
      </div>
    </div>
  );
}
