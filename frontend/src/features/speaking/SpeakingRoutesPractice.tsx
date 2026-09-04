import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Award,
  Check,
  ChevronDown,
  Loader2,
  Mic,
  RefreshCw,
  Square,
  Volume2,
} from "lucide-react";
import { useI18n } from "../../hooks/useI18n";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { SkillBar } from "../../components/SkillBar";
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
  getSpeakingQuestion,
  getSpeakingStats,
  getSpeakingAudioUrl,
  submitSpeakingAttempt,
  addSpeakingRouteExtras,
  getSpeakingRouteExtrasJob,
  type SpeakingQuestionMode,
} from "../../api/speakingRoutes";
import { getSpeakingLevel } from "../../api/academy";
import { speak } from "../../api/voz";
import { criterionLabel } from "../../utils/speaking";
import type {
  NextBestActivity,
  SpeakingAttempt,
  SpeakingExtrasJob,
  SpeakingPhrase,
  SpeakingStats,
} from "../../types/api";
import type { Section } from "../../utils/sections";
import { cn } from "../../lib/utils";
import {
  drillAnswered,
  isSessionFinished,
  sessionDone,
  type SpeakingSession,
} from "./speakingSession";
import { SpeakingLevelPanel } from "./SpeakingLevelPanel";
import { SpeakingAssessment } from "./SpeakingAssessment";
import { SpeakingScenarios } from "./SpeakingScenarios";
import { SpeakingMission } from "./SpeakingMission";

interface SpeakingRoutesPracticeProps {
  userId: string | null;
  /** Actividad activa (Speaking) para el atajo de la franja superior. */
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
function speakingMode(session: SpeakingSession | null): SpeakingQuestionMode {
  if (!session) return "all";
  return session.mode === "drill"
    ? "failed"
    : session.mode === "mastered"
      ? "mastered"
      : "all";
}

/**
 * APRENDER → Speaking por rutas (V3.8): página única con scroll, como Listening.
 *
 * El escenario de práctica vive arriba: una tarjeta de micro-conversación guiada
 * (situación + rol + línea del interlocutor con voz modelo; el alumno responde
 * hablando y tras la evaluación se revela la respuesta modelo). Debajo, el panel
 * de rutas A1–C2 con anillos y, al abrir un nivel, sus modos (practicar / repetir
 * fallidas / repasar aprendidas / añadir práctica extra) y el acceso al Speaking
 * Assessment. La ruta es un hito de práctica (techo `functional`); demostrar el
 * nivel exige examen + evidencia formal, no la ruta.
 */
export function SpeakingRoutesPractice({
  userId,
  active,
  onBack,
  onAttempt,
  onNext,
}: SpeakingRoutesPracticeProps) {
  const { t } = useI18n();
  const [view, setView] = useState<RouteView>({ kind: "routes" });
  const [stats, setStats] = useState<SpeakingStats | null>(null);
  const [assessedLevel, setAssessedLevel] = useState<string | null>(null);
  const [expandedLevel, setExpandedLevel] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);
  // Sesión focalizada activa (drill / repaso / vuelta del nivel). Sin sesión, el
  // escenario practica la ruta recomendada (stats.level) en modo libre.
  const [session, setSession] = useState<SpeakingSession | null>(null);
  // Tarjeta de intercambio activa del escenario superior.
  const [card, setCard] = useState<SpeakingPhrase | null>(null);
  const [cardLoading, setCardLoading] = useState(false);
  const [cardError, setCardError] = useState(false);
  const [result, setResult] = useState<SpeakingAttempt | null>(null);
  // Seq de "siguiente tarjeta": avanzar tras responder o saltar la recarga.
  const [seq, setSeq] = useState(0);
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [attemptError, setAttemptError] = useState<string | null>(null);
  const [micError, setMicError] = useState<MicUnavailableReason | null>(null);
  const [playing, setPlaying] = useState<"opening" | "model" | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const processedRef = useRef(false);
  const [showScenarios, setShowScenarios] = useState(false);
  const [showMissions, setShowMissions] = useState(false);
  // Job de práctica extra activo por nivel (si el panel pide +10/+25/+50).
  const [extrasJob, setExtrasJob] = useState<SpeakingExtrasJob | null>(null);

