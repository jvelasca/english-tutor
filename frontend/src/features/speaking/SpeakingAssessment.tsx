import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { motion } from "motion/react";
import { AlertTriangle, Loader2, Mic, Send, Square } from "lucide-react";
import {
  finishSpeakingAssessment,
  startSpeakingAssessment,
  submitSpeakingAssessmentPart,
} from "../../api/academy";
import { transcribe } from "../../api/voz";
import {
  getMicrophoneStream,
  MicUnavailableError,
  type MicUnavailableReason,
} from "../../utils/browserCapabilities";
import type {
  NextBestActivity,
  SpeakingAssessmentPartInfo,
  SpeakingAssessmentPartScores,
  SpeakingAssessmentResult,
} from "../../types/api";
import type { Section } from "../../utils/sections";
import {
  criterionLabel,
  formatConfidence,
  formatDurationTarget,
  formatScorePct,
  isConversationalTaskType,
} from "../../utils/speaking";
import { SpeakingRolePlay } from "./SpeakingRolePlay";
import { ActivityResult } from "../../components/ActivityResult";
import { ListenButton } from "../../components/ListenButton";
import {
  PhraseTranslateButton,
  usePhraseTranslation,
} from "../../components/PhraseTranslate";
import { NextStep } from "../../components/NextStep";
import { LevelBadge } from "../../components/LevelBadge";
import { MicUnavailableNotice } from "../../components/MicUnavailableNotice";
import { SkillBar } from "../../components/SkillBar";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { useI18n } from "../../hooks/useI18n";
import { cn } from "../../lib/utils";

type Phase = "idle" | "part" | "result";

interface SpeakingAssessmentProps {
  userId: string | null;
  onAttempt: () => void;
  onNext: (section: Section | null, step: NextBestActivity) => void;
}

function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <span className="min-w-0 break-words">{children}</span>
    </div>
  );
}

/**
 * Flujo completo del Speaking Assessment (start → 4 partes → resultado).
 * Soporta dos vías de respuesta: micrófono (grabación + transcripción) y
 * entrada manual por textarea, de modo que funcione incluso sin micrófono.
 */
