/**
 * V3.45 — Panel de un idioma del modo Conversación del Traductor.
 *
 * Cada mitad de la pantalla representa a un hablante (español / inglés): un
 * botón de micrófono grande, el estado del turno y el último par
 * (lo dicho + su traducción) con un botón para repetir el audio. El panel del
 * interlocutor puede rotarse 180° («cara a cara») para compartir el dispositivo.
 */
import { ListenButton } from "../../components/ListenButton";
import { MicUnavailableNotice } from "../../components/MicUnavailableNotice";
import { useI18n } from "../../hooks/useI18n";
import { cn } from "../../lib/utils";
import type { VoiceLanguage } from "../../api/voz";
import { BigMicButton } from "./BigMicButton";
import type { VoiceTurnController } from "./useVoiceTurn";

/** Un turno de conversación: quién habló, qué dijo y su traducción. */
export interface ConversationTurn {
  id: string;
  speaker: VoiceLanguage;
  sourceLang: VoiceLanguage;
  source: string;
  targetLang: VoiceLanguage;
  target: string;
}

type TextSize = "sm" | "base" | "lg";

interface ConversationPanelProps {
  /** Etiqueta del hablante (p. ej. «Tú · Español»). */
  label: string;
  controller: VoiceTurnController;
  /** Traducción en curso para este panel. */
  busy: boolean;
  /** El otro panel está grabando/traduciendo. */
  disabled: boolean;
  /** Último turno de este idioma (si lo hay). */
  turn: ConversationTurn | null;
  userId: string | null;
  size: TextSize;
  /** Rota el panel 180° para el modo cara a cara. */
  rotate?: boolean;
  testId?: string;
}

const SIZE_CLASSES: Record<TextSize, string> = {
  sm: "text-sm",
  base: "text-base",
  lg: "text-lg",
};

export function ConversationPanel({
  label,
  controller,
  busy,
  disabled,
  turn,
  userId,
  size,
  rotate = false,
  testId,
}: ConversationPanelProps) {
  const { t } = useI18n();
  const listening = controller.status === "listening";
  const transcribing = controller.status === "transcribing";

  const statusText = listening
    ? t("translator.conversation.listening")
    : transcribing
      ? t("translator.conversation.transcribing")
      : busy
        ? t("translator.conversation.translating")
        : t("translator.conversation.tapToSpeak");

  return (
    <section
      data-testid={testId}
      className={cn(
        "border-border bg-card/60 flex flex-col items-center gap-3 rounded-2xl border p-4",
        rotate && "rotate-180",
      )}
    >
      <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {label}
      </h3>

      <BigMicButton
        testId={testId ? `${testId}-mic` : undefined}
        status={controller.status}
        level={controller.level}
        disabled={disabled || busy}
        label={listening ? t("translator.conversation.tapToStop") : statusText}
        onToggle={controller.toggle}
      />

      <p
        role="status"
        aria-live="polite"
        className={cn(
          "text-xs",
          listening || transcribing || busy
            ? "text-primary"
            : "text-muted-foreground",
        )}
      >
        {statusText}
      </p>

      {controller.micError && (
        <MicUnavailableNotice reason={controller.micError} />
      )}
      {controller.transcribeError && (
        <p role="alert" className="text-center text-xs text-destructive">
          {t("mic.transcribeError")}
          {controller.transcribeError}
        </p>
      )}
      {controller.noSpeech && (
        <p role="status" className="text-center text-xs text-muted-foreground">
          {t("mic.noSpeech")}
        </p>
      )}

      {turn ? (
        <div className="flex w-full flex-col gap-2 border-t border-border pt-3">
          <p
            lang={turn.sourceLang}
            className={cn("text-muted-foreground", SIZE_CLASSES[size])}
          >
            {turn.source}
          </p>
          <div className="flex items-start justify-between gap-2">
            <p
              lang={turn.targetLang}
              className={cn("font-medium text-foreground", SIZE_CLASSES[size])}
            >
              {turn.target}
            </p>
            <ListenButton
              text={turn.target}
              label={t("translator.conversation.replay")}
              language={turn.targetLang}
              userId={userId}
              className="size-10"
            />
          </div>
        </div>
      ) : (
        <p className="text-center text-xs text-muted-foreground">
          {t("translator.conversation.panelEmpty")}
        </p>
      )}
    </section>
  );
}
