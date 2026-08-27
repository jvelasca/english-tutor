import { useEffect, useState } from "react";
import { getSpeakingDiagnostic } from "../../api/academy";
import type { SpeakingDiagnostic as SpeakingDiagnosticData } from "../../types/api";
import { criterionLabel } from "../../utils/speaking";
import { useI18n } from "../../hooks/useI18n";

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
    <section className="speaking-diagnostic">
      {!diagnostic ? (
        <p className="progress-empty">{t("empty.noSpeaking")}</p>
      ) : (
        <>
          <p className="speaking-recommendation">{diagnostic.recommendation}</p>
          <ul className="speaking-criteria">
            {diagnostic.criteria.map((c) => (
              <li
                key={c.criterion}
                className={`speaking-criterion${
                  c.review_due ? " review" : ""
                }`}
              >
                <span className="speaking-criterion-label">
                  {criterionLabel(c.criterion)}
                </span>
                <span className="speaking-criterion-meta">
                  {c.attempts} · {c.mean !== null ? `${Math.round(c.mean * 100)}%` : "—"}
                  {c.review_due ? ` · ${t("diag.review")}` : ""}
                </span>
              </li>
            ))}
          </ul>
          {diagnostic.trend.direction !== "n/a" && (
            <p className="speaking-trend">
              {t("diag.trend")}:{" "}
              <strong className={`trend-${diagnostic.trend.direction}`}>
                {t(trendLabel(diagnostic.trend.direction))}
              </strong>
              {diagnostic.trend.delta !== null
                ? ` (${formatDelta(diagnostic.trend.delta)})`
                : ""}
            </p>
          )}
        </>
      )}
    </section>
  );
}
