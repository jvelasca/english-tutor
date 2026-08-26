import { useEffect, useState } from "react";
import { getSpeakingJourney } from "../api/academy";
import type { SpeakingJourneyOut } from "../types/api";
import { cefrTone } from "../utils/cefr";
import { formatConfidence, numericToCefr } from "../utils/speaking";

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

interface SpeakingJourneyProps {
  userId: string | null;
}

export function SpeakingJourney({ userId }: SpeakingJourneyProps) {
  const [journey, setJourney] = useState<SpeakingJourneyOut | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      if (!userId) return;
      try {
        const data = await getSpeakingJourney(userId);
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
      <section className="speaking-journey">
        <p className="progress-empty">
          Aún no hay recorrido de expresión oral registrado.
        </p>
      </section>
    );
  }

  const pct = markerPct(journey.current_numeric);

  return (
    <section className="speaking-journey">
      <header className="speaking-journey__header">
        {journey.current_level && (
          <span className={`cefr-badge ${cefrTone(journey.current_level)}`}>
            {journey.current_level}
          </span>
        )}
        <span className="speaking-journey__confidence">
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
            YOU
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
