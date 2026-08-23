import { useState } from "react";
import type { ProgressSummary as ProgressData } from "../types/api";
import {
  formatAverage,
  formatScore,
  pronunciationLevelLabel,
} from "../utils/progress";

interface ProgressSummaryProps {
  progress: ProgressData | null;
}

export function ProgressSummary({ progress }: ProgressSummaryProps) {
  const [open, setOpen] = useState(true);

  return (
    <section className="progress">
      <button
        type="button"
        className="progress-header"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-controls="progress-panel"
      >
        <span className="progress-title">Tu progreso</span>
        <span className={`progress-chevron${open ? " open" : ""}`} aria-hidden="true">
          ▾
        </span>
      </button>

      {open && (
        <div className="progress-body" id="progress-panel">
          {progress === null ? (
            <p className="progress-empty">
              Aún no hay datos de progreso. Empieza a practicar y aquí verás tu
              resumen.
            </p>
          ) : (
            <div className="progress-content">
              <div className="progress-stats">
                <Stat label="Conversaciones" value={String(progress.conversations)} />
                <Stat label="Mensajes" value={String(progress.messages)} />
                <Stat label="Ejercicios" value={String(progress.exercises)} />
                <Stat label="Correcciones" value={String(progress.corrections)} />
              </div>

              <div className="progress-pronunciation">
                <h3>Pronunciación</h3>
                {progress.pronunciation.attempts === 0 ? (
                  <p className="progress-empty">
                    Aún no has grabado ninguna pronunciación.
                  </p>
                ) : (
                  <dl className="progress-rows">
                    <Row label="Intentos" value={String(progress.pronunciation.attempts)} />
                    <Row
                      label="Mejor puntuación"
                      value={formatScore(progress.pronunciation.best)}
                    />
                    <Row
                      label="Media"
                      value={formatAverage(progress.pronunciation.average)}
                    />
                    <Row
                      label="Última puntuación"
                      value={formatScore(progress.pronunciation.last_score)}
                    />
                    <Row
                      label="Último nivel"
                      value={pronunciationLevelLabel(
                        progress.pronunciation.last_level,
                      )}
                      level={progress.pronunciation.last_level}
                    />
                  </dl>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="progress-stat">
      <span className="progress-stat-value">{value}</span>
      <span className="progress-stat-label">{label}</span>
    </div>
  );
}

function Row({
  label,
  value,
  level,
}: {
  label: string;
  value: string;
  level?: "good" | "fair" | "needs_practice" | null;
}) {
  return (
    <div className="progress-row">
      <dt>{label}</dt>
      <dd className={level ? `progress-level ${level}` : undefined}>{value}</dd>
    </div>
  );
}
