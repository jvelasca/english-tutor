import { useEffect, useState } from "react";
import { getStudentModel } from "../../api/academy";
import type { SkillProfile, StudentModel } from "../../types/api";
import { cefrLabel, cefrTone } from "../../utils/cefr";
import { SKILL_LABELS } from "../../utils/learningLabels";
import { useI18n } from "../../hooks/useI18n";
import { SpeakingDiagnostic } from "../speaking/SpeakingDiagnostic";
import { WritingJourney } from "../writing/WritingJourney";

const PRIMARY = ["listening", "speaking", "reading", "writing"] as const;
type PrimarySkill = (typeof PRIMARY)[number];

interface ProgressScreenProps {
  userId: string | null;
}

function masteryLabel(score: number, t: (k: string) => string): string {
  if (score >= 0.75) return t("mastery.strong");
  if (score >= 0.5) return t("mastery.developing");
  return t("mastery.needsPractice");
}

function masteryClass(score: number): string {
  if (score >= 0.75) return "strong";
  if (score >= 0.5) return "developing";
  return "needs";
}

export function ProgressScreen({ userId }: ProgressScreenProps) {
  const { t } = useI18n();
  const [model, setModel] = useState<StudentModel | null>(null);
  const [selected, setSelected] = useState<PrimarySkill | null>(null);

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
  }, [userId]);

  const level = model?.estimated_level ?? null;
  const tone = level ? cefrTone(level) : "basic";
  const overall = Math.round(model?.readiness.overall ?? 0);

  const skills = model?.skills ?? [];
  const bySkill = new Map(skills.map((s) => [s.skill, s]));

  return (
    <div className="progress-screen">
      <header className="progress-screen__header flex-wrap">
        <h2 className="progress-screen__title">{t("progress.title")}</h2>
        <div className="progress-screen__headline">
          <span className={`cefr-badge ${tone}`}>{level ?? "—"}</span>
          {level && <span>{cefrLabel(level)}</span>}
        </div>
      </header>

      <section className="progress-screen__overall card">
        <div className="progress-screen__overall-row">
          <span>{t("progress.overall")}</span>
          <strong>{overall}%</strong>
        </div>
        <div
          className="today-bar"
          role="progressbar"
          aria-valuenow={overall}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <span style={{ width: `${overall}%` }} />
        </div>
      </section>

      <section className="progress-screen__skills card" aria-label={t("progress.title")}>
        <ul className="progress-screen__list">
          {PRIMARY.map((skill) => {
            const p = bySkill.get(skill);
            if (!p) return null;
            return (
              <li key={skill} className="progress-screen__skill">
                <button
                  type="button"
                  className="progress-screen__skill-main max-sm:grid-cols-[minmax(0,1fr)_auto]!"
                  onClick={() =>
                    setSelected((cur) => (cur === skill ? null : skill))
                  }
                  aria-expanded={selected === skill}
                >
                  <span className="progress-screen__skill-name">
                    {SKILL_LABELS[skill] ?? skill}
                  </span>
                  <span
                    className={`progress-screen__skill-badge ${masteryClass(p.score)}`}
                  >
                    {masteryLabel(p.score, t)}
                  </span>
                  <span className="progress-screen__skill-bar">
                    <span style={{ width: `${Math.round(p.score * 100)}%` }} />
                  </span>
                  <span className="progress-screen__skill-chevron" aria-hidden="true">
                    {selected === skill ? "▾" : "▸"}
                  </span>
                </button>

                {selected === skill && (
                  <div className="progress-screen__detail">
                    {skill === "speaking" ? (
                      <SpeakingDiagnostic userId={userId} />
                    ) : skill === "writing" ? (
                      <WritingJourney userId={userId} />
                    ) : (
                      <SkillDetail profile={p} />
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}

function SkillDetail({ profile }: { profile: SkillProfile }) {
  const { t } = useI18n();
  return (
    <div className="skill-detail">
      <div className="skill-detail__grid max-sm:grid-cols-2!">
        <div className="skill-detail__item">
          <span className="skill-detail__label">Score</span>
          <strong>{Math.round(profile.score * 100)}%</strong>
        </div>
        <div className="skill-detail__item">
          <span className="skill-detail__label">Confidence</span>
          <strong>{Math.round(profile.confidence * 100)}%</strong>
        </div>
        <div className="skill-detail__item">
          <span className="skill-detail__label">Evidence</span>
          <strong>{profile.evidence_count}</strong>
        </div>
        <div className="skill-detail__item">
          <span className="skill-detail__label">Stability</span>
          <strong>{Math.round(profile.stability * 100)}%</strong>
        </div>
      </div>
      {profile.review_due && (
        <span className="skill-detail__review">{t("home.needsReview")}</span>
      )}
    </div>
  );
}
