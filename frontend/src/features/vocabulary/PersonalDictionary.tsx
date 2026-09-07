import { useCallback, useEffect, useRef, useState } from "react";
import { motion, type Variants } from "motion/react";
import { BookOpen, Loader2, Mic, RefreshCw, Square } from "lucide-react";
import {
  getDrillCandidates,
  getDrillSentenceContext,
  getLexicon,
  submitDrillAttempt,
  submitDrillSentenceAttempt,
} from "../../api/vocabulary";
import type {
  DrillAttempt,
  DrillSentenceAttempt,
  DrillSentenceContext,
  LexicalItem,
  LexicalStatus,
  Lexicon,
} from "../../types/api";
import { cefrBarValue, sortLexicalItems } from "./dictionary";
import { useI18n } from "../../hooks/useI18n";
import { useRecordingSession } from "../../hooks/useRecordingSession";
import { LevelBadge } from "../../components/LevelBadge";
import { SkillBar } from "../../components/SkillBar";
import { ListenButton } from "../../components/ListenButton";
import { MicUnavailableNotice } from "../../components/MicUnavailableNotice";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Progress } from "../../components/ui/progress";
import {
  getMicrophoneStream,
  MicUnavailableError,
  type MicUnavailableReason,
} from "../../utils/browserCapabilities";
import { cn } from "../../lib/utils";

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
};

const STATUS_TONE: Record<LexicalStatus, string> = {
  mastered: "border-transparent bg-success/15 text-success",
  known: "border-transparent bg-primary/15 text-primary",
  learning: "border-transparent bg-warning/15 text-warning",
  weak: "border-transparent bg-destructive/10 text-destructive",
};

interface PersonalDictionaryProps {
  userId: string | null;
}

/** Diccionario personal (V2.3): evidencia por ítem léxico con estado y recall.
 * V3.19: la sección de candidatas al speaking micro-drill se nutre de la señal
 * determinista del servidor (`getDrillCandidates`) y cada palabra gana una
 * acción de micro-práctica oral dentro del panel. */
export function PersonalDictionary({ userId }: PersonalDictionaryProps) {
  const { t } = useI18n();
  const [lexicon, setLexicon] = useState<Lexicon | null>(null);
  const [candidates, setCandidates] = useState<string[]>([]);
  const [drillWord, setDrillWord] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);

  const refresh = useCallback(async () => {
    if (!userId) return;
    try {
      const [data, drill] = await Promise.all([
        getLexicon(userId),
        getDrillCandidates(userId),
      ]);
      setLexicon(data);
      setCandidates(drill.words);
      setLoadError(false);
    } catch {
      /* backend no disponible */
      setLoadError(true);
    }
  }, [userId]);

  useEffect(() => {
    if (!userId) return;
    void refresh();
  }, [userId, refresh]);

  if (!lexicon) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
        <DictionaryHeader />
        {loadError ? (
          <p className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
            {t("dictionary.loadError")}
            <button
              type="button"
              onClick={() => void refresh()}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium hover:border-primary/50"
            >
              <RefreshCw className="size-3.5" aria-hidden="true" />
              {t("common.retry")}
            </button>
          </p>
        ) : (
          <p className="mt-4 text-sm text-muted-foreground">{t("common.loading")}</p>
        )}
      </div>
    );
  }

  const { summary, items } = lexicon;
  const sorted = sortLexicalItems(items);

  const maxCefr = Math.max(1, ...summary.by_cefr.map((b) => b.count));

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-5"
      >
        <DictionaryHeader total={summary.total} />

        <motion.section variants={item} aria-label={t("dictionary.title")}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile
              label={t("dictionary.known")}
              value={summary.known}
              tone="text-primary"
            />
            <StatTile
              label={t("dictionary.learning")}
              value={summary.learning}
              tone="text-warning"
            />
            <StatTile
              label={t("dictionary.weak")}
              value={summary.weak}
              tone="text-destructive"
            />
            <StatTile
              label={t("dictionary.mastered")}
              value={summary.mastered}
              tone="text-success"
            />
          </div>
        </motion.section>

        {/* V3.21 (V20-16): fila de stats de la matriz de competencia del léxico. */}
        <motion.section variants={item} aria-label={t("dictionary.competenceTitle")}>
          <Card className="gap-3 p-5">
            <div className="flex flex-col gap-1">
              <h2 className="text-sm font-semibold">{t("dictionary.competenceTitle")}</h2>
              <p className="text-[11px] leading-relaxed text-muted-foreground">
                {t("dictionary.competenceHint")}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <StatTile
                label={t("dictionary.competenceRecognized")}
                value={summary.recognized}
                tone="text-primary"
              />
              <StatTile
                label={t("dictionary.competenceProduced")}
                value={summary.produced}
                tone="text-success"
              />
              <StatTile
                label={t("dictionary.competenceTransfer")}
                value={summary.transfer}
                tone="text-success"
              />
              <StatTile
                label={t("dictionary.competenceRetention")}
                value={summary.retention}
                tone="text-primary"
              />
              <StatTile
                label={t("dictionary.competenceGap")}
                value={summary.transfer_gap}
                tone="text-destructive"
              />
            </div>
          </Card>
        </motion.section>

        {summary.by_cefr.length > 0 && (
          <motion.section variants={item} aria-label={t("dictionary.byCefr")}>
            <Card className="gap-3 p-5">
              <h2 className="text-sm font-semibold">{t("dictionary.byCefr")}</h2>
              <ul className="flex flex-col gap-2.5">
                {summary.by_cefr.map((bucket) => (
                  <li key={bucket.cefr} className="flex items-center gap-3">
                    <LevelBadge level={bucket.cefr} className="w-12 justify-center" />
                    <SkillBar
                      value={cefrBarValue(bucket.count, maxCefr)}
                      hint={String(bucket.count)}
                      className="flex-1"
                    />
                  </li>
                ))}
              </ul>
            </Card>
          </motion.section>
        )}

        {userId && (candidates.length > 0 || drillWord !== null) && (
          <SpeakingDrillSection
            userId={userId}
            words={candidates}
            drillWord={drillWord}
            onDrillChange={setDrillWord}
            onProduced={(word) => {
              // La palabra ya no es candidata: refrescar léxico + señal.
              setCandidates((prev) => prev.filter((w) => w !== word));
              void refresh();
            }}
          />
        )}

        <motion.section variants={item} aria-label={t("dictionary.items")}>
          <Card className="gap-0 overflow-hidden p-0">
            {sorted.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-5 py-10 text-center">
                <BookOpen
                  className="size-8 text-muted-foreground/60"
                  aria-hidden="true"
                />
                <p className="text-sm text-muted-foreground">{t("dictionary.empty")}</p>
              </div>
            ) : (
              <ul className="divide-y divide-border/60">
                {sorted.map((lex) => (
                  <LexicalRow key={lex.word} lexical={lex} />
                ))}
              </ul>
            )}
          </Card>
        </motion.section>
      </motion.div>
    </div>
  );
}

