import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { Card } from "../../components/ui/card";
import { useI18n } from "../../hooks/useI18n";

/** Piezas UI mínimas compartidas por las pestañas de MI PROGRESO. */

/** Tarjeta de carga con spinner, usada mientras una pestaña hace sus fetches. */
export function TabLoading({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <Card
      role="status"
      aria-busy="true"
      aria-live="polite"
      className="flex items-center justify-center gap-2 p-6 text-sm text-muted-foreground"
    >
      <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      {label || t("common.loading")}
    </Card>
  );
}

/** Encabezado de sección en minúsculas (mismo patrón que HomeScreen/LearnHub). */
export function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      {children}
    </h2>
  );
}
