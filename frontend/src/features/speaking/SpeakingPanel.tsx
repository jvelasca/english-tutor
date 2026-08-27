import { useEffect, useState } from "react";
import { getSpeakingDiagnostic, getSpeakingLevel } from "../../api/academy";
import type {
  SpeakingCriterionProgress,
  SpeakingDiagnostic as SpeakingDiagnosticData,
  SpeakingLevelOut,
} from "../../types/api";
import { cefrTone } from "../../utils/cefr";
import { criterionLabel, formatTrendDelta, nextFocus } from "../../utils/speaking";
import { useI18n } from "../../hooks/useI18n";

interface SpeakingPanelProps {
  userId: string | null;
  onPractice?: () => void;
}

function trendArrow(direction: string): string {
  switch (direction) {
    case "up":
      return "↑";
    case "down":
      return "↓";
    default:
      return "→";
  }
}

/** Puntuación formateada a % usando la ventana reciente si existe. */
function scorePct(c: SpeakingCriterionProgress): string {
  const score = c.recent_score ?? c.mean;
  return score == null ? "—" : `${Math.round(score * 100)}%`;
}

/** Un criterio es débil si toca repasar o si su puntuación está bajo 0.6. */
function isWeak(c: SpeakingCriterionProgress): boolean {
  if (c.review_due) return true;
  const score = c.recent_score ?? c.mean;
  return score != null && score < 0.6;
}

export function SpeakingPanel({ userId, onPractice }: SpeakingPanelProps) {
  const { t } = useI18n();
  const [level, setLevel] = useState<SpeakingLevelOut | null>(null);
  const [diagnostic, setDiagnostic] =
    useState<SpeakingDiagnosticData | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      if (!userId) return;
      try {
        const [lvl, diag] = await Promise.all([
          getSpeakingLevel(userId),
          getSpeakingDiagnostic(userId),
        ]);
        if (active) {
          setLevel(lvl);
          setDiagnostic(diag);
        }
      } catch {
        /* backend no disponible */
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [userId]);

  if (!level && !diagnostic) {
    return (
      <section className="speaking-panel">
        <p className="progress-empty">{t("empty.noSpeaking")}</p>
      </section>
    );
  }

  const trend = diagnostic?.trend;
  const focus = diagnostic ? nextFocus(diagnostic.criteria) : [];

  return (
    <section className="speaking-panel">
      <header className="speaking-panel__header">
        {level?.level && (
          <span className={`cefr-badge ${cefrTone(level.level)}`}>
            {level.level}
          </span>
        )}
        {trend && trend.direction !== "n/a" && (
          <span className={`speaking-panel__trend trend-${trend.direction}`}>
            {trendArrow(trend.direction)} {formatTrendDelta(trend.delta)}
          </span>
        )}
      </header>

      {diagnostic && (
        <ul className="speaking-panel__criteria">
          {diagnostic.criteria.map((c) => (
            <li
              key={c.criterion}
              className={`speaking-panel__criterion${isWeak(c) ? " review" : ""}`}
            >
              <span className="speaking-panel__criterion-label">
                {criterionLabel(c.criterion)}
              </span>
              <span className="speaking-panel__criterion-score">
                {scorePct(c)}
              </span>
              <span
                className="speaking-panel__criterion-mark"
                aria-hidden="true"
              >
                {isWeak(c) ? "⚠" : "✓"}
              </span>
            </li>
          ))}
        </ul>
      )}

      {focus.length > 0 && (
        <div className="speaking-focus">
          <div className="speaking-focus__head">
            <span className="speaking-focus__label">NEXT FOCUS</span>
            <span className="speaking-focus__criteria">
              {focus.map(criterionLabel).join(" + ")}
            </span>
          </div>
          <button
            type="button"
            className="speaking-focus__action"
            onClick={() => onPractice?.()}
          >
            PRACTICE NOW
          </button>
        </div>
      )}
    </section>
  );
}
