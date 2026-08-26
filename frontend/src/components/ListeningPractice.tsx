import { useEffect, useRef, useState } from "react";
import {
  getListeningAudioUrl,
  getListeningDiagnostic,
  getListeningQuestion,
  getListeningStats,
  submitListeningAnswer,
  submitListeningDictation,
  submitListeningShadowing,
} from "../api/listening";
import { speak, transcribe } from "../api/voz";
import type {
  ListeningAnswerResponse,
  ListeningAudioVariant,
  ListeningDiagnostic,
  ListeningProductionResult,
  ListeningQuestion,
  ListeningStats,
} from "../types/api";

function topicLabel(topic: string): string {
  return topic.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function trendLabel(direction: string): string {
  switch (direction) {
    case "up":
      return "mejorando";
    case "down":
      return "empeorando";
    case "flat":
      return "estable";
    default:
      return "—";
  }
}

// Etiqueta legible de los buckets de retención retardada (días desde la primera
// exposición): "0-2" → "0–2 días", etc.
function retentionBucketLabel(bucket: string): string {
  switch (bucket) {
    case "0-2":
      return "0–2 días";
    case "2-7":
      return "2–7 días";
    case "7-30":
      return "7–30 días";
    case "30+":
      return "más de 30 días";
    default:
      return bucket;
  }
}

// Etiqueta honesta del tipo de audio (P0-1): no llamamos "audio real" a la voz
// sintética local; cada tipo se presenta por lo que realmente es.
function audioTypeLabel(audioType: string): string {
  switch (audioType) {
    case "recorded":
      return "Grabación real";
    case "mixed":
      return "Mezcla grabado + sintético";
    case "synthetic_multispeaker":
      return "Varias voces sintéticas";
    case "real_world":
      return "Audio real (entorno natural)";
    case "tts":
    default:
      return "Voz sintética local (TTS)";
  }
}

// Resumen legible del `breakdown` de una tarea de producción (dictado/shadowing):
// cuántas palabras se acertaron, cuántas faltaron y cuántas sobraron.
function breakdownLabel(breakdown: Record<string, unknown>): string {
  const correct = Array.isArray(breakdown.correct) ? breakdown.correct.length : 0;
  const missing = Array.isArray(breakdown.missing) ? breakdown.missing.length : 0;
  const extra = Array.isArray(breakdown.extra) ? breakdown.extra.length : 0;
  return `Palabras correctas: ${correct} · faltantes: ${missing} · extra: ${extra}`;
}

interface ListeningPracticeProps {
  userId: string | null;
  onAttempt: () => void;
}

export function ListeningPractice({
  userId,
  onAttempt,
}: ListeningPracticeProps) {
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
      audio.onerror = () => reject(new Error("No se pudo reproducir el audio"));
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
      setError(`No se pudo acceder al micrófono: ${(e as Error).message}`);
    }
  }

  return (
    <section className="listening">
      <h3>Comprensión auditiva</h3>
      {error && <p className="listening-error">{error}</p>}
      {!question ? (
        <p className="progress-empty">Cargando ejercicio…</p>
      ) : (
        <>
          <button
            type="button"
            className="listen-button"
            onClick={play}
            disabled={playing || !userId}
          >
            {playing ? "Reproduciendo…" : "Escuchar audio"}
          </button>
          {question.audio_ready && question.variants.length > 1 && (
            <div className="listening-variants">
              <span className="listening-variants-label">Velocidad:</span>
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
              Audio de referencia no disponible; usando voz generada en vivo.
            </p>
          )}
          {question.realized_difficulty < question.difficulty && (
            <p className="listening-audio-gap">
              Este audio realiza una dificultad {question.realized_difficulty} de
              las {question.difficulty} declaradas: parte de la dificultad no está
              respaldada por el audio.
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
                placeholder="Escribe lo que escuchas…"
                disabled={!!productionResult || processing}
              />
              <button
                type="button"
                className="listening-production-submit"
                onClick={submitDictation}
                disabled={
                  !userId ||
                  !dictationText.trim() ||
                  !!productionResult ||
                  processing
                }
              >
                {processing ? "Evaluando…" : "Enviar dictado"}
              </button>
            </div>
          )}

          {question.skill === "shadowing" && (
            <div className="listening-production">
              <button
                type="button"
                className={`listening-production-record${
                  recording ? " recording" : ""
                }`}
                onClick={toggleRecording}
                disabled={!userId || !!productionResult || processing}
              >
                {processing ? "Evaluando…" : recording ? "Detener" : "Grabar"}
              </button>
              {transcribedText && (
                <p className="listening-production-transcript">
                  Transcrito: {transcribedText}
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

          {result && (
            <div className={`listening-result ${result.correct ? "ok" : "ko"}`}>
              {result.correct ? "¡Correcto!" : "Incorrecto."}{" "}
              <span className="listening-script">{question.script}</span>
            </div>
          )}

          {productionResult && (
            <div
              className={`listening-production-result ${
                productionResult.correct ? "ok" : "ko"
              }`}
            >
              <div className="listening-production-score">
                {productionResult.score}/100
              </div>
              <div className="listening-production-lines">
                <div>
                  <span className="label">Precisión por palabra:</span>{" "}
                  {productionResult.word_accuracy}%
                </div>
                <div>
                  <span className="label">Similitud fonética:</span>{" "}
                  {productionResult.phonetic_score}%
                </div>
                <div>
                  <span className="label">Referencia:</span>{" "}
                  {productionResult.reference}
                </div>
                {transcribedText && (
                  <div>
                    <span className="label">Oído:</span> {transcribedText}
                  </div>
                )}
              </div>
              <p className="listening-production-breakdown">
                {breakdownLabel(productionResult.breakdown)}
              </p>
            </div>
          )}
          {stats && (
            <div className="listening-stats">
              <p>
                Aciertos: {stats.correct} de {stats.attempts}
                {stats.accuracy !== null ? ` (${stats.accuracy}%)` : ""}
              </p>
              <p className="listening-level">
                Nivel actual: <strong>{stats.level}</strong>
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
                    {s.mean_score !== null ? ` · media ${s.mean_score}%` : ""}
                    {s.review_due ? " · revisar" : ""}
                    {s.realization_gap ? " · audio no respalda" : ""}
                  </li>
                ))}
              </ul>
              {diagnostic.trend.direction !== "n/a" && (
                <p className="listening-trend">
                  Tendencia reciente:{" "}
                  <strong className={`trend-${diagnostic.trend.direction}`}>
                    {trendLabel(diagnostic.trend.direction)}
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
                  <p className="listening-breakdown-title">Precisión por tema</p>
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
                    Precisión por dificultad
                  </p>
                  <ul className="listening-pills">
                    {diagnostic.by_difficulty.map((d) => (
                      <li key={d.difficulty} className="listening-pill">
                        Nivel {d.difficulty} ·{" "}
                        {d.accuracy !== null ? `${d.accuracy}%` : "—"}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {diagnostic.recurrence.questions_seen > 0 && (
                <p className="listening-recurrence">
                  Reintentos: {diagnostic.recurrence.retried} de{" "}
                  {diagnostic.recurrence.questions_seen} · recuperados{" "}
                  {diagnostic.recurrence.recovered}
                </p>
              )}
              <div className="listening-retention">
                <p className="listening-retention-summary">
                  Retention:{" "}
                  {diagnostic.retention.immediate_accuracy !== null
                    ? `${diagnostic.retention.immediate_accuracy}%`
                    : "—"}{" "}
                  inmediata →{" "}
                  {diagnostic.retention.delayed_accuracy !== null
                    ? `${diagnostic.retention.delayed_accuracy}%`
                    : "—"}{" "}
                  retardada
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
                      · retención{" "}
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
            <p className="listening-completed">
              ¡Has completado todos los niveles de comprensión auditiva!
            </p>
          )}
          <button
            type="button"
            className="listening-next"
            onClick={load}
            disabled={!userId}
          >
            Siguiente
          </button>
        </>
      )}
    </section>
  );
}
