import { useId, useState } from "react";
import type { ReactNode } from "react";

interface InsightCardProps {
  id?: string;
  title: string;
  icon?: ReactNode;
  badge?: ReactNode;
  actions?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}

/**
 * Tarjeta colapsable reutilizable para el panel de análisis. Centraliza el
 * chrome visual (borde, radio, sombra) y el estado de colapso con la
 * accesibilidad correspondiente (aria-expanded / aria-controls).
 */
export function InsightCard({
  id,
  title,
  icon,
  badge,
  actions,
  defaultOpen = false,
  children,
}: InsightCardProps) {
  const [open, setOpen] = useState(defaultOpen);
  const bodyId = useId();

  return (
    <section
      className={`card insight-card${open ? " card--open" : ""}`}
      id={id}
    >
      <div className="card__header">
        <button
          type="button"
          className="card__toggle"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls={bodyId}
        >
          {icon && <span className="card__icon">{icon}</span>}
          <span className="card__title">{title}</span>
          {badge}
          <span className="card__chevron" aria-hidden="true">
            <ChevronIcon />
          </span>
        </button>
        {actions && <div className="card__actions">{actions}</div>}
      </div>
      {open && (
        <div className="card__body" id={bodyId}>
          {children}
        </div>
      )}
    </section>
  );
}

function ChevronIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}
