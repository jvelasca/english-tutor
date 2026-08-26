import { useRef, useState } from "react";
import {
  finishSpeakingAssessment,
  startSpeakingAssessment,
  submitSpeakingAssessmentPart,
} from "../api/academy";
import { transcribe } from "../api/voz";
import type {
  SpeakingAssessmentPartInfo,
  SpeakingAssessmentPartScores,
  SpeakingAssessmentResult,
} from "../types/api";
import { cefrTone } from "../utils/cefr";
import {
  criterionLabel,
  formatConfidence,
  formatDurationTarget,
  formatScorePct,
} from "../utils/speaking";

type Phase = "idle" | "part" | "result";

interface SpeakingAssessmentProps {
  userId: string | null;
  onAttempt: () => void;
}

/**
 * Flujo completo del Speaking Assessment (start → 4 partes → resultado).
 * Soporta dos vías de respuesta: micrófono (grabación + transcripción) y
 * entrada manual por textarea, de modo que funcione incluso sin micrófono.
 */
export function SpeakingAssessment({
  userId,
  onAttempt,
}: SpeakingAssessmentProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [totalParts, setTotalParts] = useState(0);
  const [part, setPart] = useState<SpeakingAssessmentPartInfo | null>(null);
  const [partScores, setPartScores] =
    useState<SpeakingAssessmentPartScores | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [done, setDone] = useState(false);
  const [nextPart, setNextPart] =
    useState<SpeakingAssessmentPartInfo | null>(null);
  const [result, setResult] = useState<SpeakingAssessmentResult | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [manualText, setManualText] = useState("");

  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef(0);

  async function handleStart() {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const start = await startSpeakingAssessment(userId);
      setSessionId(start.session_id);
      setTotalParts(start.total_parts);
      setPart(start.part);
      setPartScores(null);
      setSubmitted(false);
      setDone(false);
      setNextPart(null);
      setManualText("");
      setPhase("part");
    } catch (e) {
      setError(`No se pudo iniciar el assessment: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  /** Envía la respuesta hablada (transcrita o manual) de la parte actual. */
  async function submitResponse(heard: string, durationSeconds?: number) {
    if (!userId || sessionId == null) return;
    setLoading(true);
    setError(null);
    try {
      const out = await submitSpeakingAssessmentPart(
        userId,
        sessionId,
        heard,
        durationSeconds,
      );
      setPartScores(out.part_scores);
      setDone(out.done);
      setNextPart(out.next_part);
      setSubmitted(true);
    } catch (e) {
      setError(`Error al enviar la respuesta: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleAdvance() {
    if (done) {
      await handleFinish();
      return;
    }
    if (!nextPart) {
      setError("No hay siguiente parte disponible.");
      return;
    }
    setPart(nextPart);
    setPartScores(null);
    setSubmitted(false);
    setNextPart(null);
    setManualText("");
  }

  async function handleFinish() {
    if (!userId || sessionId == null) return;
    setLoading(true);
    setError(null);
    try {
      const final = await finishSpeakingAssessment(userId, sessionId);
      setResult(final);
      setPhase("result");
      onAttempt();
    } catch (e) {
      setError(`No se pudo finalizar el assessment: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setPhase("idle");
    setSessionId(null);
    setTotalParts(0);
    setPart(null);
    setPartScores(null);
    setSubmitted(false);
    setDone(false);
    setNextPart(null);
    setResult(null);
    setManualText("");
    setError(null);
  }

  async function toggleRecording() {
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
        const stopTime = performance.now();
        const durationSeconds = (stopTime - startTimeRef.current) / 1000;
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        if (blob.size === 0) return;
        setProcessing(true);
        try {
          const heard = await transcribe(blob);
          if (heard.trim()) {
            await submitResponse(heard.trim(), durationSeconds);
          }
        } catch (e) {
          setError(`No se pudo transcribir el audio: ${(e as Error).message}`);
        } finally {
          setProcessing(false);
        }
      };
      startTimeRef.current = performance.now();
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (e) {
      setError(`No se pudo acceder al micrófono: ${(e as Error).message}`);
    }
  }

  async function handleManualSubmit() {
    const heard = manualText.trim();
    if (!heard || loading) return;
    await submitResponse(heard);
    setManualText("");
  }

  if (phase === "idle") {
    return (
      <section className="speaking-assessment">
        <p className="speaking-assessment__desc">
          Completa las 4 partes del assessment oral para obtener tu nivel CEFR
          continuo, con micrófono o escribiendo tus respuestas.
        </p>
        {error && (
          <p className="speaking-assessment__error" role="alert">
            {error}
          </p>
        )}
        <button
          type="button"
          className="speaking-assessment__start"
          onClick={handleStart}
          disabled={!userId || loading}
        >
          {loading ? "Iniciando…" : "Iniciar Speaking Assessment"}
        </button>
      </section>
    );
  }

  if (phase === "result" && result) {
    return (
      <section className="speaking-assessment">
        <header className="speaking-assessment__header">
          {result.level && (
            <span className={`cefr-badge ${cefrTone(result.level)}`}>
              {result.level}
            </span>
          )}
        </header>

        <div className="speaking-assessment__result">
          <div className="speaking-assessment__result-score">
            {formatScorePct(result.score)}
          </div>
          <div className="speaking-assessment__result-meta">
            <span>Confianza {formatConfidence(result.confidence)}</span>
            <span>·</span>
            <span>{result.attempts} intentos</span>
          </div>
        </div>

        <ul className="speaking-assessment__criteria">
          {result.criteria.map((c) => {
            const score = c.recent_score ?? c.mean;
            const weak = c.review_due || (score != null && score < 0.6);
            return (
              <li
                key={c.criterion}
                className={`speaking-assessment__criterion${weak ? " review" : ""}`}
              >
                <span className="speaking-assessment__criterion-label">
                  {criterionLabel(c.criterion)}
                </span>
                <span className="speaking-assessment__criterion-score">
                  {formatScorePct(score)}
                </span>
                <span
                  className="speaking-assessment__criterion-mark"
                  aria-hidden="true"
                >
                  {weak ? "⚠" : "✓"}
                </span>
              </li>
            );
          })}
        </ul>

        {result.recommendation && (
          <p className="speaking-assessment__recommendation">
            {result.recommendation}
          </p>
        )}

        <button
          type="button"
          className="speaking-assessment__reset"
          onClick={handleReset}
        >
          Hacer otro assessment
        </button>
      </section>
    );
  }

  return (
    <section className="speaking-assessment">
      <header className="speaking-assessment__header">
        {part && (
          <span className={`cefr-badge ${cefrTone(part.cefr_target)}`}>
            {part.cefr_target}
          </span>
        )}
      </header>

      <div className="speaking-assessment__meta">
        <span>
          Parte {part?.part_index ?? 1} de {totalParts}
        </span>
        {part && (
          <span className="speaking-assessment__duration">
            ~{formatDurationTarget(part.duration_target)}
          </span>
        )}
      </div>

      {part && (
        <>
          <p className="speaking-assessment__part-title">{part.title}</p>
          <p className="speaking-assessment__prompt">{part.prompt}</p>
        </>
      )}

      {error && (
        <p className="speaking-assessment__error" role="alert">
          {error}
        </p>
      )}

      {!submitted ? (
        <>
          <div className="speaking-assessment__controls">
            <button
              type="button"
              className={`speaking-assessment__record${recording ? " recording" : ""}${processing ? " processing" : ""}`}
              onClick={toggleRecording}
              disabled={processing || !userId}
              aria-pressed={recording}
              aria-label={
                processing
                  ? "Transcribiendo respuesta"
                  : recording
                    ? "Detener grabación"
                    : "Grabar respuesta"
              }
            >
              {processing
                ? "Transcribiendo…"
                : recording
                  ? "Detener"
                  : "Grabar respuesta"}
            </button>
          </div>

          <label className="speaking-assessment__manual">
            <span className="speaking-assessment__manual-label">
              O escribe tu respuesta:
            </span>
            <textarea
              className="speaking-assessment__textarea"
              value={manualText}
              onChange={(e) => setManualText(e.target.value)}
              placeholder="Escribe aquí lo que dirías en voz alta…"
              rows={3}
              maxLength={2000}
              disabled={loading}
            />
          </label>

          <button
            type="button"
            className="speaking-assessment__submit"
            onClick={handleManualSubmit}
            disabled={!manualText.trim() || loading || !userId}
          >
            {loading ? "Enviando…" : "Enviar"}
          </button>
        </>
      ) : (
        <>
          {partScores && (
            <div className="speaking-assessment__part-score">
              <span className="speaking-assessment__part-score-value">
                {formatScorePct(partScores.overall)}
              </span>
              <span className="speaking-assessment__part-score-label">
                de esta parte
              </span>
            </div>
          )}

          {partScores && Object.keys(partScores.observed).length > 0 && (
            <ul className="speaking-assessment__observed">
              {Object.entries(partScores.observed).map(([key, seen]) => (
                <li key={key} className={seen ? "seen" : ""}>
                  {seen ? "✓" : "—"} {criterionLabel(key)}
                </li>
              ))}
            </ul>
          )}

          {error && (
            <p className="speaking-assessment__error" role="alert">
              {error}
            </p>
          )}

          <button
            type="button"
            className="speaking-assessment__next"
            onClick={handleAdvance}
            disabled={loading}
          >
            {loading ? "Procesando…" : done ? "Ver resultado" : "Siguiente parte"}
          </button>
        </>
      )}
    </section>
  );
}
