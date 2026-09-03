import { useState } from "react";
import { Loader2, Volume2 } from "lucide-react";
import { speak } from "../api/voz";
import { cn } from "../lib/utils";

interface ListenButtonProps {
  /** Texto en inglés que se reproducirá con TTS. */
  text: string;
  /** Etiqueta accesible / tooltip del botón. */
  label: string;
  className?: string;
  disabled?: boolean;
}

/**
 * Altavoz compacto (TTS) para escuchar una frase en inglés en pantallas de
 * práctica y resultados. Reutiliza `speak()` y muestra un spinner mientras
 * suena. Los fallos de voz son silenciosos: nunca bloquean el flujo.
 */
export function ListenButton({
  text,
  label,
  className,
  disabled,
}: ListenButtonProps) {
  const [busy, setBusy] = useState(false);
  const canPlay = text.trim().length > 0 && !disabled && !busy;

  async function onClick() {
    if (!canPlay) return;
    setBusy(true);
    try {
      await speak(text);
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