function DictionaryHeader({ total }: { total?: number }) {
  const { t } = useI18n();
  return (
    <motion.header variants={item} className="flex items-center justify-between gap-3">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight sm:text-3xl">
          <BookOpen className="size-6 text-primary" aria-hidden="true" />
          {t("dictionary.title")}
        </h1>
        <p className="mt-1 text-muted-foreground">{t("dictionary.subtitle")}</p>
      </div>
      {total != null && (
        <Badge variant="secondary" className="shrink-0">
          {total} {t("dictionary.total")}
        </Badge>
      )}
    </motion.header>
  );
}

function StatTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 text-left shadow-sm">
      <span className={cn("text-2xl font-bold tabular-nums", tone)}>{value}</span>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

function lexicalKindLabel(kind: string, t: (key: string) => string): string {
  // P1 (§3.2): taxonomía ampliada de Lexical Unit. Fallback genérico para
  // cualquier valor desconocido (nunca se etiqueta por defecto como "word").
  const key = `dictionary.kind.${kind}`;
  const label = t(key);
  return label === key ? t("dictionary.kind.other") : label;
}

function LexicalRow({ lexical }: { lexical: LexicalItem }) {
  const { t } = useI18n();
  const kindLabel = lexicalKindLabel(lexical.kind, t);
  const statusLabel = t(`dictionary.status.${lexical.status}`);

  return (
    <li className="flex items-center gap-3 p-3 sm:p-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-semibold text-foreground">
            {lexical.word}
          </span>
          {lexical.cefr && <LevelBadge level={lexical.cefr} className="shrink-0" />}
          <span className="shrink-0 text-xs text-muted-foreground">{kindLabel}</span>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <Progress
            value={Math.round(lexical.recall * 100)}
            className="h-1.5 flex-1"
            aria-label={`${t("dictionary.recall")} ${Math.round(lexical.recall * 100)}%`}
          />
          <span className="w-9 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
            {Math.round(lexical.recall * 100)}%
          </span>
        </div>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        <Badge className={cn(STATUS_TONE[lexical.status])}>{statusLabel}</Badge>
        {lexical.status !== "mastered" && (
          <span className="text-[11px] text-muted-foreground">
            {lexical.status === "weak"
              ? t("mastery.reviewNow")
              : t("dictionary.nextReviewIn").replace(
                  "{days}",
                  String(lexical.next_review_days),
                )}
          </span>
        )}
      </div>
    </li>
  );
}

interface SpeakingDrillSectionProps {
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
function SpeakingDrillSection({
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

type DrillStep = "recall" | "sentence";

interface WordDrillProps {
  userId: string;
  word: string;
  onProduced: () => void;
  onClose: () => void;
}

type DrillOutcome = DrillAttempt | DrillSentenceAttempt;

function isSentenceAttempt(outcome: DrillOutcome): outcome is DrillSentenceAttempt {
  return "passed" in outcome;
}

/** Micro-práctica escalera de una palabra (V3.21/F6): Paso 1 "Recall" — di la
 * palabra (scorer `submitDrillAttempt`); Paso 2 "Sentence" — repítela DENTRO de
 * una frase de contexto determinista (scorer `submitDrillSentenceAttempt`).
 * Reutiliza el scorer de pronunciación del servidor. No declara dominio (D5/E3):
 * una producción del día no consolida; se consolida con éxito espaciado (F6.2). */
function WordDrill({ userId, word, onProduced, onClose }: WordDrillProps) {
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
