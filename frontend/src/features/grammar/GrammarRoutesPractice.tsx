import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowLeft,
  Check,
  ChevronRight,
  GraduationCap,
  Loader2,
  X,
} from "lucide-react";
import { useI18n } from "../../hooks/useI18n";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { ActivityResult } from "../../components/ActivityResult";
import { LearnActivitySwitcher } from "../../components/LearnActivitySwitcher";
import { ProgressRing } from "../../components/ProgressRing";
import type { LearnActivity } from "../../router/learnHub";
import type { NextBestActivity, GrammarAttempt, GrammarQuestion, GrammarStats } from "../../types/api";
import type { Section } from "../../utils/sections";
import { cn } from "../../lib/utils";
import {
  getGrammarQuestion,
  getGrammarStats,
  submitGrammarAttempt,
  type GrammarQuestionMode,
} from "../../api/grammarRoutes";
import {
  drillAnswered,
  isSessionFinished,
  sessionDone,
  type GrammarSession,
} from "./grammarSession";
import { GrammarLevelPanel } from "./GrammarLevelPanel";
import { AssessmentLadder } from "../assessment/AssessmentLadder";

interface GrammarRoutesPracticeProps {
  userId: string | null;
  /** Actividad activa (Gramática) para el atajo de la franja superior. */
  active: LearnActivity;
  /** Navega de vuelta al hub de APRENDER (`#/aprender`). */
  onBack: () => void;
  /** La práctica registra un intento puntuado: el padre refresca métricas. */
  onAttempt: () => void;
  /** Recomendación de "siguiente mejor actividad" al terminar el examen. */
  onNext: (section: Section | null, step: NextBestActivity) => void;
}

type RouteView =
  | { kind: "routes" }
  | { kind: "assessment"; level: string };

/** Modo de pregunta del backend según el modo de sesión activo. */
function gramMode(
  session: GrammarSession | null,
): GrammarQuestionMode {
  if (!session) return "all";
  return session.mode === "drill"
    ? "failed"
    : session.mode === "mastered"
      ? "mastered"
      : "all";
}

/**
 * APRENDER → Grammar por rutas (V3.12): página única con scroll, como
 * Speaking/Listening/Pronunciation/Vocabulary.
 *
 * El escenario de práctica vive arriba: un check MC de grammar del currículo
 * (el alumno elige la opción correcta y la evaluación es instantánea y
 * determinista, con la respuesta correcta revelada tras responder). Debajo, el
 * mapa de rutas A1–C2 con anillos y, al abrir un nivel, sus modos (practicar /
 * repetir falladas / repasar aprendidas) y el bloque «Demostrar el nivel», que
 * abre los instrumentos formales del curso (examen/escalera de evaluaciones)
 * como vía para demostrar el nivel. La ruta es un hito de práctica (techo
 * `functional`); demostrar el nivel exige examen + evidencia formal, no la ruta.
 */
