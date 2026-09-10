/**
 * Escalera de micro-drill de una palabra (V3.19/V3.21/V3.33):
 * Recognition → Recall → Sentence.
 *
 * Extraída de `PersonalDictionary` para el Dictionary → Learning Bridge (V3.32):
 * se reutiliza tanto desde el diccionario personal (chips de candidatas de la
 * señal) como desde el diccionario de consulta («Practicar esta palabra»).
 * Los componentes solo dependen de `userId` + `word`: no conocen la lista de
 * candidatas ni el origen de la llamada. La evidencia que escribe un intento
 * superado es idéntica a la de cualquier otra práctica (canal speaking,
 * actividad drill) — sin etiquetas de origen (V3.32). No declara dominio
 * (D5/E3): una producción del día no consolida; se consolida con éxito
 * espaciado (F6.2).
 * V3.33: el peldaño Recognition (MCQ definición ↔ palabra) es SOLO
 * informativo — su acierto no demuestra destreza productiva (V3.13) y no
 * dispara `onProduced`; tampoco usa micrófono (lo puntúa el backend).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { motion, type Variants } from "motion/react";
import { Check, Loader2, Mic, Square } from "lucide-react";
import {
  getDrillRecognitionQuestion,
  getDrillSentenceContext,
  submitDrillAttempt,
  submitDrillRecognitionAttempt,
  submitDrillSentenceAttempt,
} from "../../api/vocabulary";
import type {
  DrillAttempt,
  DrillRecognitionAttempt,
  DrillRecognitionQuestion,
  DrillSentenceAttempt,
  DrillSentenceContext,
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { useRecordingSession } from "../../hooks/useRecordingSession";
import { ListenButton } from "../../components/ListenButton";
import { MicUnavailableNotice } from "../../components/MicUnavailableNotice";
import { Card } from "../../components/ui/card";
import {
  getMicrophoneStream,
  MicUnavailableError,
  type MicUnavailableReason,
} from "../../utils/browserCapabilities";
import { cn } from "../../lib/utils";

/** Variante de entrada de sección (idéntica a la de `PersonalDictionary`): la
 * animación la dispara el ancestro `motion` con `initial="hidden"` cuando hay
 * uno (diccionario personal); sin ancestro la sección se muestra estática. */
const item: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
};

export type DrillStep = "recognition" | "recall" | "sentence";

export interface SpeakingDrillSectionProps {
  userId: string;
  words: string[];
  drillWord: string | null;
  onDrillChange: (word: string | null) => void;
  onProduced: (word: string) => void;
}

/** Speaking micro-drill de 1 nivel honesto (V3.19): chips accionables que abren
 * una micro-práctica oral en el propio panel. No declara dominio (D5/E3).
 * La palabra en drill la controla el padre (`drillWord`) para que la sección
 * permanezca abierta mostrando el resultado aunque ya no queden candidatas. */
export function SpeakingDrillSection({
  userId,
  words,
  drillWord,
  onDrillChange,
  onProduced,
}: SpeakingDrillSectionProps) {
  const { t } = useI18n();

  return (
    <motion.section
      variants={item}
      aria-label={t("dictionary.recognizedNotProduced")}
    >
      <Card className="gap-3 p-5">
        <div className="flex items-center gap-2">
          <Mic className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-sm font-semibold">
            {t("dictionary.recognizedNotProduced")}
          </h2>
        </div>
        <p className="text-xs text-muted-foreground">
          {t("dictionary.recognizedNotProducedHint")}
        </p>
        {words.length > 0 && (
          <ul className="flex flex-wrap gap-1.5">
            {words.map((word) => (
              <li key={word}>
                <button
                  type="button"
                  onClick={() => onDrillChange(word)}
                  aria-pressed={drillWord === word}
                  aria-label={t("dictionary.drill.sayWord").replace("{word}", word)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium transition-colors",
                    drillWord === word
                      ? "border-transparent bg-primary text-primary-foreground"
                      : "border-border bg-secondary text-secondary-foreground hover:border-primary/50 hover:text-foreground",
                  )}
                >
                  <Mic className="size-3" aria-hidden="true" />
                  {word}
                </button>
              </li>
            ))}
          </ul>
        )}

        {drillWord && (
          <WordDrill
            userId={userId}
            word={drillWord}
            onProduced={() => onProduced(drillWord)}
            onClose={() => onDrillChange(null)}
          />
        )}
      </Card>
    </motion.section>
  );
}

export interface WordDrillProps {
  userId: string;
  word: string;
  onProduced: () => void;
  onClose: () => void;
}

