/**
 * V3.21 (V20-13): sesión de grabación con cronómetro visible y auto-stop.
 *
 * Dado un flag `recording`, mantiene un contador `mm:ss` mientras dura la
 * grabación y, al llegar al límite (`maxSeconds`, por defecto 120 s = el máximo
 * que acepta el backend en `config.MAX_AUDIO_DURATION_SECONDS`), invoca
 * `onAutoStop` para que el componente detenga su `MediaRecorder`. El auto-stop
 * se dispara una sola vez por sesión (guard `stoppedRef`).
 */
import { useEffect, useRef, useState } from "react";

/** Máximo por defecto: 120 s (mismo límite que el backend, V20-13). */
export const DEFAULT_MAX_RECORDING_SECONDS = 120;

function formatClock(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(safe / 60);
  const s = safe % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export interface RecordingSessionOptions {
  /** Límite de auto-stop en segundos (por defecto 120). */
  maxSeconds?: number;
  /** Se invoca al alcanzar el límite (el dueño detiene su MediaRecorder). */
  onAutoStop?: () => void;
}

export function useRecordingSession(
  recording: boolean,
  { maxSeconds = DEFAULT_MAX_RECORDING_SECONDS, onAutoStop }: RecordingSessionOptions = {},
) {
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<number | null>(null);
  const onAutoStopRef = useRef(onAutoStop);
  onAutoStopRef.current = onAutoStop;
  const stoppedRef = useRef(false);

  useEffect(() => {
    if (!recording) {
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setElapsed(0);
      stoppedRef.current = false;
      return;
    }
    setElapsed(0);
    stoppedRef.current = false;
    const startedAt = Date.now();
    intervalRef.current = window.setInterval(() => {
      const seconds = Math.floor((Date.now() - startedAt) / 1000);
      setElapsed(seconds);
      if (seconds >= maxSeconds && !stoppedRef.current) {
        stoppedRef.current = true;
        onAutoStopRef.current?.();
      }
    }, 250);
    return () => {
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [recording, maxSeconds]);

  const remaining = Math.max(0, maxSeconds - elapsed);
  return {
    /** Segundos transcurridos de la grabación actual. */
    elapsed,
    /** Segundos restantes hasta el auto-stop. */
    remaining,
    /** Reloj `mm:ss` transcurrido (para mostrar mientras se graba). */
    formatted: formatClock(elapsed),
    /** Reloj `mm:ss` restante (para el aviso de límite). */
    remainingFormatted: formatClock(remaining),
    /** Límite configurado en segundos. */
    limit: maxSeconds,
  };
}
