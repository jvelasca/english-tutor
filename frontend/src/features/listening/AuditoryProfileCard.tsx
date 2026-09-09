import { Ear } from "lucide-react";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import type { ListeningAuditoryProfile } from "../../types/api";

type Translate = (key: string) => string;

/** Clave i18n de la etiqueta de una capa cognitiva. */
export function profileLayerKey(layer: string | null): string {
  if (!layer) return "";
  return `listening.layer.${layer}`;
}

/** Clave i18n de la etiqueta de una intervención. */
export function profileInterventionKey(
  intervention: ListeningAuditoryProfile["intervention"],
): string {
  return `listening.profile.intervention.${intervention ?? "none"}`;
}

interface AuditoryProfileCardProps {
  profile: ListeningAuditoryProfile | null | undefined;
  t: Translate;
}

/**
 * Tarjeta del perfil auditivo (V3.27, Listening Engine 4.0): muestra la capa de
 * trabajo y la intervención recomendada (casos A-D de la especificación), o el
 * estado "necesita más intentos" mientras no hay muestra suficiente. Informativa
 * y no bloqueante: nunca oculta la práctica.
 */
export function AuditoryProfileCard({
  profile,
  t,
}: AuditoryProfileCardProps) {
  if (!profile) return null;
  const intervention = profile.intervention;
  const layer = profile.layer;
  if (!intervention && !layer && !profile.needs_min_attempts) return null;
  return (
    <Card className="gap-3 border-primary/25 p-4 sm:p-5">
      <div className="flex items-center gap-2">
        <Ear className="size-4 text-primary" aria-hidden="true" />
        <p className="text-sm font-semibold text-foreground">
          {t("listening.profile.title")}
        </p>
      </div>
      {intervention ? (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {t("listening.profile.workingOn")}
            </span>
            {layer && (
              <Badge variant="default">{t(profileLayerKey(layer))}</Badge>
            )}
          </div>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {t(profileInterventionKey(intervention))}
          </p>
        </div>
      ) : (
        profile.needs_min_attempts && (
          <p className="text-sm text-muted-foreground">
            {t("listening.profile.needsMore")}
          </p>
        )
      )}
    </Card>
  );
}
