import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronUp,
  Loader2,
  Mic,
  MoreHorizontal,
  Play,
  RefreshCw,
  Send,
  Square,
  Volume2,
} from "lucide-react";
import {
  getListeningAudioUrl,
  getListeningDiagnostic,
  getListeningQuestion,
  getListeningStats,
  submitListeningAnswer,
  submitListeningDictation,
  submitListeningShadowing,
} from "../../api/listening";
import {
  drillAnswered,
  isSessionFinished,
  sessionDone,
  type ListeningSession,
} from "./listeningSession";
import { ListeningLevelPanel } from "./ListeningLevelPanel";
import { speak, transcribe } from "../../api/voz";
import { getVoices } from "../../api/voices";
import {
  getMicrophoneStream,
  MicUnavailableError,
  type MicUnavailableReason,
} from "../../utils/browserCapabilities";
import type {
  ListeningAnswerResponse,
  ListeningAudioVariant,
  ListeningDiagnostic,
  ListeningProductionResult,
  ListeningQuestion,
  ListeningStats,
  NextBestActivity,
} from "../../types/api";
import type { Section } from "../../utils/sections";
import { ActivityResult } from "../../components/ActivityResult";
import { ListenButton } from "../../components/ListenButton";
import {
  PhraseTranslateButton,
  usePhraseTranslation,
} from "../../components/PhraseTranslate";
import { NextStep } from "../../components/NextStep";
import { MicUnavailableNotice } from "../../components/MicUnavailableNotice";
import { ProgressRing } from "../../components/ProgressRing";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Tooltip } from "../../components/ui/tooltip";
import { useI18n } from "../../hooks/useI18n";
import { cn } from "../../lib/utils";

// Etiqueta legible de una dimensión de resiliencia auditiva (Listening 2.0):
// "clear_speech" → "listening.resilience.clear_speech" (clave i18n localizada).
function resilienceLabel(dimension: string): string {
  return `listening.resilience.${dimension}`;
}

