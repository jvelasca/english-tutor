/**
 * Cola de repaso del léxico (V3.35, Longitudinal Learning Evidence 1.0).
 *
 * Sección «Repaso de hoy» montada en el diccionario personal, junto al speaking
 * micro-drill. Consume `GET /api/learning/review` (P1-2 de la auditoría de
 * V3.34.0): cartas FSRS `lexicon` vencidas con la ACTIVIDAD recomendada por
 * hueco de competencia (reconocer → recuperar → producir). Abre el `WordDrill`
 * directamente en ese peldaño (`initialStep`), sin el refactor del componente.
 *
 * Señal, nunca puerta (D5/E3): informa de lo que toca repasar; no expone la
 * forma esperada (la sirve el peldaño correspondiente al puntuar) y no declara
 * dominio.
 */
import { useCallback, useEffect, useState } from "react";
import { motion, type Variants } from "motion/react";
import { CalendarClock, RefreshCw } from "lucide-react";
import { getReviewQueue } from "../../api/learning";
import type {
  ReviewActivity,
  ReviewQueue,
  ReviewQueueItem,
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { WordDrill } from "./wordDrill";
import { cn } from "../../lib/utils";

const item: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
};

const ACTIVITY_TONE: Record<ReviewActivity, string> = {
  recognition: "border-transparent bg-primary/15 text-primary",
  recall: "border-transparent bg-warning/15 text-warning",
  sentence: "border-transparent bg-success/15 text-success",
  // V3.39: la actividad de escritura es producción con menos andamiaje.
  write: "border-transparent bg-success/15 text-success",
  // V3.40: la transferencia es producción espontánea (máximo andamiaje cero).
  transfer: "border-transparent bg-success/15 text-success",
};

/** Actividades en las que la palabra es el RECURSO de la tarea (se muestra);
 * en Recall/Sentence es la DIANA (se oculta hasta el intento). */
function showsWord(activity: ReviewActivity): boolean {
  return (
    activity === "recognition" ||
    activity === "write" ||
    activity === "transfer"
  );
}

interface ReviewQueueSectionProps {
  userId: string;
}

/** «Repaso de hoy»: ítems léxicos vencidos según FSRS y la actividad óptima. */
export function ReviewQueueSection({ userId }: ReviewQueueSectionProps) {
  const { t } = useI18n();
  const [queue, setQueue] = useState<ReviewQueue | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [active, setActive] = useState<ReviewQueueItem | null>(null);

  const refresh = useCallback(async () => {
    try {
      setQueue(await getReviewQueue(userId));
      setLoadError(false);
    } catch {
      /* backend no disponible */
      setLoadError(true);
    }
  }, [userId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const items = queue?.items ?? [];

  return (
    <motion.section variants={item} aria-label={t("dictionary.review.title")}>
      <Card className="gap-3 p-5">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CalendarClock className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-sm font-semibold">
              {t("dictionary.review.title")}
            </h2>
            {queue && queue.due_count > 0 && (
              <Badge variant="secondary" className="shrink-0">
                {t("dictionary.review.dueCount").replace(
                  "{count}",
                  String(queue.due_count),
                )}
              </Badge>
            )}
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            aria-label={t("common.retry")}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium text-muted-foreground hover:border-primary/50 hover:text-foreground"
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
          </button>
        </div>
        <p className="text-xs text-muted-foreground">
          {t("dictionary.review.hint")}
        </p>

        {loadError && (
          <p className="text-xs text-destructive" role="alert">
            {t("dictionary.review.loadError")}
          </p>
        )}

        {!loadError && items.length === 0 && (
          <p className="text-xs text-muted-foreground">
            {t("dictionary.review.empty")}
          </p>
        )}

        {items.length > 0 && (
          <ul className="flex flex-col gap-1.5">
            {items.map((entry) => (
              <li
                key={entry.word}
                className="flex items-center gap-3 rounded-md border border-border bg-secondary/40 px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    {showsWord(entry.activity) ? (
                      <span className="truncate text-sm font-medium" lang="en">
                        {entry.word}
                      </span>
                    ) : (
                      // V3.35.1 (P1-03): en Recall/Sentence la forma esperada NO
                      // se muestra antes del intento (el drill la oculta); el
                      // objetivo es medir recuperación, no reconocimiento.
                      <span className="truncate text-sm font-medium text-muted-foreground">
                        {t(`dictionary.review.hidden.${entry.activity}`)}
                      </span>
                    )}
                    <Badge className={cn(ACTIVITY_TONE[entry.activity])}>
                      {t(`dictionary.review.activity.${entry.activity}`)}
                    </Badge>
                  </div>
                  <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                    {t(`dictionary.review.reason.${entry.reason}`)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setActive(entry)}
                  aria-pressed={active?.word === entry.word}
                  aria-label={
                    showsWord(entry.activity)
                      ? t("dictionary.review.practice").replace(
                          "{word}",
                          entry.word,
                        )
                      : t("dictionary.review.practiceHidden")
                  }
                  className="shrink-0 rounded-md border border-border bg-background px-2 py-1 text-xs font-medium transition-colors hover:border-primary/50 hover:text-foreground"
                >
                  {t("dictionary.review.overdue")}
                </button>
              </li>
            ))}
          </ul>
        )}

        {active && (
          <WordDrill
            userId={userId}
            word={active.word}
            initialStep={active.activity}
            onProduced={() => undefined}
            onClose={() => {
              setActive(null);
              void refresh();
            }}
          />
        )}
      </Card>
    </motion.section>
  );
}
