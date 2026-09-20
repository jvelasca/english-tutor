import { useState } from "react";
import { Loader2, Square, Volume2 } from "lucide-react";
import { stopSpeaking, type VoiceLanguage } from "../api/voz";
import { useI18n } from "../hooks/useI18n";
import { useVoiceChoice, type VoiceAccent } from "../hooks/useVoiceChoice";
import { speakWithVoice } from "../hooks/useVoiceDownload";
import { cn } from "../lib/utils";
import { buildReplayText, voiceAccentKey, voiceLocale } from "../utils/voices";

interface ItemReplayButtonProps {
  /** Pregunta del ítem (lo que se lee en pantalla). */
  prompt: string;
  /**
   * **Texto** del ítem: lo que suena en el audio. Es la primera pieza de la
   * lectura «completa» (`replay_scope: "item"`); en las pantallas que solo
   * tienen una frase se omite y la pregunta hace de texto.
   */
  script?: string;
  /** Opciones del ítem, en orden; se leen con su letra (A, B, C, D). */
  options?: readonly string[];
  /**
   * Índice de la respuesta correcta. Es la pieza que cierra toda lectura: sin
   * ella el altavoz repite el ítem pero no confirma la clave.
   */
  correctIndex?: number | null;
  /** Perfil activo (para resolver las voces A/B del store). */
  userId?: string | null;
  /** Idioma de la síntesis; inglés por defecto. */
  language?: VoiceLanguage;
  className?: string;
}

/**
 * Altavoz de **repetición** con dos acentos (V3.75.5).
 *
 * Tras responder, el altavoz de antes releía solo el script del ítem y siempre
 * con la misma voz. Ahora lee el ítem **compuesto** (`buildReplayText`) y ofrece
 * un botón por acento disponible: A (la voz del perfil) y B (el segundo acento).
 * Si solo hay una voz instalada se muestra A y nada más: nunca un botón que no
 * puede sonar.
 *
 * V3.75.6: la lectura puede durar, así que mientras suena aparece un **STOP**
 * (`stopSpeaking`) que la corta sin salir de la pantalla; y lo que se lee es la
 * preferencia del perfil (`replay_scope`): el ítem completo, el ítem más las
 * opciones o solo la pregunta con la respuesta correcta.
 */
export function ItemReplayButton({
  prompt,
  script,
  options = [],
  correctIndex = null,
  userId,
  language = "en",
  className,
}: ItemReplayButtonProps) {
  const { t } = useI18n();
  const choice = useVoiceChoice(userId ?? null);
  const [busy, setBusy] = useState<VoiceAccent | null>(null);

  const text = buildReplayText(prompt, options, {
    scope: choice.replayScope,
    correctIndex,
    script,
  });
  if (!text) return null;

  const accents: VoiceAccent[] = choice.alt ? ["a", "b"] : ["a"];
  // Un ítem con opciones es un ítem con pregunta, no una frase suelta: la
  // etiqueta del grupo lo dice, aunque el perfil haya pedido la lectura corta.
  const hasOptions = options.length > 0;

  function accentWord(accent: VoiceAccent): string {
    const voiceId = choice.voiceFor(accent);
    const key = voiceAccentKey(voiceId);
    if (!key) return "";
    const label = t(`voice.accent.${key}`);
    return label === `voice.accent.${key}` ? voiceLocale(voiceId) : label;
  }

  async function play(accent: VoiceAccent) {
    if (busy) return;
    setBusy(accent);
    try {
      const voice = choice.voiceFor(accent);
      if (voice) await speakWithVoice(text, userId, language, { voice });
      else await speakWithVoice(text, userId, language);
    } catch {
      /* TTS no disponible: se ignora, nunca bloquea el resultado */
    } finally {
      setBusy(null);
    }
  }

  /** STOP: corta la locución en curso; la espera de `play` resuelve y apaga el spinner. */
  function stop() {
    stopSpeaking();
  }

  return (
    <div
      className={cn("flex shrink-0 items-center gap-1.5", className)}
      role="group"
      aria-label={hasOptions ? t("voice.replayItem") : t("voice.replayPhrase")}
    >
      {accents.map((accent) => {
        const word = accentWord(accent);
        const title = t(accent === "b" ? "voice.replayItemB" : "voice.replayItemA");
        return (
          <button
            key={accent}
            type="button"
            onClick={() => void play(accent)}
            disabled={busy !== null}
            aria-busy={busy === accent}
            aria-label={word ? `${title} · ${word}` : title}
            title={word ? `${title} · ${word}` : title}
            className={cn(
              "flex min-h-8 items-center gap-1 rounded-full border border-border bg-secondary px-2 text-[11px] font-semibold text-secondary-foreground transition-colors hover:border-primary/50 hover:text-foreground",
              "disabled:cursor-not-allowed disabled:opacity-60",
            )}
          >
            {busy === accent ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <Volume2 className="size-3.5" aria-hidden="true" />
            )}
            <span aria-hidden="true">{t(accent === "b" ? "voice.accent.b" : "voice.accent.a")}</span>
            {word && (
              <span
                className="hidden font-normal text-muted-foreground sm:inline"
                aria-hidden="true"
              >
                {word}
              </span>
            )}
          </button>
        );
      })}
      {/* V3.75.6: la lectura puede durar; el STOP solo existe mientras suena y
          corta sin desmontar el resultado. */}
      {busy !== null && (
        <button
          type="button"
          onClick={stop}
          aria-label={t("voice.stop")}
          title={t("voice.stop")}
          className="grid size-8 shrink-0 place-items-center rounded-full border border-destructive/40 bg-destructive/10 text-destructive transition-colors hover:bg-destructive/20"
        >
          <Square className="size-3 fill-current" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
