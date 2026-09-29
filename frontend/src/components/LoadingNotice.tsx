import * as React from "react";
import { Clock, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "../hooks/useI18n";

interface LoadingNoticeProps {
  /** Etiqueta base de la espera. Por defecto, `common.loading`. */
  label?: string;
  /**
   * Aviso que aparece cuando la espera se alarga. Por defecto,
   * `common.stillWorking` («sigue en marcha, el modelo local puede tardar»).
   */
  slowLabel?: string;
  /** Milisegundos antes de declarar la espera «larga». 4000 por defecto. */
  slowAfterMs?: number;
  className?: string;
}

/**
 * Aviso de espera con dos tiempos (V3.88.0).
 *
 * El proyecto ya tenía dos formas de decir «estoy cargando»: `PanelState`
 * (panel entero, con reintento) y `TabLoading` (tarjeta de pestaña). Ninguna
 * distinguía una consulta instantánea de una que va a tardar: cuando la BD o el
 * modelo local se toman su tiempo, el alumno veía el mismo «Cargando…» quieto y
 * no sabía si seguía vivo.
 *
 * Este componente arranca como spinner y, si la espera supera `slowAfterMs`,
 * cambia a un reloj y añade el aviso de lentitud. No parpadea en las consultas
 * rápidas (el umbral se elige por encima de una respuesta normal) y tranquiliza
 * en las lentas (generación con IA, primera consulta de una palabra).
 *
 * Se monta SOLO mientras dura la espera (igual que `PanelState`): al
 * desmontarse se cancela el temporizador. Si el llamador necesita reiniciar el
 * umbral entre dos cargas seguidas, que lo remonte con una `key` distinta.
 */
export function LoadingNotice({
  label,
  slowLabel,
  slowAfterMs = 4000,
  className,
}: LoadingNoticeProps) {
  const { t } = useI18n();
  const [slow, setSlow] = React.useState(false);

  React.useEffect(() => {
    const id = window.setTimeout(() => setSlow(true), slowAfterMs);
    return () => window.clearTimeout(id);
  }, [slowAfterMs]);

  return (
    <p
      role="status"
      aria-busy="true"
      aria-live="polite"
      className={cn(
        "text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm",
        className,
      )}
    >
      {slow ? (
        <Clock className="size-4 shrink-0" aria-hidden="true" />
      ) : (
        <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden="true" />
      )}
      <span>{label || t("common.loading")}</span>
      {slow ? (
        <span className="text-xs opacity-80">
          {slowLabel || t("common.stillWorking")}
        </span>
      ) : null}
    </p>
  );
}
