import { useEffect, useRef, useState } from "react";
import { speak } from "../api/voz";
import { useI18n } from "../hooks/useI18n";
import {
  getMicrophoneStream,
  MicUnavailableError,
  type MicUnavailableReason,
} from "../utils/browserCapabilities";
import { levelBar, levelPercent } from "../utils/microphoneLevel";
import { MicUnavailableNotice } from "./MicUnavailableNotice";
import { Button } from "./ui/button";
import { Progress } from "./ui/progress";

type TestPhase = "idle" | "testing" | "working" | "error";
type PlaybackPhase = "idle" | "playing" | "ok" | "error";

const LEVEL_INTERVAL_MS = 50;
const FFT_SIZE = 1024;

/**
 * Verificación de micrófono de nivel profesional: prueba la captura en vivo con
 * un medidor de nivel de entrada y la reproducción de una muestra, de modo que
 * el usuario pueda comprobar de una sola vez que micrófono y altavoces funcionan
 * antes de una actividad de speaking/listening.
 */
export function MicrophoneTest() {
  const { t } = useI18n();
  const [phase, setPhase] = useState<TestPhase>("idle");
  const [error, setError] = useState<MicUnavailableReason | null>(null);
  const [level, setLevel] = useState(0);
  const [playback, setPlayback] = useState<PlaybackPhase>("idle");

  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const timerRef = useRef<number | null>(null);

  function cleanup() {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    const ctx = audioCtxRef.current;
    audioCtxRef.current = null;
    analyserRef.current = null;
    if (ctx) {
      void ctx.close().catch(() => {});
    }
    const stream = streamRef.current;
    streamRef.current = null;
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
    }
  }

  useEffect(() => {
    return cleanup;
  }, []);

  async function startTest() {
    cleanup();
    setError(null);
    setLevel(0);
    setPlayback("idle");
    setPhase("testing");

    let stream: MediaStream;
    try {
      stream = await getMicrophoneStream();
    } catch (e) {
      setError(e instanceof MicUnavailableError ? e.reason : "unknown");
      setPhase("error");
      return;
    }

    try {
      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;
      if (audioCtx.state === "suspended") {
        await audioCtx.resume();
      }
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = FFT_SIZE;
      analyser.smoothingTimeConstant = 0.3;
      source.connect(analyser);
      analyserRef.current = analyser;
      streamRef.current = stream;

      timerRef.current = window.setInterval(() => {
        const an = analyserRef.current;
        if (!an) return;
        const samples = new Uint8Array(an.fftSize);
        an.getByteTimeDomainData(samples);
        setLevel(levelPercent(samples));
      }, LEVEL_INTERVAL_MS);

      setPhase("working");
    } catch (e) {
      cleanup();
      setError(e instanceof MicUnavailableError ? e.reason : "unknown");
      setPhase("error");
    }
  }

  function stopTest() {
    cleanup();
    setPhase("idle");
    setLevel(0);
  }

  async function testPlayback() {
    setPlayback("playing");
    try {
      await speak(t("micTest.playbackSample"));
      setPlayback("ok");
    } catch {
      setPlayback("error");
    }
  }

  const testing = phase === "testing";
  const working = phase === "working";

  return (
    <div className="space-y-3">
      {error && <MicUnavailableNotice reason={error} />}

      <div className="flex flex-wrap items-center gap-2">
        {working ? (
          <Button type="button" variant="secondary" onClick={stopTest}>
            {t("micTest.stop")}
          </Button>
        ) : (
          <Button
            type="button"
            variant={testing ? "ghost" : "default"}
            disabled={testing}
            onClick={startTest}
          >
            {testing
              ? t("common.loading")
              : error
                ? t("micTest.buttonAgain")
                : t("micTest.button")}
          </Button>
        )}
        <Button
          type="button"
          variant="outline"
          disabled={playback === "playing"}
          onClick={testPlayback}
        >
          {playback === "playing"
            ? t("common.loading")
            : t("micTest.testPlayback")}
        </Button>
      </div>

      {working && (
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {t("micTest.speakNow")}
          </p>
          <Progress value={level} aria-label={t("micTest.inputLevel")} />
          <p className="font-mono text-xs text-muted-foreground" aria-hidden="true">
            {levelBar(level)}
          </p>
        </div>
      )}

      {phase === "working" && (
        <p className="text-sm font-medium text-green-600" role="status">
          {t("micTest.working")}
        </p>
      )}

      {playback === "ok" && (
        <p className="text-sm font-medium text-green-600" role="status">
          {t("micTest.playbackOk")}
        </p>
      )}
      {playback === "error" && (
        <p className="text-sm font-medium text-destructive" role="status">
          {t("micTest.playbackError")}
        </p>
      )}
    </div>
  );
}
