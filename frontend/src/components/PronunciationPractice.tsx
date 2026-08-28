import { useRef, useState } from "react";
import { motion } from "motion/react";
import { Loader2, Mic, Square } from "lucide-react";
import { checkPronunciation } from "../api/pronunciation";
import type { NextBestActivity, PronunciationResponse } from "../types/api";
import type { Section } from "../utils/sections";
import { fluencyLevelLabel, wpmLabel } from "../utils/fluency";
import { feedbackHints, wordsCorrectLabel } from "../utils/pronunciationFeedback";
import {
  getMicrophoneStream,
  MicUnavailableError,
  type MicUnavailableReason,
} from "../utils/browserCapabilities";
import { ActivityResult } from "./ActivityResult";
import { NextStep } from "./NextStep";
import { MicUnavailableNotice } from "./MicUnavailableNotice";
import { Card } from "./ui/card";
import { useI18n } from "../hooks/useI18n";
import { cn } from "../lib/utils";

const SAMPLES = [
  "Hello, how are you?",
  "I would like a cup of coffee.",
  "The weather is nice today.",
];

interface PronunciationPracticeProps {
  userId: string | null;
  onAttempt: () => void;
  onNext: (section: Section | null, step: NextBestActivity) => void;
}

export function PronunciationPractice({
  userId,
  onAttempt,
  onNext,
}: PronunciationPracticeProps) {
  const { t } = useI18n();
  const [sentence, setSentence] = useState(SAMPLES[0]);
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<PronunciationResponse | null>(null);
  const [micError, setMicError] = useState<MicUnavailableReason | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const hints = result ? feedbackHints(result.breakdown) : [];

  async function toggle() {
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
        if (!userId) return;
        setProcessing(true);
        try {
          setResult(await checkPronunciation(blob, sentence, userId));
          onAttempt();
        } catch (e) {
          alert(`${t("pron.evalError")}${(e as Error).message}`);
        } finally {
          setProcessing(false);
        }
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (e) {
      alert(`${t("pron.micError")}${(e as Error).message}`);
    }
  }

  return (
    <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 overflow-y-auto px-4 py-6 sm:px-6">
      <header>
        <h2 className="text-2xl font-bold tracking-tight">{t("pron.title")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("pron.prompt")}</p>
      </header>

      {micError && <MicUnavailableNotice reason={micError} />}

      <Card className="gap-5 p-5 sm:p-6">
        <div className="flex flex-wrap gap-2">
          {SAMPLES.map((s) => (
            <button
              key={s}
              className={cn(
                "min-h-10 rounded-full border px-3 text-sm transition-colors",
                s === sentence
                  ? "border-transparent bg-primary text-primary-foreground"
                  : "border-border bg-secondary text-secondary-foreground hover:border-primary/50",
              )}
              onClick={() => setSentence(s)}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="flex flex-col items-center gap-3 border-t border-border pt-5">
          <motion.button
            type="button"
            onClick={toggle}
            disabled={processing || !userId}
            aria-pressed={recording}
            aria-label={
              processing
                ? t("pron.evaluating")
                : recording
                  ? t("pron.stop")
                  : t("pron.record")
            }
            whileTap={processing || !userId ? undefined : { scale: 0.94 }}
            className={cn(
              "relative grid size-16 shrink-0 place-items-center rounded-full text-primary-foreground transition-colors disabled:opacity-50",
              recording ? "bg-destructive" : "bg-primary hover:bg-primary/90",
              processing && "opacity-60",
            )}
          >
            {recording && (
              <motion.span
                aria-hidden="true"
                className="absolute inset-0 rounded-full border-2 border-destructive"
                animate={{ scale: [1, 1.6], opacity: [0.6, 0] }}
                transition={{ duration: 1.4, repeat: Infinity, ease: "easeOut" }}
              />
            )}
            {processing ? (
              <Loader2 className="size-7 animate-spin" aria-hidden="true" />
            ) : recording ? (
              <Square className="size-6" aria-hidden="true" />
            ) : (
              <Mic className="size-7" aria-hidden="true" />
            )}
          </motion.button>
          <span className="text-sm font-medium text-foreground">
            {processing
              ? t("pron.evaluating")
              : recording
                ? t("pron.stop")
                : t("pron.record")}
          </span>
        </div>
      </Card>

      {result && (
        <ActivityResult
          outcome={
            result.level === "good"
              ? "ok"
              : result.level === "fair"
                ? "neutral"
                : "ko"
          }
          title={`${t("pron.title")} · ${result.score}/100`}
          footer={<NextStep userId={userId} onNext={onNext} />}
        >
          <div className="flex flex-col gap-1 text-sm">
            <div>
              <span className="text-muted-foreground">{t("pron.expected")}:</span>{" "}
              {result.expected}
            </div>
            <div>
              <span className="text-muted-foreground">{t("pron.heard")}:</span>{" "}
              {result.heard}
            </div>
            <div>
              <span className="text-muted-foreground">{t("pron.level")}:</span>{" "}
              {result.level === "good"
                ? t("pron.level.good")
                : result.level === "fair"
                  ? t("pron.level.fair")
                  : t("pron.level.needsPractice")}
            </div>
            <div>
              <span className="text-muted-foreground">
                {t("pron.wordAccuracy")}:
              </span>{" "}
              {result.word_accuracy}%
            </div>
            <div>
              <span className="text-muted-foreground">
                {t("pron.phoneticScore")}:
              </span>{" "}
              {result.phonetic_score}%
            </div>
            <div>
              <span className="text-muted-foreground">
                {t("pron.phonemeAccuracy")}:
              </span>{" "}
              {result.phoneme_accuracy_proxy}%
            </div>
            <div>
              <span className="text-muted-foreground">{t("pron.prosody")}:</span>{" "}
              {result.prosody_proxy}%
            </div>
            <div>
              <span className="text-muted-foreground">{t("pron.fluency")}:</span>{" "}
              {fluencyLevelLabel(result.fluency.level)} ·{" "}
              {wpmLabel(result.fluency.wpm)}
            </div>
          </div>
          <p className="text-sm text-muted-foreground">
            {wordsCorrectLabel(result.breakdown)}
          </p>
          {hints.length > 0 && (
            <ul className="flex flex-col gap-1 text-sm text-foreground">
              {hints.map((hint) => (
                <li key={hint}>{hint}</li>
              ))}
            </ul>
          )}
        </ActivityResult>
      )}
    </section>
  );
}
