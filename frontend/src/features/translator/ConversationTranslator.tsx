/**
 * V3.45 — Modo Conversación del Traductor de viaje.
 *
 * Dos paneles (español / inglés) con un botón grande por hablante. Al hablar en
 * un panel se transcribe (Whisper), se traduce y, si el auto-play está activo,
 * se reproduce en voz alta en el idioma del otro panel; el turno se añade al
 * historial. Incluye «cara a cara» (rota el panel del interlocutor para
 * compartir el dispositivo) y control del tamaño del texto, siguiendo el patrón
 * de las apps punteras de traducción de viaje.
 *
 * Es una utilidad auxiliar: NO registra evidencia ni intentos de aprendizaje.
 */
import { useEffect, useState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";
import { downloadVoice, getVoices } from "../../api/voices";
import { translateText } from "../../api/translate";
import { speak, type VoiceLanguage } from "../../api/voz";
import { useI18n } from "../../hooks/useI18n";
import { cn } from "../../lib/utils";
import {
  ConversationPanel,
  type ConversationTurn,
} from "./ConversationPanel";
import { useVoiceTurn } from "./useVoiceTurn";

/** Turnos de conversación recordados entre sesiones. */
export const CONVERSATION_STORAGE_KEY = "english-tutor.translator-conversation";
const CONVERSATION_LIMIT = 12;

type TextSize = "sm" | "base" | "lg";
const TEXT_SIZES: TextSize[] = ["sm", "base", "lg"];

type VoiceState = "idle" | "preparing" | "error";

function isTurn(value: unknown): value is ConversationTurn {
  if (typeof value !== "object" || value === null) return false;
  const turn = value as Record<string, unknown>;
  return (
    typeof turn.id === "string" &&
    (turn.speaker === "es" || turn.speaker === "en") &&
    (turn.sourceLang === "es" || turn.sourceLang === "en") &&
    typeof turn.source === "string" &&
    (turn.targetLang === "es" || turn.targetLang === "en") &&
    typeof turn.target === "string"
  );
}

function readTurns(): ConversationTurn[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(CONVERSATION_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isTurn).slice(0, CONVERSATION_LIMIT);
  } catch {
    return [];
  }
}

interface ConversationTranslatorProps {
  userId: string | null;
}

