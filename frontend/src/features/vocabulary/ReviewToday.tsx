/**
 * «Repasar hoy» (V3.85.0), heredero de la cola de repaso de V3.35.
 *
 * Antes era una LISTA de hasta 20 filas con cuatro capas de texto por fila
 * (motivo, `why`, señales de la decisión y badges) y un único botón por fila
 * cuya etiqueta era «vencida». El resultado, en móvil, era una lista larga que
 * no parecía accionable —el botón se leía como un estado, no como una acción— y
 * que no aportaba nada que no dijera ya la cifra del día.
 *
 * V3.85.0 lo convierte en **resumen + una sola acción que encadena la cola**:
 * «Repasar ahora (N)» recorre los ítems vencidos uno detrás de otro, montando el
 * mismo `WordDrill` de siempre en el peldaño que el planificador recomienda
 * (`initialStep`). La traza declarada (motivo, `why` y señales de la decisión)
 * NO se pierde: deja de repetirse 20 veces y pasa a mostrarse **una sola vez**,
 * para la palabra que se está trabajando, que es cuando significa algo.
 *
 * Señal, nunca puerta (D5/E3): informa de lo que toca repasar; no expone la
 * forma esperada (la sirve el peldaño correspondiente al puntuar) y no declara
 * dominio. Sin backend nuevo: mismo `GET /api/learning/review`.
 */
import { useCallback, useEffect, useState } from "react";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { WhyThisActivity } from "../../components/WhyThisActivity";
import { useI18n } from "../../hooks/useI18n";
import { getReviewQueue } from "../../api/learning";
import { asArray, normalizeReviewQueue } from "../../api/normalize";
import type {
  ReviewActivity,
  ReviewDecision,
  ReviewQueueItem,
} from "../../types/api";
import { cn } from "../../lib/utils";
import { WordDrill } from "./wordDrill";

/**
 * Cuántos ítems se piden. El endpoint admite hasta 50: se pide el máximo para
 * que una sesión encadenada cubra el día entero de una tirada.
 */
const REVIEW_LIMIT = 50;

const ACTIVITY_TONE: Record<ReviewActivity, string> = {
  recognition: "border-transparent bg-primary/15 text-primary",
  recall: "border-transparent bg-warning/15 text-warning",
  sentence: "border-transparent bg-success/15 text-success",
  // V3.39: la actividad de escritura es producción con menos andamiaje.
  write: "border-transparent bg-success/15 text-success",
  // V3.40: la transferencia es producción espontánea (máximo andamiaje cero).
  transfer: "border-transparent bg-success/15 text-success",
};

// V3.49 (Transfer Evidence 3.0): tono de la etiqueta de CONFIANZA del eje de
// transferencia. Solo se muestra con evidencia (`level` distinto de `none`).
const CONFIDENCE_TONE: Record<string, string> = {
  low: "border-transparent bg-secondary text-muted-foreground",
  medium: "border-transparent bg-primary/15 text-primary",
  high: "border-transparent bg-success/15 text-success",
};

/**
 * V3.64 (Planner 3.0): motivos DECLARADOS de la decisión, en el idioma de la
 * interfaz. Son bandas y hechos del estado proyectado (`Decision Projection`),
 * nunca probabilidades: la traza completa vive en `GET /api/learning/review` y
 * aquí solo se muestra el porqué del encaje, sin revelar la forma esperada.
 */
function decisionSignals(
  decision: ReviewDecision,
  t: (key: string) => string,
): string[] {
  const drivers = decision.drivers ?? {};
  const labels: string[] = [];
  if (decision.difficulty_fit !== "unknown") {
    labels.push(t(`dictionary.review.decision.fit.${decision.difficulty_fit}`));
  }
  // Sin medida declarada el estado calla: no se inventa ningún motivo (P2-04).
  if (!drivers.measured) return labels;
  if (drivers.gap) {
    labels.push(t(`dictionary.review.decision.gap.${drivers.gap}`));
  }
  if (drivers.transfer_gap) {
    labels.push(t(`dictionary.review.decision.transfer.${drivers.transfer_gap}`));
  }
  if (drivers.retention_due) {
    labels.push(t("dictionary.review.decision.retention"));
  }
  if (drivers.effort && drivers.effort !== "none") {
    labels.push(t(`dictionary.review.decision.effort.${drivers.effort}`));
  }
  if (drivers.assessment_confidence) {
    labels.push(
      t(`dictionary.review.decision.confidence.${drivers.assessment_confidence}`),
    );
  }
  return labels;
}

/** V3.64: línea de motivos declarados. Nada si el estado no declara nada. */
function DecisionSignals({
  decision,
  t,
}: {
  decision: ReviewDecision;
  t: (key: string) => string;
}) {
  const signals = decisionSignals(decision, t);
  if (signals.length === 0) return null;
  return (
    <p
      className="text-[11px] text-muted-foreground/80"
      title={t("dictionary.review.decision.scope")}
    >
      {signals.join(" · ")}
    </p>
  );
}

