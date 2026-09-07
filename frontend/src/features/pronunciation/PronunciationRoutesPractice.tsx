/**
 * APRENDER → Pronunciation por rutas (V3.9), migrada al marco compartido de
 * quiz (V3.13 P2.1, wave 2).
 *
 * La página única con scroll (estadísticas, máquina de sesión, mapa A1–C2,
 * panel del nivel y acceso al Speaking Assessment) vive en
 * `features/routes/QuizRoutePage.tsx`. Este archivo aporta la configuración
 * (namespace i18n, API, panel) y la **escena personalizada de read-aloud**:
 * frase modelo con TTS, grabación con el micrófono y corrección determinista
 * del score fonético (sin LLM).
 */
import { useEffect, useRef, useState } from "react";
import { Loader2, Mic, RefreshCw, Square } from "lucide-react";
import { useI18n } from "../../hooks/useI18n";
import { useRecordingSession } from "../../hooks/useRecordingSession";
import type { LearnActivity } from "../../router/learnHub";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { ActivityResult } from "../../components/ActivityResult";
import { ListenButton } from "../../components/ListenButton";
import { RecordingPlayButton } from "../../components/RecordingPlayButton";
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
} from "../../api/pronunciationRoutes";
import { getSpeakingLevel } from "../../api/academy";
import { fluencyLevelLabel, wpmLabel } from "../../utils/fluency";
import {
  feedbackHints,
  wordsCorrectLabel,
} from "../../utils/pronunciationFeedback";
import { alignWords, type WordChipState } from "../../utils/pronunciationAlignment";
import type {
  NextBestActivity,
  PronunciationAttempt,
  PronunciationPhrase,
} from "../../types/api";
import type { Section } from "../../utils/sections";
import {
  QuizRoutePage,
  type LearnSceneProps,
  type RouteQuizConfig,
} from "../routes/QuizRoutePage";
import { PronunciationLevelPanel } from "./PronunciationLevelPanel";

/* ------------------------------------------------------------------ */
/* Config de la destreza                                                */
/* ------------------------------------------------------------------ */

/**
 * Config de la destreza. Desde DISENO-SPEAKING-UNICO (F1) esta configuración
 * se reutiliza como **modo Acento** de la página unificada Speaking
 * (`features/speaking/SpeakingRoutesPractice.tsx`), que sobrescribe el título
 * de superficie con "Speaking".
 */
export const PRONUNCIATION_ROUTE_CONFIG: RouteQuizConfig = {
  ns: "pronRoutes",
  skillTitleKey: "skill.pronunciation",
  subtitleKey: "learn.pronunciationSubtitle",
  ariaLevelItemsId: "pronunciation-level-items",
  assessment: "speaking",
  loadAssessed: (userId) =>
    getSpeakingLevel(userId).then((r) => r.level ?? null),
  LevelPanel: PronunciationLevelPanel,
  scene: PronunciationScene,
  api: {
    getStats: (userId) => getPronunciationStats(userId),
    getQuestion: (userId, level, mode) =>
      getPronunciationQuestion(userId, level, mode),
    submitAttempt: () =>
      Promise.reject(
        new Error(
          "read-aloud no usa /attempt: la escena envía el audio por su API.",
        ),
      ),
  },
};

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

export function PronunciationRoutesPractice(
  props: PronunciationRoutesPracticeProps,
) {
  return (
    <QuizRoutePage
      userId={props.userId}
      active={props.active}
      onBack={props.onBack}
      onAttempt={props.onAttempt}
      onNext={props.onNext}
      config={PRONUNCIATION_ROUTE_CONFIG}
    />
  );
}

/* ------------------------------------------------------------------ */
/* Escena de read-aloud (vive en la página compartida)                  */
/* ------------------------------------------------------------------ */

/**
 * Escena superior de pronunciation: frase modelo (escucha + lee en voz alta).
 * La grabación y el score fonético son estado local; la página solo avanza la
 * sesión con `onAnswered(id, passed)` cuando el alumno pulsa Continuar.
 */
