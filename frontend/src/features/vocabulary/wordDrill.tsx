/**
 * Escalera de micro-drill de una palabra (V3.19/V3.21/V3.33/V3.34):
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
 * V3.34 (Recall 2.0): el peldaño Recall es RECUPERACIÓN por TEXTO — el alumno
 * ve el SIGNIFICADO (cue) y teclea la palabra; no usa micrófono y su acierto
 * NO acredita producción (solo señal léxica de recall + FSRS), así que tampoco
 * dispara `onProduced`. El micrófono queda reservado al paso Sentence.
 * V3.39 (Fase 3): se añade el peldaño Write — frase PROPIA que acredita la
 * modalidad escrita y cierra el hueco `spoken ✓ / written ✗`.
 * V3.40 (Fase 4): se añade el peldaño Transfer — usar la unidad en un CONTEXTO
 * NUEVO servido por el backend; acredita `spontaneous_use` con su `context_id`.
 * Los peldaños presentacionales viven en `wordDrillSteps.tsx` (descomposición).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { motion, type Variants } from "motion/react";
import { Check, Loader2, Mic, Square } from "lucide-react";
import {
  getDrillRecallPrompt,
  getDrillRecognitionQuestion,
  getDrillSentenceContext,
  getDrillTransferContext,
  submitDrillRecallAttempt,
  submitDrillRecognitionAttempt,
  submitDrillSentenceAttempt,
  submitDrillTransferAttempt,
  submitDrillWriteAttempt,
} from "../../api/vocabulary";
import type {
  DrillAttempt,
  DrillRecallAttempt,
  DrillRecallPrompt,
  DrillRecognitionAttempt,
  DrillRecognitionQuestion,
  DrillSentenceAttempt,
  DrillSentenceContext,
  DrillTransferAttempt,
  DrillTransferContext,
  DrillWriteAttempt,
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
import {
  ProductionTextarea,
  RecallStep,
  RecognitionStep,
  TransferStep,
} from "./wordDrillSteps";

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

export type DrillStep =
  | "recognition"
  | "recall"
  | "sentence"
  | "write"
  | "transfer";

/** Etiqueta i18n de cada peldaño (orden de la escalera). */
const STEP_LABEL_KEY: Record<DrillStep, string> = {
  recognition: "dictionary.drill.stepRecognition",
  recall: "dictionary.drill.stepRecall",
  sentence: "dictionary.drill.stepSentence",
  write: "dictionary.drill.stepWrite",
  transfer: "dictionary.drill.stepTransfer",
};

const DRILL_STEPS: readonly DrillStep[] = [
  "recognition",
  "recall",
  "sentence",
  "write",
  "transfer",
];

/** V3.39: longitud mínima (en palabras) de la frase propia que acredita la
 * modalidad escrita. Espejo de `services.lexicon.WRITE_MIN_WORDS`; el servidor
 * es quien puntúa (premisa 21), esto solo se muestra en la consigna. */
const WRITE_MIN_WORDS = 4;

