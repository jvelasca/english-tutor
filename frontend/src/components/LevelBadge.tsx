import { cefrTone, cefrLabel, type CefrTone } from "@/utils/cefr";
import { useI18n } from "@/hooks/useI18n";
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

/**
 * Badge de nivel **estimado** (P2/H7): `LevelBadge` + el calificador
 * "estimado · no certificado". "Demostrado" queda reservado para los gates
 * (p. ej. el DEMONSTRATED del listening con retención ≥7 días); un nivel
 * estimado nunca debe leerse como certificación.
 */
export function EstimatedLevelBadge({
  level,
  className,
}: {
  level: string;
  className?: string;
}) {
  const { t } = useI18n();
  return (
    <span
      className={cn(
        "inline-flex flex-wrap items-center gap-x-2 gap-y-1",
        className,
      )}
    >
      <LevelBadge level={level} />
      <span
        className="text-[11px] font-medium text-muted-foreground"
        title={t("profile.estimatedQualifier")}
      >
        {t("profile.estimatedQualifier")}
      </span>
    </span>
  );
}
