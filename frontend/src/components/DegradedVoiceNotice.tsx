import { useEffect } from "react";
import { VolumeX, X } from "lucide-react";
import {
  clearDegradedVoice,
  useDegradedVoice,
} from "../hooks/useDegradedVoice";
import { useI18n } from "../hooks/useI18n";
import { LANGS } from "../utils/i18n";

/** El aviso se descarta solo pasado un rato (es informativo, no un error). */
const AUTO_DISMISS_MS = 15_000;

/**
 * Aviso global y **no bloqueante** de voz degradada (V3.72, RD-04): cuando el
 * backend sirve el audio con una voz de otro idioma, se dice cuál se usó y dónde
 * descargar la que falta, en vez de dejar al alumno con una pronunciación (o un
 * idioma) que no pidió sin explicación.
 *
 * Se monta una sola vez en el shell; el resto de la app solo llama a
 * `reportSpeakResult` a través de `speakWithVoice`.
 */
export function DegradedVoiceNotice() {
  const { t } = useI18n();
  const state = useDegradedVoice();

  useEffect(() => {
    if (!state) return;
    const timer = setTimeout(clearDegradedVoice, AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [state]);

  if (!state) return null;
  const langLabel =
    LANGS.find((entry) => entry.id === state.language)?.label ?? state.language;

  return (
    <div
      role="status"
      data-testid="degraded-voice-notice"
      className="border-border bg-card fixed bottom-4 left-4 z-50 flex max-w-sm items-start gap-3 rounded-lg border px-4 py-3 text-xs text-muted-foreground shadow-lg"
    >
      <VolumeX className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p className="min-w-0 leading-relaxed">
        {t("tts.degradedNotice")
          .replace("{lang}", langLabel)
          .replace("{voice}", state.voice)}
      </p>
      <button
        type="button"
        onClick={clearDegradedVoice}
        aria-label={t("common.close")}
        className="hover:text-foreground shrink-0"
      >
        <X className="size-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}