type DrillOutcome = DrillAttempt | DrillSentenceAttempt;

export function isSentenceAttempt(
  outcome: DrillOutcome,
): outcome is DrillSentenceAttempt {
  return "passed" in outcome;
}

/** Micro-práctica escalera de una palabra (V3.21/F6): Paso 1 "Recognition"
 * (V3.33, eslabón 2 del puente) — elige el significado de la palabra entre
 * opciones servidas por el backend (MCQ definición ↔ palabra, sin micrófono);
 * Paso 2 "Recall" — di la palabra (scorer `submitDrillAttempt`); Paso 3
 * "Sentence" — repítela DENTRO de una frase de contexto determinista (scorer
 * `submitDrillSentenceAttempt`). Reutiliza el scorer de pronunciación del
 * servidor. No declara dominio (D5/E3): una producción del día no consolida;
 * se consolida con éxito espaciado (F6.2).
 * V3.32: reutilizable desde el diccionario de consulta (botón «Practicar esta
 * palabra») porque solo depende de `userId` + `word`.
 * V3.33: el paso Recognition es SOLO informativo (V3.13: el MC de
 * reconocimiento no demuestra destrezas productivas): su acierto NO dispara
 * `onProduced` y solo el servidor puntúa (premisa 21).
 * V3.33.1: el drill ARRANCA en Recognition (primer peldaño real de la escalera)
 * y solo degrada a Recall si el backend responde `available=false`; cada
 * intento pide un `question_id` nuevo para rebarajar la posición de la
 * correcta. */
