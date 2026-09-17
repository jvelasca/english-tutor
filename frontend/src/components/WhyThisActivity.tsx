import { useI18n } from "../hooks/useI18n";
import { dimensionLabel } from "../utils/learningLabels";
import { cn } from "../lib/utils";

/** Factor limitante declarado por el servidor (contrato de `next-best`). */
export interface WhyLimitingFactor {
  id: string;
  score: number;
  missing?: boolean;
}

interface WhyThisActivityProps {
  /**
   * Frase(s) en las que el SERVIDOR declara por qué propone esta actividad
   * (contrato `why` del proyecto: inglés, frases cortas y deterministas). La UI
   * no la traduce ni recalcula señales (premisa 21); se pinta tal cual.
   */
  why?: string | string[] | null;
  /** Líneas del `because[]` del motor (cadenas también declaradas). */
  because?: string[] | null;
  limitingFactor?: WhyLimitingFactor | null;
  /**
   * `full`: etiqueta + frase + `because[]` + factor limitante (tarjeta
   * protagonista de Home). `compact`: solo etiqueta + frase; el `because[]`
   * completo sigue viviendo en `NextBestCard` (mismo criterio que `TodayPlan`).
   */
  variant?: "full" | "compact";
  className?: string;
}

/**
 * «Por qué esta actividad» (V3.72): una sola pieza para el `why` que declara el
 * motor, compartida por las superficies que lo mostraban (`NextBestCard`) y por
 * las que lo descartaban (el pie «Next» de cada práctica y la cola de repaso).
 *
 * Honestidad (premisa 21 y regla de no inventar): sin `why` ni `because` no se
 * pinta nada. La pieza **nunca** deriva motivos de señales del cliente: o el
 * servidor los declaró, o no hay explicación que mostrar.
 */
export function WhyThisActivity({
  why,
  because,
  limitingFactor,
  variant = "full",
  className,
}: WhyThisActivityProps) {
  const { t } = useI18n();
  const lines = (Array.isArray(why) ? why : why ? [why] : []).filter(Boolean);
  const reasons = (because ?? []).filter(Boolean);
  const compact = variant === "compact";

  // El `because[]` sin frase sigue explicando algo; sin nada, silencio.
  if (lines.length === 0 && (!reasons.length || compact)) return null;

  const label = (
    <span className="font-semibold">{t("home.whyThisActivity")}</span>
  );

  if (compact) {
    return (
      <p className={cn("text-[11px] text-muted-foreground", className)}>
        {label} {lines.join("; ")}
      </p>
    );
  }

  return (
    <div className={cn("text-sm text-foreground/90", className)}>
      {lines.length > 0 && (
        <p>
          {label} {lines.join("; ")}
        </p>
      )}
      {reasons.length > 0 && (
        <div className={cn(lines.length > 0 && "mt-2")}>
          <p className="font-semibold">{t("home.because")}</p>
          <ol className="mt-1 list-decimal space-y-0.5 pl-4 text-muted-foreground">
            {reasons.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ol>
          {limitingFactor && (
            <p className="mt-1 text-xs">
              {t("home.limitingFactor")}:{" "}
              <span className="font-medium text-foreground">
                {dimensionLabel(limitingFactor.id)}
                {limitingFactor.missing
                  ? ` (${t("home.missing")})`
                  : ` · ${Math.round(limitingFactor.score * 100)}%`}
              </span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
