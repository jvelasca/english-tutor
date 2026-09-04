import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Award,
  Check,
  Loader2,
  MessageSquareText,
} from "lucide-react";
import { useI18n } from "../../hooks/useI18n";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { ActivityResult } from "../../components/ActivityResult";
import { SkillBar } from "../../components/SkillBar";
import { LearnActivitySwitcher } from "../../components/LearnActivitySwitcher";
import type { LearnActivity } from "../../router/learnHub";
import { ProgressRing } from "../../components/ProgressRing";
import { criterionLabel } from "../../utils/speaking";
import { navigateTo } from "../../router/hash";
import { CHAT_PATH } from "../../router/paths";
import {
  getConversationQuestion,
  getConversationStats,
  submitConversationAttempt,
  type ConversationQuestionMode,
} from "../../api/conversationRoutes";
import { getSpeakingLevel } from "../../api/academy";
import type {
  ConversationAttempt,
  ConversationDialogue,
  ConversationStats,
  NextBestActivity,
} from "../../types/api";
import type { Section } from "../../utils/sections";
import { cn } from "../../lib/utils";
import {
  drillAnswered,
  isSessionFinished,
  sessionDone,
  type ConversationSession,
} from "./conversationSession";
import { ConversationLevelPanel } from "./ConversationLevelPanel";
import { ConversationGuidedChat } from "./ConversationGuidedChat";
import { SpeakingAssessment } from "../speaking/SpeakingAssessment";

interface ConversationRoutesPracticeProps {
  userId: string | null;
  /** Actividad activa (Conversation) para el atajo de la franja superior. */
  active: LearnActivity;
  /** Navega de vuelta al hub de APRENDER (`#/aprender`). */
  onBack: () => void;
  /** La práctica registra un intento puntuado: el padre refresca métricas. */
  onAttempt: () => void;
  /** Recomendación de "siguiente mejor actividad" al terminar el examen. */
  onNext: (section: Section | null, step: NextBestActivity) => void;
}

type RouteView = { kind: "routes" } | { kind: "assessment" };

/** Modo de pregunta del backend según el modo de sesión activo. */
function convMode(
  session: ConversationSession | null,
): ConversationQuestionMode {
  if (!session) return "all";
  return session.mode === "drill"
    ? "failed"
    : session.mode === "mastered"
      ? "mastered"
      : "all";
}

/**
 * APRENDER → Conversation por rutas (V3.10): página única con scroll, como
 * Speaking/Listening/Pronunciation.
 *
 * El escenario de práctica vive arriba: un mini-diálogo guiado multi-turno con
 * el tutor (situación, roles y metas comunicativas; se conversa por escrito o
 * con el micrófono hasta completarlo). Al terminar se evalúa el transcripto
 * completo con el pipeline de evidencia (LLM + señal objetiva de interacción).
 * Debajo, el mapa de rutas A1–C2 con anillos y, al abrir un nivel, sus modos
 * (practicar / repetir fallidos / repasar dominados) y el acceso al Speaking
 * Assessment como vía formal de demostrar el nivel. La ruta es un hito de
 * práctica (techo `functional`); demostrar el nivel exige examen + evidencia
 * formal, no la ruta.
 */
