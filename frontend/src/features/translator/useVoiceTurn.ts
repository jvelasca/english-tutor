/**
 * V3.45 — Turno de voz del modo Conversación del Traductor de viaje.
 *
 * Gobierna UN turno: pide micrófono, graba con `MediaRecorder`, mide energía con
 * un `AnalyserNode` para (a) alimentar el medidor visual y (b) cerrar el turno
 * automáticamente al detectar silencio (`utils/vad`), y transcribe con Whisper
 * (`api/voz.transcribe`) en el idioma del panel. A diferencia del dictado
 * (`MicButton`), aquí el cierre por silencio es la vía principal y el botón solo
 * actúa de "parar ahora".
 *
 * El turno se libera por completo al terminar (stream, AudioContext y
 * MediaRecorder) para no dejar el micrófono abierto entre turnos.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { transcribe, type VoiceLanguage } from "../../api/voz";
import { useRecordingSession } from "../../hooks/useRecordingSession";
import {
  MicUnavailableError,
  getMicrophoneStream,
  type MicUnavailableReason,
} from "../../utils/browserCapabilities";
import { levelPercent } from "../../utils/microphoneLevel";
import {
  MIN_SPEECH_MS,
  SILENCE_THRESHOLD,
  rms,
  shouldEndUtterance,
} from "../../utils/vad";

export type VoiceTurnStatus = "idle" | "listening" | "transcribing" | "error";

export interface VoiceTurnController {
  status: VoiceTurnStatus;
  /** Nivel de entrada 0–100 mientras se escucha (para el medidor). */
  level: number;
  micError: MicUnavailableReason | null;
  /** Mensaje crudo del fallo de transcripción (el panel lo prefija con i18n). */
  transcribeError: string | null;
  /** El turno terminó sin habla reconocible. */
  noSpeech: boolean;
  toggle: () => void;
  stop: () => void;
}

/** Estado interno del detector de habla/silencio de un turno. */
export interface TurnVadState {
  speechDetected: boolean;
  speechStartMs: number | null;
  silenceStartMs: number | null;
}

export const INITIAL_TURN_VAD_STATE: TurnVadState = {
  speechDetected: false,
  speechStartMs: null,
  silenceStartMs: null,
};

/**
 * Avanza el detector de VAD de un turno con la energía actual.
 *
 * Función pura (testeable sin DOM): decide si el turno debe cerrarse por
 * silencio. Un "pico" de voz más corto que `MIN_SPEECH_MS` se descarta y el
 * detector se reinicia, para no cerrar turnos con ruido puntual.
 */
export function nextTurnVadState(
  prev: TurnVadState,
  energy: number,
  nowMs: number,
): { state: TurnVadState; end: boolean } {
  const speech = energy > SILENCE_THRESHOLD;
  let { speechDetected, speechStartMs, silenceStartMs } = prev;

  if (speech) {
    if (!speechDetected) {
      speechDetected = true;
      speechStartMs = nowMs;
    }
    silenceStartMs = null;
  } else if (speechDetected && silenceStartMs === null) {
    silenceStartMs = nowMs;
  }

  if (shouldEndUtterance(speechDetected, silenceStartMs, nowMs)) {
    const speechDurationMs =
      speechStartMs !== null && silenceStartMs !== null
        ? silenceStartMs - speechStartMs
        : 0;
    if (speechDurationMs >= MIN_SPEECH_MS) {
      return {
        state: { speechDetected, speechStartMs, silenceStartMs },
        end: true,
      };
    }
    // Ruido demasiado corto: reinicia el detector sin cerrar el turno.
    return { state: { ...INITIAL_TURN_VAD_STATE }, end: false };
  }

  return { state: { speechDetected, speechStartMs, silenceStartMs }, end: false };
}

const VAD_INTERVAL_MS = 50;
const FFT_SIZE = 1024;