function topicLabel(topic: string): string {
  return topic.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function trendLabel(direction: string): string {
  switch (direction) {
    case "up":
      return "diag.improving";
    case "down":
      return "diag.gettingWorse";
    case "flat":
      return "diag.stable";
    default:
      return "—";
  }
}

// Etiqueta legible de los buckets de retención retardada (días desde la primera
// exposición): "0-2" → "0–2 days", etc.
function retentionBucketLabel(bucket: string): string {
  switch (bucket) {
    case "0-2":
      return "0–2 days";
    case "2-7":
      return "2–7 days";
    case "7-30":
      return "7–30 days";
    case "30+":
      return "over 30 days";
    default:
      return bucket;
  }
}

// Etiqueta honesta del tipo de audio (P0-1): no llamamos "audio real" a la voz
// sintética local; cada tipo se presenta por lo que realmente es.
function audioTypeLabel(audioType: string): string {
  switch (audioType) {
    case "recorded":
      return "Real recording";
    case "mixed":
      return "Mix of recorded + synthetic";
    case "synthetic_multispeaker":
      return "Several synthetic voices";
    case "real_world":
      return "Real-world audio (natural environment)";
    case "tts":
    default:
      return "Local synthetic voice (TTS)";
  }
}

// Resumen legible del `breakdown` de una tarea de producción (dictado/shadowing):
// cuántas palabras se acertaron, cuántas faltaron y cuántas sobraron.
function breakdownLabel(breakdown: Record<string, unknown>): string {
  const correct = Array.isArray(breakdown.correct) ? breakdown.correct.length : 0;
  const missing = Array.isArray(breakdown.missing) ? breakdown.missing.length : 0;
  const extra = Array.isArray(breakdown.extra) ? breakdown.extra.length : 0;
  return `Correct words: ${correct} · missing: ${missing} · extra: ${extra}`;
}

const WAVE_BARS = [0.45, 0.8, 0.55, 1, 0.65, 0.9, 0.5, 0.75, 0.4, 0.85, 0.6, 1, 0.7, 0.5, 0.9, 0.65];

function Waveform() {
  return (
    <div className="flex h-10 items-center justify-center gap-1" aria-hidden="true">
      {WAVE_BARS.map((h, i) => (
        <motion.span
          key={i}
          className="w-1.5 origin-center rounded-full bg-primary"
          style={{ height: `${h * 100}%` }}
          animate={{ scaleY: [1, 0.45, 1.25, 1] }}
          transition={{
            duration: 0.9,
            repeat: Infinity,
            delay: i * 0.055,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

interface ListeningPracticeProps {
  userId: string | null;
  onAttempt: () => void;
  onNext: (section: Section | null, step: NextBestActivity) => void;
}

export function ListeningPractice({
  userId,
  onAttempt,
  onNext,
}: ListeningPracticeProps) {
  const { t } = useI18n();
  const [question, setQuestion] = useState<ListeningQuestion | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<ListeningAnswerResponse | null>(null);
  const [productionResult, setProductionResult] =
    useState<ListeningProductionResult | null>(null);
  const [dictationText, setDictationText] = useState("");
  const [transcribedText, setTranscribedText] = useState("");
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  // Envío de una respuesta MCQ en curso: evita dobles taps y muestra el estado
  // "Evaluando…" para que la pantalla nunca parezca congelada mientras se espera
  // la respuesta del backend.
  const [submitting, setSubmitting] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [stats, setStats] = useState<ListeningStats | null>(null);
  const [diagnostic, setDiagnostic] = useState<ListeningDiagnostic | null>(null);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [micError, setMicError] = useState<MicUnavailableReason | null>(null);
  const [replayCount, setReplayCount] = useState(0);
  const [startedAt, setStartedAt] = useState(0);
  const [variant, setVariant] = useState<string>("normal");
  const [showAudioSettings, setShowAudioSettings] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [speakingQuestion, setSpeakingQuestion] = useState(false);
  const [session, setSession] = useState<ListeningSession | null>(null);
  const [expandedLevel, setExpandedLevel] = useState<string | null>(null);
  // Voz TTS real del perfil (Configuración → Voces): nombre amigable de la voz
  // seleccionada. Se muestra en ítems sintéticos en lugar del acento declarado
  // (que para TTS no es real). Se refresca al cambiar de usuario y al abrir la
  // tarjeta de ajustes de audio.
  const [ttsVoiceName, setTtsVoiceName] = useState<string | null>(null);

  // Traducción de apoyo EN→ES de los tres textos de la pregunta (enunciado,
  // texto oído en el resultado y referencia de dictado/shadowing). Cada una es
  // un toggle independiente que se reinicia cuando cambia la pregunta.
  const questionPhrase = usePhraseTranslation(
    question?.question ?? "",
    question?.id,
  );
  const scriptPhrase = usePhraseTranslation(
    question?.script ?? "",
    question?.id ? `${question.id}:script` : undefined,
  );
  const referencePhrase = usePhraseTranslation(
    productionResult?.reference ?? "",
    question?.id ? `${question.id}:reference` : undefined,
  );

  async function load(
    levelOverride?: string | null,
    modeOverride?: "all" | "failed",
  ) {
    if (!userId) return;
    setError(null);
    setResult(null);
    setSelected(null);
    setProductionResult(null);
    setDictationText("");
    setTranscribedText("");
    setVariant("normal");
    // Sin override, respeta el nivel y modo de la sesión en curso (si hay).
    const level = levelOverride === undefined ? session?.level : levelOverride;
    const mode =
      modeOverride ?? (session?.mode === "drill" ? "failed" : "all");
    try {
      setQuestion(await getListeningQuestion(userId, level, mode));
      setStartedAt(Date.now());
      setReplayCount(0);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  /** Sesión focalizada: practicar/repasar un nivel completo (rotación LRU). */
  function startLevelSession(level: string, total: number) {
    if (session || !userId) return;
    setSession({ mode: "level", level, total, done: 0 });
    setExpandedLevel(null);
    void load(level);
  }

  /** Sesión drill: repetir las frases falladas del nivel hasta dominarlas. */
  function startFailedDrill(level: string, failedIds: string[]) {
    if (session || !userId || failedIds.length === 0) return;
    setSession({ mode: "drill", level, total: failedIds.length, remaining: failedIds });
    setExpandedLevel(null);
    void load(level, "failed");
  }

  /** Cierra la sesión actual y vuelve al modo adaptativo (sin override de nivel). */
  function exitSession() {
    setSession(null);
    setExpandedLevel(null);
    // Override explícito a null: el cierre aún conserva la `session` vieja y sin
    // override `load()` seguiría pidiendo frases del nivel que se abandona.
    void load(null, "all");
  }

  /** Abre/cierra el historial desplegable de un nivel (uno a la vez). */
  function toggleLevel(level: string) {
    if (session) return;
    setExpandedLevel((cur) => (cur === level ? null : level));
  }

  // Tras responder: avanza el progreso de la sesión (el contador solo avanza
  // cuando se responde, no al saltar). En drill se elimina la frase del pool
  // pendiente solo si se acertó.
  function applySessionOutcome(questionId: string, correct: boolean) {
    if (!session) return;
    if (session.mode === "level") {
      setSession((s) =>
        s && s.mode === "level" ? { ...s, done: s.done + 1 } : s,
      );
    } else if (correct) {
      setSession((s) =>
        s && s.mode === "drill"
          ? { ...s, remaining: drillAnswered(s.remaining, questionId, true) }
          : s,
      );
    }
  }

  async function speakQuestion() {
    if (!question || speakingQuestion) return;
    setSpeakingQuestion(true);
    try {
      await speak(question.question, userId);
    } catch {
      // TTS de la pregunta no disponible: se ignora, no bloquea la práctica.
    } finally {
      setSpeakingQuestion(false);
    }
  }

  // CTA del resultado: si el motor recomienda seguir escuchando, avanza a la
  // siguiente frase en esta misma pantalla (la sección ya está activa y no se
  // re-monta); en otro caso navega a la destreza/objetivo recomendado.
  function handleResultNext(section: Section | null, step: NextBestActivity) {
    if (step.skill === "listening" || section === "listening") {
      void load();
      return;
    }
    onNext(section, step);
  }

  async function refreshStats() {
    if (!userId) return;
    try {
      setStats(await getListeningStats(userId));
    } catch {
      /* backend no disponible */
    }
    try {
      setDiagnostic(await getListeningDiagnostic(userId));
    } catch {
      /* backend no disponible */
    }
  }

  useEffect(() => {
    void load();
    void refreshStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  // Voz TTS seleccionada del perfil (nombre amigable) para la etiqueta honesta de
  // los ítems sintéticos. `showAudioSettings` fuerza un refresco cada vez que se
  // abre la tarjeta de audio (p. ej. tras cambiar la voz en Configuración).
  useEffect(() => {
    if (!userId) {
      setTtsVoiceName(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await getVoices(userId);
        if (!cancelled) {
          setTtsVoiceName(
            res.voices.find((v) => v.id === res.selected)?.name ?? res.selected,
          );
        }
      } catch {
        /* backend no disponible: la etiqueta omite la voz */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, showAudioSettings]);

  function playAudioUrl(url: string): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      const audio = new Audio(url);
      audio.onended = () => resolve();
      audio.onerror = () => reject(new Error("Could not play the audio"));
      audio.play().catch(reject);
    });
  }

  async function play() {
    if (!question || !userId || playing) return;
    setPlaying(true);
    setReplayCount((count) => count + 1);
    try {
      if (question.audio_ready) {
        // Audio de referencia pre-renderizado (respeta speech_rate y repetición).
        await playAudioUrl(getListeningAudioUrl(question.id, userId, variant));
      } else {
        // Degradación: TTS en vivo con el script del ítem.
        await speak(question.script, userId);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPlaying(false);
    }
  }

  async function choose(index: number) {
    if (!userId || !question || result || submitting) return;
    setSelected(index);
    setError(null);
    setSubmitting(true);
    try {
      const res = await submitListeningAnswer(
        userId,
        question.id,
        index,
        Date.now() - startedAt,
        replayCount,
      );
      setResult(res);
      setReplayCount(0);
      applySessionOutcome(question.id, res.correct);
      onAttempt();
      void refreshStats();
    } catch (e) {
      // Fallo de red o timeout: se muestra el error y la opción de saltar a la
      // siguiente, para que la pantalla nunca se quede sin salida.
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  async function submitDictation() {
    if (!userId || !question || productionResult) return;
    const text = dictationText.trim();
    if (!text) return;
    setProcessing(true);
    setError(null);
    try {
      const res = await submitListeningDictation(userId, question.id, text);
      setProductionResult(res);
      applySessionOutcome(question.id, res.correct);
      onAttempt();
      void refreshStats();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setProcessing(false);
    }
  }

  async function toggleRecording() {
    if (!userId || !question || productionResult) return;
    if (recording) {
      recorderRef.current?.stop();
      setRecording(false);
      return;
    }
    setMicError(null);
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
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        if (blob.size === 0) return;
        if (!userId || !question) return;
        setProcessing(true);
        setError(null);
        try {
          const text = await transcribe(blob);
          setTranscribedText(text);
          const res = await submitListeningShadowing(
            userId,
            question.id,
            text,
          );
          setProductionResult(res);
          applySessionOutcome(question.id, res.correct);
          onAttempt();
          void refreshStats();
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setProcessing(false);
        }
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (e) {
      setError(`${t("mic.accessError")}${(e as Error).message}`);
    }
  }

  // Resumen del encabezado del diagnóstico plegable: debilidad principal de
  // resiliencia auditiva cuando existe; si no, la recomendación recortada.
  const diagnosticSummary = diagnostic
    ? (() => {
        const main = diagnostic.resilience.dimensions.find(
          (d) => d.dimension === diagnostic.resilience.main_weakness,
        );
        return main
          ? `${t("listening.resilienceMainWeakness")}: ${t(
              resilienceLabel(main.dimension),
            )}${main.accuracy !== null ? ` · ${main.accuracy}%` : ""}`
          : diagnostic.recommendation;
      })()
    : "";

  const currentLevelStat = stats?.level
    ? stats.levels.find((lv) => lv.level === stats.level) ?? null
    : null;
  const currentLevelPct =
    currentLevelStat && currentLevelStat.total > 0
      ? (currentLevelStat.mastered / currentLevelStat.total) * 100
      : 0;

  // Color del donut de precisión según el rendimiento global.
  function ringTone(accuracy: number | null): string {
    if (accuracy === null) return "text-muted-foreground";
    if (accuracy >= 80) return "text-success";
    if (accuracy >= 60) return "text-primary";
    return "text-warning";
  }

  return (
    <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 overflow-y-auto px-4 py-6 sm:px-6">
      {error && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <span className="min-w-0 break-words">{error}</span>
            {question && !(result || productionResult) && (
              <button
                type="button"
                className="self-start rounded-md border border-destructive/40 px-3 py-1.5 text-xs font-medium text-destructive transition-colors hover:bg-destructive/15"
                onClick={() => void load()}
              >
                {t("listening.errorSkip")}
              </button>
            )}
          </div>
        </div>
      )}

      {micError && <MicUnavailableNotice reason={micError} />}

      {!question ? (
        <Card className="p-8">
          <p className="text-center text-sm text-muted-foreground">
            {t("listening.loading")}
          </p>
        </Card>
      ) : (
        <>
          {session && (
            <Card className="flex flex-row flex-wrap items-center justify-between gap-3 p-4">
              <span className="text-sm text-muted-foreground">
                {session.mode === "drill"
                  ? t("listening.drillProgress")
                      .replace("{level}", session.level)
                      .replace("{done}", String(sessionDone(session)))
                      .replace("{total}", String(session.total))
                  : t("listening.reviewProgress")
                      .replace("{level}", session.level)
                      .replace("{done}", String(session.done))
                      .replace("{total}", String(session.total))}
              </span>
              <Button
                type="button"
                variant="outline"
                className="min-h-9 gap-2"
                onClick={exitSession}
              >
                {session.mode === "drill"
                  ? t("listening.exitSession")
                  : t("listening.exitReview")}
              </Button>
            </Card>
          )}

          <Card className="relative gap-5 p-5 sm:p-6">
            <button
              type="button"
              onClick={() => setShowAudioSettings((s) => !s)}
              aria-expanded={showAudioSettings}
              aria-controls="listening-audio-settings"
              aria-label={t("listening.audioSettings")}
              className={cn(
                "absolute top-3 right-3 z-10 grid size-9 place-items-center rounded-full border transition-colors",
                showAudioSettings
                  ? "border-transparent bg-primary text-primary-foreground"
                  : "border-border bg-secondary text-secondary-foreground hover:border-primary/50 hover:text-foreground",
              )}
            >
              <MoreHorizontal className="size-4" aria-hidden="true" />
            </button>

            <div className="flex flex-col items-center gap-4 text-center">
              <motion.button
                type="button"
                onClick={play}
                disabled={playing || !userId}
                whileTap={playing || !userId ? undefined : { scale: 0.94 }}
                aria-label={playing ? t("listening.playing") : t("listening.play")}
                className="grid size-20 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/25 transition-colors hover:bg-primary/90 disabled:opacity-50"
              >
                {playing ? (
                  <Loader2 className="size-8 animate-spin" aria-hidden="true" />
                ) : (
                  <Play className="size-8 translate-x-0.5" aria-hidden="true" />
                )}
              </motion.button>

              {playing ? (
                <Waveform />
              ) : (
                <span className="text-sm font-medium text-muted-foreground">
                  {t("listening.play")}
                </span>
              )}
            </div>

            {showAudioSettings && (
              <div
                id="listening-audio-settings"
                className="flex flex-col items-center gap-4"
              >
                {question.audio_ready &&
                  question.audio_type === "tts" &&
                  question.variants.length > 1 && (
                    <div className="flex flex-wrap items-center justify-center gap-2">
                      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {t("listening.speed")}
                      </span>
                      {question.variants.map((v: ListeningAudioVariant) => (
                        <button
                          key={v.variant}
                          type="button"
                          className={cn(
                            "min-h-10 rounded-full border px-3 text-xs font-medium transition-colors",
                            v.variant === variant
                              ? "border-transparent bg-primary text-primary-foreground"
                              : "border-border bg-secondary text-secondary-foreground hover:border-primary/50",
                            "disabled:opacity-60",
                          )}
                          onClick={() => setVariant(v.variant)}
                          disabled={playing || !userId}
                        >
                          {v.label}
                        </button>
                      ))}
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {Math.round(
                          question.variants.find((v) => v.variant === variant)
                            ?.speech_rate ?? question.speech_rate,
                        )}{" "}
                        wpm
                      </span>
                    </div>
                  )}

                <div className="flex flex-col items-center gap-1.5 text-center">
                  <div className="flex items-center gap-1.5">
                    <p className="text-xs text-muted-foreground">
                      {audioTypeLabel(question.audio_type)}
                    </p>
                    {question.realized_difficulty < question.difficulty && (
                      <Tooltip
                        content={t("listening.audioGap")
                          .replace("{realized}", String(question.realized_difficulty))
                          .replace("{declared}", String(question.difficulty))}
                      >
                        <button
                          type="button"
                          className="inline-flex text-warning"
                          aria-label={t("listening.audioGapTitle")}
                        >
                          <AlertTriangle className="size-3.5" aria-hidden="true" />
                        </button>
                      </Tooltip>
                    )}
                  </div>
                  {!question.audio_ready && (
                    <p className="text-xs text-muted-foreground">
                      {t("listening.audioUnavailable")}
                    </p>
                  )}
                  {question.speech_rate > 0 && (
                    <p className="text-xs tabular-nums text-muted-foreground">
                      {question.audio_type === "tts" ? (
                        ttsVoiceName ? (
                          <span title={t("listening.ttsRealVoice")}>
                            {ttsVoiceName} ·{" "}
                          </span>
                        ) : null
                      ) : (
                        <span>{question.accent} · </span>
                      )}
                      {Math.round(question.speech_rate)} wpm ·{" "}
                      {question.duration.toFixed(1)}s
                    </p>
                  )}
                </div>
              </div>
            )}
          </Card>

          <Card className="gap-4 p-5">
            <div className="flex items-start justify-between gap-3">
              <p
                className="text-base font-semibold leading-snug"
                lang={questionPhrase.isSpanish ? "es" : "en"}
              >
                {questionPhrase.display}
              </p>
              <div className="flex shrink-0 items-center gap-2">
                <PhraseTranslateButton
                  state={questionPhrase}
                  className="size-9"
                />
                <button
                  type="button"
                  onClick={() => void speakQuestion()}
                  disabled={speakingQuestion || !userId}
                  aria-label={t("listening.speakQuestion")}
                  className="grid size-9 shrink-0 place-items-center rounded-full border border-border bg-secondary text-secondary-foreground transition-colors hover:border-primary/50 hover:text-foreground disabled:opacity-60"
                >
                  {speakingQuestion ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Volume2 className="size-4" aria-hidden="true" />
                  )}
                </button>
              </div>
            </div>

            {question.skill === "dictation" && (
              <div className="flex flex-col gap-3">
                <textarea
                  className="min-h-24 w-full resize-y rounded-md border border-input bg-background px-3 py-2.5 text-sm leading-relaxed outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-70"
                  value={dictationText}
                  onChange={(e) => setDictationText(e.target.value)}
                  placeholder={t("listening.dictationPlaceholder")}
                  disabled={!!productionResult || processing}
                />
                <Button
                  className="min-h-10 gap-2 self-start"
                  onClick={submitDictation}
                  disabled={
                    !userId ||
                    !dictationText.trim() ||
                    !!productionResult ||
                    processing
                  }
                >
                  {processing ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Send className="size-4" aria-hidden="true" />
                  )}
                  {processing
                    ? t("listening.evaluating")
                    : t("listening.submitDictation")}
                </Button>
              </div>
            )}

            {question.skill === "shadowing" && (
              <div className="flex flex-col gap-3">
                <Button
                  variant={recording ? "destructive" : "default"}
                  className="min-h-10 gap-2 self-start"
                  onClick={toggleRecording}
                  disabled={!userId || !!productionResult || processing}
                >
                  {processing ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  ) : recording ? (
                    <Square className="size-4" aria-hidden="true" />
                  ) : (
                    <Mic className="size-4" aria-hidden="true" />
                  )}
                  {processing
                    ? t("listening.evaluating")
                    : recording
                      ? t("listening.stop")
                      : t("listening.record")}
                </Button>
                {recording && (
                  <div className="flex items-center gap-2 text-xs font-medium text-destructive">
                    <motion.span
                      className="size-2 rounded-full bg-destructive"
                      animate={{ opacity: [1, 0.25, 1] }}
                      transition={{ duration: 1.2, repeat: Infinity }}
                      aria-hidden="true"
                    />
                    {t("listening.record")}
                  </div>
                )}
                {transcribedText && (
                  <p className="text-sm text-muted-foreground">
                    {t("listening.transcribed")}: {transcribedText}
                  </p>
                )}
              </div>
            )}

            {question.skill !== "dictation" &&
              question.skill !== "shadowing" && (
                <div className="grid gap-2 sm:grid-cols-2">
                  {question.options.map((opt, i) => {
                    const isCorrect = result && i === result.correct_index;
                    const isWrong = result && i === selected && !result.correct;
                    return (
                      <button
                        key={opt}
                        type="button"
                        className={cn(
                          "min-h-10 rounded-md border px-3 py-2.5 text-left text-sm transition-colors",
                          isCorrect
                            ? "border-success bg-success/15 text-foreground"
                            : isWrong
                              ? "border-destructive bg-destructive/10 text-foreground"
                              : "border-border bg-secondary text-secondary-foreground hover:border-primary/50",
                          "disabled:cursor-default disabled:opacity-70",
                        )}
                        onClick={() => choose(i)}
                        disabled={!!result || submitting}
                      >
                        {opt}
                      </button>
                    );
                  })}
                </div>
              )}

            {submitting && (
              <p
                role="status"
                aria-live="polite"
                className="flex items-center justify-center gap-2 py-1 text-xs text-muted-foreground"
              >
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                {t("listening.evaluating")}
              </p>
            )}
          </Card>

          {(result || productionResult) && (
            <ActivityResult
              outcome={
                result
                  ? result.correct
                    ? "ok"
                    : "ko"
                  : productionResult?.correct
                    ? "ok"
                    : "ko"
              }
              title={
                result
                  ? result.correct
                    ? t("listening.correct")
                    : t("listening.incorrect")
                  : `Dictation/Shadowing · ${productionResult?.score ?? 0}/100`
              }
              footer={
                session ? (
                  isSessionFinished(session) ? (
                    <Button
                      type="button"
                      className="min-h-10 gap-2"
                      onClick={exitSession}
                    >
                      {session.mode === "drill"
                        ? t("listening.drillFinish")
                        : t("listening.reviewFinish")}
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      className="min-h-10 gap-2"
                      onClick={() => void load()}
                    >
                      {t("listening.reviewNext")}
                    </Button>
                  )
                ) : (
                  <NextStep
                    userId={userId}
                    onNext={handleResultNext}
                    fallback={{
                      label: t("listening.next"),
                      onClick: () => void load(),
                    }}
                  />
                )
              }
            >
              {session?.mode === "drill" &&
                session.remaining.length === 0 && (
                  <p className="text-sm font-medium text-primary">
                    {t("listening.drillDone")
                      .replace("{total}", String(session.total))
                      .replace("{level}", session.level)}
                  </p>
                )}
              {result && (
                <div className="flex items-start justify-between gap-3">
                  <span
                    className="text-foreground"
                    lang={scriptPhrase.isSpanish ? "es" : "en"}
                  >
                    {scriptPhrase.display}
                  </span>
                  <div className="flex shrink-0 items-center gap-2">
                    <PhraseTranslateButton state={scriptPhrase} />
                    <ListenButton
                      text={question.script}
                      label={t("speak.answer")}
                    />
                  </div>
                </div>
              )}
              {productionResult && (
                <>
                  <div className="flex flex-col gap-1 text-sm">
                    <div>
                      <span className="text-muted-foreground">
                        {t("listening.wordAccuracy")}:
                      </span>{" "}
                      {productionResult.word_accuracy}%
                    </div>
                    <div>
                      <span className="text-muted-foreground">
                        {t("listening.phoneticScore")}:
                      </span>{" "}
                      {productionResult.phonetic_score}%
                    </div>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <span className="text-muted-foreground">
                          {t("listening.reference")}:
                        </span>{" "}
                        <span
                          className="text-foreground"
                          lang={referencePhrase.isSpanish ? "es" : "en"}
                        >
                          {referencePhrase.display}
                        </span>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <PhraseTranslateButton state={referencePhrase} />
                        <ListenButton
                          text={productionResult.reference}
                          label={t("speak.phrase")}
                        />
                      </div>
                    </div>
                    {transcribedText && (
                      <div>
                        <span className="text-muted-foreground">
                          {t("listening.heard")}:
                        </span>{" "}
                        {transcribedText}
                      </div>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {breakdownLabel(productionResult.breakdown)}
                  </p>
                </>
              )}
            </ActivityResult>
          )}

          {stats && (
            <Card className="gap-4 p-5">
              <div className="flex flex-wrap items-center justify-around gap-6">
                <div className="flex flex-col items-center gap-1.5">
                  <ProgressRing
                    value={stats.accuracy ?? 0}
                    size={72}
                    strokeWidth={7}
                    className={ringTone(stats.accuracy)}
                    ariaLabel={`${t("listening.accuracy")}: ${
                      stats.accuracy !== null ? `${stats.accuracy}%` : "—"
                    }`}
                  >
                    <span className="text-lg font-bold tabular-nums text-foreground">
                      {stats.accuracy !== null ? `${stats.accuracy}%` : "—"}
                    </span>
                  </ProgressRing>
                  <span className="text-xs font-medium text-foreground">
                    {t("listening.accuracy")}
                  </span>
                  <span className="text-[11px] tabular-nums text-muted-foreground">
                    {stats.correct} {t("assessment.of")} {stats.attempts}
                  </span>
                </div>

                <div className="flex flex-col items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => toggleLevel(stats.level)}
                    aria-expanded={expandedLevel === stats.level}
                    aria-controls="listening-level-items"
                    aria-label={t("listening.levelHistoryTitle").replace(
                      "{level}",
                      stats.level,
                    )}
                    disabled={!!session}
                    className={cn(
                      "flex flex-col items-center gap-1.5 rounded-lg p-1.5 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                      expandedLevel === stats.level && "bg-accent",
                      session && "cursor-not-allowed opacity-60",
                    )}
                  >
                    <ProgressRing
                      value={currentLevelPct}
                      size={72}
                      strokeWidth={7}
                      className="text-primary"
                      ariaLabel={`${t("listening.currentLevel")}: ${stats.level}`}
                    >
                      <span className="text-sm font-bold text-foreground">
                        {stats.level}
                      </span>
                    </ProgressRing>
                    <span className="text-xs font-medium text-foreground">
                      {t("listening.currentLevel")}
                    </span>
                    <span className="text-[11px] tabular-nums text-muted-foreground">
                      {currentLevelStat
                        ? t("listening.masteredOfTotal")
                            .replace(
                              "{mastered}",
                              String(currentLevelStat.mastered),
                            )
                            .replace("{total}", String(currentLevelStat.total))
                        : "—"}
                    </span>
                    {currentLevelStat?.state === "demonstrated" && (
                      <span className="text-[11px] font-semibold text-success">
                        {t("listening.demoTitle").replace(
                          "{level}",
                          stats.level,
                        )}
                      </span>
                    )}
                    {currentLevelStat?.completed &&
                      currentLevelStat.state === "functional" && (
                        <>
                          <span className="text-[11px] font-semibold text-success">
                            {t("listening.routeCompleted").replace(
                              "{level}",
                              stats.level,
                            )}
                          </span>
                          <span className="text-[11px] font-medium text-warning">
                            {t("listening.demoNotYet").replace(
                              "{level}",
                              stats.level,
                            )}
                          </span>
                        </>
                      )}
                    {currentLevelStat?.completed &&
                      currentLevelStat.state !== "demonstrated" &&
                      currentLevelStat.state !== "functional" && (
                        <span className="text-[11px] font-semibold text-success">
                          {t("listening.routeCompleted").replace(
                            "{level}",
                            stats.level,
                          )}
                        </span>
                      )}
                    {currentLevelStat &&
                      !currentLevelStat.completed &&
                      currentLevelStat.mastered === currentLevelStat.total && (
                        <span className="text-[11px] font-semibold text-warning">
                          {t("listening.routePendingCert")}
                        </span>
                      )}
                  </button>
                </div>
              </div>

              <p className="border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">
                {t("listening.routeNote").replace("{level}", stats.level)}
              </p>
              <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                {t("listening.routeCertNote")}
              </p>

              <div className="flex flex-col border-t border-border pt-4">
                <p className="text-[11px] leading-relaxed text-muted-foreground">
                  {t("listening.routeRingHelp")}
                </p>
                <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
                  {stats.levels.map((lv) => {
                    const expanded = expandedLevel === lv.level;
                    return (
                      <button
                        key={lv.level}
                        type="button"
                        onClick={() => toggleLevel(lv.level)}
                        aria-expanded={expanded}
                        aria-controls="listening-level-items"
                        aria-label={t("listening.levelHistoryTitle").replace(
                          "{level}",
                          lv.level,
                        )}
                        disabled={!!session}
                        className={cn(
                          "flex flex-col items-center gap-1.5 rounded-lg p-1.5 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                          expanded && "bg-accent",
                          session && "cursor-not-allowed opacity-60",
                        )}
                      >
                        <ProgressRing
                          value={lv.total > 0 ? (lv.mastered / lv.total) * 100 : 0}
                          size={44}
                          strokeWidth={5}
                          className={
                            lv.completed
                              ? "text-success"
                              : lv.mastered === lv.total
                                ? "text-warning"
                                : "text-primary"
                          }
                          ariaLabel={t("listening.masteredOfTotal")
                            .replace("{mastered}", String(lv.mastered))
                            .replace("{total}", String(lv.total))}
                        >
                          {lv.completed ? (
                            <Check className="size-4" aria-hidden="true" />
                          ) : (
                            <span className="text-[10px] font-semibold tabular-nums text-foreground">
                              {lv.mastered}
                            </span>
                          )}
                        </ProgressRing>
                        <span className="text-[11px] font-medium text-muted-foreground">
                          {t("listening.routeLabel").replace("{level}", lv.level)}
                        </span>
                        <span className="text-[10px] font-semibold tabular-nums text-foreground">
                          {t("listening.masteredOfTotal")
                            .replace("{mastered}", String(lv.mastered))
                            .replace("{total}", String(lv.total))}
                        </span>
                        {lv.total > 0 && (
                          <span className="text-[10px] tabular-nums text-muted-foreground">
                            {t("listening.coveragePct").replace(
                              "{pct}",
                              String(Math.round((lv.mastered / lv.total) * 100)),
                            )}
                          </span>
                        )}
                        {!lv.completed &&
                          lv.mastered > 0 &&
                          lv.gate &&
                          lv.gate.coverage_required_pct > 0 && (
                            <span className="max-w-[130px] text-center text-[9px] leading-tight text-warning">
                              {t("listening.routeGateShort")
                                .replace(
                                  "{coverage}",
                                  String(lv.gate.coverage_required_pct),
                                )
                                .replace(
                                  "{min}",
                                  String(
                                    Math.ceil(
                                      (lv.total * lv.gate.coverage_required_pct) /
                                        100,
                                    ),
                                  ),
                                )
                                .replace("{total}", String(lv.total))}
                            </span>
                          )}
                      </button>
                    );
                  })}
                </div>
                {expandedLevel !== null && !session && (
                  <div
                    id="listening-level-items"
                    className="mt-4 border-t border-border pt-4"
                  >
                    <ListeningLevelPanel
                      userId={userId}
                      level={expandedLevel}
                      routeState={
                        stats.levels.find((lv) => lv.level === expandedLevel)?.state
                      }
                      routeRetention={
                        stats.levels.find((lv) => lv.level === expandedLevel)
                          ?.retention ?? null
                      }
                      onPracticeLevel={startLevelSession}
                      onDrillFailed={startFailedDrill}
                    />
                  </div>
                )}
              </div>
            </Card>
          )}

          {diagnostic && (
            <>
              <button
                type="button"
                onClick={() => setShowAnalysis((s) => !s)}
                aria-expanded={showAnalysis}
                aria-label={
                  showAnalysis
                    ? t("listening.hideAnalysis")
                    : t("listening.showAnalysis")
                }
                className="flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-card px-5 py-4 text-left shadow-sm"
              >
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="text-sm font-semibold text-foreground">
                    {t("listening.diagnostic")}
                  </span>
                  {diagnosticSummary && (
                    <span className="truncate text-xs text-muted-foreground">
                      {diagnosticSummary}
                    </span>
                  )}
                </span>
                {showAnalysis ? (
                  <ChevronUp
                    className="size-4 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />
                ) : (
                  <ChevronDown
                    className="size-4 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />
                )}
              </button>
              <Card
                className={cn("gap-4 p-5", !showAnalysis && "hidden")}
              >
                <p className="text-sm text-foreground">
                  {diagnostic.recommendation}
                </p>

              {diagnostic.resilience.dimensions.length > 0 && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("listening.resilience")}
                  </p>
                  <ul className="flex flex-wrap gap-2">
                    {diagnostic.resilience.dimensions.map((r) => (
                      <li key={r.dimension}>
                        <Badge
                          variant={
                            r.dimension === diagnostic.resilience.main_weakness
                              ? "default"
                              : "outline"
                          }
                          className="gap-1.5"
                        >
                          {t(resilienceLabel(r.dimension))} ·{" "}
                          {r.accuracy !== null ? `${r.accuracy}%` : "—"}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                  {diagnostic.resilience.recommendation && (
                    <p className="text-sm text-muted-foreground">
                      {diagnostic.resilience.recommendation}
                    </p>
                  )}
                </div>
              )}

              <ul className="flex flex-col gap-1">
                {diagnostic.subskills.map((s) => (
                  <li
                    key={s.skill}
                    className={cn(
                      "text-xs text-muted-foreground",
                      s.review_due && "text-foreground",
                      s.realization_gap && "text-warning",
                    )}
                  >
                    {s.skill} · {s.attempts} ·{" "}
                    {s.accuracy !== null ? `${s.accuracy}%` : "—"}
                    {s.automaticity !== null
                      ? ` · auto ${Math.round(s.automaticity * 100)}%`
                      : ""}
                    {s.mean_score !== null ? ` · mean ${s.mean_score}%` : ""}
                    {s.review_due ? ` · ${t("diag.review")}` : ""}
                    {s.realization_gap ? " · audio not backed" : ""}
                  </li>
                ))}
              </ul>

              {diagnostic.trend.direction !== "n/a" && (
                <p className="text-sm text-muted-foreground">
                  {t("diag.trend")}:{" "}
                  <strong
                    className={cn(
                      diagnostic.trend.direction === "up" && "text-success",
                      diagnostic.trend.direction === "down" && "text-destructive",
                      diagnostic.trend.direction === "flat" &&
                        "text-muted-foreground",
                    )}
                  >
                    {t(trendLabel(diagnostic.trend.direction))}
                  </strong>
                  {diagnostic.trend.delta !== null
                    ? ` (${diagnostic.trend.delta > 0 ? "+" : ""}${
                        diagnostic.trend.delta
                      })`
                    : ""}
                </p>
              )}

              {diagnostic.by_topic.length > 0 && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("listening.accuracyByTopic")}
                  </p>
                  <ul className="flex flex-wrap gap-2">
                    {diagnostic.by_topic.map((t) => (
                      <li key={t.topic}>
                        <Badge variant="outline" className="gap-1.5">
                          {topicLabel(t.topic)} ·{" "}
                          {t.accuracy !== null ? `${t.accuracy}%` : "—"}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {diagnostic.by_difficulty.length > 0 && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("listening.accuracyByDifficulty")}
                  </p>
                  <ul className="flex flex-wrap gap-2">
                    {diagnostic.by_difficulty.map((d) => (
                      <li key={d.difficulty}>
                        <Badge variant="outline" className="gap-1.5">
                          {t("pron.level")} {d.difficulty} ·{" "}
                          {d.accuracy !== null ? `${d.accuracy}%` : "—"}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {diagnostic.recurrence.questions_seen > 0 && (
                <p className="text-sm text-muted-foreground">
                  {t("listening.retries")}: {diagnostic.recurrence.retried}{" "}
                  {t("assessment.of")} {diagnostic.recurrence.questions_seen} ·{" "}
                  {t("listening.recovered")} {diagnostic.recurrence.recovered}
                </p>
              )}

              <div className="flex flex-col gap-2">
                <p className="text-sm text-muted-foreground">
                  {t("listening.retention")}:{" "}
                  {diagnostic.retention.immediate_accuracy !== null
                    ? `${diagnostic.retention.immediate_accuracy}%`
                    : "—"}{" "}
                  {t("listening.immediate")} →{" "}
                  {diagnostic.retention.delayed_accuracy !== null
                    ? `${diagnostic.retention.delayed_accuracy}%`
                    : "—"}{" "}
                  {t("listening.delayed")}
                  {diagnostic.retention.retention_rate !== null && (
                    <span
                      className={cn(
                        "ml-1 font-medium",
                        diagnostic.retention.retention_rate >= 0.9
                          ? "text-success"
                          : diagnostic.retention.retention_rate >= 0.7
                            ? "text-warning"
                            : "text-destructive",
                      )}
                    >
                      · {t("listening.retention")}{" "}
                      {Math.round(diagnostic.retention.retention_rate * 100)}%
                    </span>
                  )}
                </p>
                {diagnostic.retention.by_bucket.length > 0 && (
                  <ul className="flex flex-wrap gap-2">
                    {diagnostic.retention.by_bucket.map((b) => (
                      <li key={b.bucket}>
                        <Badge variant="outline" className="gap-1.5">
                          {retentionBucketLabel(b.bucket)} ·{" "}
                          {b.accuracy !== null ? `${b.accuracy}%` : "—"}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>
            </>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3">
            {stats?.completed && (
              <p className="text-sm font-semibold text-success">
                {t("listening.completed")}
              </p>
            )}
            {!(result || productionResult) && session?.mode !== "drill" && (
              <Button
                variant="outline"
                className="min-h-10 gap-2"
                onClick={() => void load()}
                disabled={!userId}
              >
                <RefreshCw className="size-4" aria-hidden="true" />
                {t("listening.skip")}
              </Button>
            )}
          </div>
        </>
      )}
    </section>
  );
}
