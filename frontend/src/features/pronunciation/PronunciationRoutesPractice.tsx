import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Award,
  Check,
  Loader2,
  Mic,
  RefreshCw,
  Square,
} from "lucide-react";
import { useI18n } from "../../hooks/useI18n";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { ActivityResult } from "../../components/ActivityResult";
import { ListenButton } from "../../components/ListenButton";
import { LearnActivitySwitcher } from "../../components/LearnActivitySwitcher";
import type { LearnActivity } from "../../router/learnHub";
import { ProgressRing } from "../../components/ProgressRing";
import { MicUnavailableNotice } from "../../components/MicUnavailableNotice";
import {
  PhraseTranslateButton,
  usePhraseTranslation,
} from "../../components/PhraseTranslate";
import {
  getMicrophoneStream,
  MicUnavailableError,
  type MicUnavailableReason,
} from "../../utils/browserCapabilities";
import {
  getPronunciationQuestion,
  getPronunciationStats,
  submitPronunciationAttempt,
  type PronunciationQuestionMode,
} from "../../api/pronunciationRoutes";
import { getSpeakingLevel } from "../../api/academy";
import {
  fluencyLevelLabel,
  wpmLabel,
} from "../../utils/fluency";
import {
  feedbackHints,
  wordsCorrectLabel,
} from "../../utils/pronunciationFeedback";
import type {
  NextBestActivity,
  PronunciationAttempt,
  PronunciationPhrase,
  PronunciationStats,
} from "../../types/api";
import type { Section } from "../../utils/sections";
import { cn } from "../../lib/utils";
import {
  drillAnswered,
  isSessionFinished,
  sessionDone,
  type PronunciationSession,
} from "./pronunciationSession";
import { PronunciationLevelPanel } from "./PronunciationLevelPanel";
import { SpeakingAssessment } from "../speaking/SpeakingAssessment";

interface PronunciationRoutesPracticeProps {
  userId: string | null;
  /** Actividad activa (Pronunciation) para el atajo de la franja superior. */
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
function pronMode(session: PronunciationSession | null): PronunciationQuestionMode {
  if (!session) return "all";
  return session.mode === "drill"
    ? "failed"
    : session.mode === "mastered"
      ? "mastered"
      : "all";
}

/**
 * APRENDER → Pronunciation por rutas (V3.9): página única con scroll, como
 * Listening/Speaking.
 *
 * El escenario de práctica vive arriba: una frase modelo de read-aloud (el
 * alumno la escucha con TTS local y la lee en voz alta; la evaluación es
 * determinista, sin LLM). Debajo, el panel de rutas A1–C2 con anillos y, al
 * abrir un nivel, sus modos (practicar / repetir fallidas / repasar aprendidas)
 * y el acceso al Speaking Assessment como vía formal de demostrar el nivel. La
 * ruta es un hito de práctica (techo `functional`); demostrar el nivel exige
 * examen + evidencia formal, no la ruta.
 */
export function PronunciationRoutesPractice({
  userId,
  active,
  onBack,
  onAttempt,
  onNext,
}: PronunciationRoutesPracticeProps) {
  const { t } = useI18n();
  const [view, setView] = useState<RouteView>({ kind: "routes" });
  const [stats, setStats] = useState<PronunciationStats | null>(null);
  const [assessedLevel, setAssessedLevel] = useState<string | null>(null);
  const [expandedLevel, setExpandedLevel] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);
  // Sesión focalizada activa (drill / repaso / vuelta del nivel). Sin sesión, el
  // escenario practica la ruta recomendada (stats.level) en modo libre.
  const [session, setSession] = useState<PronunciationSession | null>(null);
  // Frase activa del escenario superior.
  const [phrase, setPhrase] = useState<PronunciationPhrase | null>(null);
  const [cardLoading, setCardLoading] = useState(false);
  const [cardError, setCardError] = useState(false);
  const [result, setResult] = useState<PronunciationAttempt | null>(null);
  // Seq de "siguiente frase": avanzar tras responder o saltar la recarga.
  const [seq, setSeq] = useState(0);
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [attemptError, setAttemptError] = useState<string | null>(null);
  const [micError, setMicError] = useState<MicUnavailableReason | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const processedRef = useRef(false);

