import type { LearningProfile, ProgressHistory } from "../types/api";
import type { Section } from "../utils/sections";
import { cefrLabel, cefrTone } from "../utils/cefr";
import { SKILL_LABELS } from "../utils/learningLabels";
import { LearnToday } from "./LearnToday";
import type { SessionStep } from "../types/api";

const SKILL_TO_SECTION: Record<string, Section> = {
  listening: "listening",
  speaking: "speaking",
  reading: "reading",
  writing: "writing",
  grammar: "grammar",
  pronunciation: "pronunciation",
};

interface LearningHomeProps {
  userId: string | null;
  profile: LearningProfile | null;
  history: ProgressHistory | null;
  onStep: (step: SessionStep) => void;
  onPracticeSkill: (section: Section) => void;
  refreshKey?: number;
}

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Buenos días";
  if (h < 20) return "Buenas tardes";
  return "Buenas noches";
}

function focusSection(profile: LearningProfile): Section | null {
  const blocking = profile.readiness.blocking_skills[0];
  if (blocking && SKILL_TO_SECTION[blocking]) return SKILL_TO_SECTION[blocking];

  // Fallback: la destreza con menor score entre las que tienen pantalla propia.
  let weakest: { skill: string; score: number } | null = null;
  for (const s of profile.skills) {
    if (!SKILL_TO_SECTION[s.skill]) continue;
    if (!weakest || s.score < weakest.score) {
      weakest = { skill: s.skill, score: s.score };
    }
  }
  return weakest ? SKILL_TO_SECTION[weakest.skill] : null;
}

function overallTrend(profile: LearningProfile): "up" | "down" | "flat" | null {
  const trends = profile.skills
    .map((s) => s.trend)
    .filter((t): t is number => t !== null);
  if (trends.length === 0) return null;
  const sum = trends.reduce((a, b) => a + b, 0);
  if (sum > 0.5) return "up";
  if (sum < -0.5) return "down";
  return "flat";
}

export function LearningHome({
  userId,
  profile,
  history,
  onStep,
  onPracticeSkill,
  refreshKey = 0,
}: LearningHomeProps) {
  const level = profile?.estimated_level ?? null;
  const tone = level ? cefrTone(level) : "basic";
  const readiness = Math.round(profile?.readiness.overall ?? 0);
  const trend = profile ? overallTrend(profile) : null;
  const focus = profile ? focusSection(profile) : null;

  const streak = history?.streak;
  const activityTotal = history
    ? history.series.reduce(
        (acc, p) =>
          acc + p.messages + p.exercises + p.corrections + p.pronunciation,
        0,
      )
    : 0;

  return (
    <div className="home">
      <div className="home-greeting">
        <h2 className="home-greeting__title">{greeting()}</h2>
        <p className="home-greeting__sub">Continúa tu camino con el inglés.</p>
      </div>

      <section className="home-hero card">
        <div className="home-hero__head">
          <span className={`cefr-badge ${tone}`}>{level ?? "—"}</span>
          {level && (
            <span className="home-hero__label">{cefrLabel(level)}</span>
          )}
          {trend && (
            <span className={`home-trend home-trend--${trend}`}>
              {trend === "up" ? "↑ Mejorando" : trend === "down" ? "↓ Repasar" : "→ Estable"}
            </span>
          )}
        </div>
        <div className="home-hero__readiness">
          <div className="home-hero__row">
            <span className="home-hero__readiness-label">
              Preparación para {profile?.target_level ?? "el siguiente nivel"}
            </span>
            <strong>{readiness}%</strong>
          </div>
          <div
            className="today-bar"
            role="progressbar"
            aria-valuenow={readiness}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <span style={{ width: `${readiness}%` }} />
          </div>
        </div>
      </section>

      <LearnToday userId={userId} onStep={onStep} refreshKey={refreshKey} />

      {profile && profile.skills.length > 0 && (
        <section className="home-skills card" aria-label="Tus destrezas">
          <h2 className="home-skills__title">Your skills</h2>
          <div className="home-skills__list">
            {profile.skills.map((skill) => (
              <div key={skill.skill} className="home-skill">
                <div className="home-skill__head">
                  <span>{SKILL_LABELS[skill.skill] ?? skill.skill}</span>
                  <span className="home-skill__score">
                    {Math.round(skill.score * 100)}%
                  </span>
                </div>
                <div className="today-bar">
                  <span style={{ width: `${Math.round(skill.score * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {streak && (
        <section className="home-streak card">
          <div className="home-streak__item">
            <span className="home-streak__big">{streak.current_days}</span>
            <span className="home-streak__label">días de racha</span>
          </div>
          <div className="home-streak__item">
            <span className="home-streak__big">{streak.best_days}</span>
            <span className="home-streak__label">mejor racha</span>
          </div>
          <div className="home-streak__item">
            <span className="home-streak__big">{activityTotal}</span>
            <span className="home-streak__label">actividad reciente</span>
          </div>
        </section>
      )}

      {focus && (
        <section className="home-cta card">
          <div className="home-cta__text">
            <span className="home-cta__kicker">Next focus</span>
            <span className="home-cta__title">{SKILL_LABELS[focus] ?? focus}</span>
          </div>
          <button
            type="button"
            className="home-cta__button"
            onClick={() => onPracticeSkill(focus)}
          >
            Practice now
          </button>
        </section>
      )}
    </div>
  );
}