export interface SpeakingDrillSectionProps {
  userId: string;
  words: string[];
  drillWord: string | null;
  onDrillChange: (word: string | null) => void;
  onProduced: (word: string) => void;
  /** V3.35: peldaño con el que abre el drill de la palabra seleccionada (la
   * cola de repaso abre directamente en la actividad recomendada). */
  initialStep?: DrillStep;
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
  initialStep,
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
            initialStep={initialStep}
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
  /** V3.35: peldaño inicial de la escalera. Por defecto Recognition (V3.33.1);
   * la cola de repaso abre en la actividad recomendada por hueco. */
  initialStep?: DrillStep;
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
 * Paso 2 "Recall" (V3.34, Recall 2.0) — recupera y teclea la palabra a partir
 * de su significado (sin micrófono, puntuado en servidor); Paso 3 "Sentence" —
 * repítela DENTRO de una frase de contexto determinista (scorer
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
 * correcta.
 * V3.34: el peldaño Recall pasa a ser recuperación por TEXTO (se retira el
 * paso oral de palabra suelta): el micrófono queda solo para Sentence y
 * `onProduced` solo lo dispara Sentence (un recall correcto deja señal léxica
 * de recall, no producción). Si Recall no tiene cue, degrada a Sentence. */
export function WordDrill({
  userId,
  word,
  onProduced,
  onClose,
  initialStep = "recognition",
}: WordDrillProps) {
  const { t } = useI18n();
  // V3.33.1: el drill abre en el primer peldaño (Recognition) salvo que la cola
  // de repaso pida otro (V3.35). Si la pregunta no está disponible,
  // `loadRecognition` degrada a Recall (V3.19).
  const [step, setStep] = useState<DrillStep>(initialStep);
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
  // V3.34: estado del paso Recall (cue + palabra tecleada; la esperada solo
  // llega en la respuesta).
  const [recall, setRecall] = useState<DrillRecallPrompt | null>(null);
  const [recallError, setRecallError] = useState<string | null>(null);
  const [recallAnswer, setRecallAnswer] = useState("");
  const [recallOutcome, setRecallOutcome] = useState<DrillRecallAttempt | null>(
    null,
  );
  // V3.39: estado del paso Write (frase propia con la palabra objetivo; la
  // puntuación es del servidor: unidad alineada + longitud mínima).
  const [writeAnswer, setWriteAnswer] = useState("");
  const [writeOutcome, setWriteOutcome] = useState<DrillWriteAttempt | null>(
    null,
  );
  // Instante en que la consigna de escritura quedó visible (latencia
  // observacional; opcional, como en Recall).
  const writeShownAtRef = useRef<number | null>(null);
  // V3.40: estado del paso Transfer (consigna de contexto NUEVO + producción
  // propia; la puntuación es del servidor y el `context_id` viaja al ledger).
  const [transfer, setTransfer] = useState<DrillTransferContext | null>(null);
  const [transferError, setTransferError] = useState<string | null>(null);
  const [transferAnswer, setTransferAnswer] = useState("");
  const [transferOutcome, setTransferOutcome] =
    useState<DrillTransferAttempt | null>(null);
  const transferShownAtRef = useRef<number | null>(null);
  // V3.36: instante en que el cue de Recall quedó visible. La latencia
  // (cue → envío) se manda como `response_time_ms` del evento de evidencia; es
  // observacional (no cambia la puntuación) y opcional (sin cue no hay medida).
  const recallShownAtRef = useRef<number | null>(null);
  // V3.21 (V20-13): cronómetro visible + auto-stop a 120 s (máximo del backend).
  const recordingSession = useRecordingSession(recording, {
    onAutoStop: () => {
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop();
        setRecording(false);
      }
    },
  });

  /** Carga la frase de contexto del paso Sentence (determinista en servidor). */
  const loadSentence = useCallback(() => {
    setSentenceError(null);
    getDrillSentenceContext(userId, word)
      .then((ctx) => setSentence(ctx))
      .catch((e) =>
        setSentenceError(t("dictionary.drill.error").concat((e as Error).message)),
      );
  }, [userId, word, t]);

  /** Carga el cue del paso Recall (V3.34). Si no hay cue utilizable
   * (`available=false`), degrada a Sentence sin romper la escalera y sin pisar
   * una elección manual de otro paso. */
  const loadRecall = useCallback(() => {
    setRecallError(null);
    setRecallAnswer("");
    setRecallOutcome(null);
    recallShownAtRef.current = null;
    getDrillRecallPrompt(userId, word)
      .then((prompt) => {
        setRecall(prompt);
        // V3.36: el reloj de la latencia arranca cuando el cue es utilizable
        // (con `available=false` no hay intento posible y no se mide nada).
        recallShownAtRef.current = prompt.available ? Date.now() : null;
        if (!prompt.available) {
          setStep((current) => {
            if (current !== "recall") return current;
            loadSentence();
            return "sentence";
          });
        }
      })
      .catch((e) =>
        setRecallError(
          t("dictionary.drill.error").concat((e as Error).message),
        ),
      );
  }, [userId, word, t, loadSentence]);

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
          setStep((current) => {
            if (current !== "recognition") return current;
            loadRecall();
            return "recall";
          });
        }
      })
      .catch((e) =>
        setRecognitionError(
          t("dictionary.drill.error").concat((e as Error).message),
        ),
      );
  }, [userId, word, t, loadRecall]);

  /** Carga la consigna del paso Transfer (V3.40): contexto NUEVO elegido por el
   * servidor entre los que el ítem aún no usó. Si no hay consigna
   * (`available=false`), degrada a Sentence sin romper la escalera. */
  const loadTransfer = useCallback(() => {
    setTransferError(null);
    setTransferAnswer("");
    setTransferOutcome(null);
    transferShownAtRef.current = null;
    getDrillTransferContext(userId, word)
      .then((ctx) => {
        setTransfer(ctx);
        transferShownAtRef.current = ctx.available ? Date.now() : null;
      })
      .catch((e) =>
        setTransferError(
          t("dictionary.drill.error").concat((e as Error).message),
        ),
      );
  }, [userId, word, t]);

  // V3.33.1 / V3.35: el drill arranca en el peldaño pedido (`initialStep`,
  // Recognition por defecto) y limpia el intento anterior al montar o cambiar
  // de palabra o de peldaño inicial.
  useEffect(() => {
    setStep(initialStep);
    setSentence(null);
    setSentenceError(null);
    setResult(null);
    setError(null);
    setRecognition(null);
    setRecall(null);
    setWriteAnswer("");
    setWriteOutcome(null);
    writeShownAtRef.current = initialStep === "write" ? Date.now() : null;
    setTransfer(null);
    setTransferAnswer("");
    setTransferOutcome(null);
    transferShownAtRef.current = initialStep === "transfer" ? Date.now() : null;
    if (initialStep === "recall") {
      loadRecall();
    } else if (initialStep === "sentence") {
      loadSentence();
    } else if (initialStep === "transfer") {
      // V3.40: el paso Transfer sí carga consigna (el contexto nuevo).
      loadTransfer();
    } else if (initialStep !== "write") {
      // Los pasos Write (V3.39) no tienen contenido que cargar: la consigna es
      // la propia palabra objetivo (ya visible) y la puntuación es del servidor.
      loadRecognition();
    }
  }, [loadRecognition, loadRecall, loadSentence, loadTransfer, initialStep]);

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
    if (next === "recall") {
      // V3.34: cada entrada en Recall pide el cue (determinista en servidor).
      loadRecall();
      setStep(next);
      return;
    }
    if (next === "write") {
      // V3.39: cada entrada reinicia el intento y arranca el reloj de latencia.
      setWriteAnswer("");
      setWriteOutcome(null);
      writeShownAtRef.current = Date.now();
      setStep(next);
      return;
    }
    if (next === "transfer") {
      // V3.40: cada entrada pide una consigna de contexto nuevo (determinista
      // en servidor según los contextos ya usados) y reinicia el intento.
      loadTransfer();
      setStep(next);
      return;
    }
    if (next === "sentence" && !sentence) {
      loadSentence();
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

  async function submitRecall() {
    if (!recall || !recall.available || !recallAnswer.trim()) return;
    setProcessing(true);
    setError(null);
    try {
      // V3.36: latencia cue → envío (observacional). Si no se midió, se omite.
      const shownAt = recallShownAtRef.current;
      const responseTimeMs =
        shownAt === null ? undefined : Math.max(0, Date.now() - shownAt);
      const outcome = await submitDrillRecallAttempt(
        userId,
        word,
        recallAnswer,
        responseTimeMs,
        recall.cue_kind || undefined,
      );
      setRecallOutcome(outcome);
    } catch (e) {
      setError(t("dictionary.drill.error").concat((e as Error).message));
    } finally {
      setProcessing(false);
    }
  }

  async function submitWrite() {
    if (!writeAnswer.trim() || writeOutcome !== null) return;
    setProcessing(true);
    setError(null);
    try {
      const shownAt = writeShownAtRef.current;
      const responseTimeMs =
        shownAt === null ? undefined : Math.max(0, Date.now() - shownAt);
      const outcome = await submitDrillWriteAttempt(
        userId,
        word,
        writeAnswer,
        responseTimeMs,
      );
      setWriteOutcome(outcome);
      if (outcome.passed) onProduced();
    } catch (e) {
      setError(t("dictionary.drill.error").concat((e as Error).message));
    } finally {
      setProcessing(false);
    }
  }

  async function submitTransfer() {
    if (!transfer || !transfer.available) return;
    if (!transferAnswer.trim() || transferOutcome !== null) return;
    setProcessing(true);
    setError(null);
    try {
      const shownAt = transferShownAtRef.current;
      const responseTimeMs =
        shownAt === null ? undefined : Math.max(0, Date.now() - shownAt);
      const outcome = await submitDrillTransferAttempt(
        userId,
        word,
        transferAnswer,
        transfer.context_id,
        responseTimeMs,
      );
      setTransferOutcome(outcome);
      if (outcome.passed) onProduced();
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
          // V3.34: el micrófono queda reservado al paso Sentence (la escalera
          // ya no tiene un paso oral de palabra suelta).
          const attempt = await submitDrillSentenceAttempt(userId, word, blob);
          setResult(attempt);
          if (attempt.passed) onProduced();
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

  const micBlocked =
    processing ||
    (step === "sentence" && (sentence === null || sentenceError !== null));
  // V3.34: en Recall se OCULTA la palabra diana (el resultado la revela).
  // V3.43 (P1-01): en Transfer TAMBIÉN: la consigna da un escenario, nunca el
  // target, así que la cabecera no puede revelarlo antes del intento.
  const hideTarget =
    (step === "recall" && recallOutcome === null) ||
    (step === "transfer" && transferOutcome === null);

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-background/60 p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {hideTarget ? (
            <span
              className={cn(
                "text-base font-semibold",
                step === "recall" &&
                  recall?.cue_kind === "cloze" &&
                  "font-mono",
              )}
            >
              {step === "transfer"
                ? t("dictionary.drill.transferHiddenTarget")
                : recall
                  ? recall.cue
                  : "…"}
            </span>
          ) : (
            <>
              <span className="text-lg font-semibold" lang="en">
                {word}
              </span>
              <ListenButton text={word} label={t("speak.phrase")} />
            </>
          )}
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
          (V3.21/F6.1 + V3.33 Recognition + V3.34 Recall por texto). */}
      <div
        role="group"
        aria-label={t("dictionary.drill.steps")}
        className="flex w-fit items-center gap-1 rounded-md bg-secondary p-1"
      >
        {DRILL_STEPS.map((option) => (
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
            {t(STEP_LABEL_KEY[option])}
          </button>
        ))}
      </div>

      {step === "recognition" ? (
        <RecognitionStep
          question={recognition}
          error={recognitionError}
          selected={recognitionSelected}
          onSelect={setRecognitionSelected}
          disabled={processing || recognitionOutcome !== null}
        />
      ) : step === "recall" ? (
        <RecallStep
          prompt={recall}
          error={recallError}
          answer={recallAnswer}
          onAnswerChange={setRecallAnswer}
          outcome={recallOutcome}
          processing={processing}
          onSubmit={() => void submitRecall()}
        />
      ) : step === "write" ? (
        <ProductionTextarea
          prompt={t("dictionary.drill.writePrompt").replace("{word}", word)}
          value={writeAnswer}
          onValueChange={setWriteAnswer}
          disabled={processing || writeOutcome !== null}
          inputLabel={t("dictionary.drill.writeInputLabel")}
          placeholder={t("dictionary.drill.writePlaceholder")}
          minWordsNote={t("dictionary.drill.writeMinWords").replace(
            "{count}",
            String(WRITE_MIN_WORDS),
          )}
        />
      ) : step === "transfer" ? (
        <TransferStep
          context={transfer}
          error={transferError}
          answer={transferAnswer}
          onAnswerChange={setTransferAnswer}
          disabled={processing || transferOutcome !== null}
          minWordsNote={t("dictionary.drill.writeMinWords").replace(
            "{count}",
            String(WRITE_MIN_WORDS),
          )}
          inputLabel={t("dictionary.drill.transferInputLabel")}
          placeholder={t("dictionary.drill.transferPlaceholder")}
        />
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
      ) : step === "recall" ? null : step === "write" ? (
        <div className="flex items-center gap-3">
          <motion.button
            type="button"
            onClick={() => void submitWrite()}
            disabled={!writeAnswer.trim() || processing || writeOutcome !== null}
            aria-label={t("dictionary.drill.writeCheck")}
            whileTap={processing ? undefined : { scale: 0.96 }}
            className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {processing ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Check className="size-4" aria-hidden="true" />
            )}
            {t("dictionary.drill.writeCheck")}
          </motion.button>
        </div>
      ) : step === "transfer" ? (
        <div className="flex items-center gap-3">
          <motion.button
            type="button"
            onClick={() => void submitTransfer()}
            disabled={
              !transfer ||
              !transfer.available ||
              !transferAnswer.trim() ||
              processing ||
              transferOutcome !== null
            }
            aria-label={t("dictionary.drill.transferCheck")}
            whileTap={processing ? undefined : { scale: 0.96 }}
            className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {processing ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Check className="size-4" aria-hidden="true" />
            )}
            {t("dictionary.drill.transferCheck")}
          </motion.button>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <motion.button
            type="button"
            onClick={() => void toggle()}
            disabled={!sentence || micBlocked}
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

      {/* V3.34: feedback del paso Recall (recuperación por texto: el acierto
          deja señal léxica de recall, nunca producción ni onProduced). */}
      {step === "recall" && recallOutcome && (
        <div
          className={cn(
            "rounded-md px-3 py-2 text-sm",
            recallOutcome.correct
              ? "bg-success/10 text-success"
              : "bg-warning/10 text-warning",
          )}
          role="status"
        >
          {recallOutcome.correct
            ? t("dictionary.drill.recallCorrect")
            : t("dictionary.drill.recallIncorrect").replace(
                "{expected}",
                recallOutcome.expected || "—",
              )}
        </div>
      )}

      {/* V3.39: feedback del paso Write. El acierto acredita la modalidad
          escrita (cierra el hueco del motor de tarea óptima); el fallo explica
          qué faltó (palabra objetivo / longitud) sin declarar dominio. */}
      {step === "write" && writeOutcome && (
        <div
          className={cn(
            "rounded-md px-3 py-2 text-sm",
            writeOutcome.passed
              ? "bg-success/10 text-success"
              : "bg-warning/10 text-warning",
          )}
          role="status"
        >
          {writeOutcome.passed
            ? t("dictionary.drill.writePassed")
            : writeOutcome.used_word
              ? t("dictionary.drill.writeTooShort").replace(
                  "{count}",
                  String(WRITE_MIN_WORDS),
                )
              : t("dictionary.drill.writeMissingWord").replace(
                  "{word}",
                  word,
                )}
        </div>
      )}

      {/* V3.40: feedback del paso Transfer. El acierto acredita
          `spontaneous_use` en un contexto NUEVO (transferencia real cuando se
          logra en >= 2 contextos); el fallo explica qué faltó sin declarar
          dominio. V3.43 (P1-02): un acierto léxico con uso semánticamente
          sospechoso se avisa en tono warning (hubo producción léxica, pero no
          cuenta como éxito limpio). */}
      {step === "transfer" && transferOutcome && (
        <div
          className={cn(
            "rounded-md px-3 py-2 text-sm",
            transferOutcome.passed && transferOutcome.adequacy !== "suspect"
              ? "bg-success/10 text-success"
              : "bg-warning/10 text-warning",
          )}
          role="status"
        >
          {transferOutcome.passed
            ? transferOutcome.adequacy === "suspect"
              ? t("dictionary.drill.transferSemanticWarning")
              : t("dictionary.drill.transferPassed")
            : transferOutcome.used_word
              ? t("dictionary.drill.writeTooShort").replace(
                  "{count}",
                  String(WRITE_MIN_WORDS),
                )
              : t("dictionary.drill.writeMissingWord").replace(
                  "{word}",
                  word,
                )}
        </div>
      )}
    </div>
  );
}
