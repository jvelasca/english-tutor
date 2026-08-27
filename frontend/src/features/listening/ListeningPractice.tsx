import { useEffect, useRef, useState } from "react";
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
import { useI18n } from "../../hooks/useI18n";

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
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
    <section className="listening">
      {error && <p className="listening-error">{error}</p>}
      {!question ? (
        <p className="progress-empty">{t("listening.loading")}</p>
      ) : (
        <>
          <button
            type="button"
            className="listen-button min-h-10"
            onClick={play}
            disabled={playing || !userId}
          >
            {playing ? t("listening.playing") : t("listening.play")}
          </button>
          {question.audio_ready && question.variants.length > 1 && (
            <div className="listening-variants">
              <span className="listening-variants-label">{t("listening.speed")}</span>
              {question.variants.map((v: ListeningAudioVariant) => (
                <button
                  key={v.variant}
                  type="button"
                  className={`listening-variant${
                    v.variant === variant ? " active" : ""
                  }`}
                  onClick={() => setVariant(v.variant)}
                  disabled={playing || !userId}
                >
                  {v.label}
                </button>
              ))}
              <span className="listening-variants-speed">
                {Math.round(
                  question.variants.find((v) => v.variant === variant)
                    ?.speech_rate ?? question.speech_rate,
                )}{" "}
                wpm
              </span>
            </div>
          )}
          <p className="listening-audio-type">
            {audioTypeLabel(question.audio_type)}
          </p>
          {!question.audio_ready && (
            <p className="listening-audio-degraded">
              {t("listening.audioUnavailable")}
            </p>
          )}
          {question.realized_difficulty < question.difficulty && (
            <p className="listening-audio-gap">
              {t("listening.audioGap")} {question.realized_difficulty} of the{" "}
              {question.difficulty} {t("listening.audioGapEnd")}
            </p>
          )}
          {question.speech_rate > 0 && (
            <p className="listening-audio-meta">
              {question.accent} · {Math.round(question.speech_rate)} wpm ·{" "}
              {question.duration.toFixed(1)}s
            </p>
          )}
          <p className="listening-question">{question.question}</p>

          {question.skill === "dictation" && (
            <div className="listening-production">
              <textarea
                className="listening-production-textarea"
                value={dictationText}
                onChange={(e) => setDictationText(e.target.value)}
                placeholder={t("listening.dictationPlaceholder")}
                disabled={!!productionResult || processing}
              />
              <button
                type="button"
                className="listening-production-submit min-h-10"
                onClick={submitDictation}
                disabled={
                  !userId ||
                  !dictationText.trim() ||
                  !!productionResult ||
                  processing
                }
              >
                {processing ? t("listening.evaluating") : t("listening.submitDictation")}
              </button>
            </div>
          )}

          {question.skill === "shadowing" && (
            <div className="listening-production">
              <button
                type="button"
                className={`listening-production-record min-h-10${
                  recording ? " recording" : ""
                }`}
                onClick={toggleRecording}
                disabled={!userId || !!productionResult || processing}
              >
                {processing
                  ? t("listening.evaluating")
                  : recording
                    ? t("listening.stop")
                    : t("listening.record")}
              </button>
              {transcribedText && (
                <p className="listening-production-transcript">
                  {t("listening.transcribed")}: {transcribedText}
                </p>
              )}
            </div>
          )}

          {question.skill !== "dictation" &&
            question.skill !== "shadowing" && (
              <div className="listening-options">
                {question.options.map((opt, i) => {
                  let cls = "listening-option";
                  if (result && i === result.correct_index) cls += " correct";
                  if (result && i === selected && !result.correct)
                    cls += " wrong";
                  return (
                    <button
                      key={opt}
                      type="button"
                      className={cls}
                      onClick={() => choose(i)}
                      disabled={!!result}
                    >
                      {opt}
                    </button>
                  );
                })}
              </div>
            )}

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
                <span className="listening-script">{question.script}</span>
              )}
              {productionResult && (
                <>
                  <div className="listening-production-lines">
                    <div>
                      <span className="label">{t("listening.wordAccuracy")}:</span>{" "}
                      {productionResult.word_accuracy}%
                    </div>
                    <div>
                      <span className="label">{t("listening.phoneticScore")}:</span>{" "}
                      {productionResult.phonetic_score}%
                    </div>
                    <div>
                      <span className="label">{t("listening.reference")}:</span>{" "}
                      {productionResult.reference}
                    </div>
                    {transcribedText && (
                      <div>
                        <span className="label">{t("listening.heard")}:</span>{" "}
                        {transcribedText}
                      </div>
                    )}
                  </div>
                  <p className="listening-production-breakdown">
                    {breakdownLabel(productionResult.breakdown)}
                  </p>
                </>
              )}
            </ActivityResult>
          )}
          {stats && (
            <div className="listening-stats">
              <p>
                {t("listening.scoreOf")}: {stats.correct}{" "}
                {t("assessment.of")} {stats.attempts}
                {stats.accuracy !== null ? ` (${stats.accuracy}%)` : ""}
              </p>
              <p className="listening-level">
                {t("listening.currentLevel")}: <strong>{stats.level}</strong>
              </p>
              <ul className="listening-levels">
                {stats.levels.map((lv) => (
                  <li
                    key={lv.level}
                    className={`listening-level-pill${
                      lv.completed ? " completed" : ""
                    }`}
                  >
                    {lv.level} · {lv.mastered}/{lv.total}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {diagnostic && (
            <div className="listening-diagnostic">
              <p className="listening-recommendation">
                {diagnostic.recommendation}
              </p>
              <ul className="listening-subskills">
                {diagnostic.subskills.map((s) => (
                  <li
                    key={s.skill}
                    className={`listening-subskill${
                      s.review_due ? " review" : ""
                    }${s.realization_gap ? " gap" : ""}`}
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
                <p className="listening-trend">
                  {t("diag.trend")}:{" "}
                  <strong className={`trend-${diagnostic.trend.direction}`}>
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
                <div className="listening-breakdown">
                  <p className="listening-breakdown-title">{t("listening.accuracyByTopic")}</p>
                  <ul className="listening-pills">
                    {diagnostic.by_topic.map((t) => (
                      <li key={t.topic} className="listening-pill">
                        {topicLabel(t.topic)} ·{" "}
                        {t.accuracy !== null ? `${t.accuracy}%` : "—"}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {diagnostic.by_difficulty.length > 0 && (
                <div className="listening-breakdown">
                  <p className="listening-breakdown-title">
                    {t("listening.accuracyByDifficulty")}
                  </p>
                  <ul className="listening-pills">
                    {diagnostic.by_difficulty.map((d) => (
                      <li key={d.difficulty} className="listening-pill">
                        {t("pron.level")} {d.difficulty} ·{" "}
                        {d.accuracy !== null ? `${d.accuracy}%` : "—"}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {diagnostic.recurrence.questions_seen > 0 && (
                <p className="listening-recurrence">
                  {t("listening.retries")}: {diagnostic.recurrence.retried}{" "}
                  {t("assessment.of")} {diagnostic.recurrence.questions_seen} ·{" "}
                  {t("listening.recovered")} {diagnostic.recurrence.recovered}
                </p>
              )}
              <div className="listening-retention">
                <p className="listening-retention-summary">
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
                      className={`listening-retention-rate ${
                        diagnostic.retention.retention_rate >= 0.9
                          ? "high"
                          : diagnostic.retention.retention_rate >= 0.7
                            ? "mid"
                            : "low"
                      }`}
                    >
                      {" "}
                      · {t("listening.retention")}{" "}
                      {Math.round(diagnostic.retention.retention_rate * 100)}%
                    </span>
                  )}
                </p>
                {diagnostic.retention.by_bucket.length > 0 && (
                  <ul className="listening-pills">
                    {diagnostic.retention.by_bucket.map((b) => (
                      <li key={b.bucket} className="listening-pill">
                        {retentionBucketLabel(b.bucket)} ·{" "}
                        {b.accuracy !== null ? `${b.accuracy}%` : "—"}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
          {stats?.completed && (
            <p className="listening-completed">{t("listening.completed")}</p>
          )}
          <button
            type="button"
            className="listening-next"
            onClick={load}
            disabled={!userId}
          >
            {t("listening.next")}
          </button>
        </>
      )}
    </section>
  );
}
