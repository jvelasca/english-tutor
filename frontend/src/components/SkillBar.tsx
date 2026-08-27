import { motion } from "motion/react";
import { cn } from "@/lib/utils";

/**
 * Barra de progreso de destreza con animación de llenado al entrar en viewport.
 * `value` está normalizado a 0..1 (como `skill.score` del Student Model).
 */
export function SkillBar({
  label,
  value,
  hint,
  className,
}: {
  label?: string;
  value: number;
  hint?: string;
  className?: string;
}) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div className={cn("space-y-1.5", className)}>
      {(label || hint) && (
        <div className="flex items-baseline justify-between gap-2 text-sm">
          {label && <span className="text-foreground">{label}</span>}
          {hint && (
            <span className="text-muted-foreground text-xs">{hint}</span>
          )}
        </div>
      )}
      <div className="bg-primary/15 h-2 w-full overflow-hidden rounded-full">
        <motion.div
          className="bg-primary h-full rounded-full"
          initial={{ width: 0 }}
          whileInView={{ width: `${pct}%` }}
          viewport={{ once: true }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>
    </div>
  );
}
