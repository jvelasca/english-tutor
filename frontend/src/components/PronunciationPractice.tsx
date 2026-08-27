import { useRef, useState } from "react";
import { checkPronunciation } from "../api/pronunciation";
import type { NextBestActivity, PronunciationResponse } from "../types/api";
import type { Section } from "../utils/sections";
import { fluencyLevelLabel, wpmLabel } from "../utils/fluency";
import { feedbackHints, wordsCorrectLabel } from "../utils/pronunciationFeedback";
import { ActivityResult } from "./ActivityResult";
import { NextStep } from "./NextStep";
import { useI18n } from "../hooks/useI18n";

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
    <section className="pronunciation">
      <h3>{t("pron.title")}</h3>
      <p className="pronunciation-prompt">{t("pron.prompt")}</p>
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
          className={`record-button min-h-10${recording ? " recording" : ""}`}
          onClick={toggle}
          disabled={processing || !userId}
        >
          {processing
            ? t("pron.evaluating")
            : recording
              ? t("pron.stop")
              : t("pron.record")}
        </button>
      </div>

      {result && (
        <ActivityResult
          outcome={result.level === "good" ? "ok" : result.level === "fair" ? "neutral" : "ko"}
          title={`${t("pron.title")} · ${result.score}/100`}
          footer={<NextStep userId={userId} onNext={onNext} />}
        >
          <div className="lines">
            <div>
              <span className="label">{t("pron.expected")}:</span> {result.expected}
            </div>
            <div>
              <span className="label">{t("pron.heard")}:</span> {result.heard}
            </div>
            <div>
              <span className="label">{t("pron.level")}:</span>{" "}
              {result.level === "good"
                ? t("pron.level.good")
                : result.level === "fair"
                  ? t("pron.level.fair")
                  : t("pron.level.needsPractice")}
            </div>
            <div>
              <span className="label">{t("pron.wordAccuracy")}:</span>{" "}
              {result.word_accuracy}%
            </div>
            <div>
              <span className="label">{t("pron.phoneticScore")}:</span>{" "}
              {result.phonetic_score}%
            </div>
            <div>
              <span className="label">{t("pron.phonemeAccuracy")}:</span>{" "}
              {result.phoneme_accuracy_proxy}%
            </div>
            <div>
              <span className="label">{t("pron.prosody")}:</span>{" "}
              {result.prosody_proxy}%
            </div>
            <div>
              <span className="label">{t("pron.fluency")}:</span>{" "}
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
        </ActivityResult>
      )}
    </section>
  );
}
