import { motion } from "motion/react";
import { cn } from "@/lib/utils";

export type JourneyNodeState = "done" | "current" | "locked";

/**
 * Nodo del recorrido CEFR (A1 → B2). Píldora circular con el código del nivel.
 * El estado `active` marca el nivel seleccionado ("tú estás aquí") con un pulso
 * suave: un anillo que se expande y desvanece en bucle.
 */
export function JourneyNode({
  level,
  state,
  active = false,
  onClick,
  disabled = false,
}: {
  level: string;
  state: JourneyNodeState;
  active?: boolean;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      disabled={disabled}
      whileTap={disabled ? undefined : { scale: 0.92 }}
      aria-label={level}
      aria-current={active ? "true" : undefined}
      className={cn(
        "relative grid size-12 shrink-0 select-none place-items-center rounded-full text-sm font-bold transition-colors",
        state === "done" && "bg-primary text-primary-foreground shadow-sm",
        state === "current" && "border-2 border-primary bg-card text-primary",
        state === "locked" && "border border-border bg-card text-muted-foreground/50",
        disabled && "cursor-not-allowed",
      )}
    >
      {active && (
        <motion.span
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 rounded-full border-2 border-primary"
          animate={{ scale: [1, 1.7], opacity: [0.6, 0] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
        />
      )}
      <span className="relative">{level}</span>
    </motion.button>
  );
}
