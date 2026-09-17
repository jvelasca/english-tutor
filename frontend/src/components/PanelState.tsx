import { Loader2, RefreshCw } from "lucide-react";
import { Button } from "./ui/button";
import { useI18n } from "../hooks/useI18n";

interface PanelStateProps {
  state: "loading" | "error";
  /** Si se pasa, el error ofrece reintentar (patrón de `HomeScreen`). */
  onRetry?: () => void;
}

/**
 * Estado de carga/fallo con reintento para los paneles que leen del backend
 * (V3.72, F4).
 *
 * Estos paneles atrapaban el error con un `catch {}` vacío: si el backend no
 * estaba listo, quedaban en blanco para siempre, sin decir nada, sin distinguir
 * «no hay datos» de «no se pudo cargar» y sin forma de reintentar salvo recargar
 * la página. `HomeScreen` ya usaba el patrón `loading → error → reintento`; esto
 * lo hace reutilizable en vez de triplicarlo.
 */
export function PanelState({ state, onRetry }: PanelStateProps) {
  const { t } = useI18n();

  if (state === "loading") {
    return (
      <p
        role="status"
        aria-busy="true"
        className="text-muted-foreground flex items-center gap-2 text-sm"
      >
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        {t("common.loading")}
      </p>
    );
  }

  return (
    <div role="alert" className="flex flex-col items-start gap-2">
      <p className="text-muted-foreground text-sm">{t("common.unavailable")}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="gap-2" onClick={onRetry}>
          <RefreshCw className="size-4" aria-hidden="true" />
          {t("common.retry")}
        </Button>
      )}
    </div>
  );
}
