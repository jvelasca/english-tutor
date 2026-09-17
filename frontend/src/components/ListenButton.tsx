import { useState } from "react";
import { Loader2, Volume2 } from "lucide-react";
import type { VoiceLanguage } from "../api/voz";
import { speakWithVoice } from "../hooks/useVoiceDownload";
import { cn } from "../lib/utils";

interface ListenButtonProps {
  /** Texto que se reproducirá con TTS. */
  text: string;
  /** Etiqueta accesible / tooltip del botón. */
  label: string;
  /** V3.39 (Fase 2): idioma de la síntesis; `"en"` por defecto (histórico). */
  language?: VoiceLanguage;
  /** V3.39 (Fase 2): perfil opcional para respetar su voz del idioma. */
  userId?: string | null;
  className?: string;
  disabled?: boolean;
}

/**
 * Altavoz compacto (TTS) para escuchar una frase en pantallas de práctica y
 * resultados. Reutiliza `speakWithVoice()` (consentimiento/descarga de voz y
 * aviso global de degradación, V3.72) y muestra un spinner mientras suena. Los
 * fallos de voz son silenciosos: nunca bloquean el flujo.
 */
export function ListenButton({
  text,
  label,
  language = "en",
  userId,
  className,
  disabled,
}: ListenButtonProps) {
  const [busy, setBusy] = useState(false);
  const canPlay = text.trim().length > 0 && !disabled && !busy;

  async function onClick() {
    if (!canPlay) return;
    setBusy(true);
    try {
      await speakWithVoice(text, userId, language);
    } catch {
      /* TTS no disponible: se ignora, no rompe el resultado */
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!canPlay}
      aria-label={label}
      title={label}
      aria-busy={busy}
      className={cn(
        "grid size-8 shrink-0 place-items-center rounded-full border border-border bg-secondary text-secondary-foreground transition-colors hover:border-primary/50 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
    >
      {busy ? (
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      ) : (
        <Volume2 className="size-4" aria-hidden="true" />
      )}
    </button>
  );
}
