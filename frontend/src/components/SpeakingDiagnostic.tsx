import { useEffect, useState } from "react";
import { getSpeakingDiagnostic } from "../api/academy";
import type { SpeakingDiagnostic as SpeakingDiagnosticData } from "../types/api";

/** Etiqueta legible de cada criterio del rubric de speaking. */
function criterionLabel(criterion: string): string {
  switch (criterion) {
    case "task_achievement":
      return "Tarea";
    case "grammatical_control":
      return "Gramática";
    case "lexical_resource":
      return "Léxico";
    case "fluency":
      return "Fluidez";
    case "pronunciation":
      return "Pronunciación";
    case "coherence":
      return "Coherencia";
    case "interaction":
      return "Interacción";
    default:
      return criterion;
  }
}

function trendLabel(direction: string): string {
  switch (direction) {
    case "up":
      return "mejorando";
    case "down":
      return "empeorando";
    case "flat":
      return "estable";
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
      <h3>Expresión oral</h3>
      {!diagnostic ? (
        <p className="progress-empty">
          Aún no hay práctica de expresión oral registrada.
        </p>
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
                  {c.review_due ? " · revisar" : ""}
                </span>
              </li>
            ))}
          </ul>
          {diagnostic.trend.direction !== "n/a" && (
            <p className="speaking-trend">
              Tendencia reciente:{" "}
              <strong className={`trend-${diagnostic.trend.direction}`}>
                {trendLabel(diagnostic.trend.direction)}
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
