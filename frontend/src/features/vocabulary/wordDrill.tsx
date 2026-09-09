/**
 * Escalera de micro-drill oral de una palabra (V3.19/V3.21): Recall → Sentence.
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
 */
import { useRef, useState } from "react";
import { motion, type Variants } from "motion/react";
import { Loader2, Mic, Square } from "lucide-react";
import {
  getDrillSentenceContext,
  submitDrillAttempt,
  submitDrillSentenceAttempt,
} from "../../api/vocabulary";
import type {
  DrillAttempt,
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

export type DrillStep = "recall" | "sentence";

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

/** Micro-práctica escalera de una palabra (V3.21/F6): Paso 1 "Recall" — di la
 * palabra (scorer `submitDrillAttempt`); Paso 2 "Sentence" — repítela DENTRO de
 * una frase de contexto determinista (scorer `submitDrillSentenceAttempt`).
 * Reutiliza el scorer de pronunciación del servidor. No declara dominio (D5/E3):
 * una producción del día no consolida; se consolida con éxito espaciado (F6.2).
 * V3.32: reutilizable desde el diccionario de consulta (botón «Practicar esta
 * palabra») porque solo depende de `userId` + `word`. */
export function WordDrill({ userId, word, onProduced, onClose }: WordDrillProps) {
  const { t } = useI18n();
  const [step, setStep] = useState<DrillStep>("recall");
  const [sentence, setSentence] = useState<DrillSentenceContext | null>(null);
  const [sentenceError, setSentenceError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<DrillOutcome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [micReason, setMicReason] = useState<MicUnavailableReason | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  // V3.21 (V20-13): cronómetro visible + auto-stop a 120 s (máximo del backend).
  const recordingSession = useRecordingSession(recording, {
    onAutoStop: () => {
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop();
        setRecording(false);
      }
    },
  });

  function chooseStep(next: DrillStep) {
    if (next === step || recording || processing) return;
    setResult(null);
    setError(null);
    setStep(next);
    if (next === "sentence" && !sentence) {
      setSentenceError(null);
      getDrillSentenceContext(userId, word)
        .then((ctx) => setSentence(ctx))
        .catch((e) =>
          setSentenceError(t("dictionary.drill.error").concat((e as Error).message)),
        );
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

      {/* Escalera Recall -> Sentence en la misma tarjeta (V3.21/F6.1). */}
      <div
        role="group"
        aria-label={t("dictionary.drill.steps")}
        className="flex w-fit items-center gap-1 rounded-md bg-secondary p-1"
      >
        {(["recall", "sentence"] as const).map((option) => (
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
            {option === "recall"
              ? t("dictionary.drill.stepRecall")
              : t("dictionary.drill.stepSentence")}
          </button>
        ))}
      </div>

      {step === "recall" ? (
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
    </div>
  );
}
