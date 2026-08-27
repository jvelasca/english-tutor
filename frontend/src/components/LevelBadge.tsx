import { cefrTone, cefrLabel, type CefrTone } from "@/utils/cefr";
import { cn } from "@/lib/utils";

const TONE_CLASS: Record<CefrTone, string> = {
  basic: "text-warning bg-warning/15",
  intermediate: "text-primary bg-primary/15",
  advanced: "text-success bg-success/15",
};

/**
 * Insignia de nivel CEFR con color según el tramo (básico/intermedio/avanzado).
 * Muestra el código del nivel (A1…C2) y, opcionalmente, su descriptor.
 */
export function LevelBadge({
  level,
  showLabel = false,
  className,
}: {
  level: string;
  showLabel?: boolean;
  className?: string;
}) {
  const tone = cefrTone(level);
  const label = cefrLabel(level);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold tracking-wide",
        TONE_CLASS[tone],
        className,
      )}
    >
      <span className="text-sm leading-none font-extrabold">{level}</span>
      {showLabel && label !== level && (
        <span className="font-medium opacity-90">{label}</span>
      )}
    </span>
  );
}