/**
 * Carga la cola de repaso del día. Expone el recuento para que el bloque de
 * estudio pueda rotular su acción («Repasar ahora (N)») y los ítems que la
 * sesión encadenada va a recorrer.
 */
export function useReviewToday(userId: string) {
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [dueCount, setDueCount] = useState(0);
  const [loadError, setLoadError] = useState(false);

  const refresh = useCallback(async () => {
    try {
      // V3.77.2: se normaliza en la frontera del estado. El `queue?.items ?? []`
      // de antes no protegía contra un `items` no-array pero *truthy*.
      const queue = normalizeReviewQueue(
        await getReviewQueue(userId, REVIEW_LIMIT),
      );
      setItems(asArray<ReviewQueueItem>(queue.items));
      setDueCount(Math.max(0, queue.due_count || 0));
      setLoadError(false);
    } catch {
      /* backend no disponible */
      setLoadError(true);
    }
  }, [userId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { items, dueCount, loadError, refresh };
}

interface ReviewSessionProps {
  userId: string;
  /** Ítems a recorrer, en el orden que sirvió la cola (urgencia). */
  items: ReviewQueueItem[];
  /** Se llama al terminar la cola o al cerrar el drill. */
  onExit: () => void;
}

/**
 * Sesión de repaso ENCADENADA: una palabra detrás de otra.
 *
 * No auto-avanza al superar el peldaño: `WordDrill` dispara `onProduced` en
 * cuanto el intento pasa, y desmontarlo en ese instante ocultaría el feedback de
 * lo que el alumno acaba de escribir. Se deja el drill montado y se ofrece
 * «Siguiente palabra», que es además cuando el repaso deja de parecer un
 * formulario y pasa a ser algo que se maneja.
 */
export function ReviewSession({ userId, items, onExit }: ReviewSessionProps) {
  const { t } = useI18n();
  const [index, setIndex] = useState(0);
  const [produced, setProduced] = useState(false);

  const current: ReviewQueueItem | undefined = items[index];

  // Cola agotada (o cerrada): se sale y el contenedor refresca el recuento.
  useEffect(() => {
    if (index >= items.length) onExit();
  }, [index, items.length, onExit]);

  // Cada palabra arranca sin el «siguiente» de la anterior.
  useEffect(() => {
    setProduced(false);
  }, [index]);

  if (!current) return null;

  const isLast = index === items.length - 1;

  return (
    <div className="flex min-w-0 flex-col gap-3">
      {/* Sin botón «Cerrar» propio: el drill ya trae el suyo y salir de él sale
          de la sesión (`onClose={onExit}`). Dos controles idénticos en la misma
          tarjeta era justo el ruido que esta release retira. */}
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold">{t("dictionary.review.title")}</h2>
        <span className="text-xs tabular-nums text-muted-foreground">
          {t("dictionary.review.sessionProgress")
            .replace("{index}", String(index + 1))
            .replace("{total}", String(items.length))}
        </span>
        <Badge className={cn(ACTIVITY_TONE[current.activity])}>
          {t(`dictionary.review.activity.${current.activity}`)}
        </Badge>
        {current.transfer_confidence &&
          current.transfer_confidence.level !== "none" && (
            <Badge
              className={cn(CONFIDENCE_TONE[current.transfer_confidence.level])}
              title={t("dictionary.review.transfer.scope")}
              aria-label={t("dictionary.review.transfer.scope")}
            >
              {t(
                `dictionary.review.transfer.level.${current.transfer_confidence.level}`,
              )}
            </Badge>
          )}
      </div>

      {/* La traza declarada de esta palabra: por qué toca y qué la motiva. Antes
          se repetía en cada fila de la lista; ahora se dice una sola vez, para
          lo que se está trabajando. */}
      <div className="flex min-w-0 flex-col gap-0.5">
        <p className="text-xs text-muted-foreground">
          {t(`dictionary.review.reason.${current.reason}`)}
        </p>
        <WhyThisActivity variant="compact" why={current.why} />
        {current.decision && (
          <DecisionSignals decision={current.decision} t={t} />
        )}
      </div>

      <WordDrill
        userId={userId}
        word={current.word}
        initialStep={current.activity}
        // V3.68 (P1-02): el `decision_id` que sirvió la cola viaja al drill, que
        // lo devuelve en cada GET/POST del peldaño y declara el ciclo de vida
        // (`started`/`abandoned`).
        decisionId={current.decision_id}
        onProduced={() => setProduced(true)}
        onClose={onExit}
      />

      {produced ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            onClick={() => setIndex((n) => n + 1)}
            className="w-full sm:w-auto"
          >
            {isLast
              ? t("dictionary.review.sessionFinish")
              : t("dictionary.review.sessionNext")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