export function WordDrill({ userId, word, onProduced, onClose }: WordDrillProps) {
  const { t } = useI18n();
  // V3.33.1: el drill abre en el primer peldaño (Recognition). Si la pregunta
  // no está disponible, `loadRecognition` degrada a Recall (V3.19).
  const [step, setStep] = useState<DrillStep>("recognition");
  const [sentence, setSentence] = useState<DrillSentenceContext | null>(null);
  const [sentenceError, setSentenceError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<DrillOutcome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [micReason, setMicReason] = useState<MicUnavailableReason | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  // V3.33: estado del paso Recognition (la pregunta es determinista en el
  // servidor dado el `question_id`; la correcta solo llega en la respuesta).
  const [recognition, setRecognition] =
    useState<DrillRecognitionQuestion | null>(null);
  const [recognitionError, setRecognitionError] = useState<string | null>(null);
  const [recognitionSelected, setRecognitionSelected] = useState<number | null>(
    null,
  );
  const [recognitionOutcome, setRecognitionOutcome] =
    useState<DrillRecognitionAttempt | null>(null);
  // V3.21 (V20-13): cronómetro visible + auto-stop a 120 s (máximo del backend).
  const recordingSession = useRecordingSession(recording, {
    onAutoStop: () => {
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop();
        setRecording(false);
      }
    },
  });

  /** Pide una pregunta de Recognition (V3.33.1): cada intento recibe un
   * `question_id` nuevo, así que la posición de la correcta cambia entre
   * intentos. Si el backend no tiene contenido suficiente (`available=false`),
   * degrada a Recall para no romper la escalera. */
  const loadRecognition = useCallback(() => {
    setRecognitionError(null);
    setRecognitionSelected(null);
    setRecognitionOutcome(null);
    getDrillRecognitionQuestion(userId, word)
      .then((question) => {
        setRecognition(question);
        if (!question.available) {
          // Degrada solo si el alumno sigue en Recognize: no pisa una elección
          // manual de otro paso (p. ej. ya está en Sentence).
          setStep((current) => (current === "recognition" ? "recall" : current));
        }
      })
      .catch((e) =>
        setRecognitionError(
          t("dictionary.drill.error").concat((e as Error).message),
        ),
      );
  }, [userId, word, t]);

  // V3.33.1: el drill arranca en Recognition (primer peldaño real de la
  // escalera) y limpia el intento anterior al montar o cambiar de palabra.
  useEffect(() => {
    setStep("recognition");
    setSentence(null);
    setSentenceError(null);
    setResult(null);
    setError(null);
    setRecognition(null);
    loadRecognition();
  }, [loadRecognition]);

  function chooseStep(next: DrillStep) {
    if (next === step || recording || processing) return;
    setResult(null);
    setError(null);
    if (next === "recognition") {
      // V3.33.1: cada entrada en Recognition pide una pregunta nueva (nuevo
      // `question_id`): se reinicia el intento anterior y la correcta cambia de
      // posición, de modo que no se puede memorizar el patrón.
      loadRecognition();
      setStep(next);
      return;
    }
    if (next === "sentence" && !sentence) {
      setSentenceError(null);
      getDrillSentenceContext(userId, word)
        .then((ctx) => setSentence(ctx))
        .catch((e) =>
          setSentenceError(t("dictionary.drill.error").concat((e as Error).message)),
        );
    }
    setStep(next);
  }

  async function submitRecognition() {
    if (!recognition || !recognition.available || recognitionSelected === null) {
      return;
    }
    setProcessing(true);
    setError(null);
    try {
      const outcome = await submitDrillRecognitionAttempt(
        userId,
        word,
        recognitionSelected,
        recognition.question_id,
      );
      setRecognitionOutcome(outcome);
    } catch (e) {
      setError(t("dictionary.drill.error").concat((e as Error).message));
    } finally {
      setProcessing(false);
    }
  }

  async function toggle() {
    if (recording) {
      recorderRef.current?.stop();
      setRecording(false);
      return;
    }
    setError(null);
    setMicReason(null);
    let stream: MediaStream;
    try {
      stream = await getMicrophoneStream();
    } catch (e) {
      setMicReason(e instanceof MicUnavailableError ? e.reason : "unknown");
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
        if (blob.size === 0) return;
        setProcessing(true);
        try {
          const attempt: DrillOutcome =
            step === "sentence"
              ? await submitDrillSentenceAttempt(userId, word, blob)
              : await submitDrillAttempt(userId, word, blob);
          setResult(attempt);
          const success = isSentenceAttempt(attempt)
            ? attempt.passed
            : attempt.produced;
          if (success) onProduced();
        } catch (e) {
          setError(t("dictionary.drill.error").concat((e as Error).message));
        } finally {
          setProcessing(false);
        }
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (e) {
      setError(t("dictionary.drill.micError").concat((e as Error).message));
    }
  }

  const asrUnclear =
    result && result.asr_status && result.asr_status !== "ok" ? result : null;
  const asrLabel = asrUnclear
    ? `${t("asr.title")} — ${t(`asr.message.${asrUnclear.asr_status}`)}`
    : "";

  const phraseReady = step === "recall" || sentence !== null;
  const micBlocked =
    processing || (step === "sentence" && (sentence === null || sentenceError !== null));

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-background/60 p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold" lang="en">
            {word}
          </span>
          <ListenButton text={word} label={t("speak.phrase")} />
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-muted-foreground underline-offset-2 hover:underline"
        >
          {t("common.close")}
        </button>
      </div>

      {/* Escalera Recognize -> Recall -> Sentence en la misma tarjeta
          (V3.21/F6.1 + V3.33 Recognition). */}
      <div
        role="group"
        aria-label={t("dictionary.drill.steps")}
        className="flex w-fit items-center gap-1 rounded-md bg-secondary p-1"
      >
        {(["recognition", "recall", "sentence"] as const).map((option) => (
          <button
            key={option}
            type="button"
            disabled={recording || processing}
            onClick={() => chooseStep(option)}
            aria-pressed={step === option}
            className={cn(
              "rounded px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-50",
              step === option
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {option === "recognition"
              ? t("dictionary.drill.stepRecognition")
              : option === "recall"
                ? t("dictionary.drill.stepRecall")
                : t("dictionary.drill.stepSentence")}
          </button>
        ))}
      </div>

      {step === "recognition" ? (
        recognition ? (
          recognition.available ? (
            <div className="flex flex-col gap-2">
              <p className="text-xs text-muted-foreground">
                {t("dictionary.drill.recognitionPrompt")}
              </p>
              <ul
                role="group"
                aria-label={t("dictionary.drill.recognitionPrompt")}
                className="flex flex-col gap-1.5"
              >
                {recognition.options.map((option, i) => (
                  <li key={`${i}-${option}`}>
                    <button
                      type="button"
                      disabled={processing || recognitionOutcome !== null}
                      onClick={() => setRecognitionSelected(i)}
                      aria-pressed={recognitionSelected === i}
                      className={cn(
                        "w-full rounded-md border px-3 py-2 text-left text-sm transition-colors disabled:opacity-60",
                        recognitionSelected === i
                          ? "border-transparent bg-primary text-primary-foreground"
                          : "border-border bg-secondary text-secondary-foreground hover:border-primary/50 hover:text-foreground",
                      )}
                    >
                      {option}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              {t("dictionary.drill.recognitionUnavailable")}
            </p>
          )
        ) : recognitionError ? (
          <p className="text-xs text-destructive" role="alert">
            {recognitionError}
          </p>
        ) : (
          <Loader2
            className="size-4 animate-spin text-muted-foreground"
            aria-hidden="true"
          />
        )
      ) : step === "recall" ? (
        <p className="text-xs text-muted-foreground">{t("dictionary.drill.prompt")}</p>
      ) : sentence ? (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted-foreground">
            {t("dictionary.drill.sentencePrompt")}
          </p>
          <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-background px-3 py-2">
            <span className="text-sm font-medium" lang="en">
              {sentence.phrase}
            </span>
            <ListenButton
              text={sentence.phrase}
              label={t("dictionary.drill.sentenceListen")}
            />
          </div>
          {sentence.source === "template" && (
            <p className="text-[11px] text-muted-foreground">
              {t("dictionary.drill.sentenceTemplateNote")}
            </p>
          )}
        </div>
      ) : null}

      {sentenceError && (
        <p className="text-xs text-destructive" role="alert">
          {sentenceError}
        </p>
      )}
      {micReason && <MicUnavailableNotice reason={micReason} />}
      {error && (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}

      {step === "recognition" ? (
        <div className="flex items-center gap-3">
          <motion.button
            type="button"
            onClick={() => void submitRecognition()}
            disabled={
              !recognition ||
              !recognition.available ||
              recognitionSelected === null ||
              processing ||
              recognitionOutcome !== null
            }
            aria-label={t("dictionary.drill.recognitionCheck")}
            whileTap={processing ? undefined : { scale: 0.96 }}
            className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {processing ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Check className="size-4" aria-hidden="true" />
            )}
            {t("dictionary.drill.recognitionCheck")}
          </motion.button>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <motion.button
            type="button"
            onClick={() => void toggle()}
            disabled={!phraseReady || micBlocked}
            aria-pressed={recording}
            aria-label={
              processing
                ? t("pron.evaluating")
                : recording
                  ? t("pron.stop")
                  : t("pron.record")
            }
            whileTap={processing ? undefined : { scale: 0.94 }}
            className={cn(
              "grid size-12 place-items-center rounded-full text-primary-foreground transition-colors disabled:opacity-50",
              recording ? "bg-destructive" : "bg-primary hover:bg-primary/90",
            )}
          >
            {processing ? (
              <Loader2 className="size-5 animate-spin" aria-hidden="true" />
            ) : recording ? (
              <Square className="size-4" aria-hidden="true" />
            ) : (
              <Mic className="size-5" aria-hidden="true" />
            )}
          </motion.button>
          <span className="text-sm font-medium text-foreground">
            {processing
              ? t("pron.evaluating")
              : recording
                ? recordingSession.formatted
                : t("pron.record")}
          </span>
        </div>
      )}

      {result && (
        <div
          className={cn(
            "rounded-md px-3 py-2 text-sm",
            asrUnclear
              ? "bg-muted text-muted-foreground"
              : isSentenceAttempt(result)
                ? result.passed
                  ? "bg-success/10 text-success"
                  : "bg-warning/10 text-warning"
                : (result as DrillAttempt).produced
                  ? "bg-success/10 text-success"
                  : "bg-warning/10 text-warning",
          )}
          role="status"
        >
          {asrUnclear
            ? asrLabel
            : isSentenceAttempt(result)
              ? result.passed
                ? t("dictionary.drill.sentencePassed")
                : result.produced
                  ? t("dictionary.drill.sentenceWordOnly")
                  : t("dictionary.drill.sentenceNotPassed")
                      .replace("{heard}", result.heard || "—")
                      .replace("{score}", String(result.score))
              : (result as DrillAttempt).produced
                ? t("dictionary.drill.produced")
                : t("dictionary.drill.notProduced")
                    .replace("{heard}", result.heard || "—")
                    .replace("{score}", String(result.score))}
        </div>
      )}

      {/* V3.33: feedback del paso Recognition (informativo: el acierto no
          produce evidencia ni dispara onProduced). */}
      {step === "recognition" && recognitionOutcome && (
        <div
          className={cn(
            "rounded-md px-3 py-2 text-sm",
            recognitionOutcome.correct
              ? "bg-success/10 text-success"
              : "bg-warning/10 text-warning",
          )}
          role="status"
        >
          {recognitionOutcome.correct
            ? t("dictionary.drill.recognitionCorrect")
            : t("dictionary.drill.recognitionIncorrect").replace(
                "{correct}",
                recognition?.options[recognitionOutcome.correct_index] ?? "—",
              )}
        </div>
      )}
    </div>
  );
}
