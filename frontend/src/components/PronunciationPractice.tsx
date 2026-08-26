import { useRef, useState } from "react";
import { checkPronunciation } from "../api/pronunciation";
import type { PronunciationResponse } from "../types/api";
import { fluencyLevelLabel, wpmLabel } from "../utils/fluency";
import { feedbackHints, wordsCorrectLabel } from "../utils/pronunciationFeedback";

const SAMPLES = [
  "Hello, how are you?",
  "I would like a cup of coffee.",
  "The weather is nice today.",
];

interface PronunciationPracticeProps {
  userId: string | null;
  onAttempt: () => void;
}

export function PronunciationPractice({
  userId,
  onAttempt,
}: PronunciationPracticeProps) {
  const [sentence, setSentence] = useState(SAMPLES[0]);
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<PronunciationResponse | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const hints = result ? feedbackHints(result.breakdown) : [];

  async function toggle() {
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
        if (!userId) return;
        setProcessing(true);
        try {
          setResult(await checkPronunciation(blob, sentence, userId));
          onAttempt();
        } catch (e) {
          alert(`Error al evaluar la pronunciación: ${(e as Error).message}`);
        } finally {
          setProcessing(false);
        }
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (e) {
      alert(`No se pudo acceder al micrófono: ${(e as Error).message}`);
    }
  }

  return (
    <section className="pronunciation">
      <h3>Práctica de pronunciación</h3>
      <p className="pronunciation-prompt">
        Lee la frase en voz alta y pulsa el micrófono:
      </p>
      <div className="pronunciation-samples">
        {SAMPLES.map((s) => (
          <button
            key={s}
            className={s === sentence ? "sample active" : "sample"}
            onClick={() => setSentence(s)}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="pronunciation-controls">
        <button
          className={`record-button${recording ? " recording" : ""}`}
          onClick={toggle}
          disabled={processing || !userId}
        >
          {processing
            ? "Evaluando…"
            : recording
              ? "Detener"
              : "Grabar"}
        </button>
      </div>

      {result && (
        <div className={`pronunciation-result ${result.level}`}>
          <div className="score">{result.score}/100</div>
          <div className="lines">
            <div>
              <span className="label">Esperado:</span> {result.expected}
            </div>
            <div>
              <span className="label">Oído:</span> {result.heard}
            </div>
            <div>
              <span className="label">Nivel:</span>{" "}
              {result.level === "good"
                ? "Muy bien"
                : result.level === "fair"
                  ? "Aceptable"
                  : "Sigue practicando"}
            </div>
            <div>
              <span className="label">Precisión por palabra:</span>{" "}
              {result.word_accuracy}%
            </div>
            <div>
              <span className="label">Similitud fonética:</span>{" "}
              {result.phonetic_score}%
            </div>
            <div>
              <span className="label">Precisión de fonemas (proxy de texto):</span>{" "}
              {result.phoneme_accuracy_proxy}%
            </div>
            <div>
              <span className="label">Ritmo silábico (proxy, sin audio):</span>{" "}
              {result.prosody_proxy}%
            </div>
            <div>
              <span className="label">Fluidez:</span>{" "}
              {fluencyLevelLabel(result.fluency.level)} ·{" "}
              {wpmLabel(result.fluency.wpm)}
            </div>
          </div>
          <p className="pronunciation-words-label">
            {wordsCorrectLabel(result.breakdown)}
          </p>
          {hints.length > 0 && (
            <ul className="pronunciation-hints">
              {hints.map((hint) => (
                <li key={hint}>{hint}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
