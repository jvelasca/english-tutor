import { useEffect, useRef, useState } from "react";
import { useI18n } from "../hooks/useI18n";
import { SystemStatus } from "./SystemStatus";

/**
 * Barra de estado con revelación progresiva: colapsada en un indicador mínimo
 * ("● Ready"); al hacer clic se expande en un popover con el estado del sistema
 * (API / base de datos / Ollama / STT / TTS / versión / URL LAN).
 */
export function StatusBar() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

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

  return (
    <footer className="status-bar" ref={ref}>
      <button
        type="button"
        className="status-bar__trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="dialog"
        aria-expanded={open}
        title={t("status.systemStatus")}
      >
        <span className="status-bar__dot" aria-hidden="true" />
        <span>{t("status.ready")}</span>
      </button>

      {open && (
        <div className="status-popover" role="dialog" aria-label={t("status.systemStatus")}>
          <div className="status-popover__head">
            <strong>{t("status.systemStatus")}</strong>
          </div>
          <SystemStatus />
        </div>
      )}
    </footer>
  );
}
