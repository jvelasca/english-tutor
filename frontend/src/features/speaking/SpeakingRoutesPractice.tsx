/**
 * APRENDER → Speaking por rutas (V3.8), migrada al marco compartido de quiz
 * (V3.13 P2.1, wave 3).
 *
 * La página única con scroll (estadísticas, máquina de sesión, mapa A1–C2,
 * panel del nivel y acceso al Speaking Assessment) vive en
 * `features/routes/QuizRoutePage.tsx`. Este archivo aporta la configuración
 * (namespace i18n, API, panel con práctica extra), la **escena personalizada
 * de micro-conversación guiada** (grabación + evaluación + respuesta modelo
 * con voz) y los desplegables contextuales (escenarios y misiones) que también
 * aportan evidencia oral.
 */
import { useRef, useState } from "react";
import {
  ChevronDown,
  Loader2,
  Mic,
  RefreshCw,
  Square,
  Volume2,
} from "lucide-react";
import { useI18n } from "../../hooks/useI18n";
import type { LearnActivity } from "../../router/learnHub";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { SkillBar } from "../../components/SkillBar";
import { ActivityResult } from "../../components/ActivityResult";
import { ListenButton } from "../../components/ListenButton";
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
} from "../../api/speakingRoutes";
import { getSpeakingLevel } from "../../api/academy";
import { speak } from "../../api/voz";
import { criterionLabel } from "../../utils/speaking";
import { cn } from "../../lib/utils";
import type {
  NextBestActivity,
  SpeakingAttempt,
  SpeakingExtrasJob,
  SpeakingPhrase,
} from "../../types/api";
import type { Section } from "../../utils/sections";
import {
  QuizRoutePage,
  type LearnSceneProps,
  type RouteLevelPanelProps,
  type RouteQuizConfig,
} from "../routes/QuizRoutePage";
import { SpeakingLevelPanel } from "./SpeakingLevelPanel";
import { SpeakingScenarios } from "./SpeakingScenarios";
import { SpeakingMission } from "./SpeakingMission";

/* ------------------------------------------------------------------ */
/* Config de la destreza                                                */
/* ------------------------------------------------------------------ */

const SPEAKING_ROUTE_CONFIG: RouteQuizConfig = {
  ns: "speaking",
  skillTitleKey: "skill.speaking",
  subtitleKey: "learn.speakingSubtitle",
  ariaLevelItemsId: "speaking-level-items",
  assessment: "speaking",
  loadAssessed: (userId) =>
    getSpeakingLevel(userId).then((r) => r.level ?? null),
  LevelPanel: SpeakingLevelPanelRoute,
  scene: SpeakingScene,
  trailing: SpeakingContextualBlocks,
  api: {
    getStats: (userId) => getSpeakingStats(userId),
    getQuestion: (userId, level, mode) =>
      getSpeakingQuestion(userId, level, mode),
    submitAttempt: () =>
      Promise.reject(
        new Error(
          "speaking no usa /attempt directo: la escena envía el audio por su API.",
        ),
      ),
  },
};

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

export function SpeakingRoutesPractice(props: SpeakingRoutesPracticeProps) {
  return (
    <QuizRoutePage
      userId={props.userId}
      active={props.active}
      onBack={props.onBack}
      onAttempt={props.onAttempt}
      onNext={props.onNext}
      config={SPEAKING_ROUTE_CONFIG}
    />
  );
}

/* ------------------------------------------------------------------ */
/* Panel de nivel con práctica extra (envuelve SpeakingLevelPanel)      */
/* ------------------------------------------------------------------ */

/**
 * SpeakingLevelPanel necesita gestionar el job de "añadir práctica extra"
 * (generación local de +10/+25/+50 tarjetas). El adaptador posee ese estado y
 * se lo entrega al panel, de modo que la página compartida no necesita conocer
 * esta lógica específica de speaking.
 */
