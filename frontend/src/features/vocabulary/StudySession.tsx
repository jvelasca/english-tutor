/**
 * Sesión de estudio de tarjetas: voltear + 4 grados FSRS.
 *
 * Camino etiquetado (D5/E3): solo reprograma `fsrs_cards` (lexicon o flashcard
 * según la tarjeta) y escribe eventos informativos. No abre el drill ni escribe
 * mastery.
 *
 * V3.78.0 — de `RetentionSession` a `StudySession`. Dos cambios de fondo:
 *
 * 1. **Recibe los ítems**, no los pide. Antes la sesión pedía su propia cola y
 *    por eso solo podía existir UNA sesión: la del léxico entero. Ahora el
 *    contenedor decide qué se estudia (el mazo automático, un mazo manual, una
 *    lista concreta) y aquí solo se pinta. Es lo que permite que haya una sola
 *    superficie de estudio sin duplicar el motor de tarjetas.
 * 2. **Los grados los aplica el contenedor** (`onGrade`), porque el endpoint
 *    depende del mazo. Aquí se garantiza lo que V3.77.2 arregló: la calificación
 *    no cierra la sesión recargando la cola, así que el resumen final («N
 *    tarjetas repasadas») es alcanzable y el contador no se pierde.
 *
 * El resumen y el arranque los controla el contenedor con la `key`: una sesión
 * nueva remonta el componente, así que no hay que «resetear» estado por efecto.
 */
import { useState } from "react";
import { Layers, RefreshCw } from "lucide-react";
import type { FlashcardStudyItem } from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { ItemReplayButton } from "../../components/ItemReplayButton";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { cn } from "../../lib/utils";

const GRADES = [
  { grade: 1, key: "fsrs.grade.again", tone: "text-destructive" },
  { grade: 2, key: "fsrs.grade.hard", tone: "text-warning" },
  { grade: 3, key: "fsrs.grade.good", tone: "text-primary" },
  { grade: 4, key: "fsrs.grade.easy", tone: "text-success" },
] as const;

interface StudySessionProps {
  userId: string;
  /** Ítems de la sesión, ya resueltos por el contenedor. */
  items: FlashcardStudyItem[];
  /** Nombre del mazo, solo para la cabecera. */
  deckName: string;
  /** Califica una tarjeta. El contenedor decide el endpoint y el mazo. */
  onGrade: (item: FlashcardStudyItem, grade: number) => Promise<void>;
  /** Vuelve al panel de entrada. El contenedor recarga la cola al hacerlo. */
  onExit: () => void;
  /**
   * V3.78.0: volver a empezar con la cola RECARGADA. Es la «acción de
   * actualizar» que pidió V3.77.2: si la sesión acaba de terminar, lo útil no
   * es volver a mirar el mismo panel, es ver si queda algo y seguir. Si el
   * contenedor no la ofrece, el botón no se pinta (no se promete nada).
   */
  onRestart?: () => void;
}

export function StudySession({
  userId,
  items,
  deckName,
  onGrade,
  onExit,
  onRestart,
}: StudySessionProps) {
  const { t } = useI18n();
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [done, setDone] = useState(0);

  const current = items[index] ?? null;

  async function grade(g: number) {
    if (!current || busy) return;
    setBusy(true);
    try {
      await onGrade(current, g);
      setDone((n) => n + 1);
      setFlipped(false);
      // V3.77.2: la sesión NO se cierra recargando la cola. Se avanza el índice
      // para que `current` sea null y el resumen se pinte con el contador
      // intacto; si se recargara aquí, el contador se borraría y el alumno
      // nunca vería cuánto había hecho.
      setIndex((i) => i + 1);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  if (!current) {
    return (
      <Card className="gap-3 p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Layers className="size-4 text-primary" aria-hidden="true" />
          {deckName}
        </h2>
        <p className="text-sm font-medium">
          {t("flashcards.study.finished").replace("{n}", String(done))}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" variant="outline" onClick={onExit}>
            {t("flashcards.study.back")}
          </Button>
          {onRestart ? (
            <Button type="button" size="sm" variant="ghost" onClick={onRestart}>
              <RefreshCw className="size-3.5" aria-hidden="true" />
              {t("flashcards.study.refresh")}
            </Button>
          ) : null}
        </div>
      </Card>
    );
  }

  return (
    <Card className="gap-4 p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{deckName}</h2>
        <div className="flex items-center gap-2">
          <Badge variant={current.is_new ? "default" : "secondary"}>
            {current.is_new
              ? t("flashcards.study.newCard")
              : t("flashcards.study.reviewCard")}
          </Badge>
          <Badge variant="secondary">
            {t("flashcards.study.progress")
              .replace("{i}", String(index + 1))
              .replace("{n}", String(items.length))}
          </Badge>
        </div>
      </div>

      <button
        type="button"
        onClick={() => setFlipped((f) => !f)}
        className={cn(
          "flex min-h-36 w-full flex-col items-center justify-center gap-3 rounded-xl border border-border bg-secondary/40 px-4 py-6 text-center transition-colors hover:border-primary/40",
        )}
        aria-label={t("flashcards.study.flip")}
      >
        <span className="text-2xl font-bold tracking-tight" lang="en">
          {current.front}
        </span>
        {flipped ? (
          <div className="flex flex-col gap-1">
            {current.back ? (
              <span className="text-lg font-semibold" lang="es">
                {current.back}
              </span>
            ) : null}
            {current.definition ? (
              <span className="text-sm text-muted-foreground" lang="en">
                {current.definition}
              </span>
            ) : null}
            {!current.back && !current.definition ? (
              <span className="text-sm text-muted-foreground">
                {t("flashcards.study.noFace")}
              </span>
            ) : null}
          </div>
        ) : (
          <span className="text-xs text-muted-foreground">
            {t("flashcards.study.tapReveal")}
          </span>
        )}
      </button>

      {current.card_type === "lexicon" ? (
        <div className="flex items-center justify-center gap-2">
          <ItemReplayButton prompt={current.front} userId={userId} />
        </div>
      ) : null}

      {error ? (
        <p className="flex items-center gap-2 text-sm text-destructive">
          {t("dictionary.loadError")}
          <button
            type="button"
            onClick={() => setError(false)}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium hover:border-primary/50"
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            {t("common.retry")}
          </button>
        </p>
      ) : null}

      {flipped ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {GRADES.map((g) => (
            <Button
              key={g.grade}
              type="button"
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => void grade(g.grade)}
              className={cn("font-semibold", g.tone)}
            >
              {t(g.key)}
            </Button>
          ))}
        </div>
      ) : (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="w-fit self-center"
          onClick={() => setFlipped(true)}
        >
          {t("flashcards.study.reveal")}
        </Button>
      )}

      <button
        type="button"
        className="text-xs text-muted-foreground underline-offset-2 hover:underline"
        onClick={onExit}
      >
        {t("flashcards.study.exit")}
      </button>
    </Card>
  );
}
