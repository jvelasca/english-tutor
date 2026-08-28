import { useEffect, useState } from "react";
import { getSpeakingDiagnostic, getSpeakingEndurance } from "../../api/academy";
import type {
  ConversationEndurance,
  SpeakingDiagnostic as SpeakingDiagnosticData,
} from "../../types/api";
import { criterionLabel } from "../../utils/speaking";
import { useI18n } from "../../hooks/useI18n";
import { Card } from "../../components/ui/card";
import { cn } from "../../lib/utils";

function trendLabel(direction: string): string {
  switch (direction) {
    case "up":
      return "diag.improving";
    case "down":
      return "diag.gettingWorse";
    case "flat":
      return "diag.stable";
    default:
      return "—";
  }
}

/** Puntos porcentuales con signo (la delta del diagnóstico es una media 0..1). */
function formatDelta(delta: number): string {
  return `${delta > 0 ? "+" : ""}${Math.round(delta * 100)} pts`;
}

/** Etiqueta i18n de cada sub-dimensión de Interaction Quality. */
function interactionQualityLabelKey(dimension: string): string {
  switch (dimension) {
    case "initiation":
      return "speaking.iq.initiation";
    case "response":
      return "speaking.iq.response";
    case "follow_up":
      return "speaking.iq.follow_up";
    case "repair":
      return "speaking.iq.repair";
    case "turn_taking":
      return "speaking.iq.turn_taking";
    default:
      return dimension;
  }
}

/** Duración legible (segundos → "1m 30s"). */
function formatSeconds(seconds: number): string {
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

interface SpeakingDiagnosticProps {
  userId: string | null;
}

export function SpeakingDiagnostic({ userId }: SpeakingDiagnosticProps) {
  const { t } = useI18n();
  const [diagnostic, setDiagnostic] =
    useState<SpeakingDiagnosticData | null>(null);
  const [endurance, setEndurance] = useState<ConversationEndurance | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      if (!userId) return;
      try {
        const data = await getSpeakingDiagnostic(userId);
        if (active) setDiagnostic(data);
      } catch {
        /* backend no disponible */
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [userId]);

  useEffect(() => {
    let active = true;
    async function load() {
      if (!userId) return;
      try {
        const data = await getSpeakingEndurance(userId);
        if (active) setEndurance(data);
      } catch {
        /* backend no disponible */
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [userId]);

  return (
    <Card className="gap-4 p-5">
      {!diagnostic ? (
        <p className="text-center text-sm text-muted-foreground">
          {t("empty.noSpeaking")}
        </p>
      ) : (
        <>
          <p className="text-sm text-foreground">
            {diagnostic.recommendation}
          </p>
          <ul className="flex flex-col gap-1">
            {diagnostic.criteria.map((c) => (
              <li
                key={c.criterion}
                className={cn(
                  "flex items-center justify-between gap-3 text-xs",
                  c.review_due ? "text-foreground" : "text-muted-foreground",
                )}
              >
                <span className="font-medium">
                  {criterionLabel(c.criterion)}
                  {c.proxy ? (
                    <span
                      className="ml-1.5 rounded-full border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground"
                      title={t("diag.proxy")}
                    >
                      {t("diag.proxy")}
                    </span>
                  ) : null}
                </span>
                <span className="tabular-nums">
                  {c.attempts} ·{" "}
                  {c.mean !== null ? `${Math.round(c.mean * 100)}%` : "—"}
                  {c.review_due ? ` · ${t("diag.review")}` : ""}
                </span>
              </li>
            ))}
          </ul>

          {diagnostic.interaction_quality &&
            diagnostic.interaction_quality.length > 0 && (
              <div className="flex flex-col gap-1">
                <h4 className="text-xs font-semibold text-foreground">
                  {t("speaking.interactionQuality")}
                </h4>
                <ul className="flex flex-col gap-1">
                  {diagnostic.interaction_quality.map((iq) => (
                    <li
                      key={iq.dimension}
                      className="flex items-center justify-between gap-3 text-xs text-muted-foreground"
                    >
                      <span>{t(interactionQualityLabelKey(iq.dimension))}</span>
                      <span className="tabular-nums">
                        {iq.mean !== null
                          ? `${Math.round(iq.mean * 100)}%`
                          : "—"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

          {endurance && endurance.turns > 0 && (
            <div className="flex flex-col gap-1">
              <h4 className="text-xs font-semibold text-foreground">
                {t("speaking.endurance")}
              </h4>
              <p className="text-xs text-muted-foreground">
                {endurance.turns} {t("speaking.enduranceTurns")} ·{" "}
                {formatSeconds(endurance.total_speaking_seconds)}
                {endurance.current_goal_seconds !== null
                  ? ` · ${t("speaking.enduranceGoal")}: ${formatSeconds(
                      endurance.current_goal_seconds,
                    )}`
                  : ""}
              </p>
              <div className="flex gap-1.5">
                {endurance.milestones.map((m) => (
                  <span
                    key={m.seconds}
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] tabular-nums",
                      m.achieved
                        ? "bg-primary/10 text-primary"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    {formatSeconds(m.seconds)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {diagnostic.trend.direction !== "n/a" && (
            <p className="text-xs text-muted-foreground">
              {t("diag.trend")}:{" "}
              <strong
                className={cn(
                  diagnostic.trend.direction === "up" && "text-success",
                  diagnostic.trend.direction === "down" && "text-destructive",
                  diagnostic.trend.direction === "flat" &&
                    "text-muted-foreground",
                )}
              >
                {t(trendLabel(diagnostic.trend.direction))}
              </strong>
              {diagnostic.trend.delta !== null
                ? ` (${formatDelta(diagnostic.trend.delta)})`
                : ""}
            </p>
          )}
        </>
      )}
    </Card>
  );
}
