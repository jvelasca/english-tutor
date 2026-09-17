import { Loader2 } from "lucide-react";
import {
  confirmVoiceDownload,
  dismissVoiceDownload,
  useVoiceDownloadRequest,
} from "../hooks/useVoiceDownload";
import { useI18n } from "../hooks/useI18n";

/**
 * Consentimiento de descarga de voz (V3.72, RD-04).
 *
 * Sustituye la descarga automática y silenciosa que hacía el Traductor (~60 MB
 * desde Hugging Face al montar la pantalla): aquí se dice qué voz falta, cuánto
 * ocupa y que solo se descarga una vez, y se pide permiso. El progreso es
 * **indeterminado** porque el endpoint es síncrono y bloqueante, así que no hay
 * porcentaje honesto que mostrar.
 */
export function VoiceDownloadDialog() {
  const { t } = useI18n();
  const request = useVoiceDownloadRequest();
  if (!request) return null;

  const downloading = request.status === "downloading";
  return (
    <div className="dialog-backdrop" onClick={downloading ? undefined : dismissVoiceDownload}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={t("tts.downloadTitle")}
        data-testid="voice-download-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="dialog-header">
          <h2>{t("tts.downloadTitle")}</h2>
          <button
            type="button"
            className="dialog-close flex h-10 w-10 items-center justify-center"
            onClick={dismissVoiceDownload}
            disabled={downloading}
            aria-label={t("common.close")}
          >
            ×
          </button>
        </header>

        <div className="dialog-body">
          <p className="text-sm leading-relaxed">
            {t("tts.downloadBody")
              .replace("{name}", request.voice.name)
              .replace("{size}", String(request.voice.size_mb))}
          </p>

          {downloading && (
            <p
              role="status"
              className="text-muted-foreground flex items-center gap-2 text-xs"
            >
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              {t("tts.downloadProgress")}
            </p>
          )}

          {request.status === "error" && (
            <p role="alert" className="text-destructive text-xs">
              {t("tts.downloadError")}
              {request.error}
            </p>
          )}
        </div>

        <footer className="dialog-footer">
          <button
            type="button"
            className="dialog-secondary"
            onClick={dismissVoiceDownload}
            disabled={downloading}
          >
            {t("tts.downloadCancel")}
          </button>
          <button
            type="button"
            className="dialog-primary flex items-center gap-2"
            onClick={() => void confirmVoiceDownload()}
            disabled={downloading}
          >
            {downloading && (
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            )}
            {request.status === "error"
              ? t("tts.downloadRetry")
              : t("tts.downloadConfirm")}
          </button>
        </footer>
      </div>
    </div>
  );
}
