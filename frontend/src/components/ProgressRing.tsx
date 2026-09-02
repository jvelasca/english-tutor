import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Anillo de progreso (donut) puro, sin dependencias.
 * `value` va de 0 a 100; el color se controla desde fuera con clases
 * `text-*` (el trazo usa `currentColor` y el track un 15 % de opacidad).
 * `children` se centra dentro del anillo (porcentaje, icono, nivel…).
 */
export function ProgressRing({
  value,
  size = 56,
  strokeWidth = 6,
  className,
  ariaLabel,
  children,
}: {
  value: number;
  size?: number;
  strokeWidth?: number;
  className?: string;
  ariaLabel?: string;
  children?: ReactNode;
}) {
  const clamped = Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);

  return (
    <div
      className={cn("relative inline-grid shrink-0 place-items-center", className)}
      style={{ width: size, height: size }}
      role="progressbar"
      aria-label={ariaLabel}
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="opacity-15"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">{children}</div>
    </div>
  );
}
