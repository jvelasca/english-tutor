import { useRef, useState } from "react";
import { transcribe } from "../api/voz";
import { useI18n } from "../hooks/useI18n";
import {
  getMicrophoneStream,
  MicUnavailableError,
  type MicUnavailableReason,
} from "../utils/browserCapabilities";
import { MicUnavailableNotice } from "./MicUnavailableNotice";

interface MicButtonProps {
  onTranscribed: (text: string) => void;
  disabled?: boolean;
}

export function MicButton({ onTranscribed, disabled = false }: MicButtonProps) {
  const { t } = useI18n();
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [micError, setMicError] = useState<MicUnavailableReason | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  async function start() {
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
        setProcessing(true);
        try {
          const text = await transcribe(blob);
          if (text) onTranscribed(text);
        } catch (e) {
          alert(`${t("mic.transcribeError")}${(e as Error).message}`);
        } finally {
          setProcessing(false);
        }
      };

      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (e) {
      alert(`${t("mic.accessError")}${(e as Error).message}`);
    }
  }

  function stop() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  return (
    <div className="relative">
      {micError && (
        <div className="absolute bottom-full left-0 z-20 mb-2 w-72 max-w-[80vw]">
          <MicUnavailableNotice reason={micError} />
        </div>
      )}
      <button
        type="button"
        className={`mic-button${recording ? " recording" : ""}${
          processing ? " processing" : ""
        }`}
        onClick={recording ? stop : start}
        disabled={disabled}
        title={recording ? t("mic.stop") : t("mic.record")}
        aria-label={recording ? t("mic.stop") : t("mic.record")}
        aria-pressed={recording}
      >
        <MicIcon />
      </button>
    </div>
  );
}

function MicIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}
