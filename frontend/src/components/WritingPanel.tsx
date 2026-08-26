import { useEffect, useState } from "react";
import { getWritingDiagnostic, getWritingLevel } from "../api/academy";
import type {
  WritingCriterionProgress,
  WritingDiagnostic as WritingDiagnosticData,
  WritingLevelOut,
} from "../types/api";
import { cefrTone } from "../utils/cefr";
import {
  formatTrendDelta,
  writingCriterionLabel,
  writingNextFocus,
} from "../utils/writing";

interface WritingPanelProps {
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
function scorePct(c: WritingCriterionProgress): string {
  const score = c.recent_score ?? c.mean;
  return score == null ? "—" : `${Math.round(score * 100)}%`;
}

/** Un criterio es débil si toca repasar o si su puntuación está bajo 0.6. */
function isWeak(c: WritingCriterionProgress): boolean {
  if (c.review_due) return true;
  const score = c.recent_score ?? c.mean;
  return score != null && score < 0.6;
}

export function WritingPanel({ userId, onPractice }: WritingPanelProps) {
  const [level, setLevel] = useState<WritingLevelOut | null>(null);
  const [diagnostic, setDiagnostic] =
    useState<WritingDiagnosticData | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      if (!userId) return;
      try {
        const [lvl, diag] = await Promise.all([
          getWritingLevel(userId),
          getWritingDiagnostic(userId),
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
      <section className="writing-panel">
        <p className="progress-empty">
          Aún no hay práctica de expresión escrita registrada.
        </p>
      </section>
    );
  }

  const trend = diagnostic?.trend;
  const focus = diagnostic ? writingNextFocus(diagnostic.criteria) : [];

  return (
    <section className="writing-panel">
      <header className="writing-panel__header">
        {level?.level && (
          <span className={`cefr-badge ${cefrTone(level.level)}`}>
            {level.level}
          </span>
        )}
        {trend && trend.direction !== "n/a" && (
          <span className={`writing-panel__trend trend-${trend.direction}`}>
            {trendArrow(trend.direction)} {formatTrendDelta(trend.delta)}
          </span>
        )}
      </header>

      {diagnostic && (
        <ul className="writing-panel__criteria">
          {diagnostic.criteria.map((c) => (
            <li
              key={c.criterion}
              className={`writing-panel__criterion${isWeak(c) ? " review" : ""}`}
            >
              <span className="writing-panel__criterion-label">
                {writingCriterionLabel(c.criterion)}
              </span>
              <span className="writing-panel__criterion-score">
                {scorePct(c)}
              </span>
              <span
                className="writing-panel__criterion-mark"
                aria-hidden="true"
              >
                {isWeak(c) ? "⚠" : "✓"}
              </span>
            </li>
          ))}
        </ul>
      )}

      {focus.length > 0 && (
        <div className="writing-focus">
          <div className="writing-focus__head">
            <span className="writing-focus__label">NEXT FOCUS</span>
            <span className="writing-focus__criteria">
              {focus.map(writingCriterionLabel).join(" + ")}
            </span>
          </div>
          <button
            type="button"
            className="writing-focus__action"
            onClick={() => onPractice?.()}
          >
            PRACTICE NOW
          </button>
        </div>
      )}
    </section>
  );
}
