import { useRef, useState } from "react";
import { Loader2, Square } from "lucide-react";
import { transcribe } from "../../api/voz";
import { useI18n } from "../../hooks/useI18n";
import {
  getMicrophoneStream,
  MicUnavailableError,
  type MicUnavailableReason,
} from "../../utils/browserCapabilities";
import { MicUnavailableNotice } from "../../components/MicUnavailableNotice";

interface ConversationVoiceButtonProps {
  /** Se llama al empezar a grabar (para medir la latencia de reacción). */
  onStarted?: () => void;
  /** Turno hablado listo: texto transcrito y duración real del audio en ms. */
  onSpoken: (text: string, durationMs: number) => void;
  disabled?: boolean;
}

/** Duración real de un blob de audio en ms (o null si no puede medirse). */
function audioDurationMs(blob: Blob): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio();
    audio.preload = "metadata";
    const done = (ms: number | null) => {
      URL.revokeObjectURL(url);
      resolve(ms);
    };
    audio.onloadedmetadata = () =>
      done(Number.isFinite(audio.duration) ? audio.duration * 1000 : null);
    audio.onerror = () => done(null);
    audio.src = url;
  });
}

/**
 * Botón de TURNO HABLADO del diálogo guiado (DISENO-SPEAKING-UNICO F3).
 *
 * A diferencia del micrófono de dictado (que solo transcribe al campo), este
 * botón graba la respuesta del alumno como un turno oral: transcribe el audio,
 * mide su duración real y entrega ambos al chat para que el turno se persista
 * con `mode="voice"` y telemetría de habla. El backend ya distingue el tecleo
 * (`mode="conversation"`, CONV-01) de los turnos que sí computan como voz.
 */
export function ConversationVoiceButton({
  onStarted,
  onSpoken,
  disabled = false,
}: ConversationVoiceButtonProps) {
  const { t } = useI18n();
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [micError, setMicError] = useState<MicUnavailableReason | null>(null);
  const [transcribeError, setTranscribeError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);

  async function start() {
    setMicError(null);
    setTranscribeError(null);
    let stream: MediaStream;
    try {
      stream = await getMicrophoneStream();
    } catch (e) {
      setMicError(e instanceof MicUnavailableError ? e.reason : "unknown");
      return;
    }
    onStarted?.();
    startedAtRef.current = performance.now();
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
        setTranscribeError(null);
        try {
          const realMs = await audioDurationMs(blob);
          const fallbackMs = performance.now() - startedAtRef.current;
          const durationMs = realMs ?? fallbackMs;
          const text = await transcribe(blob);
          if (text) onSpoken(text, Math.max(1, Math.round(durationMs)));
        } catch (e) {
          setTranscribeError(`${t("mic.transcribeError")}${(e as Error).message}`);
        } finally {
          setProcessing(false);
        }
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (e) {
      setMicError(e instanceof MicUnavailableError ? e.reason : "unknown");
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
      {transcribeError && (
        <div
          role="alert"
          className="absolute bottom-full left-0 z-20 mb-2 w-72 max-w-[80vw] rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive"
        >
          {transcribeError}
        </div>
      )}
      <button
        type="button"
        className={`mic-button${recording ? " recording" : ""}${
          processing ? " processing" : ""
        }`}
        onClick={recording ? stop : start}
        disabled={disabled || processing}
        title={recording ? t("mic.stop") : processing ? t("pron.evaluating") : t("mic.record")}
        aria-label={
          recording ? t("mic.stop") : processing ? t("pron.evaluating") : t("mic.record")
        }
        aria-pressed={recording}
      >
        {processing ? (
          <Loader2 className="animate-spin" size={18} aria-hidden="true" />
        ) : recording ? (
          <Square size={18} aria-hidden="true" />
        ) : (
          <MicIcon />
        )}
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
