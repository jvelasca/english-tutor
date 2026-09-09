// Transcripción dinámica con sync grueso (V3.28, Bloque D).
//
// Muestra el transcript por frases según el estado de revelado del micro-flujo:
// - `full` → todas las frases, resaltando la frase activa según `currentTime`.
// - `partial` → solo la frase/segmento permitido por `transcript_state_inicial`.
// - `hidden` → no renderiza nada.
//
// Los timings son heurísticos (reparto proporcional de `duration` en el backend,
// `sync: "coarse_heuristic"`): este componente nunca los presenta como alineación
// acústica (el karaoke palabra a palabra queda en Fase 3 / V3.29).
import { useI18n } from "../../hooks/useI18n";
import { cn } from "../../lib/utils";
import { Card } from "../../components/ui/card";
import {
  activeSentenceIndex,
  revealSentenceIndexes,
  type SentenceTiming,
  type TranscriptState,
} from "./microFlow";

interface CoarseTranscriptProps {
  timings: SentenceTiming[];
  state: TranscriptState;
  currentTime: number;
}

export function CoarseTranscript({
  timings,
  state,
  currentTime,
}: CoarseTranscriptProps) {
  const { t } = useI18n();
  const active = activeSentenceIndex(timings, currentTime);
  const visible = new Set(revealSentenceIndexes(state, timings, active));
  const phrases = timings.filter((segment) => visible.has(segment.index));
  if (phrases.length === 0) return null;
  return (
    <Card className="gap-3 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {state === "partial"
            ? t("listening.coarseTranscript.partialTitle")
            : t("listening.coarseTranscript.title")}
        </p>
        <span className="text-[11px] text-muted-foreground">
          {t("listening.coarseTranscript.syncTag")}
        </span>
      </div>
      <div
        lang="en"
        className="flex flex-wrap gap-1 text-sm leading-relaxed text-foreground"
      >
        {phrases.map((segment) => (
          <span
            key={`${segment.index}:${segment.start}`}
            className={cn(
              "rounded-md px-1 py-0.5 transition-colors",
              segment.index === active
                ? "bg-primary/15 font-medium ring-1 ring-primary/30"
                : "text-muted-foreground",
            )}
          >
            {segment.text}
          </span>
        ))}
      </div>
      <p className="text-xs italic text-muted-foreground">
        {t("listening.coarseTranscript.syncHint")}
      </p>
    </Card>
  );
}
