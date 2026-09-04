import { useEffect, useState } from "react";
import { getWritingJourney } from "../../api/academy";
import type { WritingJourneyOut } from "../../types/api";
import { cefrTone } from "../../utils/cefr";
import { formatConfidence, numericToCefr } from "../../utils/writing";
import { useI18n } from "../../hooks/useI18n";

const MILESTONES = ["A2", "B1", "B2"] as const;
const MILESTONE_START = 2;
const MILESTONE_END = 4;

/** Posición porcentual del marcador "YOU" entre el primer y último hito. */
function markerPct(numeric: number | null): number {
  if (numeric === null) return 0;
  const pct =
    ((numeric - MILESTONE_START) / (MILESTONE_END - MILESTONE_START)) * 100;
  return Math.min(100, Math.max(0, pct));
}

interface WritingJourneyProps {
  userId: string | null;
}

export function WritingJourney({ userId }: WritingJourneyProps) {
  const { t } = useI18n();
  const [journey, setJourney] = useState<WritingJourneyOut | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      if (!userId) return;
      try {
        const data = await getWritingJourney(userId);
        if (active) setJourney(data);
      } catch {
        /* backend no disponible */
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [userId]);

  if (!journey || journey.steps.length === 0) {
    return (
      <section className="writing-journey">
        <p className="progress-empty">{t("empty.noWritingJourney")}</p>
      </section>
    );
  }

  const pct = markerPct(journey.current_numeric);

  return (
    <section className="writing-journey">
      <header className="writing-journey__header">
        {journey.current_level && (
          <span className={`cefr-badge ${cefrTone(journey.current_level)}`}>
            {journey.current_level}
          </span>
        )}
        <span className="writing-journey__confidence">
          {formatConfidence(journey.current_confidence)}
        </span>
      </header>

      <div className="journey-bar">
        <div className="journey-track">
          <span className="journey-fill" style={{ width: `${pct}%` }} />
          {MILESTONES.map((m, i) => (
            <span
              key={m}
              className="journey-node"
              style={{ left: `${(i / (MILESTONES.length - 1)) * 100}%` }}
              aria-hidden="true"
            />
          ))}
          <span className="journey-marker" style={{ left: `${pct}%` }}>
            {t("writing.you")}
          </span>
        </div>
        <div className="journey-labels">
          {MILESTONES.map((m) => (
            <span key={m} className="journey-label">
              {m}
            </span>
          ))}
        </div>
      </div>

      <div className="journey-steps">
        <span className="journey-steps__row">
          {journey.steps.map((s) => numericToCefr(s.numeric)).join(" → ")}
        </span>
        <span className="journey-steps__row journey-steps__confidence">
          {journey.steps.map((s) => formatConfidence(s.confidence)).join(" → ")}
        </span>
      </div>
    </section>
  );
}