export function ConversationRoutesPractice({
  userId,
  active,
  onBack,
  onAttempt,
  onNext,
}: ConversationRoutesPracticeProps) {
  const { t } = useI18n();
  const [view, setView] = useState<RouteView>({ kind: "routes" });
  const [stats, setStats] = useState<ConversationStats | null>(null);
  const [assessedLevel, setAssessedLevel] = useState<string | null>(null);
  const [expandedLevel, setExpandedLevel] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);
  // Sesión focalizada activa (drill / repaso / vuelta del nivel).
  const [session, setSession] = useState<ConversationSession | null>(null);
  // Diálogo activo del escenario superior.
  const [dialogue, setDialogue] = useState<ConversationDialogue | null>(null);
  const [cardLoading, setCardLoading] = useState(false);
  const [cardError, setCardError] = useState(false);
  const [chatStarted, setChatStarted] = useState(false);
  // Evaluación del transcripto tras terminar una conversación.
  const [result, setResult] = useState<ConversationAttempt | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [evaluateError, setEvaluateError] = useState<string | null>(null);
  // Conversación terminada lista para evaluar (se llena al terminar el chat).
  const lastConvIdRef = useRef<string | null>(null);
  // Seq de "siguiente diálogo": avanzar tras evaluar o saltar la recarga.
  const [seq, setSeq] = useState(0);

  // --- Carga inicial de estadísticas y nivel oral demostrado ------------------
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setLoadError(false);
    const uid = userId;
    void (async () => {
      try {
        const [s, lvl] = await Promise.all([
          getConversationStats(uid),
          getSpeakingLevel(uid),
        ]);
        if (cancelled) return;
        setStats(s);
        setAssessedLevel(lvl.level);
        setExpandedLevel((cur) => cur ?? s.level ?? null);
      } catch {
        if (!cancelled) setLoadError(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshNonce]);

  // --- Diálogo activo del escenario -------------------------------------------
  const finished = session !== null && isSessionFinished(session);
  const stageLevel = session?.level ?? stats?.level ?? null;
  const stageMode = convMode(session);

  useEffect(() => {
    if (!userId || finished || !stageLevel) return;
    let cancelled = false;
    setCardLoading(true);
    setCardError(false);
    setDialogue(null);
    setResult(null);
    setEvaluateError(null);
    setChatStarted(false);
    lastConvIdRef.current = null;
    const uid = userId;
    void (async () => {
      try {
        const q = await getConversationQuestion(uid, stageLevel, stageMode);
        if (!cancelled) {
          setDialogue(q);
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

  /** Pide el siguiente diálogo del mismo bucket (avanzar / saltar). */
  function nextDialogue() {
    setResult(null);
    setEvaluateError(null);
    setSeq((s) => s + 1);
  }

  // --- Acciones de sesión (panel de nivel) -----------------------------------

  function startSession(next: ConversationSession) {
    setResult(null);
    setEvaluateError(null);
    setSeq((s) => s + 1);
    setSession(next);
  }

  function exitSession() {
    setSession(null);
    setResult(null);
    setEvaluateError(null);
    setRefreshNonce((n) => n + 1);
    setSeq((s) => s + 1);
  }

  async function submitEvaluation() {
    const convId = lastConvIdRef.current;
    if (!userId || !dialogue || !convId || evaluating) return;
    setEvaluating(true);
    setEvaluateError(null);
    try {
      const att = await submitConversationAttempt(userId, dialogue.id, convId);
      setResult(att);
      setChatStarted(false);
      refreshAfterAttempt();
      onAttempt();
    } catch (e) {
      setEvaluateError((e as Error).message);
    } finally {
      setEvaluating(false);
    }
  }

  /** Avanza tras ver el resultado de un diálogo (o acaba la sesión). */
  function advance(passed: boolean) {
    if (!session) {
      // Práctica libre (sin sesión): simplemente siguiente diálogo.
      onAttempt();
      nextDialogue();
      return;
    }
    let next: ConversationSession;
    if (session.mode === "drill") {
      next = {
        ...session,
        remaining: drillAnswered(session.remaining, dialogue?.id ?? "", passed),
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
    nextDialogue();
  }

  if (loadError) {
    return (
      <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center gap-3 px-4 py-16 text-center">
        <p className="text-sm text-destructive">{t("convRoutes.loadError")}</p>
        <Button
          type="button"
          variant="outline"
          onClick={() => setRefreshNonce((n) => n + 1)}
        >
          {t("convRoutes.retry")}
        </Button>
      </section>
    );
  }

  if (!userId) {
    return (
      <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        {t("convRoutes.loading")}
      </div>
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
            {t("convRoutes.backRoutes")}
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <SpeakingAssessment
            userId={userId}
            onAttempt={onAttempt}
            onNext={onNext}
          />
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
              {t("skill.conversation")}
            </h1>
            <p className="mt-1.5 text-muted-foreground">
              {t("learn.conversationSubtitle")}
            </p>
            <p className="mt-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
              {t("convRoutes.routesSubtitle")}
            </p>
          </header>

          {!stats ? (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              {t("convRoutes.loading")}
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              {/* ---- Escenario de práctica superior (página única) ---- */}
              {finished && session ? (
                <ActivityResult outcome="ok" title={t("convRoutes.sessionEnded")}>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {session.mode === "drill"
                      ? t("convRoutes.doneDrillLine")
                          .replace("{total}", String(session.total))
                          .replace("{level}", session.level)
                      : session.mode === "mastered"
                        ? t("convRoutes.doneReviewLine")
                            .replace("{total}", String(session.total))
                            .replace("{level}", session.level)
                        : t("convRoutes.doneLevelLine")
                            .replace("{total}", String(session.total))
                            .replace("{level}", session.level)}
                  </p>
                  <div className="pt-1">
                    <Button type="button" onClick={exitSession}>
                      {t("convRoutes.backRoutes")}
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
                            ? t("convRoutes.modeDrill")
                            : session.mode === "mastered"
                              ? t("convRoutes.modeReview").replace(
                                  "{level}",
                                  session.level,
                                )
                              : t("convRoutes.modeLevel").replace(
                                  "{level}",
                                  session.level,
                                )}
                        </Badge>
                        <Badge variant="outline" className="tabular-nums">
                          {sessionDone(session)} / {session.total}
                        </Badge>
                        <span className="text-muted-foreground">
                          {session.mode === "drill"
                            ? t("convRoutes.drillHint")
                            : t("convRoutes.sessionHint")}
                        </span>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={exitSession}
                      >
                        {t("convRoutes.exitSession")}
                      </Button>
                    </Card>
                  )}

                  <ConversationPracticeCard
                    userId={userId}
                    dialogue={dialogue}
                    cardLoading={cardLoading}
                    cardError={cardError}
                    chatStarted={chatStarted}
                    onStarted={() => setChatStarted(true)}
                    evaluating={evaluating}
                    evaluateError={evaluateError}
                    result={result}
                    sessionActive={session !== null}
                    onFinished={(convId) => {
                      lastConvIdRef.current = convId;
                      void submitEvaluation();
                    }}
                    onRetryEvaluation={() => void submitEvaluation()}
                    onContinue={() => {
                      if (result) advance(result.passed);
                    }}
                    onSkip={nextDialogue}
                    t={t}
                  />
                </>
              )}

              {/* ---- Rutas A1–C2 (mapa de práctica, espejo de Speaking) ---- */}
              <ConversationRoutesSection
                userId={userId}
                stats={stats}
                assessedLevel={assessedLevel}
                expandedLevel={expandedLevel}
                setExpandedLevel={setExpandedLevel}
                disabled={session !== null || evaluating}
                refreshNonce={refreshNonce}
                onStartSession={startSession}
                onDemonstrate={() => setView({ kind: "assessment" })}
              />

              {/* ---- Acceso a la conversación libre con el tutor ---- */}
              <Card className="flex flex-col gap-2 border-dashed p-4">
                <p className="flex items-center gap-2 text-xs font-semibold text-foreground">
                  <MessageSquareText className="size-4" aria-hidden="true" />
                  {t("convRoutes.freeChatTitle")}
                </p>
                <p className="text-[11px] leading-relaxed text-muted-foreground">
                  {t("convRoutes.freeChatNote")}
                </p>
                <div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="min-h-8 gap-1.5"
                    onClick={() => navigateTo(CHAT_PATH)}
                  >
                    <MessageSquareText className="size-3.5" aria-hidden="true" />
                    {t("convRoutes.freeChatCta")}
                  </Button>
                </div>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface ConversationRoutesSectionProps {
  userId: string;
  stats: ConversationStats;
  assessedLevel: string | null;
  expandedLevel: string | null;
  setExpandedLevel: (level: string | null) => void;
  disabled: boolean;
  refreshNonce: number;
  onStartSession: (session: ConversationSession) => void;
  onDemonstrate: () => void;
}

/** Mapa de rutas de conversation: resumen + tira de anillos + panel del nivel. */
function ConversationRoutesSection({
  userId,
  stats,
  assessedLevel,
  expandedLevel,
  setExpandedLevel,
  disabled,
  refreshNonce,
  onStartSession,
  onDemonstrate,
}: ConversationRoutesSectionProps) {
  const { t } = useI18n();

  return (
    <Card className="gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5 text-xs">
          <span className="font-semibold uppercase tracking-wide text-muted-foreground">
            {t("convRoutes.routesMapTitle")}
          </span>
          <span className="text-muted-foreground">
            {t("convRoutes.routesMapHint")}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <ProgressRing
            value={stats.accuracy ?? 0}
            size={58}
            strokeWidth={6}
            ariaLabel={`${t("convRoutes.accuracy")}: ${
              stats.accuracy !== null ? `${stats.accuracy}%` : "—"
            }`}
          >
            <span className="text-xs font-bold tabular-nums text-foreground">
              {stats.accuracy !== null ? `${Math.round(stats.accuracy)}%` : "—"}
            </span>
          </ProgressRing>
          <div className="flex flex-col gap-0.5 text-xs">
            <span className="font-semibold text-foreground">
              {t("convRoutes.accuracy")}
            </span>
            <span className="tabular-nums text-muted-foreground">
              {stats.passed} {t("assessment.of")} {stats.attempts}
            </span>
            {assessedLevel ? (
              <Badge variant="outline" className="mt-1 w-fit gap-1">
                <Award className="size-3.5" aria-hidden="true" />
                {t("convRoutes.assessedLevel").replace(
                  "{level}",
                  assessedLevel,
                )}
              </Badge>
            ) : (
              <span className="mt-0.5 text-muted-foreground">
                {t("convRoutes.assessedLevelNone")}
              </span>
            )}
          </div>
        </div>
      </div>

      <p className="border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">
        {t("convRoutes.routeNote").replace("{level}", stats.level)}
      </p>
      <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
        {t("convRoutes.routeCertNote")}
      </p>

      <div className="flex flex-col border-t border-border pt-4">
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("convRoutes.routeRingHelp")}
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
                aria-controls="conversation-level-items"
                aria-label={t("convRoutes.levelHistoryTitle").replace(
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
                  ariaLabel={t("convRoutes.masteredOfTotal")
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
                  {t("convRoutes.masteredOfTotal")
                    .replace("{mastered}", String(lv.mastered))
                    .replace("{total}", String(lv.total))}
                </span>
                {lv.total > 0 && lv.mastered > 0 && !lv.completed && (
                  <span className="text-[10px] tabular-nums text-muted-foreground">
                    {t("convRoutes.coveragePct").replace(
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
            id="conversation-level-items"
            className="mt-4 border-t border-border pt-4"
          >
            <ConversationLevelPanel
              userId={userId}
              level={expandedLevel}
              routeState={
                stats.levels.find((lv) => lv.level === expandedLevel)?.state
              }
              assessedLevel={assessedLevel}
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

interface ConversationPracticeCardProps {
  userId: string;
  dialogue: ConversationDialogue | null;
  cardLoading: boolean;
  cardError: boolean;
  /** El alumno ya ha enviado al menos un turno: no se puede saltar. */
  chatStarted: boolean;
  onStarted: () => void;
  evaluating: boolean;
  evaluateError: string | null;
  result: ConversationAttempt | null;
  sessionActive: boolean;
  /** El mini-chat ha terminado y deja el `conversation_id` para evaluar. */
  onFinished: (conversationId: string) => void;
  onRetryEvaluation: () => void;
  /** Continuar tras un resultado (avanza la sesión) o saltar sin conversar. */
  onContinue: () => void;
  onSkip: () => void;
  t: TranslateFn;
}

/** Tarjeta del escenario de conversación guiada (arriba, siempre visible). */
function ConversationPracticeCard({
  userId,
  dialogue,
  cardLoading,
  cardError,
  chatStarted,
  onStarted,
  evaluating,
  evaluateError,
  result,
  sessionActive,
  onFinished,
  onRetryEvaluation,
  onContinue,
  onSkip,
  t,
}: ConversationPracticeCardProps) {
  if (cardLoading || !dialogue) {
    return (
      <Card className="p-8">
        <p className="flex items-center justify-center gap-2 text-center text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          {t("convRoutes.loading")}
        </p>
      </Card>
    );
  }

  if (cardError) {
    return (
      <Card className="flex flex-col items-center gap-3 p-6 text-center">
        <p className="text-sm text-destructive">{t("convRoutes.loadError")}</p>
        <Button type="button" variant="outline" onClick={onContinue}>
          {t("convRoutes.retry")}
        </Button>
      </Card>
    );
  }

  // Evaluación en curso (el transcripto completo se puntúa con el LLM local).
  if (evaluating) {
    return (
      <Card className="flex flex-col items-center gap-3 p-8 text-center">
        <Loader2 className="size-6 animate-spin text-primary" aria-hidden="true" />
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <MessageSquareText className="size-4" aria-hidden="true" />
          {t("convRoutes.evaluating")}
        </p>
      </Card>
    );
  }

  // Resultado de la conversación terminada.
  if (result) {
    const criteria = Object.entries(result.criteria).filter(
      (entry): entry is [string, number] =>
        entry[1] !== null && entry[1] !== undefined,
    );
    return (
      <Card className="gap-4 p-5 sm:p-6">
        <ActivityResult
          outcome={result.passed ? "ok" : "ko"}
          title={`${t("convRoutes.resultTitle")} · ${Math.round(
            result.overall * 100,
          )}/100`}
          footer={
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" onClick={onContinue}>
                {t("convRoutes.continue")}
              </Button>
            </div>
          }
        >
          <header className="flex flex-wrap items-center gap-2">
            <Badge variant={result.passed ? "default" : "destructive"}>
              {result.passed
                ? t("convRoutes.resultPassed")
                : t("convRoutes.resultNotPassed")}
            </Badge>
            <Badge variant="outline">{result.level}</Badge>
            <span className="text-xs text-muted-foreground">
              {result.topic.replace(/_/g, " ")}
            </span>
          </header>

          {result.heard && (
            <div className="flex flex-col gap-1 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs">
              <span className="font-semibold text-muted-foreground">
                {t("convRoutes.transcriptLabel")}
              </span>
              <span className="leading-relaxed text-foreground" lang="en">
                {result.heard}
              </span>
            </div>
          )}

          {result.communicative_goals.length > 0 && (
            <div className="flex flex-col gap-1 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs">
              <span className="font-semibold text-muted-foreground">
                {t("convRoutes.goalsLabel")}
              </span>
              <ul className="flex flex-col gap-1 text-foreground">
                {result.communicative_goals.map((goal) => (
                  <li key={`${result.dialogue_id}-${goal}`}>• {goal}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-col gap-2.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t("convRoutes.criteriaTitle")}
            </p>
            {criteria.map(([name, value]) => (
              <SkillBar
                key={name}
                label={criterionLabel(name)}
                value={value}
                hint={`${Math.round(value * 100)}%`}
              />
            ))}
          </div>

          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {t("convRoutes.resultHonestNote")}
          </p>
        </ActivityResult>
      </Card>
    );
  }

  return (
    <Card className="gap-4 p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{dialogue.level}</Badge>
          <span className="text-muted-foreground">
            {t("convRoutes.practiceHint")}
          </span>
        </div>
        {!chatStarted && !sessionActive && (
          <Button type="button" variant="ghost" size="sm" onClick={onSkip}>
            {t("convRoutes.skip")}
          </Button>
        )}
      </div>

      <ConversationGuidedChat
        key={dialogue.id}
        userId={userId}
        dialogue={dialogue}
        onFirstMessage={onStarted}
        onFinish={(_heard, _durationSeconds, conversationId) =>
          onFinished(conversationId)
        }
      />

      {evaluateError && (
        <div
          role="alert"
          className="flex flex-col items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-center text-xs text-destructive"
        >
          <p className="break-words">{evaluateError}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRetryEvaluation}
          >
            {t("convRoutes.retry")}
          </Button>
        </div>
      )}
    </Card>
  );
}
