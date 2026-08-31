import { bandLabel, cefrTone } from "../utils/cefr";
import { formatAverage } from "../utils/progress";
import type { LearningProfile as ProfileData } from "../types/api";
import { useI18n } from "../hooks/useI18n";

interface LearningProfileProps {
  profile: ProfileData | null;
}

const BANDS = [
  "vocabulary",
  "grammar",
  "pronunciation",
  "listening",
  "speaking",
  "reading",
  "writing",
] as const;

function formatTrend(trend: number | null): string {
  if (trend === null) return "—";
  const sign = trend > 0 ? "+" : "";
  return `${sign}${trend.toFixed(0)}%`;
}

function trendDirection(trend: number | null): "up" | "down" | "flat" {
  if (trend === null || Math.abs(trend) < 0.5) return "flat";
  return trend > 0 ? "up" : "down";
}

export function LearningProfile({ profile }: LearningProfileProps) {
  const { t } = useI18n();
  if (profile === null) {
    return (
      <section className="learning-profile">
        <p className="progress-empty">{t("empty.noProfile")}</p>
      </section>
    );
  }

  const abilityPct = Math.round((profile.overall_ability / 6) * 100);

  return (
    <section className="learning-profile">
      {profile.estimated_descriptor && (
        <p className="cefr-descriptor">{profile.estimated_descriptor}</p>
      )}

      <div className="cefr-ability" title={t("profile.globalAbilityTitle")}>
        <span className="cefr-confidence-label">{t("profile.globalAbility")}</span>
        <div className="cefr-confidence-track">
          <div
            className="cefr-confidence-fill"
            style={{ width: `${abilityPct}%` }}
          />
        </div>
        <span className="cefr-confidence-value">
          {profile.overall_ability.toFixed(1)} / 6
        </span>
      </div>

      <div className="cefr-bands">
        {BANDS.map((skill) => (
          <span
            key={skill}
            className={`cefr-band ${cefrTone(profile.estimated_bands[skill])}`}
            title={t("profile.bandTitle")}
          >
            <span className="cefr-band-label">{bandLabel(skill)}</span>
            <span className="cefr-band-value">
              {profile.estimated_bands[skill]}
            </span>
          </span>
        ))}
      </div>

      <div className="cefr-readiness">
        <span className="cefr-confidence-label">
          {t("profile.readyFor")} {profile.target_level}
        </span>
        <span className="cefr-confidence-value">
          {t(`readiness.${profile.readiness.band}`)}
        </span>
        <span className="cefr-confidence-sub">
          {Math.round(profile.readiness.overall)}%
        </span>
        {profile.readiness.blocking_skills.length > 0 && (
          <p className="readiness-blocking">
            {t("profile.workOn")}{" "}
            {profile.readiness.blocking_skills.map(bandLabel).join(", ")}
          </p>
        )}
      </div>

      {profile.skills.length > 0 && (
        <div className="cefr-evidence">
          {profile.skills.map((item) => {
            const dir = trendDirection(item.trend);
            return (
              <div key={item.skill} className="cefr-evidence-row">
                <span className="cefr-evidence-skill">{bandLabel(item.skill)}</span>
                <span className="cefr-evidence-band">{item.band}</span>
                <span className="cefr-evidence-samples">
                  {item.samples} {t("profile.samples")} ·{" "}
                  {Math.round(item.confidence * 100)}%
                </span>
                <span className={`trend trend-${dir}`} title={t("profile.recentTrend")}>
                  {formatTrend(item.trend)}
                </span>
              </div>
            );
          })}
        </div>
      )}

      <div className="learning-grid">
        <div className="learning-block">
          <h3>{t("profile.vocabulary")}</h3>
          <p className="learning-big">{profile.vocabulary_size}</p>
          {(profile.vocabulary_mastered > 0 || profile.vocabulary_exposed > 0) && (
            <p className="learning-sub">
              {profile.vocabulary_mastered} {t("profile.mastered")} ·{" "}
              {profile.vocabulary_exposed} {t("profile.seen")}
            </p>
          )}
          {profile.top_words.length > 0 ? (
            <ul className="learning-chips">
              {profile.top_words.map((w) => (
                <li key={w} className="learning-chip">
                  {w}
                </li>
              ))}
            </ul>
          ) : (
            <p className="progress-empty">{t("profile.noWords")}</p>
          )}
        </div>

        <div className="learning-block">
          <h3>{t("profile.avgPronunciation")}</h3>
          <p className="learning-big">
            {profile.pronunciation_average === null
              ? "—"
              : formatAverage(profile.pronunciation_average)}
          </p>
        </div>
      </div>

      <div className="learning-block">
        <h3>{t("profile.recurringErrors")}</h3>
        {profile.recurring_errors.length === 0 ? (
          <p className="progress-empty">{t("profile.noErrors")}</p>
        ) : (
          <ul className="learning-errors">
            {profile.recurring_errors.map((e) => (
              <li key={e.rule} className="learning-error">
                <span className="learning-error-count">{e.count}×</span>
                <span>{e.message}</span>
              </li>
            ))}
          </ul>
        )}
        {profile.mastered_count > 0 && (
          <p className="learning-mastered">
            {t("profile.errorsOvercome")} {profile.mastered_count}
          </p>
        )}
      </div>

      <div className="learning-block">
        <h3>{t("profile.recommendations")}</h3>
        <ul className="learning-recs">
          {profile.recommendations.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