  // --- Carga inicial de estadísticas y nivel oral demostrado ------------------
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setLoadError(false);
    const uid = userId;
    void (async () => {
      try {
        const [s, lvl] = await Promise.all([
          getPronunciationStats(uid),
          getSpeakingLevel(uid),
        ]);
        if (cancelled) return;
        setStats(s);
        setAssessedLevel(lvl.level);
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

  // --- Frase activa del escenario -------------------------------------------
  const finished = session !== null && isSessionFinished(session);
  const stageLevel = session?.level ?? stats?.level ?? null;
  const stageMode = pronMode(session);

  useEffect(() => {
    if (!userId || finished || !stageLevel) return;
    let cancelled = false;
    setCardLoading(true);
    setCardError(false);
    setPhrase(null);
    setResult(null);
    setAttemptError(null);
    processedRef.current = false;
    const uid = userId;
    void (async () => {
      try {
        const q = await getPronunciationQuestion(uid, stageLevel, stageMode);
        if (!cancelled) {
          setPhrase(q);
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

  /** Pide la siguiente frase del mismo bucket (avanzar / saltar). */
  function nextCard() {
    setResult(null);
    setAttemptError(null);
    setMicError(null);
    setSeq((s) => s + 1);
  }

  // --- Acciones de sesión (panel de nivel) -----------------------------------

  function startSession(next: PronunciationSession) {
    setResult(null);
    setAttemptError(null);
    setMicError(null);
    setSeq((s) => s + 1);
    setSession(next);
  }

  function exitSession() {
    setSession(null);
    setResult(null);
    setAttemptError(null);
    setMicError(null);
    setRefreshNonce((n) => n + 1);
    setSeq((s) => s + 1);
  }

  /** Avanza tras ver el resultado de una frase (o acaba la sesión). */
  function advance(passed: boolean) {
    if (!session) {
      // Práctica libre (sin sesión): simplemente siguiente frase.
      onAttempt();
      nextCard();
      return;
    }
    let next: PronunciationSession;
    if (session.mode === "drill") {
      next = {
        ...session,
        remaining: drillAnswered(session.remaining, phrase?.id ?? "", passed),
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

  async function toggleRecording() {
    if (recording) {
      recorderRef.current?.stop();
      setRecording(false);
      return;
    }
    if (!phrase) return;
    setMicError(null);
    setAttemptError(null);
    let stream: MediaStream;
    try {
      stream = await getMicrophoneStream();
    } catch (e) {
      setMicError(e instanceof MicUnavailableError ? e.reason : "unknown");
      return;
    }
    try {
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop());
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        if (blob.size === 0 || processedRef.current || !userId || !phrase) return;
        processedRef.current = true;
        setProcessing(true);
        setAttemptError(null);
        try {
          const attempt = await submitPronunciationAttempt(
            userId,
            phrase.id,
            blob,
          );
          setResult(attempt);
          refreshAfterAttempt();
          onAttempt();
        } catch (e) {
          processedRef.current = false;
          setAttemptError((e as Error).message);
        } finally {
          setProcessing(false);
        }
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (e) {
      setAttemptError((e as Error).message);
    }
  }

  if (loadError) {
    return (
      <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center gap-3 px-4 py-16 text-center">
        <p className="text-sm text-destructive">{t("pronRoutes.loadError")}</p>
        <Button
          type="button"
          variant="outline"
          onClick={() => setRefreshNonce((n) => n + 1)}
        >
          {t("pronRoutes.retry")}
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
            {t("pronRoutes.backRoutes")}
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
              {t("skill.pronunciation")}
            </h1>
            <p className="mt-1.5 text-muted-foreground">
              {t("learn.pronunciationSubtitle")}
            </p>
            <p className="mt-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
              {t("pronRoutes.routesSubtitle")}
            </p>
          </header>

          {!stats ? (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              {t("pronRoutes.loading")}
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              {/* ---- Escenario de práctica superior (página única) ---- */}
              {finished && session ? (
                <ActivityResult outcome="ok" title={t("pronRoutes.sessionEnded")}>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {session.mode === "drill"
                      ? t("pronRoutes.doneDrillLine")
                          .replace("{total}", String(session.total))
                          .replace("{level}", session.level)
                      : session.mode === "mastered"
                        ? t("pronRoutes.doneReviewLine")
                            .replace("{total}", String(session.total))
                            .replace("{level}", session.level)
                        : t("pronRoutes.doneLevelLine")
                            .replace("{total}", String(session.total))
                            .replace("{level}", session.level)}
                  </p>
                  <div className="pt-1">
                    <Button type="button" onClick={exitSession}>
                      {t("pronRoutes.backRoutes")}
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
                            ? t("pronRoutes.modeDrill")
                            : session.mode === "mastered"
                              ? t("pronRoutes.modeReview").replace(
                                  "{level}",
                                  session.level,
                                )
                              : t("pronRoutes.modeLevel").replace(
                                  "{level}",
                                  session.level,
                                )}
                        </Badge>
                        <Badge variant="outline" className="tabular-nums">
                          {sessionDone(session)} / {session.total}
                        </Badge>
                        <span className="text-muted-foreground">
                          {session.mode === "drill"
                            ? t("pronRoutes.drillHint")
                            : t("pronRoutes.sessionHint")}
                        </span>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={exitSession}
                      >
                        {t("pronRoutes.exitSession")}
                      </Button>
                    </Card>
                  )}

                  {micError && <MicUnavailableNotice reason={micError} />}

                  <PracticeReadCard
                    phrase={phrase}
                    cardLoading={cardLoading}
                    cardError={cardError}
                    result={result}
                    processing={processing}
                    recording={recording}
                    attemptError={attemptError}
                    onToggleRecording={() => void toggleRecording()}
                    onAdvance={() => {
                      if (!session && !result) {
                        nextCard();
                        return;
                      }
                      if (result) advance(result.passed);
                    }}
                    onSkip={nextCard}
                    onRetry={() => {
                      setAttemptError(null);
                      processedRef.current = false;
                    }}
                    sessionActive={session !== null}
                    isFinished={finished}
                    t={t}
                  />
                </>
              )}

              {/* ---- Rutas A1–C2 (mapa de práctica, espejo de Speaking) ---- */}
              <PronunciationRoutesSection
                userId={userId}
                stats={stats}
                assessedLevel={assessedLevel}
                expandedLevel={expandedLevel}
                setExpandedLevel={setExpandedLevel}
                disabled={session !== null}
                refreshNonce={refreshNonce}
                onStartSession={startSession}
                onDemonstrate={() => setView({ kind: "assessment" })}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface PronunciationRoutesSectionProps {
  userId: string | null;
  stats: PronunciationStats;
  assessedLevel: string | null;
  expandedLevel: string | null;
  setExpandedLevel: (level: string | null) => void;
  disabled: boolean;
  refreshNonce: number;
  onStartSession: (session: PronunciationSession) => void;
  onDemonstrate: () => void;
}

/** Mapa de rutas de pronunciation: resumen + tira de anillos + panel del nivel. */
function PronunciationRoutesSection({
  userId,
  stats,
  assessedLevel,
  expandedLevel,
  setExpandedLevel,
  disabled,
  refreshNonce,
  onStartSession,
  onDemonstrate,
}: PronunciationRoutesSectionProps) {
  const { t } = useI18n();

  return (
    <Card className="gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5 text-xs">
          <span className="font-semibold uppercase tracking-wide text-muted-foreground">
            {t("pronRoutes.routesMapTitle")}
          </span>
          <span className="text-muted-foreground">
            {t("pronRoutes.routesMapHint")}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <ProgressRing
            value={stats.accuracy ?? 0}
            size={58}
            strokeWidth={6}
            ariaLabel={`${t("pronRoutes.accuracy")}: ${
              stats.accuracy !== null ? `${stats.accuracy}%` : "—"
            }`}
          >
            <span className="text-xs font-bold tabular-nums text-foreground">
              {stats.accuracy !== null ? `${Math.round(stats.accuracy)}%` : "—"}
            </span>
          </ProgressRing>
          <div className="flex flex-col gap-0.5 text-xs">
            <span className="font-semibold text-foreground">
              {t("pronRoutes.accuracy")}
            </span>
            <span className="tabular-nums text-muted-foreground">
              {stats.passed} {t("assessment.of")} {stats.attempts}
            </span>
            {assessedLevel ? (
              <Badge variant="outline" className="mt-1 w-fit gap-1">
                <Award className="size-3.5" aria-hidden="true" />
                {t("pronRoutes.assessedLevel").replace(
                  "{level}",
                  assessedLevel,
                )}
              </Badge>
            ) : (
              <span className="mt-0.5 text-muted-foreground">
                {t("pronRoutes.assessedLevelNone")}
              </span>
            )}
          </div>
        </div>
      </div>

      <p className="border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">
        {t("pronRoutes.routeNote").replace("{level}", stats.level)}
      </p>
      <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
        {t("pronRoutes.routeCertNote")}
      </p>

      <div className="flex flex-col border-t border-border pt-4">
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("pronRoutes.routeRingHelp")}
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
                aria-controls="pronunciation-level-items"
                aria-label={t("pronRoutes.levelHistoryTitle").replace(
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
                  ariaLabel={t("pronRoutes.masteredOfTotal")
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
                  {t("pronRoutes.masteredOfTotal")
                    .replace("{mastered}", String(lv.mastered))
                    .replace("{total}", String(lv.total))}
                </span>
                {lv.total > 0 && lv.mastered > 0 && !lv.completed && (
                  <span className="text-[10px] tabular-nums text-muted-foreground">
                    {t("pronRoutes.coveragePct").replace(
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
            id="pronunciation-level-items"
            className="mt-4 border-t border-border pt-4"
          >
            <PronunciationLevelPanel
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

interface PracticeReadCardProps {
  phrase: PronunciationPhrase | null;
  cardLoading: boolean;
  cardError: boolean;
  result: PronunciationAttempt | null;
  processing: boolean;
  recording: boolean;
  attemptError: string | null;
  onToggleRecording: () => void;
  /** Continuar tras un resultado (avanza la sesión) o saltar sin responder. */
  onAdvance: () => void;
  onSkip: () => void;
  onRetry: () => void;
  sessionActive: boolean;
  isFinished: boolean;
  t: TranslateFn;
}

/** Tarjeta del escenario de read-aloud (arriba, siempre visible). */
function PracticeReadCard({
  phrase,
  cardLoading,
  cardError,
  result,
  processing,
  recording,
  attemptError,
  onToggleRecording,
  onAdvance,
  onSkip,
  onRetry,
  t,
}: PracticeReadCardProps) {
  const phraseText = usePhraseTranslation(phrase?.script ?? "");
  const expectedText = usePhraseTranslation(result?.script ?? "");

  if (cardLoading || !phrase) {
    return (
      <Card className="p-8">
        <p className="flex items-center justify-center gap-2 text-center text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          {t("pronRoutes.loading")}
        </p>
      </Card>
    );
  }

  if (cardError) {
    return (
      <Card className="flex flex-col items-center gap-3 p-6 text-center">
        <p className="text-sm text-destructive">{t("pronRoutes.loadError")}</p>
        <Button type="button" variant="outline" onClick={onAdvance}>
          {t("pronRoutes.retry")}
        </Button>
      </Card>
    );
  }

  const outcome = result
    ? result.grade === "good"
      ? "ok"
      : result.grade === "fair"
        ? "neutral"
        : "ko"
    : "ok";
  const hints = result ? feedbackHints(result.breakdown, t) : [];

  return (
    <Card className="gap-4 p-5 sm:p-6">
      {result ? (
        <ActivityResult
          outcome={outcome}
          title={`${t("pron.title")} · ${result.score}/100`}
          footer={
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" onClick={() => onAdvance()}>
                {t("pronRoutes.continue")}
              </Button>
            </div>
          }
        >
          <header className="flex flex-wrap items-center gap-2">
            <Badge
              variant={result.passed ? "default" : "destructive"}
            >
              {result.passed
                ? t("pronRoutes.resultPassed")
                : t("pronRoutes.resultNotPassed")}
            </Badge>
            <span className="text-sm text-muted-foreground">
              {result.grade === "good"
                ? t("pron.level.good")
                : result.grade === "fair"
                  ? t("pron.level.fair")
                  : t("pron.level.needsPractice")}
            </span>
          </header>

          {result.heard && (
            <div className="flex flex-col gap-1 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs">
              <span className="font-semibold text-muted-foreground">
                {t("pron.heard")}
              </span>
              <span className="leading-relaxed text-foreground" lang="en">
                {result.heard}
              </span>
            </div>
          )}

          <div className="flex flex-col gap-2.5">
            <div className="flex items-start justify-between gap-3 text-sm">
              <span className="text-muted-foreground">{t("pron.expected")}:</span>
              <span
                className="flex items-center gap-1.5 text-right text-foreground"
                lang={expectedText.isSpanish ? "es" : "en"}
              >
                {expectedText.display}
                <PhraseTranslateButton state={expectedText} />
              </span>
            </div>
            <div className="flex items-start justify-between gap-3 text-sm">
              <span className="text-muted-foreground">
                {t("pron.wordAccuracy")}
              </span>
              <span className="tabular-nums text-foreground">
                {result.word_accuracy}%
              </span>
            </div>
            <div className="flex items-start justify-between gap-3 text-sm">
              <span className="text-muted-foreground">
                {t("pron.phoneticScore")}
              </span>
              <span className="tabular-nums text-foreground">
                {result.phonetic_score}%
              </span>
            </div>
            <div className="flex items-start justify-between gap-3 text-sm">
              <span className="text-muted-foreground">
                {t("pron.phonemeAccuracy")}
              </span>
              <span className="tabular-nums text-foreground">
                {result.phoneme_accuracy_proxy}%
              </span>
            </div>
            <div className="flex items-start justify-between gap-3 text-sm">
              <span className="text-muted-foreground">{t("pron.prosody")}</span>
              <span className="tabular-nums text-foreground">
                {result.prosody_proxy}%
              </span>
            </div>
            <div className="flex items-start justify-between gap-3 text-sm">
              <span className="text-muted-foreground">{t("pron.fluency")}</span>
              <span className="tabular-nums text-foreground">
                {fluencyLevelLabel(result.fluency.level, t)} ·{" "}
                {wpmLabel(result.fluency.wpm, t)}
              </span>
            </div>
          </div>

          <p className="text-sm text-muted-foreground">
            {wordsCorrectLabel(result.breakdown, t)}
          </p>
          {hints.length > 0 && (
            <ul className="flex flex-col gap-1 text-sm text-foreground">
              {hints.map((hint) => (
                <li key={hint}>{hint}</li>
              ))}
            </ul>
          )}
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {t("pronRoutes.resultHonestNote")}
          </p>
        </ActivityResult>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-[10px] normal-case">
                {phrase.topic.replace(/_/g, " ")}
              </Badge>
              <Badge variant="secondary">{phrase.level}</Badge>
            </div>
            <span className="text-[11px] text-muted-foreground">
              {t("pronRoutes.phraseHint")}
            </span>
          </div>

          {/* Frase a leer en voz alta */}
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("pronRoutes.scriptLabel")}
              </p>
              <div className="flex items-center gap-1.5">
                <PhraseTranslateButton state={phraseText} />
                <ListenButton text={phrase.script} label={t("speak.phrase")} />
              </div>
            </div>
            <p
              className="rounded-xl border border-border bg-secondary/30 px-4 py-4 text-center text-lg font-medium leading-relaxed tracking-wide text-foreground sm:text-xl"
              lang={phraseText.isSpanish ? "es" : "en"}
            >
              {phraseText.display}
            </p>
          </div>

          {attemptError && (
            <div
              role="alert"
              className="flex flex-col items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-center text-xs text-destructive"
            >
              <p className="break-words">{attemptError}</p>
              <Button type="button" variant="outline" size="sm" onClick={onRetry}>
                {t("pronRoutes.retry")}
              </Button>
            </div>
          )}

          <div className="flex flex-col items-center gap-1.5">
            <Button
              type="button"
              size="lg"
              className={cn(
                "min-h-14 gap-2 px-8",
                recording &&
                  "bg-destructive text-destructive-foreground hover:bg-destructive/90",
              )}
              onClick={onToggleRecording}
              disabled={processing}
            >
              {recording ? (
                <Square className="size-5" aria-hidden="true" />
              ) : processing ? (
                <RefreshCw className="size-5 animate-spin" aria-hidden="true" />
              ) : (
                <Mic className="size-5" aria-hidden="true" />
              )}
              {processing
                ? t("pron.evaluating")
                : recording
                  ? t("pron.stop")
                  : t("pron.record")}
            </Button>
            <span className="text-xs text-muted-foreground">
              {t("pronRoutes.recordHint")}
            </span>
          </div>

          {!processing && !recording && (
            <div className="flex justify-end">
              <Button type="button" variant="ghost" size="sm" onClick={onSkip}>
                {t("pronRoutes.skip")}
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
