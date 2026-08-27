import { useEffect, useState } from "react";
import { getSpeakingDiagnostic, getSpeakingLevel } from "../../api/academy";
import type {
  SpeakingCriterionProgress,
  SpeakingDiagnostic as SpeakingDiagnosticData,
  SpeakingLevelOut,
} from "../../types/api";
import { criterionLabel, formatTrendDelta, nextFocus } from "../../utils/speaking";
import { useI18n } from "../../hooks/useI18n";
import { LevelBadge } from "../../components/LevelBadge";
import { SkillBar } from "../../components/SkillBar";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { cn } from "../../lib/utils";

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
      <Card className="p-5">
        <p className="text-center text-sm text-muted-foreground">
          {t("empty.noSpeaking")}
        </p>
      </Card>
    );
  }

  const trend = diagnostic?.trend;
  const focus = diagnostic ? nextFocus(diagnostic.criteria) : [];

  return (
    <Card className="gap-5 p-5">
      <header className="flex flex-wrap items-center gap-2">
        {level?.level && <LevelBadge level={level.level} />}
        {trend && trend.direction !== "n/a" && (
          <span
            className={cn(
              "ml-auto inline-flex items-center gap-1 text-xs font-bold tabular-nums",
              trend.direction === "up" && "text-success",
              trend.direction === "down" && "text-destructive",
              trend.direction === "flat" && "text-muted-foreground",
            )}
          >
            {trendArrow(trend.direction)} {formatTrendDelta(trend.delta)}
          </span>
        )}
      </header>

      {diagnostic && (
        <ul className="flex flex-col gap-3">
          {diagnostic.criteria.map((c) => (
            <li key={c.criterion}>
              <SkillBar
                label={criterionLabel(c.criterion)}
                value={c.recent_score ?? c.mean ?? 0}
                hint={`${isWeak(c) ? "⚠ " : "✓ "}${scorePct(c)}`}
              />
            </li>
          ))}
        </ul>
      )}

      {focus.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-primary/25 bg-primary/5 p-4">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
              {t("home.nextFocus")}
            </p>
            <p className="truncate text-sm font-semibold text-foreground">
              {focus.map(criterionLabel).join(" + ")}
            </p>
          </div>
          <Button
            className="min-h-10 uppercase tracking-wide"
            onClick={() => onPractice?.()}
          >
            {t("home.practiceNow")}
          </Button>
        </div>
      )}
    </Card>
  );
}