function SpeakingLevelPanelRoute(props: RouteLevelPanelProps) {
  const [extrasJob, setExtrasJob] = useState<SpeakingExtrasJob | null>(null);

  async function pollExtrasJob(level: string, jobId: string) {
    if (!props.userId) return;
    let done = false;
    while (!done) {
      try {
        const job = await getSpeakingRouteExtrasJob(
          props.userId,
          level,
          jobId,
        );
        setExtrasJob(job);
        if (job.status !== "running") done = true;
        else await new Promise((r) => setTimeout(r, 2500));
      } catch {
        done = true;
      }
    }
  }

  async function handleAddExtras(level: string, count: number) {
    if (!props.userId) return;
    setExtrasJob(null);
    try {
      const job = await addSpeakingRouteExtras(props.userId, level, count);
      setExtrasJob(job);
      void pollExtrasJob(level, job.job_id);
    } catch {
      /* el panel muestra el estado running/done; error por polling */
    }
  }

  return (
    <SpeakingLevelPanel
      {...props}
      extrasJob={extrasJob?.level === props.level ? extrasJob : null}
      onAddExtras={(level, count) => void handleAddExtras(level, count)}
    />
  );
}

/* ------------------------------------------------------------------ */
/* Escena de micro-conversación guiada (vive en la página compartida)   */
/* ------------------------------------------------------------------ */

/**
 * Escena superior de speaking: tarjeta de micro-conversación guiada
 * (situación + rol + línea del interlocutor con voz; el alumno responde
 * hablando). La grabación, la evaluación y la respuesta modelo son estado
 * local; la página avanza la sesión con `onAnswered(id, passed)`.
 */
export function SpeakingScene({
  userId,
  item,
  itemLoading,
  itemError,
  onReport,
  onAnswered,
  onSkip,
}: LearnSceneProps) {
  const card = item as SpeakingPhrase | null;
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<SpeakingAttempt | null>(null);
  const [attemptError, setAttemptError] = useState<string | null>(null);
  const [micError, setMicError] = useState<MicUnavailableReason | null>(null);
  const [playing, setPlaying] = useState<"opening" | "model" | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const processedRef = useRef(false);

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
        if (blob.size === 0 || processedRef.current || !userId || !card) {
          return;
        }
        processedRef.current = true;
        setProcessing(true);
        setAttemptError(null);
        try {
          const attempt = await submitSpeakingAttempt(userId, card.id, blob);
          setResult(attempt);
          onReport();
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

  return (
    <>
      {micError && <MicUnavailableNotice reason={micError} />}
      <PracticeExchangeCard
        card={card}
        cardLoading={itemLoading}
        cardError={itemError}
        result={result}
        processing={processing}
        recording={recording}
        playing={playing}
        attemptError={attemptError}
        onToggleRecording={() => void toggleRecording()}
        onPlay={(kind) => void playAudio(kind)}
        onAdvance={() => {
          if (card && result) onAnswered(card.id, result.passed);
        }}
        onSkip={onSkip}
        onRetry={() => {
          setAttemptError(null);
          processedRef.current = false;
        }}
      />
    </>
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
}: PracticeExchangeCardProps) {
  const { t } = useI18n();
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
        <Button type="button" variant="outline" onClick={onSkip}>
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
              <Button type="button" onClick={onAdvance}>
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

/* ------------------------------------------------------------------ */
/* Práctica contextual tras el mapa (escenarios y misiones)             */
/* ------------------------------------------------------------------ */

/** Desplegables de SpeakingScenarios y SpeakingMission (evidencia oral). */
function SpeakingContextualBlocks({ userId }: { userId: string | null }) {
  const { t } = useI18n();
  const [showScenarios, setShowScenarios] = useState(false);
  const [showMissions, setShowMissions] = useState(false);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-3">
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
        {showScenarios && userId && <SpeakingScenarios userId={userId} />}
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
        {showMissions && userId && <SpeakingMission userId={userId} />}
      </div>
    </div>
  );
}