export function PronunciationScene({
  userId,
  item,
  itemLoading,
  itemError,
  onReport,
  onAnswered,
  onSkip,
}: LearnSceneProps) {
  const phrase = item as PronunciationPhrase | null;
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<PronunciationAttempt | null>(null);
  const [attemptError, setAttemptError] = useState<string | null>(null);
  const [micError, setMicError] = useState<MicUnavailableReason | null>(null);
  // Object URL de la grabación real del alumno (no sube al servidor: solo se
  // transcribe). Permite «Oír mi grabación» junto a la frase modelo.
  const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const processedRef = useRef(false);

  // Libera el object URL de la grabación al cambiar o al desmontar la escena.
  useEffect(() => {
    const url = recordingUrl;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [recordingUrl]);

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
        if (blob.size === 0 || processedRef.current || !userId || !phrase) {
          return;
        }
        // Conserva la grabación real en memoria para reproducirla en el
        // resultado («Oír mi grabación»); el servidor nunca la persiste.
        setRecordingUrl(URL.createObjectURL(blob));
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

  const continueAfter = () => {
    if (phrase && result) onAnswered(phrase.id, result.passed);
  };

  return (
    <>
      {micError && <MicUnavailableNotice reason={micError} />}
      <PracticeReadCard
        phrase={phrase}
        cardLoading={itemLoading}
        cardError={itemError}
        result={result}
        processing={processing}
        recording={recording}
        recordingUrl={recordingUrl}
        attemptError={attemptError}
        onToggleRecording={() => void toggleRecording()}
        onAdvance={continueAfter}
        onSkip={onSkip}
        onRetry={() => {
          setAttemptError(null);
          setResult(null);
          processedRef.current = false;
        }}
      />
    </>
  );
}

interface PracticeReadCardProps {
  phrase: PronunciationPhrase | null;
  cardLoading: boolean;
  cardError: boolean;
  result: PronunciationAttempt | null;
  processing: boolean;
  recording: boolean;
  /** Object URL de la grabación del alumno para reproducirla en el resultado. */
  recordingUrl: string | null;
  attemptError: string | null;
  onToggleRecording: () => void;
  /** Continuar tras un resultado (avanza la sesión) o saltar sin responder. */
  onAdvance: () => void;
  onSkip: () => void;
  onRetry: () => void;
}

const CHIP_STYLES: Record<WordChipState, string> = {
  ok: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  sub: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  miss: "border-destructive/40 bg-destructive/10 text-destructive",
};

/** Frase del resultado coloreada palabra a palabra (mockup §6.3). */
function PhraseWordChips({
  script,
  heard,
  t,
}: {
  script: string;
  heard: string;
  t: (k: string) => string;
}) {
  const { expected, extras } = alignWords(script, heard);

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {t("pron.wordByWord")}
      </p>
      <div
        className="flex flex-wrap items-center gap-1.5"
        role="list"
        aria-label={t("pron.wordByWord")}
      >
        {expected.map((item, idx) => {
          const { word, state } = item;
          const aria =
            state === "ok"
              ? t("pron.chip.ok")
              : state === "miss"
                ? t("pron.chip.miss")
                : t("pron.chip.sub").replace("{heard}", item.heard ?? "");
          return (
            <span
              key={`${word}-${idx}`}
              role="listitem"
              title={aria}
              aria-label={aria}
              className={`flex min-h-7 items-center gap-1 rounded-lg border px-2 py-1 text-xs font-medium sm:text-sm ${CHIP_STYLES[state]}`}
            >
              <span>{word}</span>
              {state === "sub" && item.heard && (
                <span className="text-[10px] font-normal opacity-80">
                  → {item.heard}
                </span>
              )}
            </span>
          );
        })}
        {extras.map((word) => (
          <span
            key={`extra-${word}`}
            role="listitem"
            title={t("pron.chip.extra")}
            aria-label={t("pron.chip.extra")}
            className="flex min-h-7 items-center rounded-lg border border-dashed border-destructive/40 bg-destructive/5 px-2 py-1 text-xs font-medium text-destructive sm:text-sm"
          >
            +{word}
          </span>
        ))}
      </div>
      {extras.length > 0 && (
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("pron.chip.extraHint")}
        </p>
      )}
      {/* V3.21 (V20-02): nota permanente: estos colores son de la transcripción
          (ASR), no de un análisis acústico de la pronunciación. */}
      <p className="text-[11px] leading-relaxed text-muted-foreground">
        {t("pron.chipsNote")}
      </p>
    </div>
  );
}

/** Tarjeta del escenario de read-aloud (arriba, siempre visible). */
function PracticeReadCard({
  phrase,
  cardLoading,
  cardError,
  result,
  processing,
  recording,
  recordingUrl,
  attemptError,
  onToggleRecording,
  onAdvance,
  onSkip,
  onRetry,
}: PracticeReadCardProps) {
  const { t } = useI18n();
  const phraseText = usePhraseTranslation(phrase?.script ?? "");
  const expectedText = usePhraseTranslation(result?.script ?? "");
  // V3.21 (V20-13): cronómetro visible + auto-stop a 120 s (máximo del backend)
  // mientras se graba la lectura.
  const recordingRef = useRef(recording);
  recordingRef.current = recording;
  const recordingSession = useRecordingSession(recording, {
    onAutoStop: () => {
      if (recordingRef.current) onToggleRecording();
    },
  });

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
        <Button type="button" variant="outline" onClick={onSkip}>
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
        result.asr_status && result.asr_status !== "ok" ? (
          /* V3.21 (V20-14/15): el ASR no reconoció el audio. No se muestra
             feedback de color (no es un fallo lingüístico): se avisa y se pide
             repetir. El intento no se persiste en el backend. */
          <ActivityResult
            outcome="neutral"
            title={t("asr.title")}
            footer={
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" onClick={onRetry}>
                  {t("asr.tryAgain")}
                </Button>
              </div>
            }
          >
            <p className="text-sm leading-relaxed text-muted-foreground">
              {t(`asr.message.${result.asr_status}`)}
            </p>
          </ActivityResult>
        ) : (
        <ActivityResult
          outcome={outcome}
          title={`${t("pron.title")} · ${result.score}/100`}
          footer={
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" onClick={onAdvance}>
                {t("pronRoutes.continue")}
              </Button>
            </div>
          }
        >
          <header className="flex flex-wrap items-center gap-2">
            <Badge variant={result.passed ? "default" : "destructive"}>
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

          <div className="flex flex-wrap items-center gap-2">
            {recordingUrl && (
              <RecordingPlayButton
                src={recordingUrl}
                label={t("pronRoutes.playMine")}
              />
            )}
            <ListenButton text={result.script} label={t("speak.phrase")} />
          </div>

          <PhraseWordChips script={result.script} heard={result.heard} t={t} />

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
        )
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
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onRetry}
              >
                {t("pronRoutes.retry")}
              </Button>
            </div>
          )}

          <div className="flex flex-col items-center gap-1.5">
            <Button
              type="button"
              size="lg"
              className={
                recording
                  ? "min-h-14 gap-2 bg-destructive px-8 text-destructive-foreground hover:bg-destructive/90"
                  : "min-h-14 gap-2 px-8"
              }
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
              {recording
                ? t("pronRoutes.recordHint") + " · " + recordingSession.formatted
                : t("pronRoutes.recordHint")}
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
