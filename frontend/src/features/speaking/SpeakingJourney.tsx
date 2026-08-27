import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { getSpeakingJourney } from "../../api/academy";
import type { SpeakingJourneyOut } from "../../types/api";
import { formatConfidence, numericToCefr } from "../../utils/speaking";
import { useI18n } from "../../hooks/useI18n";
import { LevelBadge } from "../../components/LevelBadge";
import { Card } from "../../components/ui/card";

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
  const { t } = useI18n();
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
      <Card className="p-5">
        <p className="text-center text-sm text-muted-foreground">
          {t("empty.noSpeakingJourney")}
        </p>
      </Card>
    );
  }

  const pct = markerPct(journey.current_numeric);

  return (
    <Card className="gap-5 p-5">
      <header className="flex items-center gap-2">
        {journey.current_level && (
          <LevelBadge level={journey.current_level} />
        )}
        <span className="ml-auto text-xs font-bold tabular-nums text-primary">
          {formatConfidence(journey.current_confidence)}
        </span>
      </header>

      <div className="pt-7">
        <div className="relative h-2 rounded-full bg-secondary">
          <motion.div
            className="absolute inset-y-0 left-0 rounded-full bg-primary"
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          />
          {MILESTONES.map((m, i) => (
            <span
              key={m}
              className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-primary bg-card"
              style={{ left: `${(i / (MILESTONES.length - 1)) * 100}%` }}
              aria-hidden="true"
            />
          ))}
          <span
            className="absolute -top-6 -translate-x-1/2 whitespace-nowrap rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-bold leading-tight text-primary-foreground"
            style={{ left: `${pct}%` }}
          >
            {t("course.you")}
          </span>
        </div>
        <div className="mt-1.5 flex justify-between text-xs text-muted-foreground">
          {MILESTONES.map((m) => (
            <span key={m}>{m}</span>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-0.5 border-t border-border pt-3 text-xs">
        <span className="tabular-nums text-muted-foreground">
          {journey.steps.map((s) => numericToCefr(s.numeric)).join(" → ")}
        </span>
        <span className="font-semibold tabular-nums text-primary">
          {journey.steps
            .map((s) => formatConfidence(s.confidence))
            .join(" → ")}
        </span>
      </div>
    </Card>
  );
}