export function useVoiceTurn(
  language: VoiceLanguage,
  onTranscribed: (text: string) => void,
): VoiceTurnController {
  const [status, setStatus] = useState<VoiceTurnStatus>("idle");
  const [level, setLevel] = useState(0);
  const [micError, setMicError] = useState<MicUnavailableReason | null>(null);
  const [transcribeError, setTranscribeError] = useState<string | null>(null);
  const [noSpeech, setNoSpeech] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const vadRef = useRef<TurnVadState>({ ...INITIAL_TURN_VAD_STATE });
  const activeRef = useRef(false);
  const processingRef = useRef(false);

  const languageRef = useRef(language);
  languageRef.current = language;
  const onTranscribedRef = useRef(onTranscribed);
  onTranscribedRef.current = onTranscribed;

  const releaseAudio = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    const source = sourceRef.current;
    sourceRef.current = null;
    if (source) {
      try {
        source.disconnect();
      } catch {
        /* noop */
      }
    }
    const ctx = audioCtxRef.current;
    audioCtxRef.current = null;
    if (ctx) void ctx.close().catch(() => {});
    const stream = streamRef.current;
    streamRef.current = null;
    if (stream) stream.getTracks().forEach((track) => track.stop());
    analyserRef.current = null;
    chunksRef.current = [];
  }, []);

  const finish = useCallback(() => {
    if (!activeRef.current || processingRef.current) return;
    processingRef.current = true;
    setLevel(0);
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    const recorder = recorderRef.current;
    recorderRef.current = null;

    if (!recorder || recorder.state === "inactive") {
      releaseAudio();
      activeRef.current = false;
      processingRef.current = false;
      setStatus("idle");
      return;
    }

    const blobPromise = new Promise<Blob>((resolve) => {
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        resolve(blob);
      };
      try {
        recorder.stop();
      } catch {
        resolve(new Blob());
      }
    });

    setStatus("transcribing");
    void blobPromise.then(async (blob) => {
      releaseAudio();
      let text = "";
      if (blob.size > 0) {
        try {
          text = await transcribe(blob, languageRef.current);
        } catch (e) {
          setTranscribeError((e as Error).message);
          activeRef.current = false;
          processingRef.current = false;
          setStatus("error");
          return;
        }
      }
      text = text.trim();
      if (text) {
        setNoSpeech(false);
        onTranscribedRef.current(text);
      } else {
        setNoSpeech(true);
      }
      activeRef.current = false;
      processingRef.current = false;
      setStatus("idle");
    });
  }, [releaseAudio]);

  const tick = useCallback(() => {
    if (!activeRef.current || processingRef.current) return;
    const analyser = analyserRef.current;
    if (!analyser) return;
    const samples = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(samples);
    const energy = rms(samples);
    setLevel(levelPercent(samples));
    const now = Date.now();
    const { state, end } = nextTurnVadState(vadRef.current, energy, now);
    vadRef.current = state;
    if (end) finish();
  }, [finish]);

  const start = useCallback(async () => {
    if (activeRef.current) return;
    activeRef.current = true;
    processingRef.current = false;
    setMicError(null);
    setTranscribeError(null);
    setNoSpeech(false);
    setLevel(0);
    setStatus("listening");
    vadRef.current = { ...INITIAL_TURN_VAD_STATE };

    let stream: MediaStream;
    try {
      stream = await getMicrophoneStream();
    } catch (e) {
      activeRef.current = false;
      setMicError(e instanceof MicUnavailableError ? e.reason : "unknown");
      setStatus("error");
      return;
    }
    if (!activeRef.current) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    streamRef.current = stream;

    try {
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.start();
      recorderRef.current = recorder;
    } catch (e) {
      releaseAudio();
      activeRef.current = false;
      setMicError(e instanceof MicUnavailableError ? e.reason : "unknown");
      setStatus("error");
      return;
    }

    // VAD/medidor opcionales: si el navegador no da AudioContext, el turno sigue
    // funcionando con parada manual (y el auto-stop de 120 s).
    try {
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      if (ctx.state === "suspended") void ctx.resume().catch(() => {});
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = FFT_SIZE;
      analyser.smoothingTimeConstant = 0.3;
      source.connect(analyser);
      sourceRef.current = source;
      analyserRef.current = analyser;
      timerRef.current = window.setInterval(tick, VAD_INTERVAL_MS);
    } catch {
      /* sin VAD: parada manual */
    }
  }, [releaseAudio, tick]);

  const toggle = useCallback(() => {
    if (activeRef.current) finish();
    else void start();
  }, [finish, start]);

  // Auto-stop de seguridad a los 120 s (máximo del backend).
  useRecordingSession(status === "listening", { onAutoStop: () => finish() });

  useEffect(() => {
    return () => {
      activeRef.current = false;
      processingRef.current = false;
      releaseAudio();
    };
  }, [releaseAudio]);

  return {
    status,
    level,
    micError,
    transcribeError,
    noSpeech,
    toggle,
    stop: finish,
  };
}
