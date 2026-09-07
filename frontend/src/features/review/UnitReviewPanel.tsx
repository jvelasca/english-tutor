import { useCallback, useEffect, useState } from "react";
import {
  BookOpenCheck,
  CheckCircle2,
  Loader2,
  RefreshCw,
  XCircle,
} from "lucide-react";
import {
  getUnitMicroReview,
  getUnitReviewPlan,
  submitUnitMicroReview,
} from "../../api/academy";
import type {
  MicroReviewItem,
  MicroReviewResult,
  MicroReviewSession,
  UnitReviewPlan,
  UnitReviewPlanUnit,
  UnitReviewWindow,
  UnitReviewWindowState,
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { cn } from "../../lib/utils";
import {
  countReviewableUnits,
  flattenReviewLevels,
  formatPercent,
  hasReviewableWindow,
  isReviewableWindowState,
  optionLetter,
  windowStateTone,
} from "./unitReviewLogic";

interface UnitReviewPanelProps {
  userId: string | null;
}

function windowStateClass(state: UnitReviewWindowState): string {
  switch (windowStateTone(state)) {
    case "passed":
      return "border-success/50 bg-success/10 text-success";
    case "due_now":
      return "border-warning/50 bg-warning/10 text-warning";
    case "failed":
      return "border-destructive/50 bg-destructive/10 text-destructive";
    default:
      return "border-border bg-muted text-muted-foreground";
  }
}

/**
 * Repaso/SRS por unidad (V3.16 + V3.18/O3): ventanas fijas 7/30/90 de las
 * unidades completadas, agregadas por niveles (actual + anteriores
 * matriculados con unidades completadas o con plan activo), + micro-review con
 * los checks MC oficiales.
 *
 * El micro-review es práctica de retención: el servidor puntúa las respuestas
 * (nunca envía `correct_index` antes de responder) y NO cuenta como
 * demostración de dominio (D5) — así lo dice la copia honesta de la UI.
 */
export function UnitReviewPanel({ userId }: UnitReviewPanelProps) {
  const { t } = useI18n();
  const [plan, setPlan] = useState<UnitReviewPlan | null>(null);
  const [state, setState] = useState<"loading" | "error" | "done">(
    "loading",
  );
  const [tick, setTick] = useState(0);
  const [review, setReview] = useState<{
    unit: UnitReviewPlanUnit;
    window: UnitReviewWindow;
  } | null>(null);

  const refresh = useCallback(async () => {
    if (!userId) {
      setPlan(null);
      setState("error");
      return;
    }
    try {
      const data = await getUnitReviewPlan(userId);
      setPlan(data);
      setState("done");
    } catch {
      setPlan(null);
      setState("error");
    }
  }, [userId]);

  useEffect(() => {
    setState("loading");
    void refresh();
  }, [refresh, tick]);

  if (!userId) return null;

  if (review) {
    return (
      <div className="space-y-3">
        <UnitMicroReview
          userId={userId}
          levelId={review.unit.level_id}
          unitId={review.unit.unit_id}
          unitTitle={review.unit.title}
          windowDays={review.window.window_days}
          onExit={() => {
            setReview(null);
            setTick((n) => n + 1);
          }}
        />
      </div>
    );
  }

  const levels = plan?.levels ?? [];
  const units = flattenReviewLevels(levels);
  const reviewable = units.filter(hasReviewableWindow);

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-base font-semibold">{t("unitReview.title")}</h3>
        <p className="text-sm text-muted-foreground">
          {t("unitReview.subtitle")}
        </p>
      </div>

      {state === "loading" && !plan && (
        <p
          role="status"
          aria-busy="true"
          className="flex items-center gap-1.5 text-sm text-muted-foreground"
        >
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          {t("unitReview.loading")}
        </p>
      )}

      {state === "error" && !plan && (
        <div className="flex flex-col items-start gap-2">
          <p className="text-sm text-muted-foreground" role="alert">
            {t("unitReview.unavailable")}
          </p>
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={() => setTick((n) => n + 1)}
          >
            <RefreshCw className="size-4" aria-hidden="true" />
            {t("unitReview.retry")}
          </Button>
        </div>
      )}

      {state === "done" && plan && units.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("unitReview.empty")}</p>
      )}

      {state === "done" &&
        plan &&
        levels.map((lv) => (
          <section key={lv.level_id} className="space-y-2" aria-label={lv.level}>
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border/60 pb-1">
              <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                {lv.level}
              </h4>
              <p className="text-xs text-muted-foreground">
                {`${t("unitReview.dueCount")}: ${countReviewableUnits(lv.units)}`}
              </p>
            </div>

            {lv.units.map((unit) => (
              <Card key={unit.unit_id} className="space-y-2 p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-medium leading-tight">{unit.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {unit.module_title} · {unit.objectives_mastered}/
                      {unit.objectives_total} {t("unitReview.objectives")}
                    </p>
                  </div>
                  {unit.completed ? (
                    <CheckCircle2
                      className="mt-0.5 size-4 shrink-0 text-success"
                      aria-hidden="true"
                    />
                  ) : (
                    <BookOpenCheck
                      className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                      aria-hidden="true"
                    />
                  )}
                </div>

                <div className="flex flex-wrap gap-2">
                  {unit.windows.map((window) => {
                    const label = t(`unitReview.window.${window.window_days}`);
                    const stateLabel = t(`unitReview.state.${window.state}`);
                    const actionable = isReviewableWindowState(window.state);
                    return actionable ? (
                      <Button
                        key={window.window_days}
                        type="button"
                        size="sm"
                        variant="outline"
                        className="gap-1.5"
                        onClick={() => setReview({ unit, window })}
                      >
                        <span
                          className={cn(
                            "rounded-full border px-1.5 py-0 text-[10px] font-semibold uppercase",
                            windowStateClass(window.state),
                          )}
                        >
                          {stateLabel}
                        </span>
                        {label}
                      </Button>
                    ) : (
                      <span
                        key={window.window_days}
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs",
                          windowStateClass(window.state),
                        )}
                      >
                        {label}
                        {window.state === "passed" && (
                          <CheckCircle2
                            className="size-3.5"
                            aria-hidden="true"
                          />
                        )}
                      </span>
                    );
                  })}
                </div>
              </Card>
            ))}
          </section>
        ))}

      {state === "done" &&
        plan &&
        units.length > 0 &&
        reviewable.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {t("unitReview.noneDue")}
          </p>
        )}
    </div>
  );
}

