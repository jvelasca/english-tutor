/**
 * V3.45 — Botón de micrófono grande del modo Conversación del Traductor.
 *
 * Botón circular pensado para pulsarlo con el pulgar y pasárselo al
 * interlocutor (patrón de las apps de traducción de viaje). El estado visual
 * lo controla el turno (`useVoiceTurn`): inactivo, escuchando (con anillo que
 * late según el nivel de voz) o transcribiendo.
 */
import { Loader2, Mic, Square } from "lucide-react";
import { cn } from "../../lib/utils";
import type { VoiceTurnStatus } from "./useVoiceTurn";

interface BigMicButtonProps {
  /** Etiqueta accesible / tooltip (depende del estado). */
  label: string;
  status: VoiceTurnStatus;
  /** Nivel de entrada 0–100 mientras se escucha. */
  level: number;
  disabled?: boolean;
  onToggle: () => void;
  testId?: string;
}

export function BigMicButton({
  label,
  status,
  level,
  disabled = false,
  onToggle,
  testId,
}: BigMicButtonProps) {
  const listening = status === "listening";
  const transcribing = status === "transcribing";

  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onToggle}
      disabled={disabled || transcribing}
      aria-pressed={listening}
      aria-label={label}
      title={label}
      className={cn(
        "relative grid size-24 shrink-0 place-items-center rounded-full shadow-lg transition-colors",
        listening
          ? "bg-destructive text-destructive-foreground shadow-destructive/25"
          : "bg-primary text-primary-foreground shadow-primary/25 hover:bg-primary/90",
        "disabled:cursor-not-allowed disabled:opacity-50",
      )}
    >
      {listening && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 rounded-full ring-4 ring-destructive/40 transition-transform duration-100"
          style={{
            transform: `scale(${1 + level / 250})`,
            opacity: 0.35 + level / 250,
          }}
        />
      )}
      {transcribing ? (
        <Loader2 className="size-9 animate-spin" aria-hidden="true" />
      ) : listening ? (
        <Square className="size-8" aria-hidden="true" />
      ) : (
        <Mic className="size-9" aria-hidden="true" />
      )}
    </button>
  );
}
