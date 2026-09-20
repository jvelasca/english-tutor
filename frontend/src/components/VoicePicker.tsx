import { useState } from "react";
import { Check, Loader2, Volume2 } from "lucide-react";
import { useI18n } from "../hooks/useI18n";
import {
  useVoiceChoice,
  type VoiceAccent,
} from "../hooks/useVoiceChoice";
import { cn } from "../lib/utils";
import {
  voiceAccentKey,
  voiceDisplayName,
  voiceLocale,
  type ReplayScope,
} from "../utils/voices";

/**
 * Las tres lecturas, en el orden en que se ofrecen (la primera es el defecto).
 *
 * Viven juntas a propósito: el tipo `ReplayScope` y estas tablas son el único
 * sitio donde se enumera lo que el alumno puede elegir, así que añadir una
 * lectura nueva —o cambiar su etiqueta— es una edición, no una cacería de
 * literales por el JSX.
 */
const REPLAY_SCOPES: readonly ReplayScope[] = ["item", "withOptions", "correct"];

const REPLAY_SCOPE_LABELS: Record<ReplayScope, string> = {
  item: "voice.replayScopeItem",
  withOptions: "voice.replayScopeWithOptions",
  correct: "voice.replayScopeCorrect",
};

/** Clave del «recibo» que describe la lectura activa (las piezas que la forman). */
const REPLAY_SCOPE_RECEIPTS: Record<ReplayScope, string> = {
  item: "voice.replayScopeItemHint",
  withOptions: "voice.replayScopeWithOptionsHint",
  correct: "voice.replayScopeCorrectHint",
};

interface VoicePickerProps {
  /** Perfil activo; sin perfil la elección no se persiste (solo en memoria). */
  userId: string | null;
  className?: string;
  /**
   * Si se pasa, se añaden los chips «Probar A» / «Probar B»: el llamador decide
   * QUÉ suena con esa voz (en listening, el audio del ítem; en las rutas, el
   * enunciado). Sin `onPreview` el selector solo configura, no prueba.
   */
  onPreview?: (accent: VoiceAccent) => void | Promise<void>;
  /** Nota adicional del llamador (p. ej. la honestidad del acento sintético). */
  note?: string;
}

/**
 * Selector de las dos voces del perfil (V3.75.5).
 *
 * Antes el «...» de la tarjeta de audio solo **mostraba** «Voz sintética local
 * (TTS)» + el nombre de la voz: no había camino para cambiarla desde la
 * práctica. Aquí se elige la voz A (la del perfil, `tts_voice`) y la voz B
 * (segundo acento, `tts_voice_alt`), con las voces **instaladas** del idioma de
 * la A —ofrecer otro idioma sería leer el ítem en otra lengua, no otro acento—.
 *
 * El estado vive en `useVoiceChoice` (store de módulo), así que este control y
 * los altavoces de la misma pantalla siempre ven la misma pareja de voces.
 *
 * V3.75.6: añade la preferencia de **lectura al repetir** (`replay_scope`): el
 * ítem completo (texto + pregunta + respuesta correcta, por defecto), el ítem más
 * las opciones o solo la pregunta con la respuesta correcta. Vive aquí porque el
 * «...» es el mismo en Listening y en las rutas de quiz, y no depende del
 * catálogo de voces.
 */