/**
 * Micro-review de una ventana: un check MC oficial por tarjeta (D8), el
 * servidor puntúa al enviar y el resultado revela las respuestas correctas.
 */
function UnitMicroReview({
  userId,
  levelId,
  unitId,
  unitTitle,
  windowDays,
  onExit,
}: {
  userId: string;
  levelId: string;
  unitId: string;
  unitTitle: string;
  windowDays: number;
  onExit: () => void;
}) {
  const { t } = useI18n();
  const [session, setSession] = useState<MicroReviewSession | null>(null);
  const [phase, setPhase] = useState<"loading" | "questions" | "result">(
    "loading",
  );
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [result, setResult] = useState<MicroReviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await getUnitMicroReview(userId, unitId, windowDays, levelId);
        if (cancelled) return;
        setSession(data);
        setPhase("questions");
      } catch {
        if (!cancelled) setError(t("unitReview.unavailable"));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, unitId, windowDays, levelId, t]);

  if (phase === "loading" && !session) {
    return (
      <p
        role="status"
        aria-busy="true"
        className="flex items-center gap-1.5 text-sm text-muted-foreground"
      >
        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
        {t("unitReview.loading")}
      </p>
    );
  }

  if (error && !session) {
    return (
      <div className="flex flex-col items-start gap-2">
        <p className="text-sm text-muted-foreground" role="alert">
          {error}
        </p>
        <Button variant="outline" size="sm" onClick={onExit}>
          {t("unitReview.back")}
        </Button>
      </div>
    );
  }

  if (!session) return null;
  const items = session.items;

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      const out = await submitUnitMicroReview(
        userId,
        unitId,
        windowDays,
        answers,
        levelId,
      );
      setResult(out);
      setPhase("result");
    } catch {
      setError(t("microReview.submitError"));
    } finally {
      setBusy(false);
    }
  }

  // --- Resultado (revela la respuesta correcta al fallar) ------------------
  if (phase === "result" && result) {
    return (
      <div className="space-y-3" aria-live="polite">
        <Card className="space-y-3 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-medium">{unitTitle}</p>
            <p className="text-xs text-muted-foreground">
              {t(`unitReview.window.${windowDays}`)}
            </p>
          </div>
          <p
            className={cn(
              "text-lg font-semibold",
              result.passed ? "text-success" : "text-destructive",
            )}
          >
            {result.passed
              ? t("microReview.resultPassed")
              : t("microReview.resultFailed")}
          </p>
          <p className="text-sm text-muted-foreground">
            {t("microReview.accuracy")}:{" "}
            <span className="font-semibold tabular-nums text-foreground">
              {formatPercent(result.accuracy)}
            </span>{" "}
            ({result.correct}/{result.total})
          </p>
          {!result.passed && (
            <p className="text-sm text-muted-foreground">
              {t("microReview.retryHint")}
            </p>
          )}
        </Card>

        <ul className="space-y-2">
          {result.items.map((item) => (
            <li key={item.item_id}>
              <Card className="space-y-1.5 p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium">{item.prompt}</p>
                  {item.correct ? (
                    <CheckCircle2
                      className="size-4 shrink-0 text-success"
                      aria-label={t("microReview.answered")}
                    />
                  ) : (
                    <XCircle
                      className="size-4 shrink-0 text-destructive"
                      aria-label={t("microReview.resultFailed")}
                    />
                  )}
                </div>
                <ol className="space-y-1 text-sm">
                  {item.options.map((option, optionIndex) => {
                    const isSelected = optionIndex === item.selected_index;
                    const isCorrect = optionIndex === item.correct_index;
                    return (
                      <li
                        key={`${item.item_id}-${optionIndex}`}
                        className={cn(
                          "rounded-md px-2 py-1",
                          isSelected && !isCorrect &&
                            "bg-destructive/10 text-destructive",
                          isCorrect && "bg-success/10 text-success",
                        )}
                      >
                        <span className="mr-1.5 font-semibold">
                          {optionLetter(optionIndex)}.
                        </span>
                        {option}
                        {isCorrect && (
                          <span className="ml-2 text-xs font-semibold">
                            ✓ {t("microReview.correctAnswer")}
                          </span>
                        )}
                        {isSelected && !isCorrect && (
                          <span className="ml-2 text-xs">
                            ✗ {t("microReview.yourAnswer")}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ol>
              </Card>
            </li>
          ))}
        </ul>

        <Button type="button" onClick={onExit}>
          {t("unitReview.back")}
        </Button>
      </div>
    );
  }

  // --- Preguntas (una a una, sin correct_index) -----------------------------
  const current = items[index] as MicroReviewItem | undefined;
  const selected = current ? answers[current.item_id] : undefined;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold">{unitTitle}</p>
        <p className="text-xs text-muted-foreground">
          {t("microReview.progress")} {index + 1} {t("microReview.of")}{" "}
          {items.length}
        </p>
      </div>
      <p className="text-xs italic text-muted-foreground">
        {t("microReview.honestNote")}
      </p>

      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      {current && (
        <Card className="space-y-3 p-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {current.objective_title} · {t(`skill.${current.skill}`)}
            </p>
            <p className="mt-1 font-medium">{current.prompt}</p>
          </div>
          <div className="space-y-2">
            {current.options.map((option, optionIndex) => {
              const isSelected = selected === optionIndex;
              return (
                <button
                  key={`${current.item_id}-${optionIndex}`}
                  type="button"
                  onClick={() =>
                    setAnswers((prev) => ({
                      ...prev,
                      [current.item_id]: optionIndex,
                    }))
                  }
                  aria-pressed={isSelected}
                  className={cn(
                    "flex w-full items-start gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors",
                    isSelected
                      ? "border-primary/60 bg-primary/10 text-foreground"
                      : "border-border bg-transparent hover:bg-accent",
                  )}
                >
                  <span className="font-semibold">
                    {optionLetter(optionIndex)}.
                  </span>
                  <span>{option}</span>
                </button>
              );
            })}
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {index < items.length - 1 ? (
              <Button
                type="button"
                disabled={selected === undefined || busy}
                onClick={() => setIndex((n) => n + 1)}
              >
                {t("microReview.next")}
              </Button>
            ) : (
              <Button
                type="button"
                disabled={selected === undefined || busy}
                onClick={() => void finish()}
              >
                {t("microReview.finish")}
              </Button>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
