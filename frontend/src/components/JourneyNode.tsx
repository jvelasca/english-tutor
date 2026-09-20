import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import { levelClass } from "@/utils/cefr";

export type JourneyNodeState = "done" | "current" | "locked";

/**
 * Nodo del recorrido CEFR (A1 → B2). Píldora circular con el código del nivel,
 * teñida con la **rampa de niveles** (`.lv-*`): completado lleva relleno suave y
 * borde del color del escalón, «estás aquí» se queda sin relleno y engorda el
 * borde, y bloqueado permanece neutro porque todavía no tiene nivel que mostrar.
 * El estado `active` marca el nivel seleccionado con un pulso suave: un anillo
 * que se expande y desvanece en bucle, también del color del nivel (los tokens
 * `--lv-*` se heredan al anillo).
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
        // Bloqueado se queda neutro: todavía no hay nivel que colorear, y la
        // rampa (sin capa) ganaría a las utilidades de gris si se aplicara.
        state !== "locked" && levelClass(level),
        state === "done" && "lv-outline border shadow-sm",
        state === "current" && "lv-quiet lv-outline border-2",
        state === "locked" && "border border-border bg-card text-muted-foreground/50",
        disabled && "cursor-not-allowed",
      )}
    >
      {active && (
        <motion.span
          aria-hidden="true"
          className="lv-outline pointer-events-none absolute inset-0 rounded-full border-2"
          animate={{ scale: [1, 1.7], opacity: [0.6, 0] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
        />
      )}
      <span className="relative">{level}</span>
    </motion.button>
  );
}
