import type { ReactNode } from "react";

export type ActivityOutcome = "ok" | "ko" | "neutral";

/**
 * Contenedor compartido de resultado de actividad (Learning UX 2.0). Cada
 * actividad conserva su propio scoring, pero termina en una pantalla de
 * resultado uniforme con un pie "Next" común (ver `NextStep`).
 */
export function ActivityResult({
  outcome,
  title,
  children,
  footer,
}: {
  outcome: ActivityOutcome;
  title: string;
  children?: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <section className="activity-result" aria-live="polite">
      <header className="activity-result__head">
        <span
          className={`activity-result__badge activity-result__badge--${outcome}`}
          aria-hidden="true"
        >
          {outcome === "ok" ? "✓" : outcome === "ko" ? "×" : "•"}
        </span>
        <strong className="activity-result__title">{title}</strong>
      </header>
      {children && <div className="activity-result__body">{children}</div>}
      {footer && <footer className="activity-result__footer">{footer}</footer>}
    </section>
  );
}