export function SpeakingAssessment({
  userId,
  onAttempt,
  onNext,
}: SpeakingAssessmentProps) {
  const { t } = useI18n();
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
  const [micError, setMicError] = useState<MicUnavailableReason | null>(null);
  const [manualText, setManualText] = useState("");

  // Traducción de apoyo del prompt de la parte actual (se reinicia en cada parte).
  const promptPhrase = usePhraseTranslation(part?.prompt ?? "", part?.id);

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
      setError(`${t("assessment.startError")}${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  /** Envía la respuesta hablada (transcrita, manual o role-play) de la parte actual. */
  async function submitResponse(
    heard: string,
    durationSeconds?: number,
    conversationId?: string,
  ) {
    if (!userId || sessionId == null) return;
    setLoading(true);
    setError(null);
    try {
      const out = await submitSpeakingAssessmentPart(
        userId,
        sessionId,
        heard,
        durationSeconds,
        conversationId,
      );
      setPartScores(out.part_scores);
      setDone(out.done);
      setNextPart(out.next_part);
      setSubmitted(true);
    } catch (e) {
      setError(`${t("assessment.submitError")}${(e as Error).message}`);
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
      setError(t("assessment.noNextPart"));
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
      setError(`${t("assessment.finishError")}${(e as Error).message}`);
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
          setError(`${t("assessment.transcribeError")}${(e as Error).message}`);
        } finally {
          setProcessing(false);
        }
      };
      startTimeRef.current = performance.now();
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (e) {
      setError(`${t("assessment.micError")}${(e as Error).message}`);
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
      <Card className="gap-4 p-5">
        <p className="text-sm leading-relaxed text-muted-foreground">
          {t("assessment.startDesc")}
        </p>
        {error && <ErrorNote>{error}</ErrorNote>}
        <Button
          className="min-h-10 gap-2 self-start"
          onClick={handleStart}
          disabled={!userId || loading}
        >
          {loading && (
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          )}
          {loading ? t("assessment.starting") : t("assessment.start")}
        </Button>
      </Card>
    );
  }

  if (phase === "result" && result) {
    return (
      <ActivityResult
        outcome="neutral"
        title={t("assessment.titleScore").replace(
          "{score}",
          formatScorePct(result.score),
        )}
        footer={<NextStep userId={userId} onNext={onNext} />}
      >
        <header className="flex flex-wrap items-center gap-2">
          {result.level && <LevelBadge level={result.level} />}
        </header>

        <div className="rounded-md border border-border bg-muted px-3 py-2 text-xs text-muted-foreground">
          <span>
            {t("assessment.confidence")} {formatConfidence(result.confidence)}
          </span>
          <span aria-hidden="true"> · </span>
          <span>
            {result.attempts} {t("assessment.attempts")}
          </span>
        </div>

        <ul className="flex flex-col gap-3">
          {result.criteria.map((c) => {
            const score = c.recent_score ?? c.mean;
            const weak = c.review_due || (score != null && score < 0.6);
            return (
              <li key={c.criterion}>
                <SkillBar
                  label={criterionLabel(c.criterion)}
                  value={score ?? 0}
                  hint={`${weak ? "⚠ " : "✓ "}${formatScorePct(score)}`}
                />
              </li>
            );
          })}
        </ul>

        {result.recommendation && (
          <p className="text-sm leading-relaxed text-foreground">
            {result.recommendation}
          </p>
        )}

        <Button
          variant="outline"
          className="min-h-10 self-start"
          onClick={handleReset}
        >
          {t("assessment.another")}
        </Button>
      </ActivityResult>
    );
  }

  return (
    <Card className="gap-4 p-5">
      <header className="flex flex-wrap items-center gap-2">
        {part && <LevelBadge level={part.cefr_target} />}
      </header>

      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          {t("assessment.part")} {part?.part_index ?? 1} {t("assessment.of")}{" "}
          {totalParts}
        </span>
        {part && (
          <span className="tabular-nums text-muted-foreground">
            ~{formatDurationTarget(part.duration_target)}
          </span>
        )}
      </div>

      {part && (
        <>
          <p className="text-base font-semibold leading-snug">{part.title}</p>
          <div className="flex items-start justify-between gap-3">
            <p
              className="min-w-0 flex-1 rounded-md border border-border bg-muted px-3 py-2.5 text-sm leading-relaxed text-foreground"
              lang={promptPhrase.isSpanish ? "es" : "en"}
            >
              {promptPhrase.display}
            </p>
            <div className="flex shrink-0 items-center gap-2">
              <PhraseTranslateButton state={promptPhrase} />
              <ListenButton text={part.prompt} label={t("speak.phrase")} />
            </div>
          </div>
        </>
      )}

      {error && <ErrorNote>{error}</ErrorNote>}

      {micError && <MicUnavailableNotice reason={micError} />}

      {!submitted ? (
        part && isConversationalTaskType(part.task_type) ? (
          <SpeakingRolePlay
            key={part.id}
            userId={userId ?? ""}
            scenario={part.prompt}
            onFinish={(heard, durationSeconds, conversationId) =>
              void submitResponse(heard, durationSeconds, conversationId)
            }
          />
        ) : (
          <>
            <div className="flex items-center gap-3">
              <motion.button
                type="button"
                onClick={toggleRecording}
                disabled={processing || !userId}
                aria-pressed={recording}
                aria-label={
                  processing
                    ? t("assessment.transcribing")
                    : recording
                      ? t("assessment.stop")
                      : t("assessment.record")
                }
                whileTap={
                  processing || !userId ? undefined : { scale: 0.94 }
                }
                className={cn(
                  "relative grid size-14 shrink-0 place-items-center rounded-full text-primary-foreground transition-colors disabled:opacity-50",
                  recording
                    ? "bg-destructive"
                    : "bg-primary hover:bg-primary/90",
                  processing && "opacity-60",
                )}
              >
                {recording && (
                  <motion.span
                    aria-hidden="true"
                    className="absolute inset-0 rounded-full border-2 border-destructive"
                    animate={{ scale: [1, 1.6], opacity: [0.6, 0] }}
                    transition={{
                      duration: 1.4,
                      repeat: Infinity,
                      ease: "easeOut",
                    }}
                  />
                )}
                {processing ? (
                  <Loader2 className="size-6 animate-spin" aria-hidden="true" />
                ) : recording ? (
                  <Square className="size-5" aria-hidden="true" />
                ) : (
                  <Mic className="size-6" aria-hidden="true" />
                )}
              </motion.button>
              <span className="text-sm font-medium text-foreground">
                {processing
                  ? t("assessment.transcribing")
                  : recording
                    ? t("assessment.stop")
                    : t("assessment.record")}
              </span>
            </div>

            <label className="flex flex-col gap-2">
              <span className="text-xs font-medium text-muted-foreground">
                {t("assessment.orType")}
              </span>
              <textarea
                className="min-h-[72px] w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm leading-relaxed outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/50 disabled:opacity-60"
                value={manualText}
                onChange={(e) => setManualText(e.target.value)}
                placeholder={t("assessment.placeholder")}
                rows={3}
                maxLength={2000}
                disabled={loading}
              />
            </label>

            <Button
              className="min-h-10 gap-2 self-start"
              onClick={handleManualSubmit}
              disabled={!manualText.trim() || loading || !userId}
            >
              {loading ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Send className="size-4" aria-hidden="true" />
              )}
              {loading ? t("assessment.sending") : t("assessment.submit")}
            </Button>
          </>
        )
      ) : (
        <>
          {partScores && (
            <div className="flex items-baseline gap-2 rounded-md border border-border bg-muted px-3 py-2.5">
              <span className="text-xl font-bold text-primary">
                {formatScorePct(partScores.overall)}
              </span>
              <span className="text-xs text-muted-foreground">
                {t("assessment.ofThisPart")}
              </span>
            </div>
          )}

          {partScores && Object.keys(partScores.observed).length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {Object.entries(partScores.observed).map(([key, seen]) => (
                <li key={key}>
                  <Badge
                    variant={seen ? "default" : "outline"}
                    className="gap-1.5"
                  >
                    {seen ? "✓" : "—"} {criterionLabel(key)}
                  </Badge>
                </li>
              ))}
            </ul>
          )}

          {error && <ErrorNote>{error}</ErrorNote>}

          <Button
            className="min-h-10 gap-2 self-start"
            onClick={handleAdvance}
            disabled={loading}
          >
            {loading && (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            )}
            {loading
              ? t("assessment.processing")
              : done
                ? t("assessment.viewResult")
                : t("assessment.nextPart")}
          </Button>
        </>
      )}
    </Card>
  );
}
