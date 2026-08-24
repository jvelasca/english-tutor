import { useEffect, useRef, useState } from "react";
import { speak, transcribe } from "../api/voz";
import {
  MAX_CHUNK_MS,
  MIN_SPEECH_MS,
  SILENCE_THRESHOLD,
  rms,
  shouldEndUtterance,
} from "../utils/vad";

export type HandsFreeStatus =
  | "idle"
  | "listening"
  | "transcribing"
  | "thinking"
  | "speaking";

export interface HandsFreeController {
  enabled: boolean;
  status: HandsFreeStatus;
  toggle: () => void;
  stop: () => void;
}

const VAD_INTERVAL_MS = 50;
const FFT_SIZE = 1024;

/**
 * Modo de conversación por voz continua. Mantiene un único `MediaStream`
 * vivo (no se vuelve a pedir permiso por turno), mide energía con
 * `AnalyserNode` y captura con `MediaRecorder` por chunk. Al detectar
 * silencio tras habla, transcribe, envía al chat y reproduce la respuesta.
 */
export function useHandsFree(
  sendText: (text: string) => Promise<string>,
): HandsFreeController {
  const [enabled, setEnabled] = useState(false);
  const [status, setStatus] = useState<HandsFreeStatus>("idle");

  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const vadTimerRef = useRef<number | null>(null);

  const enabledRef = useRef(false);
  const speechDetectedRef = useRef(false);
  const speechStartRef = useRef<number | null>(null);
  const silenceStartRef = useRef<number | null>(null);
  const chunkStartRef = useRef<number | null>(null);
  const processingRef = useRef(false);

  const sendTextRef = useRef(sendText);
  sendTextRef.current = sendText;

  const stopInternalRef = useRef<() => void>(() => {});

  function stopInternal() {
    enabledRef.current = false;
    processingRef.current = false;
    speechDetectedRef.current = false;
    speechStartRef.current = null;
    silenceStartRef.current = null;
    chunkStartRef.current = null;

    if (vadTimerRef.current !== null) {
      window.clearInterval(vadTimerRef.current);
      vadTimerRef.current = null;
    }

    const recorder = recorderRef.current;
    recorderRef.current = null;
    if (recorder && recorder.state !== "inactive") {
      recorder.ondataavailable = null;
      recorder.onstop = null;
      try {
        recorder.stop();
      } catch {
        /* ya estaba detenido */
      }
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

    const audioCtx = audioCtxRef.current;
    audioCtxRef.current = null;
    if (audioCtx) {
      void audioCtx.close().catch(() => {});
    }

    const stream = streamRef.current;
    streamRef.current = null;
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
    }

    analyserRef.current = null;
    chunksRef.current = [];
    setEnabled(false);
    setStatus("idle");
  }

  stopInternalRef.current = stopInternal;

  function startRecorder() {
    const stream = streamRef.current;
    if (!stream || typeof MediaRecorder === "undefined") {
      stopInternal();
      return;
    }
    try {
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.start();
      recorderRef.current = recorder;
      chunkStartRef.current = Date.now();
    } catch {
      stopInternal();
    }
  }

  function stopRecorderAndCollect(): Promise<Blob> {
    const recorder = recorderRef.current;
    recorderRef.current = null;
    if (!recorder || recorder.state === "inactive") {
      chunksRef.current = [];
      return Promise.resolve(new Blob());
    }
    return new Promise<Blob>((resolve) => {
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        chunksRef.current = [];
        resolve(blob);
      };
      recorder.stop();
    });
  }

  function resumeListening() {
    if (!enabledRef.current) return;
    processingRef.current = false;
    speechDetectedRef.current = false;
    speechStartRef.current = null;
    silenceStartRef.current = null;
    chunkStartRef.current = null;
    startRecorder();
    setStatus("listening");
  }

  async function processUtterance(blob: Blob) {
    if (!enabledRef.current) return;

    setStatus("transcribing");
    let text = "";
    try {
      if (blob.size > 0) text = await transcribe(blob);
    } catch {
      text = "";
    }

    if (!enabledRef.current) return;
    text = text.trim();
    if (!text) {
      resumeListening();
      return;
    }

    setStatus("thinking");
    let reply = "";
    try {
      reply = await sendTextRef.current(text);
    } catch {
      reply = "";
    }

    if (!enabledRef.current) return;
    if (!reply) {
      resumeListening();
      return;
    }

    setStatus("speaking");
    try {
      await speak(reply);
    } catch {
      /* un fallo de TTS no detiene el bucle */
    }

    if (enabledRef.current) resumeListening();
  }

  function endUtterance() {
    if (processingRef.current) return;

    const now = Date.now();
    const speechStart = speechStartRef.current;
    if (speechStart !== null && now - speechStart < MIN_SPEECH_MS) {
      speechDetectedRef.current = false;
      speechStartRef.current = null;
      silenceStartRef.current = null;
      return;
    }

    processingRef.current = true;
    speechDetectedRef.current = false;
    speechStartRef.current = null;
    silenceStartRef.current = null;

    void stopRecorderAndCollect().then((blob) => {
      void processUtterance(blob);
    });
  }

  function onVadTick() {
    if (!enabledRef.current || processingRef.current) return;
    const analyser = analyserRef.current;
    if (!analyser) return;

    const samples = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(samples);
    const energy = rms(samples);
    const now = Date.now();

    const speech = energy > SILENCE_THRESHOLD;

    if (speech) {
      if (!speechDetectedRef.current) {
        speechDetectedRef.current = true;
        speechStartRef.current = now;
      }
      silenceStartRef.current = null;
    } else if (speechDetectedRef.current && silenceStartRef.current === null) {
      silenceStartRef.current = now;
    }

    const chunkStart = chunkStartRef.current;
    if (chunkStart !== null && now - chunkStart >= MAX_CHUNK_MS) {
      endUtterance();
      return;
    }

    if (
      shouldEndUtterance(speechDetectedRef.current, silenceStartRef.current, now)
    ) {
      endUtterance();
    }
  }

  async function start() {
    if (enabledRef.current) return;

    enabledRef.current = true;
    setEnabled(true);
    setStatus("listening");

    try {
      // Ambos arranques se lanzan de forma síncrona dentro del gesto de usuario
      // (clic) para cumplir la política de autoplay.
      const streamPromise = navigator.mediaDevices.getUserMedia({ audio: true });
      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;
      if (audioCtx.state === "suspended") {
        await audioCtx.resume();
      }

      const stream = await streamPromise;
      if (!enabledRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;

      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = FFT_SIZE;
      analyser.smoothingTimeConstant = 0.3;
      source.connect(analyser);
      sourceRef.current = source;
      analyserRef.current = analyser;

      startRecorder();
      vadTimerRef.current = window.setInterval(onVadTick, VAD_INTERVAL_MS);
    } catch {
      stopInternal();
    }
  }

  function toggle() {
    if (enabledRef.current) {
      stopInternal();
    } else {
      void start();
    }
  }

  useEffect(() => {
    return () => stopInternalRef.current();
  }, []);

  return { enabled, status, toggle, stop: stopInternal };
}