export function ConversationTranslator({ userId }: ConversationTranslatorProps) {
  const { t } = useI18n();
  const [turns, setTurns] = useState<ConversationTurn[]>(readTurns);
  const [latest, setLatest] = useState<Partial<Record<VoiceLanguage, string>>>(
    {},
  );
  const [autoPlay, setAutoPlay] = useState(true);
  const [faceToFace, setFaceToFace] = useState(false);
  const [size, setSize] = useState<TextSize>("base");
  const [busyLang, setBusyLang] = useState<VoiceLanguage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(
        CONVERSATION_STORAGE_KEY,
        JSON.stringify(turns),
      );
    } catch {
      /* almacenamiento no disponible: el historial es best-effort */
    }
  }, [turns]);

  // V3.45: si falta la voz española, se descarga en segundo plano la primera
  // vez (una sola vez por montaje); si falla, se avisa sin bloquear el uso.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await getVoices(userId);
        const esDefault = data.defaults?.es;
        if (!esDefault) return;
        const installed = data.voices.some((v) => v.id.startsWith("es_"));
        if (installed) return;
        setVoiceState("preparing");
        await downloadVoice(esDefault);
        if (!cancelled) setVoiceState("idle");
      } catch {
        if (!cancelled) setVoiceState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  async function handleTurn(speaker: VoiceLanguage, text: string) {
    const targetLang: VoiceLanguage = speaker === "es" ? "en" : "es";
    const direction = speaker === "es" ? "es-en" : "en-es";
    setBusyLang(speaker);
    setError(null);
    try {
      const translation = await translateText(text, direction);
      const turn: ConversationTurn = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        speaker,
        sourceLang: speaker,
        source: text,
        targetLang,
        target: translation,
      };
      setTurns((prev) => [turn, ...prev].slice(0, CONVERSATION_LIMIT));
      setLatest((prev) => ({ ...prev, [speaker]: turn.id }));
      if (autoPlay) {
        void speak(translation, userId, targetLang).catch(() => {
          /* TTS no disponible: el turno ya está en pantalla */
        });
      }
    } catch (e) {
      setError(`${t("translator.error")}${(e as Error).message}`);
    } finally {
      setBusyLang(null);
    }
  }

  const esTurn = useVoiceTurn("es", (text) => void handleTurn("es", text));
  const enTurn = useVoiceTurn("en", (text) => void handleTurn("en", text));

  const esActive = esTurn.status !== "idle";
  const enActive = enTurn.status !== "idle";

  const turnFor = (lang: VoiceLanguage): ConversationTurn | null => {
    const id = latest[lang];
    if (!id) return null;
    return turns.find((turn) => turn.id === id) ?? null;
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <label className="flex items-center gap-2 text-xs font-semibold text-foreground">
          <input
            type="checkbox"
            checked={autoPlay}
            onChange={(e) => setAutoPlay(e.target.checked)}
            className="size-4 accent-[var(--color-accent)]"
          />
          {t("translator.conversation.autoPlay")}
        </label>
        <label className="flex items-center gap-2 text-xs font-semibold text-foreground">
          <input
            type="checkbox"
            checked={faceToFace}
            onChange={(e) => setFaceToFace(e.target.checked)}
            className="size-4 accent-[var(--color-accent)]"
          />
          {t("translator.conversation.faceToFace")}
        </label>
        <div
          role="group"
          aria-label={t("translator.conversation.textSize")}
          className="bg-secondary flex items-center gap-1 rounded-md p-1"
        >
          {TEXT_SIZES.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={size === value}
              onClick={() => setSize(value)}
              className={cn(
                "grid size-7 place-items-center rounded text-xs font-semibold transition-colors",
                size === value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
                value === "sm" && "text-[10px]",
                value === "lg" && "text-sm",
              )}
            >
              A
            </button>
          ))}
        </div>
      </div>

      {voiceState === "preparing" && (
        <p
          role="status"
          className="flex items-center gap-2 text-xs text-muted-foreground"
        >
          <RefreshCw className="size-3.5 animate-spin" aria-hidden="true" />
          {t("translator.conversation.voicePreparing")}
        </p>
      )}
      {voiceState === "error" && (
        <p role="status" className="text-xs text-destructive">
          {t("translator.conversation.voiceError")}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <ConversationPanel
          testId="conversation-panel-es"
          label={t("translator.conversation.youLabel")}
          controller={esTurn}
          busy={busyLang === "es"}
          disabled={enActive}
          turn={turnFor("es")}
          userId={userId}
          size={size}
        />
        <ConversationPanel
          testId="conversation-panel-en"
          label={t("translator.conversation.themLabel")}
          controller={enTurn}
          busy={busyLang === "en"}
          disabled={esActive}
          turn={turnFor("en")}
          userId={userId}
          size={size}
          rotate={faceToFace}
        />
      </div>

      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {t("translator.conversation.turns")}
          </h3>
          {turns.length > 0 && (
            <button
              type="button"
              onClick={() => setTurns([])}
              aria-label={t("translator.conversation.clear")}
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs font-semibold"
            >
              <Trash2 className="size-3.5" aria-hidden="true" />
              {t("translator.conversation.clear")}
            </button>
          )}
        </div>
        {turns.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("translator.conversation.empty")}
          </p>
        ) : (
          <ul
            data-testid="conversation-turns"
            className="flex flex-col gap-1.5"
          >
            {turns.map((turn) => (
              <li
                key={turn.id}
                className="border-border bg-card flex flex-col gap-0.5 rounded-lg border px-3 py-2"
              >
                <span className="text-[10px] font-semibold tracking-wide text-muted-foreground uppercase">
                  {turn.speaker === "es"
                    ? t("translator.conversation.youLabel")
                    : t("translator.conversation.themLabel")}
                </span>
                <span
                  lang={turn.sourceLang}
                  className="text-xs text-muted-foreground"
                >
                  {turn.source}
                </span>
                <span lang={turn.targetLang} className="text-sm">
                  {turn.target}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
