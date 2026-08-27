import { useEffect, useState } from "react";
import { getSpeakingDiagnostic } from "../../api/academy";
import type { SpeakingDiagnostic as SpeakingDiagnosticData } from "../../types/api";
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

interface SpeakingDiagnosticProps {
  userId: string | null;
}

export function SpeakingDiagnostic({ userId }: SpeakingDiagnosticProps) {
  const { t } = useI18n();
  const [diagnostic, setDiagnostic] =
    useState<SpeakingDiagnosticData | null>(null);

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
                </span>
                <span className="tabular-nums">
                  {c.attempts} ·{" "}
                  {c.mean !== null ? `${Math.round(c.mean * 100)}%` : "—"}
                  {c.review_due ? ` · ${t("diag.review")}` : ""}
                </span>
              </li>
            ))}
          </ul>
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
