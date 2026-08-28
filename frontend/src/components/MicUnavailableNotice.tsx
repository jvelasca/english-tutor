import { AlertTriangle } from "lucide-react";
import { useI18n } from "../hooks/useI18n";
import type { MicUnavailableReason } from "../utils/browserCapabilities";

/**
 * Aviso pedagógico de micrófono no disponible: explica la causa y una lista de
 * comprobaciones, en lugar de mostrar el `TypeError` crudo del navegador.
 */
export function MicUnavailableNotice({ reason }: { reason: MicUnavailableReason }) {
  const { t } = useI18n();
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 space-y-1.5">
        <p className="font-semibold">{t("mic.unavailableTitle")}</p>
        <p className="text-destructive/90">{t(`mic.unavailable.${reason}`)}</p>
        <p className="font-medium text-destructive/80">
          {t("mic.unavailable.checkTitle")}
        </p>
        <ul className="list-disc pl-4 text-destructive/80">
          <li>{t("mic.unavailable.checkSecure")}</li>
          <li>{t("mic.unavailable.checkPermission")}</li>
          <li>{t("mic.unavailable.checkBrowser")}</li>
        </ul>
      </div>
    </div>
  );
}
