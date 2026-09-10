import { useEffect, useRef, useState } from "react";
import { getHealth } from "../api/health";
import { useI18n } from "../hooks/useI18n";
import { cn } from "@/lib/utils";
import { SystemStatus } from "./SystemStatus";

/** Periodo de sondeo del estado del servidor (ms). */
const POLL_INTERVAL_MS = 15_000;

/**
 * Indicador de conexión con el servidor integrado en la CABECERA (V3.38.1).
 *
 * Sustituye a la barra de estado inferior de V3.x: un punto verde/rojo con la
 * etiqueta Conectado/Desconectado, junto al subtítulo de la app. Al pulsarlo
 * abre un popover con el panel completo `<SystemStatus />` (que sigue viviendo
 * también en Ajustes), de modo que no se pierde información y se gana espacio
 * útil en la parte inferior de la app.
 */
export function ConnectionIndicator() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [online, setOnline] = useState<boolean | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        await getHealth();
        if (!cancelled) setOnline(true);
      } catch {
        if (!cancelled) setOnline(false);
      }
    }
    void check();
    const id = window.setInterval(() => {
      void check();
    }, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const tone =
    online === null
      ? "status-dot--unknown"
      : online
        ? "status-dot--ok"
        : "status-dot--off";
  const label =
    online === null
      ? t("status.connectionChecking")
      : online
        ? t("status.connected")
        : t("status.disconnected");

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={t("status.systemStatus")}
        title={t("status.systemStatus")}
        className="border-border text-muted-foreground hover:text-foreground flex min-h-9 items-center gap-1.5 rounded-full border px-2.5 text-xs font-semibold transition-colors"
      >
        <span className={cn("status-dot", tone)} aria-hidden="true" />
        <span className="hidden sm:inline">{label}</span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-label={t("status.systemStatus")}
          className="border-border bg-popover text-popover-foreground absolute top-full left-0 z-50 mt-2 max-h-[70vh] w-[min(20rem,calc(100vw-2rem))] overflow-y-auto rounded-xl border p-4 shadow-lg"
        >
          <strong className="mb-2 block text-sm">
            {t("status.systemStatus")}
          </strong>
          <SystemStatus />
        </div>
      )}
    </div>
  );
}
