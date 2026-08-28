import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import {
  Loader2,
  Mic,
  Play,
  RefreshCw,
  Send,
  Square,
  AlertTriangle,
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
import { speak, transcribe } from "../../api/voz";
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
import { NextStep } from "../../components/NextStep";
import { MicUnavailableNotice } from "../../components/MicUnavailableNotice";
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

  async function load() {
    if (!userId) return;
    setError(null);
    setResult(null);
    setSelected(null);
    setProductionResult(null);
    setDictationText("");
    setTranscribedText("");
    setVariant("normal");
    try {
      setQuestion(await getListeningQuestion(userId));
      setStartedAt(Date.now());
      setReplayCount(0);
    } catch (e) {
      setError((e as Error).message);
    }
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
        await speak(question.script);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPlaying(false);
    }
  }

  async function choose(index: number) {
    if (!userId || !question || result) return;
    setSelected(index);
    try {
      setResult(
        await submitListeningAnswer(
          userId,
          question.id,
          index,
          Date.now() - startedAt,
          replayCount,
        ),
      );
      setReplayCount(0);
      onAttempt();
      void refreshStats();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function submitDictation() {
    if (!userId || !question || productionResult) return;
    const text = dictationText.trim();
    if (!text) return;
    setProcessing(true);
    setError(null);
    try {
      setProductionResult(
        await submitListeningDictation(userId, question.id, text),
      );
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
          setProductionResult(
            await submitListeningShadowing(userId, question.id, text),
          );
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

  return (
    <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 overflow-y-auto px-4 py-6 sm:px-6">
      {error && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span className="min-w-0 break-words">{error}</span>
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
          <Card className="gap-6 p-5 sm:p-6">
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
                  {question.accent} · {Math.round(question.speech_rate)} wpm ·{" "}
                  {question.duration.toFixed(1)}s
                </p>
              )}
            </div>
          </Card>

          <Card className="gap-4 p-5">
            <p className="text-base font-semibold leading-snug">
              {question.question}
            </p>

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
                          "disabled:cursor-default",
                        )}
                        onClick={() => choose(i)}
                        disabled={!!result}
                      >
                        {opt}
                      </button>
                    );
                  })}
                </div>
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
              footer={<NextStep userId={userId} onNext={onNext} />}
            >
              {result && (
                <span className="text-foreground">{question.script}</span>
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
                    <div>
                      <span className="text-muted-foreground">
                        {t("listening.reference")}:
                      </span>{" "}
                      {productionResult.reference}
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
            <Card className="gap-3 p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                <span className="text-muted-foreground">
                  {t("listening.scoreOf")}:{" "}
                  <span className="font-medium text-foreground">
                    {stats.correct}
                  </span>{" "}
                  {t("assessment.of")}{" "}
                  <span className="font-medium text-foreground">
                    {stats.attempts}
                  </span>
                  {stats.accuracy !== null ? ` (${stats.accuracy}%)` : ""}
                </span>
                <span className="text-muted-foreground">
                  {t("listening.currentLevel")}:{" "}
                  <span className="font-semibold text-foreground">
                    {stats.level}
                  </span>
                </span>
              </div>
              <ul className="flex flex-wrap gap-2">
                {stats.levels.map((lv) => (
                  <li key={lv.level}>
                    <Badge
                      variant={lv.completed ? "default" : "outline"}
                      className="gap-1.5"
                    >
                      {lv.level} · {lv.mastered}/{lv.total}
                    </Badge>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {diagnostic && (
            <Card className="gap-4 p-5">
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
          )}

          <div className="flex flex-wrap items-center justify-between gap-3">
            {stats?.completed && (
              <p className="text-sm font-semibold text-success">
                {t("listening.completed")}
              </p>
            )}
            <Button
              variant="outline"
              className="min-h-10 gap-2"
              onClick={load}
              disabled={!userId}
            >
              <RefreshCw className="size-4" aria-hidden="true" />
              {t("listening.next")}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