export function GrammarRoutesPractice({
  userId,
  active,
  onBack,
  onAttempt,
}: GrammarRoutesPracticeProps) {
  const { t } = useI18n();
  const [view, setView] = useState<RouteView>({ kind: "routes" });
  const [stats, setStats] = useState<GrammarStats | null>(null);
  const [expandedLevel, setExpandedLevel] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);
  // Sesión focalizada activa (drill / repaso / vuelta del nivel). Sin sesión, el
  // escenario practica la ruta recomendada (stats.level) en modo libre.
  const [session, setSession] = useState<GrammarSession | null>(null);
  // Pregunta activa del escenario superior.
  const [question, setQuestion] = useState<GrammarQuestion | null>(null);
  const [cardLoading, setCardLoading] = useState(false);
  const [cardError, setCardError] = useState(false);
  const [result, setResult] = useState<GrammarAttempt | null>(null);
  const [busy, setBusy] = useState(false);
  const [attemptError, setAttemptError] = useState<string | null>(null);
  // Seq de "siguiente pregunta": avanzar tras responder o saltar.
  const [seq, setSeq] = useState(0);

  // --- Carga inicial de estadísticas ------------------------------------------
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setLoadError(false);
    const uid = userId;
    void (async () => {
      try {
        const s = await getGrammarStats(uid);
        if (cancelled) return;
        setStats(s);
        // Despliega por defecto el nivel en el que está el alumno.
        setExpandedLevel((cur) => cur ?? s.level ?? null);
      } catch {
        if (!cancelled) setLoadError(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshNonce]);

  // --- Pregunta activa del escenario ------------------------------------------
  const finished = session !== null && isSessionFinished(session);
  const stageLevel = session?.level ?? stats?.level ?? null;
  const stageMode = gramMode(session);

  useEffect(() => {
    if (!userId || finished || !stageLevel) return;
    let cancelled = false;
    setCardLoading(true);
    setCardError(false);
    setQuestion(null);
    setResult(null);
    setAttemptError(null);
    const uid = userId;
    void (async () => {
      try {
        const q = await getGrammarQuestion(uid, stageLevel, stageMode);
        if (!cancelled) {
          setQuestion(q);
          setCardLoading(false);
        }
      } catch {
        if (!cancelled) {
          setCardLoading(false);
          setCardError(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, stageLevel, stageMode, seq, finished]);

  /** Recarga estadísticas (anillos) y fuerza el refresco de los paneles. */
  function refreshAfterAttempt() {
    if (!userId) return;
    setRefreshNonce((n) => n + 1);
  }

  /** Pide la siguiente pregunta del mismo bucket (avanzar / saltar). */
  function nextCard() {
    setResult(null);
    setAttemptError(null);
    setSeq((s) => s + 1);
  }

  // --- Acciones de sesión (panel de nivel) -----------------------------------

  function startSession(next: GrammarSession) {
    setResult(null);
    setAttemptError(null);
    setSeq((s) => s + 1);
    setSession(next);
  }

  function exitSession() {
    setSession(null);
    setResult(null);
    setAttemptError(null);
    setRefreshNonce((n) => n + 1);
    setSeq((s) => s + 1);
  }

  /** Avanza tras ver el resultado de una pregunta (o acaba la sesión). */
  function advance(passed: boolean) {
    if (!session) {
      // Práctica libre (sin sesión): simplemente siguiente pregunta.
      onAttempt();
      nextCard();
      return;
    }
    let next: GrammarSession;
    if (session.mode === "drill") {
      next = {
        ...session,
        remaining: drillAnswered(session.remaining, question?.check_id ?? "", passed),
      };
    } else {
      next = { ...session, done: session.done + 1 };
    }
    onAttempt();
    refreshAfterAttempt();
    if (isSessionFinished(next)) {
      setSession(next);
      setResult(null);
      return;
    }
    setSession(next);
    nextCard();
  }

  /** Elige una opción: puntúa al instante (determinista) y muestra feedback. */
  async function pick(optionIndex: number) {
    if (!userId || !question || busy) return;
    setBusy(true);
    setAttemptError(null);
    try {
      const attempt = await submitGrammarAttempt(
        userId,
        question.check_id,
        optionIndex,
      );
      setResult(attempt);
      refreshAfterAttempt();
      onAttempt();
    } catch (e) {
      setAttemptError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (loadError) {
    return (
      <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center gap-3 px-4 py-16 text-center">
        <p className="text-sm text-destructive">{t("gramRoutes.loadError")}</p>
        <Button
          type="button"
          variant="outline"
          onClick={() => setRefreshNonce((n) => n + 1)}
        >
          {t("gramRoutes.retry")}
        </Button>
      </section>
    );
  }

  if (view.kind === "assessment") {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background/90 px-2 py-1.5 backdrop-blur">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="min-h-9 shrink-0 gap-1 px-2 text-sm font-medium"
            onClick={() => setView({ kind: "routes" })}
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            {t("gramRoutes.backRoutes")}
          </Button>
          <span className="text-xs text-muted-foreground">
            {t("gramRoutes.formalTitle").replace("{level}", view.level)}
          </span>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
            <div className="mb-4 flex flex-col gap-1.5">
              <h1 className="text-lg font-bold tracking-tight">
                {t("gramRoutes.formalTitle").replace("{level}", view.level)}
              </h1>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {t("gramRoutes.formalNote")}
              </p>
            </div>
            <AssessmentLadder
              userId={userId}
              levelId={view.level.toLowerCase()}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background/90 px-2 py-1.5 backdrop-blur">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="min-h-9 shrink-0 gap-1 px-2 text-sm font-medium"
          onClick={onBack}
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          {t("learn.back")}
        </Button>
        <LearnActivitySwitcher active={active} />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
          <header className="mb-6">
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              {t("skill.grammar")}
            </h1>
            <p className="mt-1.5 text-muted-foreground">
              {t("learn.grammarSubtitle")}
            </p>
            <p className="mt-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
              {t("gramRoutes.routesSubtitle")}
            </p>
          </header>

          {!stats ? (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              {t("gramRoutes.loading")}
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              {/* ---- Escenario de práctica superior (página única) ---- */}
              {finished && session ? (
                <ActivityResult outcome="ok" title={t("gramRoutes.sessionEnded")}>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {session.mode === "drill"
                      ? t("gramRoutes.doneDrillLine")
                          .replace("{total}", String(session.total))
                          .replace("{level}", session.level)
                      : session.mode === "mastered"
                        ? t("gramRoutes.doneReviewLine")
                            .replace("{total}", String(session.total))
                            .replace("{level}", session.level)
                        : t("gramRoutes.doneLevelLine")
                            .replace("{total}", String(session.total))
                            .replace("{level}", session.level)}
                  </p>
                  <div className="pt-1">
                    <Button type="button" onClick={exitSession}>
                      {t("gramRoutes.backRoutes")}
                    </Button>
                  </div>
                </ActivityResult>
              ) : (
                <>
                  {session && (
                    <Card className="flex flex-row flex-wrap items-center justify-between gap-3 p-3">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <Badge variant="secondary">
                          {session.mode === "drill"
                            ? t("gramRoutes.modeDrill")
                            : session.mode === "mastered"
                              ? t("gramRoutes.modeReview").replace(
                                  "{level}",
                                  session.level,
                                )
                              : t("gramRoutes.modeLevel").replace(
                                  "{level}",
                                  session.level,
                                )}
                        </Badge>
                        <Badge variant="outline" className="tabular-nums">
                          {sessionDone(session)} / {session.total}
                        </Badge>
                        <span className="text-muted-foreground">
                          {session.mode === "drill"
                            ? t("gramRoutes.drillHint")
                            : t("gramRoutes.sessionHint")}
                        </span>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={exitSession}
                      >
                        {t("gramRoutes.exitSession")}
                      </Button>
                    </Card>
                  )}

                  <GrammarPracticeCard
                    question={question}
                    cardLoading={cardLoading}
                    cardError={cardError}
                    result={result}
                    busy={busy}
                    attemptError={attemptError}
                    onPick={(i) => void pick(i)}
                    onAdvance={() => {
                      if (!session && !result) {
                        nextCard();
                        return;
                      }
                      if (result) advance(result.passed);
                    }}
                    onSkip={nextCard}
                    sessionActive={session !== null}
                    t={t}
                  />
                </>
              )}

              {/* ---- Rutas A1–C2 (mapa de práctica, espejo de las demás) ---- */}
              <GrammarRoutesSection
                userId={userId}
                stats={stats}
                expandedLevel={expandedLevel}
                setExpandedLevel={setExpandedLevel}
                disabled={session !== null}
                refreshNonce={refreshNonce}
                onStartSession={startSession}
                onDemonstrate={(level) =>
                  setView({ kind: "assessment", level })
                }
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface GrammarRoutesSectionProps {
  userId: string | null;
  stats: GrammarStats;
  expandedLevel: string | null;
  setExpandedLevel: (level: string | null) => void;
  disabled: boolean;
  refreshNonce: number;
  onStartSession: (session: GrammarSession) => void;
  onDemonstrate: (level: string) => void;
}

/** Mapa de rutas de grammar: resumen + tira de anillos + panel del nivel. */
function GrammarRoutesSection({
  userId,
  stats,
  expandedLevel,
  setExpandedLevel,
  disabled,
  refreshNonce,
  onStartSession,
  onDemonstrate,
}: GrammarRoutesSectionProps) {
  const { t } = useI18n();

  return (
    <Card className="gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5 text-xs">
          <span className="font-semibold uppercase tracking-wide text-muted-foreground">
            {t("gramRoutes.routesMapTitle")}
          </span>
          <span className="text-muted-foreground">
            {t("gramRoutes.routesMapHint")}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <ProgressRing
            value={stats.accuracy ?? 0}
            size={58}
            strokeWidth={6}
            ariaLabel={`${t("gramRoutes.accuracy")}: ${
              stats.accuracy !== null ? `${stats.accuracy}%` : "—"
            }`}
          >
            <span className="text-xs font-bold tabular-nums text-foreground">
              {stats.accuracy !== null ? `${Math.round(stats.accuracy)}%` : "—"}
            </span>
          </ProgressRing>
          <div className="flex flex-col gap-0.5 text-xs">
            <span className="font-semibold text-foreground">
              {t("gramRoutes.accuracy")}
            </span>
            <span className="tabular-nums text-muted-foreground">
              {stats.passed} {t("assessment.of")} {stats.attempts}
            </span>
          </div>
        </div>
      </div>

      <p className="border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">
        {t("gramRoutes.routeNote").replace("{level}", stats.level)}
      </p>
      <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
        {t("gramRoutes.routeCertNote")}
      </p>

      <div className="flex flex-col border-t border-border pt-4">
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("gramRoutes.routeRingHelp")}
        </p>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          {stats.levels.map((lv) => {
            const expanded = expandedLevel === lv.level;
            const pct = lv.completed
              ? 100
              : lv.total > 0
                ? (lv.mastered / lv.total) * 100
                : 0;
            return (
              <button
                key={lv.level}
                type="button"
                onClick={() => setExpandedLevel(expanded ? null : lv.level)}
                aria-expanded={expanded}
                aria-controls="grammar-level-items"
                aria-label={t("gramRoutes.levelHistoryTitle").replace(
                  "{level}",
                  lv.level,
                )}
                disabled={disabled}
                className={cn(
                  "flex flex-col items-center gap-1.5 rounded-lg p-1.5 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                  expanded && "bg-accent",
                  disabled && "cursor-not-allowed opacity-60",
                )}
              >
                <ProgressRing
                  value={pct}
                  size={46}
                  strokeWidth={5}
                  className={
                    lv.completed
                      ? "text-success"
                      : lv.mastered > 0
                        ? "text-primary"
                        : "text-muted-foreground"
                  }
                  ariaLabel={t("gramRoutes.masteredOfTotal")
                    .replace("{mastered}", String(lv.mastered))
                    .replace("{total}", String(lv.total))}
                >
                  {lv.completed ? (
                    <Check className="size-4" aria-hidden="true" />
                  ) : (
                    <span className="text-[11px] font-semibold tabular-nums text-foreground">
                      {lv.level}
                    </span>
                  )}
                </ProgressRing>
                <span className="text-[10px] font-medium text-muted-foreground">
                  {lv.completed ? lv.level : ""}
                </span>
                <span className="text-[10px] font-semibold tabular-nums text-foreground">
                  {t("gramRoutes.masteredOfTotal")
                    .replace("{mastered}", String(lv.mastered))
                    .replace("{total}", String(lv.total))}
                </span>
                {lv.total > 0 && lv.mastered > 0 && !lv.completed && (
                  <span className="text-[10px] tabular-nums text-muted-foreground">
                    {t("gramRoutes.coveragePct").replace(
                      "{pct}",
                      String(Math.round((lv.mastered / lv.total) * 100)),
                    )}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {expandedLevel !== null && !disabled && (
          <div
            id="grammar-level-items"
            className="mt-4 border-t border-border pt-4"
          >
            <GrammarLevelPanel
              userId={userId}
              level={expandedLevel}
              disabled={disabled}
              refreshNonce={refreshNonce}
              onPracticeLevel={(level, total) =>
                onStartSession({ mode: "level", level, total, done: 0 })
              }
              onDrillFailed={(level, failedIds) =>
                onStartSession({
                  mode: "drill",
                  level,
                  total: failedIds.length,
                  remaining: failedIds,
                })
              }
              onReviewLearned={(level, total) =>
                onStartSession({ mode: "mastered", level, total, done: 0 })
              }
              onDemonstrate={onDemonstrate}
            />
          </div>
        )}
      </div>
    </Card>
  );
}

type TranslateFn = (k: string) => string;

interface GrammarPracticeCardProps {
  question: GrammarQuestion | null;
  cardLoading: boolean;
  cardError: boolean;
  result: GrammarAttempt | null;
  busy: boolean;
  attemptError: string | null;
  onPick: (optionIndex: number) => void;
  /** Continuar tras un resultado (avanza la sesión) o saltar sin responder. */
  onAdvance: () => void;
  onSkip: () => void;
  sessionActive: boolean;
  t: TranslateFn;
}

/** Tarjeta del escenario MC (arriba, siempre visible). */
function GrammarPracticeCard({
  question,
  cardLoading,
  cardError,
  result,
  busy,
  attemptError,
  onPick,
  onAdvance,
  onSkip,
  sessionActive,
  t,
}: GrammarPracticeCardProps) {
  if (cardLoading || !question) {
    return (
      <Card className="p-8">
        <p className="flex items-center justify-center gap-2 text-center text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          {t("gramRoutes.loading")}
        </p>
      </Card>
    );
  }

  if (cardError) {
    return (
      <Card className="flex flex-col items-center gap-3 p-6 text-center">
        <p className="text-sm text-destructive">{t("gramRoutes.loadError")}</p>
        <Button type="button" variant="outline" onClick={onAdvance}>
          {t("gramRoutes.retry")}
        </Button>
      </Card>
    );
  }

  if (result) {
    const reveal = (index: number): { tone: string; mark: ReactNode } => {
      if (index === result.correct_index) {
        return {
          tone: "border-success/40 bg-success/10 text-success",
          mark: <Check className="size-3.5 shrink-0" aria-hidden="true" />,
        };
      }
      if (index === result.selected_index) {
        return {
          tone: "border-destructive/40 bg-destructive/10 text-destructive",
          mark: <X className="size-3.5 shrink-0" aria-hidden="true" />,
        };
      }
      return { tone: "border-border", mark: null };
    };

    return (
      <Card className="gap-4 p-5 sm:p-6">
        <ActivityResult
          outcome={result.passed ? "ok" : "ko"}
          title={`${result.passed ? t("gramRoutes.resultPassed") : t("gramRoutes.resultNotPassed")}`}
          footer={
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" onClick={onAdvance}>
                {t("gramRoutes.continue")}
              </Button>
            </div>
          }
        >
          <header className="flex flex-wrap items-center gap-2">
            <Badge variant={result.passed ? "default" : "destructive"}>
              {result.passed
                ? t("gramRoutes.resultPassed")
                : t("gramRoutes.resultNotPassed")}
            </Badge>
            <span className="text-sm text-muted-foreground">
              {t("gramRoutes.resultScore").replace(
                "{score}",
                String(Math.round(result.score)),
              )}
            </span>
          </header>

          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t("gramRoutes.questionLabel")}
            </span>
            <p
              className="rounded-lg border border-border bg-secondary/20 px-3 py-2 text-sm font-medium leading-relaxed text-foreground"
              lang="en"
            >
              {result.prompt}
            </p>
          </div>

          <ul className="flex flex-col gap-1.5" aria-label={t("gramRoutes.answerLabel")}>
            {result.options.map((option, idx) => {
              const revealState = reveal(idx);
              return (
                <li
                  key={`${result.check_id}-${idx}`}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm",
                    revealState.tone,
                  )}
                >
                  <span
                    className={cn(
                      "flex size-5 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold",
                      idx === result.correct_index
                        ? "border-success/50 text-success"
                        : idx === result.selected_index
                          ? "border-destructive/50 text-destructive"
                          : "border-border text-muted-foreground",
                    )}
                  >
                    {String.fromCharCode(65 + idx)}
                  </span>
                  <span className="flex-1 text-foreground" lang="en">
                    {option}
                  </span>
                  {revealState.mark}
                </li>
              );
            })}
          </ul>

          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {t("gramRoutes.resultHonestNote")}
          </p>
        </ActivityResult>
      </Card>
    );
  }

  return (
    <Card className="gap-4 p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px] normal-case">
            {question.topic.replace(/_/g, " ")}
          </Badge>
          <Badge variant="secondary">{question.level}</Badge>
        </div>
        <span className="text-[11px] text-muted-foreground">
          {t("gramRoutes.pickHint")}
        </span>
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("gramRoutes.questionLabel")}
        </span>
        <p
          className="rounded-xl border border-border bg-secondary/30 px-4 py-3.5 text-base font-medium leading-relaxed text-foreground sm:text-lg"
          lang="en"
        >
          {question.prompt}
        </p>
      </div>

      {attemptError && (
        <div
          role="alert"
          className="flex flex-col items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-center text-xs text-destructive"
        >
          <p className="break-words">{attemptError}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => undefined}
          >
            {t("gramRoutes.retry")}
          </Button>
        </div>
      )}

      <ul
        className="flex flex-col gap-1.5"
        aria-label={t("gramRoutes.answerLabel")}
      >
        {question.options.map((option, idx) => (
          <li key={`${question.check_id}-${idx}`}>
            <button
              type="button"
              disabled={busy}
              onClick={() => onPick(idx)}
              className="group flex w-full items-center gap-2.5 rounded-lg border border-border px-3 py-2.5 text-left text-sm text-foreground transition-colors hover:border-primary/50 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-wait disabled:opacity-60"
            >
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-border text-[11px] font-semibold text-muted-foreground transition-colors group-hover:border-primary/50 group-hover:text-primary">
                {String.fromCharCode(65 + idx)}
              </span>
              <span className="flex-1" lang="en">
                {option}
              </span>
              <ChevronRight
                className="size-4 shrink-0 text-muted-foreground/60 transition-transform group-hover:translate-x-0.5"
                aria-hidden="true"
              />
            </button>
          </li>
        ))}
      </ul>

      {busy && (
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          {t("gramRoutes.evaluating")}
        </p>
      )}

      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-[11px] leading-relaxed text-muted-foreground">
          <GraduationCap className="size-3.5 shrink-0" aria-hidden="true" />
          {t("gramRoutes.pickNote")}
        </p>
        {!sessionActive && !busy && (
          <Button type="button" variant="ghost" size="sm" onClick={onSkip}>
            {t("gramRoutes.skip")}
          </Button>
        )}
      </div>
    </Card>
  );
}