export function VoicePicker({
  userId,
  className,
  onPreview,
  note,
}: VoicePickerProps) {
  const { t } = useI18n();
  const choice = useVoiceChoice(userId);
  const [previewing, setPreviewing] = useState<VoiceAccent | null>(null);

  const accentOf = (voiceId: string): string => {
    const key = voiceAccentKey(voiceId);
    if (!key) return "";
    const label = t(`voice.accent.${key}`);
    // Una locale sin traducción se muestra tal cual (`en_AU`) en vez de la clave.
    return label === `voice.accent.${key}` ? voiceLocale(voiceId) : label;
  };

  async function preview(accent: VoiceAccent) {
    if (!onPreview || previewing) return;
    setPreviewing(accent);
    try {
      await onPreview(accent);
    } finally {
      setPreviewing(null);
    }
  }

  const voiceLoading = choice.status === "loading" || choice.status === "idle";
  const voiceMissing = choice.status === "error" || choice.voices.length === 0;
  const altOptions = choice.voices.filter((voice) => voice.id !== choice.primary);

  const row = (
    titleKey: string,
    voices: typeof choice.voices,
    selected: string,
    onSelect: (voiceId: string) => void,
    disabled: boolean,
  ) => (
    <div className="flex flex-col gap-2">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {t(titleKey)}
      </span>
      <div
        className="flex flex-wrap gap-2"
        role="radiogroup"
        aria-label={t(titleKey)}
      >
        {voices.map((voice) => {
          const active = voice.id === selected;
          const accent = accentOf(voice.id);
          return (
            <button
              key={voice.id}
              type="button"
              role="radio"
              aria-checked={active}
              disabled={disabled}
              onClick={() => onSelect(voice.id)}
              className={cn(
                "flex min-h-9 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition-colors",
                active
                  ? "border-primary/60 bg-primary/10 text-foreground"
                  : "border-border bg-secondary text-secondary-foreground hover:border-primary/40",
                "disabled:cursor-not-allowed disabled:opacity-60",
              )}
              title={voice.id}
            >
              <span
                className={cn(
                  "grid size-3.5 shrink-0 place-items-center rounded-full border",
                  active ? "border-primary" : "border-border",
                )}
                aria-hidden="true"
              >
                {active && <Check className="size-2.5" />}
              </span>
              <span className="truncate">{voiceDisplayName(voice)}</span>
              {accent && (
                <span className="text-[10px] font-normal text-muted-foreground">
                  {accent}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );

  const voicesBlock = voiceLoading ? (
    <p className="flex items-center gap-2 text-xs text-muted-foreground">
      <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
      {t("common.loading")}
    </p>
  ) : voiceMissing ? (
    <p className="text-xs text-muted-foreground">{t("voice.error")}</p>
  ) : (
    <>
      {row(
        "voice.primary",
        choice.voices,
        choice.primary,
        (voiceId) => void choice.setPrimary(voiceId),
        false,
      )}

      <div className="border-t border-border/60" aria-hidden="true" />

      {altOptions.length > 0 ? (
        row(
          "voice.secondary",
          altOptions,
          choice.alt,
          (voiceId) => void choice.setAlt(voiceId),
          false,
        )
      ) : (
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("voice.single")}
        </p>
      )}

      {onPreview && choice.alt && (
        <div className="flex flex-wrap gap-2">
          {(["a", "b"] as VoiceAccent[]).map((accent) => (
            <button
              key={accent}
              type="button"
              disabled={previewing !== null}
              onClick={() => void preview(accent)}
              aria-busy={previewing === accent}
              className={cn(
                "flex min-h-9 items-center gap-1.5 rounded-full border border-border bg-card px-3 text-xs font-medium text-foreground transition-colors hover:border-primary/50",
                "disabled:cursor-not-allowed disabled:opacity-60",
              )}
            >
              {previewing === accent ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <Volume2 className="size-3.5" aria-hidden="true" />
              )}
              {previewing === accent
                ? t("voice.previewing")
                : t(accent === "a" ? "voice.tryA" : "voice.tryB")}
            </button>
          ))}
        </div>
      )}

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        {t("voice.pickerHint")}
      </p>
    </>
  );

  return (
    <div className={cn("flex flex-col gap-3.5", className)}>
      {voicesBlock}

      {/* V3.75.6: la lectura de después de responder se compone de cuatro piezas
          (texto del ítem, pregunta, opciones y respuesta correcta). El alumno
          elige la composición; no depende del catálogo de voces, así que sigue
          disponible aunque este falle. */}
      <div className="border-t border-border/60" aria-hidden="true" />

      <div className="flex flex-col gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          {t("voice.replayScope")}
        </span>
        <div
          className="flex flex-wrap gap-2"
          role="radiogroup"
          aria-label={t("voice.replayScope")}
        >
          {REPLAY_SCOPES.map((scope) => {
            const active = choice.replayScope === scope;
            return (
              <button
                key={scope}
                type="button"
                role="radio"
                aria-checked={active}
                disabled={voiceLoading}
                onClick={() => void choice.setReplayScope(scope)}
                className={cn(
                  "flex min-h-9 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition-colors",
                  active
                    ? "border-primary/60 bg-primary/10 text-foreground"
                    : "border-border bg-secondary text-secondary-foreground hover:border-primary/40",
                  "disabled:cursor-not-allowed disabled:opacity-60",
                )}
              >
                <span
                  className={cn(
                    "grid size-3.5 shrink-0 place-items-center rounded-full border",
                    active ? "border-primary" : "border-border",
                  )}
                  aria-hidden="true"
                >
                  {active && <Check className="size-2.5" />}
                </span>
                <span>{t(REPLAY_SCOPE_LABELS[scope])}</span>
              </button>
            );
          })}
        </div>
        {/* Recibo de la lectura elegida: las tres opciones se llaman igual de bien
            («el ítem…») y la diferencia real está en las piezas que entran, así
            que en vez de explicar las tres se describe la activa. */}
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t(REPLAY_SCOPE_RECEIPTS[choice.replayScope])}
        </p>
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("voice.replayScopeHint")}
        </p>
      </div>

      {note && (
        <p className="text-[11px] leading-relaxed text-muted-foreground">{note}</p>
      )}
    </div>
  );
}