  // --- Carga inicial de estadísticas y nivel oral demostrado ------------------
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setLoadError(false);
    const uid = userId;
    void (async () => {
      try {
        const [s, lvl] = await Promise.all([
          getSpeakingStats(uid),
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

  // --- Tarjeta de intercambio activa del escenario ---------------------------
  const finished = session !== null && isSessionFinished(session);
  const stageLevel = session?.level ?? stats?.level ?? null;
  const stageMode = speakingMode(session);

  useEffect(() => {
    if (!userId || finished || !stageLevel) return;
    let cancelled = false;
    setCardLoading(true);
    setCardError(false);
    setCard(null);
    setResult(null);
    setAttemptError(null);
    processedRef.current = false;
    const uid = userId;
    void (async () => {
      try {
        const q = await getSpeakingQuestion(uid, stageLevel, stageMode);
        if (!cancelled) {
          setCard(q);
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

  /** Pide la siguiente tarjeta del mismo bucket (avanzar / saltar). */
  function nextCard() {
    setResult(null);
    setAttemptError(null);
    setMicError(null);
    setSeq((s) => s + 1);
  }

  // --- Acciones de sesión (panel de nivel) -----------------------------------

  function startSession(next: SpeakingSession) {
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

  /** Avanza tras ver el resultado de una tarjeta (o acaba la sesión). */
  function advance(passed: boolean) {
    if (!session) {
      // Práctica libre (sin sesión): simplemente siguiente tarjeta.
      onAttempt();
      nextCard();
      return;
    }
    let next: SpeakingSession;
    if (session.mode === "drill") {
      next = {
        ...session,
        remaining: drillAnswered(session.remaining, card?.id ?? "", passed),
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

  /** Reproduce la voz modelo de la línea del interlocutor o de la respuesta. */
  async function playAudio(kind: "opening" | "model") {
    if (!card || !userId) return;
    const text = kind === "model" ? (result?.model_response ?? "") : card.app_line;
    if (!text) return;
    setPlaying(kind);
    try {
      const url = getSpeakingAudioUrl(card.id, userId, kind);
      if (!audioRef.current) audioRef.current = new Audio();
      const audio = audioRef.current;
      audio.src = url;
      await audio.play();
      audio.onended = () => setPlaying(null);
      audio.onerror = () => {
        audio.onerror = null;
        setPlaying(null);
        void speak(text);
      };
    } catch {
      setPlaying(null);
      try {
        await speak(text);
      } catch {
        /* sin voz: el alumno puede responder igualmente */
      }
    }
  }

  async function toggleRecording() {
    if (recording) {
      recorderRef.current?.stop();
      setRecording(false);
      return;
    }
    if (!card) return;
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
        if (blob.size === 0 || processedRef.current || !userId || !card) return;
        processedRef.current = true;
        setProcessing(true);
        setAttemptError(null);
        try {
          const attempt = await submitSpeakingAttempt(userId, card.id, blob);
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
        <p className="text-sm text-destructive">{t("speaking.loadError")}</p>
        <Button
          type="button"
          variant="outline"
          onClick={() => setRefreshNonce((n) => n + 1)}
        >
          {t("speaking.retry")}
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
            {t("speaking.backRoutes")}
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <SpeakingAssessment userId={userId} onAttempt={onAttempt} onNext={onNext} />
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
              {t("skill.speaking")}
            </h1>
            <p className="mt-1.5 text-muted-foreground">{t("learn.speakingSubtitle")}</p>
            <p className="mt-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
              {t("speaking.routesSubtitle")}
            </p>
          </header>

          {!stats ? (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              {t("speaking.loading")}
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              {/* ---- Escenario de práctica superior (página única) ---- */}
              {finished && session ? (
                <ActivityResult outcome="ok" title={t("speaking.sessionEnded")}>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {session.mode === "drill"
                      ? t("speaking.doneDrillLine")
                          .replace("{total}", String(session.total))
                          .replace("{level}", session.level)
                      : session.mode === "mastered"
                        ? t("speaking.doneReviewLine")
                            .replace("{total}", String(session.total))
                            .replace("{level}", session.level)
                        : t("speaking.doneLevelLine")
                            .replace("{total}", String(session.total))
                            .replace("{level}", session.level)}
                  </p>
                  <div className="pt-1">
                    <Button type="button" onClick={exitSession}>
                      {t("speaking.backRoutes")}
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
                            ? t("speaking.modeDrill")
                            : session.mode === "mastered"
                              ? t("speaking.modeReview").replace(
                                  "{level}",
                                  session.level,
                                )
                              : t("speaking.modeLevel").replace(
                                  "{level}",
                                  session.level,
                                )}
                        </Badge>
                        <Badge variant="outline" className="tabular-nums">
                          {sessionDone(session)} / {session.total}
                        </Badge>
                        <span className="text-muted-foreground">
                          {session.mode === "drill"
                            ? t("speaking.drillHint")
                            : t("speaking.sessionHint")}
                        </span>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={exitSession}
                      >
                        {t("speaking.exitSession")}
                      </Button>
                    </Card>
                  )}

                  {micError && <MicUnavailableNotice reason={micError} />}

                  <PracticeExchangeCard
                    card={card}
                    cardLoading={cardLoading}
                    cardError={cardError}
                    result={result}
                    processing={processing}
                    recording={recording}
                    playing={playing}
                    attemptError={attemptError}
                    onToggleRecording={() => void toggleRecording()}
                    onPlay={(kind) => void playAudio(kind)}
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

              {/* ---- Rutas A1–C2 (mapa de práctica, espejo de Listening) ---- */}
              <SpeakingRoutesSection
                userId={userId}
                stats={stats}
                assessedLevel={assessedLevel}
                expandedLevel={expandedLevel}
                setExpandedLevel={setExpandedLevel}
                disabled={session !== null}
                refreshNonce={refreshNonce}
                extrasJob={extrasJob?.level === expandedLevel ? extrasJob : null}
                onStartSession={startSession}
                onDemonstrate={() => setView({ kind: "assessment" })}
                onAddExtras={async (level, count) => {
                  if (!userId) return;
                  setExtrasJob(null);
                  try {
                    const job = await addSpeakingRouteExtras(userId, level, count);
                    setExtrasJob(job);
                    pollExtrasJob(level, job.job_id);
                  } catch {
                    /* el panel muestra el estado running/done; error por polling */
                  }
                }}
              />

              {/* Práctica contextual que también aporta evidencia oral. */}
              <div className="mt-2 flex flex-col gap-3">
                <button
                  type="button"
                  onClick={() => setShowScenarios((s) => !s)}
                  aria-expanded={showScenarios}
                  className="flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-card px-5 py-3.5 text-left shadow-sm"
                >
                  <span className="text-base font-bold tracking-tight text-foreground">
                    {t("scenarios.title")}
                  </span>
                  <ChevronDown
                    className={cn(
                      "size-4 shrink-0 text-muted-foreground transition-transform",
                      showScenarios && "rotate-180",
                    )}
                    aria-hidden="true"
                  />
                </button>
                {showScenarios && <SpeakingScenarios userId={userId} />}
              </div>
              <div className="flex flex-col gap-3">
                <button
                  type="button"
                  onClick={() => setShowMissions((s) => !s)}
                  aria-expanded={showMissions}
                  className="flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-card px-5 py-3.5 text-left shadow-sm"
                >
                  <span className="text-base font-bold tracking-tight text-foreground">
                    {t("panels.speakingMission")}
                  </span>
                  <ChevronDown
                    className={cn(
                      "size-4 shrink-0 text-muted-foreground transition-transform",
                      showMissions && "rotate-180",
                    )}
                    aria-hidden="true"
                  />
                </button>
                {showMissions && <SpeakingMission userId={userId} />}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  /** Sonda el job de práctica extra hasta que termina (patrón de listening). */
  async function pollExtrasJob(level: string, jobId: string) {
    if (!userId) return;
    let done = false;
    while (!done) {
      try {
        const job = await getSpeakingRouteExtrasJob(userId, level, jobId);
        setExtrasJob(job);
        if (job.status !== "running") done = true;
        else await new Promise((r) => setTimeout(r, 2500));
      } catch {
        done = true;
      }
    }
  }
}

interface SpeakingRoutesSectionProps {
  userId: string | null;
  stats: SpeakingStats;
  assessedLevel: string | null;
  expandedLevel: string | null;
  setExpandedLevel: (level: string | null) => void;
  disabled: boolean;
  refreshNonce: number;
  extrasJob: SpeakingExtrasJob | null;
  onStartSession: (session: SpeakingSession) => void;
  onDemonstrate: () => void;
  onAddExtras: (level: string, count: number) => void;
}

/** Mapa de rutas de speaking: resumen + tira de anillos + panel del nivel. */
function SpeakingRoutesSection({
  userId,
  stats,
  assessedLevel,
  expandedLevel,
  setExpandedLevel,
  disabled,
  refreshNonce,
  extrasJob,
  onStartSession,
  onDemonstrate,
  onAddExtras,
}: SpeakingRoutesSectionProps) {
  const { t } = useI18n();

  return (
    <Card className="gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5 text-xs">
          <span className="font-semibold uppercase tracking-wide text-muted-foreground">
            {t("speaking.routesMapTitle")}
          </span>
          <span className="text-muted-foreground">{t("speaking.routesMapHint")}</span>
        </div>
        <div className="flex items-center gap-3">
          <ProgressRing
            value={stats.accuracy ?? 0}
            size={58}
            strokeWidth={6}
            ariaLabel={`${t("speaking.accuracy")}: ${
              stats.accuracy !== null ? `${stats.accuracy}%` : "—"
            }`}
          >
            <span className="text-xs font-bold tabular-nums text-foreground">
              {stats.accuracy !== null ? `${Math.round(stats.accuracy)}%` : "—"}
            </span>
          </ProgressRing>
          <div className="flex flex-col gap-0.5 text-xs">
            <span className="font-semibold text-foreground">{t("speaking.accuracy")}</span>
            <span className="tabular-nums text-muted-foreground">
              {stats.passed} {t("assessment.of")} {stats.attempts}
            </span>
            {assessedLevel ? (
              <Badge variant="outline" className="mt-1 w-fit gap-1">
                <Award className="size-3.5" aria-hidden="true" />
                {t("speaking.assessedLevel").replace("{level}", assessedLevel)}
              </Badge>
            ) : (
              <span className="mt-0.5 text-muted-foreground">
                {t("speaking.assessedLevelNone")}
              </span>
            )}
          </div>
        </div>
      </div>

      <p className="border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">
        {t("speaking.routeNote").replace("{level}", stats.level)}
      </p>
      <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
        {t("speaking.routeCertNote")}
      </p>

      <div className="flex flex-col border-t border-border pt-4">
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("speaking.routeRingHelp")}
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
                aria-controls="speaking-level-items"
                aria-label={t("speaking.levelHistoryTitle").replace(
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
                      : lv.state === "functional"
                        ? "text-primary"
                        : lv.mastered > 0
                          ? "text-primary"
                          : "text-muted-foreground"
                  }
                  ariaLabel={t("speaking.masteredOfTotal")
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
                  {t("speaking.masteredOfTotal")
                    .replace("{mastered}", String(lv.mastered))
                    .replace("{total}", String(lv.total))}
                </span>
                {lv.total > 0 && lv.mastered > 0 && !lv.completed && (
                  <span className="text-[10px] tabular-nums text-muted-foreground">
                    {t("speaking.coveragePct").replace(
                      "{pct}",
                      String(Math.round((lv.mastered / lv.total) * 100)),
                    )}
                  </span>
                )}
                {(lv.extras ?? 0) > 0 && (
                  <span className="max-w-[140px] text-center text-[9px] leading-tight tabular-nums text-muted-foreground">
                    {t("speaking.extraBreakdown")
                      .replace(
                        "{base}",
                        String(lv.base_total ?? lv.total - (lv.extras ?? 0)),
                      )
                      .replace("{extras}", String(lv.extras))}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {expandedLevel !== null && !disabled && (
          <div id="speaking-level-items" className="mt-4 border-t border-border pt-4">
            <SpeakingLevelPanel
              userId={userId}
              level={expandedLevel}
              routeState={
                stats.levels.find((lv) => lv.level === expandedLevel)?.state
              }
              assessedLevel={assessedLevel}
              disabled={disabled}
              extrasJob={extrasJob}
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
              onAddExtras={onAddExtras}
            />
          </div>
        )}
      </div>
    </Card>
  );
}

interface PracticeExchangeCardProps {
  card: SpeakingPhrase | null;
  cardLoading: boolean;
  cardError: boolean;
  result: SpeakingAttempt | null;
  processing: boolean;
  recording: boolean;
  playing: "opening" | "model" | null;
  attemptError: string | null;
  onToggleRecording: () => void;
  onPlay: (kind: "opening" | "model") => void;
  /** Continuar tras un resultado (avanza la sesión) o saltar sin responder. */
  onAdvance: () => void;
  onSkip: () => void;
  onRetry: () => void;
  sessionActive: boolean;
  isFinished: boolean;
  t: (k: string) => string;
}

/** Tarjeta del escenario de micro-conversación guiada (arriba, siempre visible). */
function PracticeExchangeCard({
  card,
  cardLoading,
  cardError,
  result,
  processing,
  recording,
  playing,
  attemptError,
  onToggleRecording,
  onPlay,
  onAdvance,
  onSkip,
  onRetry,
  t,
}: PracticeExchangeCardProps) {
  const appLine = usePhraseTranslation(card?.app_line ?? "");
  const modelText = usePhraseTranslation(result?.model_response ?? "");

  if (cardLoading || !card) {
    return (
      <Card className="p-8">
        <p className="flex items-center justify-center gap-2 text-center text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          {t("speaking.loading")}
        </p>
      </Card>
    );
  }

  if (cardError) {
    return (
      <Card className="flex flex-col items-center gap-3 p-6 text-center">
        <p className="text-sm text-destructive">{t("speaking.loadError")}</p>
        <Button type="button" variant="outline" onClick={onAdvance}>
          {t("speaking.retry")}
        </Button>
      </Card>
    );
  }

  return (
    <Card className="gap-4 p-5 sm:p-6">
      {result ? (
        <ActivityResult
          outcome={result.passed ? "ok" : "ko"}
          title={result.passed ? t("speaking.passedTitle") : t("speaking.notPassedTitle")}
          footer={
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" onClick={() => onAdvance()}>
                {t("speaking.continue")}
              </Button>
            </div>
          }
        >
          <header className="flex flex-wrap items-center gap-2">
            <Badge variant={result.passed ? "default" : "destructive"}>
              {result.passed
                ? t("speaking.resultPassed")
                : t("speaking.resultNotPassed")}
            </Badge>
            <span className="text-sm tabular-nums text-foreground">
              {Math.round(result.overall * 100)}% {t("speaking.overallShort")}
            </span>
          </header>

          {result.heard && (
            <div className="flex flex-col gap-1 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs">
              <span className="font-semibold text-muted-foreground">
                {t("speaking.youSaidLabel")}
              </span>
              <span className="leading-relaxed text-foreground" lang="en">
                {result.heard}
              </span>
            </div>
          )}

          <div className="flex flex-col gap-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t("speaking.criteriaIntro")}
            </p>
            {Object.entries(result.criteria).map(([name, value]) =>
              value === null || value === undefined ? null : (
                <SkillBar
                  key={name}
                  label={criterionLabel(name)}
                  value={value}
                  hint={`${Math.round(value * 100)}%`}
                />
              ),
            )}
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              {t("speaking.resultHonestNote")}
            </p>
          </div>

          {/* Respuesta modelo revelada tras la evaluación */}
          {result.model_response && (
            <div className="flex flex-col gap-2 rounded-lg border border-primary/25 bg-primary/5 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                  {t("speaking.modelResponseTitle")}
                </p>
                <div className="flex items-center gap-1.5">
                  <PhraseTranslateButton state={modelText} />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="min-h-8 gap-1.5 px-2.5 text-xs"
                    onClick={() => onPlay("model")}
                    disabled={playing === "model"}
                  >
                    {playing === "model" ? (
                      <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                    ) : (
                      <Volume2 className="size-3.5" aria-hidden="true" />
                    )}
                    {t("speaking.playModel")}
                  </Button>
                </div>
              </div>
              <p
                className="text-base font-medium leading-relaxed text-foreground"
                lang="en"
              >
                {result.model_response}
              </p>
            </div>
          )}
        </ActivityResult>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-[10px] normal-case">
                {card.topic.replace(/_/g, " ")}
              </Badge>
              <Badge variant="secondary">{card.level}</Badge>
            </div>
            <span className="text-[11px] text-muted-foreground">
              {t("speaking.exchangeHint")}
            </span>
          </div>

          {/* Situación y rol */}
          {(card.setup || card.you) && (
            <div className="flex flex-col gap-1 rounded-lg border border-border bg-muted/30 px-4 py-3 text-sm">
              {card.setup && (
                <p className="leading-relaxed text-muted-foreground" lang="en">
                  <span className="font-semibold text-foreground">
                    {t("speaking.setupLabel")}:{" "}
                  </span>
                  {card.setup}
                </p>
              )}
              {card.you && (
                <p className="leading-relaxed text-foreground" lang="en">
                  <span className="font-semibold text-foreground">
                    {t("speaking.roleLabel")}:{" "}
                  </span>
                  {card.you}
                </p>
              )}
            </div>
          )}

          {/* Línea del interlocutor */}
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("speaking.interlocutorLabel")}
              </p>
              <div className="flex items-center gap-1.5">
                <PhraseTranslateButton state={appLine} />
                <ListenButton text={card.app_line} label={t("speak.phrase")} />
              </div>
            </div>
            <p
              className="rounded-xl border border-border bg-secondary/30 px-4 py-4 text-center text-lg font-medium leading-relaxed tracking-wide text-foreground sm:text-xl"
              lang="en"
            >
              {card.app_line}
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button
              type="button"
              variant="outline"
              className="min-h-9 gap-2"
              onClick={() => onPlay("opening")}
              disabled={playing === "opening"}
            >
              {playing === "opening" ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Volume2 className="size-4" aria-hidden="true" />
              )}
              {t("speaking.playOpening")}
            </Button>
          </div>

          {attemptError && (
            <div
              role="alert"
              className="flex flex-col items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-center text-xs text-destructive"
            >
              <p className="break-words">{attemptError}</p>
              <Button type="button" variant="outline" size="sm" onClick={onRetry}>
                {t("speaking.retry")}
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
                ? t("speaking.evaluating")
                : recording
                  ? t("speaking.stop")
                  : t("speaking.record")}
            </Button>
            <span className="text-xs text-muted-foreground">
              {t("speaking.recordHint")}
            </span>
          </div>

          {!processing && !recording && (
            <div className="flex justify-end">
              <Button type="button" variant="ghost" size="sm" onClick={onSkip}>
                {t("speaking.skip")}
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
