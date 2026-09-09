// Transcripción karaoke palabra a palabra (V3.29, Fase 3).
//
// Muestra el transcript por palabras según el estado de revelado del
// micro-flujo, resaltando la palabra activa mientras suena el audio y
// permitiendo saltar a cualquier palabra con un toque (`onSeekToWord`).
//
// Los tiempos vienen del sidecar `word_alignment_proxy` del backend (señal ASR:
// `sync: asr_word_proxy`), NO son verdad acústica; slow/fast se escalan en el
// cliente por `activeVariantFactor`. Cuando el backend no sirve `wordTimings`
// (sin sidecar o cobertura baja) este componente devuelve `null` y la UI sigue
// usando `CoarseTranscript` (sync de frase heurístico).
import { useI18n } from "../../hooks/useI18n";
import { cn } from "../../lib/utils";
import { Card } from "../../components/ui/card";
import type { ListeningWordTiming } from "../../types/api";
import {
  activeSentenceIndex,
  activeWordIndex,
  revealSentenceIndexes,
  scaleWordTimings,
  type SentenceTiming,
  type TranscriptState,
} from "./microFlow";

interface KaraokeTranscriptProps {
  /** Palabras servidas por el backend (variante `normal` de la voz default). */
  wordTimings: ListeningWordTiming[];
  /** Frases de `sentenceTimings` para revelar por frase y agrupar. */
  sentenceTimings: SentenceTiming[];
  state: TranscriptState;
  currentTime: number;
  /** Factor de tiempo de la variante activa (slow/fast) respecto a `normal`. */
  activeVariantFactor: number;
  /** Salta la reproducción al instante `t` (s) — seek del AudioController. */
  onSeekToWord: (start: number) => void;
}

export function KaraokeTranscript({
  wordTimings,
  sentenceTimings,
  state,
  currentTime,
  activeVariantFactor,
  onSeekToWord,
}: KaraokeTranscriptProps) {
  const { t } = useI18n();
  if (wordTimings.length === 0) return null;

  const words = scaleWordTimings(wordTimings, activeVariantFactor);
  const activeSentence = activeSentenceIndex(sentenceTimings, currentTime);
  const activeWord = activeWordIndex(words, currentTime);

  let visible = words;
  if (sentenceTimings.length > 0) {
    const revealed = new Set(
      revealSentenceIndexes(state, sentenceTimings, activeSentence),
    );
    visible = words.filter((word) => revealed.has(word.sentence));
  } else if (state !== "full") {
    // Sin frases (`duration` ausente) el karaoke degrada a una sola línea
    // continua solo cuando el revelado es completo; en `hidden`/`partial` sin
    // fronteras de frase no hay nada revelable.
    return null;
  }
  if (visible.length === 0) return null;

  return (
    <Card className="gap-3 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {state === "partial"
            ? t("listening.karaokeTranscript.partialTitle")
            : t("listening.karaokeTranscript.title")}
        </p>
        <span className="text-[11px] text-muted-foreground">
          {t("listening.karaokeTranscript.syncTag")}
        </span>
      </div>
      <div
        lang="en"
        className="flex flex-wrap items-baseline gap-x-1 gap-y-0.5 text-sm leading-relaxed text-foreground"
      >
        {visible.map((word) => {
          const isActive = word.index === activeWord;
          return (
            <button
              key={`${word.index}:${word.start}`}
              type="button"
              onClick={() => onSeekToWord(word.start)}
              className={cn(
                "cursor-pointer rounded-md px-0.5 py-0.5 text-left transition-colors",
                "hover:bg-primary/10",
                isActive && "bg-primary/15 font-medium ring-1 ring-primary/30",
              )}
              title={t("listening.karaokeTranscript.seekWord")}
            >
              {word.text}
            </button>
          );
        })}
      </div>
      <p className="text-xs italic text-muted-foreground">
        {t("listening.karaokeTranscript.syncHint")}
      </p>
    </Card>
  );
}
