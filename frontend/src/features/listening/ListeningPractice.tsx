// ListeningPractice — práctica de Listening (Listening Engine 4.0).
//
// V3.29 (Fase 3): integra el karaoke palabra a palabra (`KaraokeTranscript`,
// sidecar `word_alignment_proxy` del backend), los controles de audio precisos
// (seek slider + bucle A/B) y el salto a la palabra fallada (dictado/cloze),
// además del micro-flujo V3.27/V3.28, la transcripción dinámica por frase
// (`CoarseTranscript`, sync grueso heurístico) y el Shadowing 2.0.
import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronUp,
  Flag,
  Loader2,
  Mic,
  MoreHorizontal,
  Play,
  RefreshCw,
  Repeat2,
  Send,
  Sparkles,
  Square,
  Volume2,
  X,
} from "lucide-react";
import {
  addRouteExtras,
  getListeningAudioUrl,
  getListeningDiagnostic,
  getListeningQuestion,
  getListeningStats,
  getRouteExtrasJob,
  submitListeningAnswer,
  submitListeningDictation,
  submitListeningShadowing,
  type ListeningQuestionMode,
} from "../../api/listening";
import {
  drillAnswered,
  isSessionFinished,
  sessionDone,
  type ListeningSession,
} from "./listeningSession";
import { audioTypeKey, retentionBucketKey } from "../../utils/listeningLabels";
import { ListeningLevelPanel } from "./ListeningLevelPanel";
import { transcribe } from "../../api/voz";
import {
  getMicrophoneStream,
  MicUnavailableError,
  type MicUnavailableReason,
} from "../../utils/browserCapabilities";
import type {
  ListeningAnswerResponse,
  ListeningAudioVariant,
  ListeningDiagnostic,
  ListeningExtrasJob,
  ListeningProductionResult,
  ListeningQuestion,
  ListeningStats,
  ListeningSupportMetadata,
  NextBestActivity,
} from "../../types/api";
import type { Section } from "../../utils/sections";
import { ActivityResult } from "../../components/ActivityResult";
import { ItemReplayButton } from "../../components/ItemReplayButton";
import { VoicePicker } from "../../components/VoicePicker";
import {
  useVoiceChoice,
  type VoiceAccent,
} from "../../hooks/useVoiceChoice";
import { speakWithVoice } from "../../hooks/useVoiceDownload";
import { InfoDisclosure } from "../../components/InfoDisclosure";
import {
  PhraseTranslateButton,
  usePhraseTranslation,
} from "../../components/PhraseTranslate";
import { NextStep } from "../../components/NextStep";
import { MicUnavailableNotice } from "../../components/MicUnavailableNotice";
import { ProgressRing } from "../../components/ProgressRing";
// Insignia de nivel con la rampa (V3.75.4): el color del nivel lo pone
// `levelClass` sobre los tokens de `styles/legacy.css`.
import { LevelBadge } from "../../components/LevelBadge";
import { levelClass } from "../../utils/cefr";
// Playback de la grabación del alumno en el shadowing de listening (V3.28,
// Bloque E): reutiliza el componente de Pronunciation/Speaking.
import { RecordingPlayButton } from "../../components/RecordingPlayButton";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Tooltip } from "../../components/ui/tooltip";
import { useI18n } from "../../hooks/useI18n";
import { useSelectedRoute } from "../../hooks/useSelectedRoute";
import {
  resolveRouteLevel,
  type SelectedRouteLevel,
} from "../../utils/selectedRoute";
import { cn } from "../../lib/utils";
// Micro-flujo por ítem (V3.27, Listening Engine 4.0): máquina de presentación
// que ejecuta el contrato `flow` + `transcript_policy` servido por el backend.
import {
  advanceToNext,
  completeShadowing,
  completeStageWithAnswer,
  currentStep,
  failedWordTiming,
  firstFailedWord,
  flowOf,
  hasFlow,
  initialFlow,
  isProductionFlow,
  revealFull,
  scaleWordTimings,
  variantTimeScale,
  type FailedWordRef,
  type MicroFlowState,
  type TranscriptState,
} from "./microFlow";
import { AuditoryProfileCard } from "./AuditoryProfileCard";
// AudioController 4.0 (V3.28, Bloque B): reproducción del audio de referencia
// sobre un único elemento con play/pause/seek/velocidad/bucle de segmento.
//
// Integración real en esta pantalla (V3.28.1, P1-04): `play(url)` reproduce la
// variante de la escalera y `pause()` corta al cambiar de ítem/desmontar; el
// estado `playing`/`currentTime` alimenta el resaltado de frase activa. Desde
// V3.29 (Fase 3) también se integran el seek preciso (slider + palabra fallada)
// y el bucle de segmento (control A/B y replay de palabra); quedan sin UI
// `setRate` fino con `preservesPitch` y `replaySegment` directo.
import { useAudioController } from "./useAudioController";
// Máquina de estados PURA del bucle A/B (V3.52.1): único origen de verdad que
// mantiene sincronizados el estado de la UI y el segmento del AudioController.
import {
  EMPTY_AB_LOOP,
  MIN_AB_LOOP_SECONDS,
  armLoop,
  canClear,
  clearLoop as clearAbLoop,
  loopFromSegment,
  toggleMark,
  type AbLoopState,
} from "./abLoop";
// Transcripción dinámica con sync grueso (V3.28, Bloque D): resalta la frase
// activa según `currentTime` y respeta el revelado `hidden/partial/full`.
import { CoarseTranscript } from "./CoarseTranscript";
// Transcripción karaoke palabra a palabra (V3.29, Fase 3): resalta cada palabra
// al oírla (word_timings del sidecar word_alignment_proxy) y permite saltar.
import { KaraokeTranscript } from "./KaraokeTranscript";

// Etiqueta legible de una dimensión de resiliencia auditiva (Listening 2.0):
// "clear_speech" → "listening.resilience.clear_speech" (clave i18n localizada).
function resilienceLabel(dimension: string): string {
  return `listening.resilience.${dimension}`;
}

function topicLabel(topic: string): string {
  return topic.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function trendLabel(direction: string): string {
  switch (direction) {
    case "up":
      return "diag.improving";
    case "down":
      return "diag.gettingWorse";
    case "flat":
      return "diag.stable";
    default:
      return "—";
  }
}

// Etiqueta legible de los buckets de retención retardada y del tipo de audio:
// los textos viven ahora en `utils/listeningLabels.ts` como claves i18n (V3.6.1).
function retentionBucketLabel(bucket: string, t: (k: string) => string): string {
  const key = retentionBucketKey(bucket);
  return key ? t(key) : bucket;
}

function audioTypeLabel(audioType: string, t: (k: string) => string): string {
  return t(audioTypeKey(audioType));
}

/** Formatea segundos como `m:ss` (seek slider y control A/B, V3.29 P5). */
function formatSeconds(total: number): string {
  const seconds = Math.max(0, Math.floor(Number.isFinite(total) ? total : 0));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

const WAVE_BARS = [0.45, 0.8, 0.55, 1, 0.65, 0.9, 0.5, 0.75, 0.4, 0.85, 0.6, 1, 0.7, 0.5, 0.9, 0.65];

function Waveform() {
  return (
    <div
      className="flex h-6 items-center justify-center gap-1 sm:h-10"
      aria-hidden="true"
    >
      {WAVE_BARS.map((h, i) => (
        <motion.span
          key={i}
          className="w-1 origin-center rounded-full bg-primary sm:w-1.5"
          style={{ height: `${h * 100}%` }}
          animate={{ scaleY: [1, 0.45, 1.25, 1] }}
          transition={{
            duration: 0.9,
            repeat: Infinity,
            delay: i * 0.055,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

interface ListeningPracticeProps {
  userId: string | null;
  onAttempt: () => void;
  onNext: (section: Section | null, step: NextBestActivity) => void;
}

export function ListeningPractice({
  userId,
  onAttempt,
  onNext,
}: ListeningPracticeProps) {
  const { t } = useI18n();
  // V3.48.1: ruta CEFR seleccionada por el alumno (persistente). `null` = Auto.
  const { selectedLevel, setSelectedLevel } = useSelectedRoute(userId);
  const [question, setQuestion] = useState<ListeningQuestion | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<ListeningAnswerResponse | null>(null);
  const [productionResult, setProductionResult] =
    useState<ListeningProductionResult | null>(null);
  const [dictationText, setDictationText] = useState("");
  const [transcribedText, setTranscribedText] = useState("");
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  // Envío de una respuesta MCQ en curso: evita dobles taps y muestra el estado
  // "Evaluando…" para que la pantalla nunca parezca congelada mientras se espera
  // la respuesta del backend.
  const [submitting, setSubmitting] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  // Shadowing 2.0 (V3.28, Bloque E): la grabación del alumno se conserva como
  // objeto URL local para su playback (mismo diseño que Speaking/Pronunciation:
  // el audio no se sube a disco, solo se transcribe; el playback es local e
  // inmediato). Las señales auxiliares (duración y velocidad proxy en wpm) se
  // calculan aquí, de forma determinista, y viajan con el envío del shadowing.
  const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
  const [shadowingDurationMs, setShadowingDurationMs] = useState<number | null>(
    null,
  );
  const [shadowingSpeechRate, setShadowingSpeechRate] = useState<number | null>(
    null,
  );
  const recordingStartedAtRef = useRef(0);
  const [stats, setStats] = useState<ListeningStats | null>(null);
  const [diagnostic, setDiagnostic] = useState<ListeningDiagnostic | null>(null);
  // AudioController 4.0 (V3.28): único elemento de audio para el audio de
  // referencia. `playing` refleja la reproducción real del elemento; el TTS en
  // vivo (degradación sin audio pre-renderizado) mantiene su propio indicador.
  const {
    controller: audioController,
    playing: elementPlaying,
    currentTime: audioTime,
    duration: audioDuration,
  } = useAudioController();
  const [ttsLivePlaying, setTtsLivePlaying] = useState(false);
  const playing = elementPlaying || ttsLivePlaying;
  const [error, setError] = useState<string | null>(null);
  const [micError, setMicError] = useState<MicUnavailableReason | null>(null);
  const [replayCount, setReplayCount] = useState(0);
  const [startedAt, setStartedAt] = useState(0);
  const [variant, setVariant] = useState<string>("normal");
  const [showAudioSettings, setShowAudioSettings] = useState(false);
  // Control de bucle A/B de la tarjeta de audio (V3.29; máquina de estados PURA
  // en `abLoop.ts` desde V3.52.1). Un único estado evita la desincronización
  // entre la UI (`markStart`/`isLooping`) y el segmento real del controller.
  const [abLoop, setAbLoop] = useState<AbLoopState>(EMPTY_AB_LOOP);
  const markStart = abLoop.markStart;
  const isLooping = abLoop.looping;
  const loopEnd = abLoop.loopEnd;
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [speakingQuestion, setSpeakingQuestion] = useState(false);
  const [session, setSession] = useState<ListeningSession | null>(null);
  const [expandedLevel, setExpandedLevel] = useState<string | null>(null);
  // Micro-flujo por ítem (V3.27, V3.28 Listening Engine 4.0): estado de la
  // máquina de presentación. Se activa cuando la pregunta trae `flow` del
  // backend: rutas adaptativa, por nivel (`level`) y drill (`failed`). Solo el
  // repaso `mastered` sigue en modo compacto (sin flow, decisión V3.28).
  const [flowState, setFlowState] = useState<MicroFlowState | null>(null);
  // Voz TTS real del perfil y segunda voz (V3.75.5). El store de acentos vive en
  // `useVoiceChoice`: él lee el catálogo una sola vez para toda la app, así que la
  // etiqueta de voz, el selector del «...» y el altavoz de repetición ven lo
  // mismo. La voz A (la del perfil) es la que usa PLAY: el flujo de escucha no
  // cambia; la B existe para comparar acentos.
  const voiceChoice = useVoiceChoice(userId);
  const primaryVoiceName =
    voiceChoice.voices.find((voice) => voice.id === voiceChoice.primary)?.name ??
    voiceChoice.primary ??
    null;

  // Trabajos de generación de práctica extra por ruta (V3.6). El POST crea el
  // trabajo y `pollExtrasJob` hace polling hasta `done`/`error`; al terminar se
  // refrescan stats y el panel del nivel (extrasNonce).
  const [extrasJobs, setExtrasJobs] = useState<Record<string, ListeningExtrasJob>>(
    {},
  );
  const [extrasNonce, setExtrasNonce] = useState(0);
  const pollTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // Limpia los temporizadores de polling al desmontar la pantalla.
  useEffect(() => {
    const timers = pollTimersRef.current;
    return () => {
      Object.values(timers).forEach((timer) => clearTimeout(timer));
    };
  }, []);

  // Al cambiar de pregunta (o al desmontar) se detiene el audio de referencia:
  // con el AudioController 4.0 el elemento es único y reutilizable, así que no
  // debe seguir sonando la frase anterior cuando el usuario avanza.
  useEffect(() => {
    return () => {
      audioController?.pause();
    };
  }, [question?.id, audioController]);

  // Shadowing 2.0 (V3.28, Bloque E): cada objeto URL local de la grabación se
  // revoca al sustituirse por otro o al desmontar (no retener blobs en memoria).
  useEffect(() => {
    const url = recordingUrl;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [recordingUrl]);

  // Traducción de apoyo EN→ES de los tres textos de la pregunta (enunciado,
  // texto oído en el resultado y referencia de dictado/shadowing). Cada una es
  // un toggle independiente que se reinicia cuando cambia la pregunta.
  const questionPhrase = usePhraseTranslation(
    question?.question ?? "",
    question?.id,
  );
  const scriptPhrase = usePhraseTranslation(
    question?.script ?? "",
    question?.id ? `${question.id}:script` : undefined,
  );
  const referencePhrase = usePhraseTranslation(
    productionResult?.reference ?? "",
    question?.id ? `${question.id}:reference` : undefined,
  );

  // --- Micro-flujo por ítem (V3.27/V3.28): derivados y controles -----------
  // `flowSteps`/`flowPolicy`/`micro` existen cuando el backend sirvió `flow`
  // (adaptativo, nivel y drill; no en el repaso mastered compacto). Los ítems
  // de producción (dictation/shadowing) traen un flujo de un solo paso y
  // conservan su tarea directa.
  const flowSteps = question ? flowOf(question) : [];
  const flowPolicy = question?.transcriptPolicy;
  const micro =
    question && hasFlow(question) && !isProductionFlow(question) && flowState
      ? flowState
      : null;

  // Estado de revelado de la transcripción para el render del transcript:
  // - flujo receptivo (`micro`): lo que dicta la máquina (hidden/partial/full);
  // - tarea de producción directa (dictation/shadowing, `micro` null): tras el
  //   resultado se revela completa (V3.29, Fase 3) para revisar palabra a
  //   palabra lo que sonaba; antes de responder permanece oculta.
  const isProductionTask = question ? isProductionFlow(question) : false;
  const transcriptVisible: TranscriptState = micro
    ? micro.transcript
    : isProductionTask && (result !== null || productionResult !== null)
      ? "full"
      : "hidden";

  /** Seek preciso del AudioController (karaoke / palabra fallada). Si el audio
   * aún no está cargado el seek se aplica cuando lo esté (duration ya notificada
   * por el controlador desde V3.29). */
  function seekTo(seconds: number) {
    audioController?.seek(seconds);
  }

  /** Ref de la palabra/frase fallada (V3.29, P6), escalada a la variante que se
   * va a reproducir. Resuelve el target según el resultado:
   * - dictado (`productionResult`): primera palabra de `breakdown.missing` /
   *   `substituted[].expected`;
   * - MCQ incorrecto (`result.correct === false`): la opción correcta (diana).
   * Solo hay salto fiable con audio pre-renderizado y word timings del sidecar.
   */
  function failedWordRefFor(
    rateVariant: "normal" | "slow",
  ): FailedWordRef | null {
    if (!question || !question.audio_ready || !audioController) return null;
    const timings = question.wordTimings ?? [];
    if (timings.length === 0) return null;
    let target: string | null = null;
    if (productionResult?.task_type === "dictation") {
      target = firstFailedWord(productionResult.breakdown);
    } else if (result && !result.correct) {
      target = question.options[result.correct_index] ?? null;
    }
    if (!target) return null;
    return failedWordTiming(
      target,
      scaleWordTimings(timings, variantTimeScale(question, rateVariant)),
      question.sentenceTimings ?? [],
    );
  }

  /** Repite la palabra fallada (V3.29, P6): seek al inicio de su ref (+0.05s de
   * margen), bucle sobre su intervalo y reproducción de la variante pedida. La
   * cadena pedagógica de la auditoría (palabra fallada → replay → slow) activa
   * primero `normal` y ofrece el segundo botón en `slow`. */
  async function repeatFailedWord(rateVariant: "normal" | "slow") {
    if (!question || !userId || !audioController) return;
    const ref = failedWordRefFor(rateVariant);
    if (!ref) return;
    setVariant(rateVariant);
    const margin = Math.max(0, ref.start - 0.05);
    audioController.load(getListeningAudioUrl(question.id, userId, rateVariant));
    audioController.loop(margin, ref.end);
    audioController.seek(margin);
    // V3.52.1: refleja el bucle en la UI A/B; antes se armaba un segmento
    // «invisible» que la pantalla no podía mostrar ni quitar.
    setAbLoop(loopFromSegment(margin, ref.end));
    try {
      await audioController.play();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const failedRefNormal = failedWordRefFor("normal");
  const failedRefSlow = failedWordRefFor("slow");

  /** Metadatos de apoyo del intento (evidencia ampliada V3.27). Solo se envían
   * en ítems servidos con `flow`; el resto conserva el envío anterior. */
  function supportOpts(): ListeningSupportMetadata | undefined {
    if (!question || !flowState) return undefined;
    return {
      layer: question.layer ?? undefined,
      speedUsed: variant,
      stage: flowState.stage ?? undefined,
      transcriptUsed: flowState.transcript,
    };
  }

  /** Aplica la máquina de estados tras responder en while2. */
  function applyFlowAnswer(correct: boolean) {
    if (!question || !flowState || !flowPolicy || !micro) return;
    setFlowState(
      completeStageWithAnswer(flowState, correct, flowPolicy, flowSteps),
    );
  }

  /** Avanza una etapa de presentación (pre → while1 → while2). */
  function continueStage() {
    if (!flowState) return;
    const next = advanceToNext(flowState, flowSteps);
    setFlowState(next.finished ? null : next);
    if (next.finished) void load();
  }

  /** V3.75.3: pulsar PLAY declara «he escuchado» y abre la pregunta.
   *
   * La etapa `while1` («escucha global») ya no tiene tarjeta ni botón propio: la
   * señal de que se ha escuchado es el propio PLAY. Solo aplica al flujo
   * receptivo (en producción no hay `while1`) y `advanceToNext` no dispara
   * `load()` porque el flujo no termina, así que avanza a la pregunta sin tocar
   * el ítem.
   */
  function markListened() {
    if (micro?.stage === "while1") continueStage();
  }

  /** Desde el resultado en `post` avanza al siguiente paso (shadowing) o, si el
   * flujo terminó, carga la siguiente pregunta. */
  function continueFromResult() {
    if (!micro || !flowState) {
      void load();
      return;
    }
    if (flowState.stepIndex + 1 < flowSteps.length) {
      setFlowState(advanceToNext(flowState, flowSteps));
    } else {
      setFlowState(null);
      void load();
    }
  }

  /** Termina la etapa de shadowing libre y avanza. */
  function finishShadowingStage() {
    if (!flowState) return;
    const next = advanceToNext(completeShadowing(flowState), flowSteps);
    setFlowState(next.finished ? null : next);
    if (next.finished) void load();
  }

  /** Salta la etapa de shadowing solo si el paso lo permite (`allow_skip`). */
  function skipShadowingStage() {
    if (!flowState) return;
    const step = currentStep(flowState, flowSteps);
    if (step && !step.allow_skip) return;
    const next = advanceToNext(flowState, flowSteps);
    setFlowState(next.finished ? null : next);
    if (next.finished) void load();
  }

  /** Reintenta la pregunta tras un fallo con reintentos disponibles. */
  function retryQuestion() {
    setResult(null);
    setSelected(null);
    setError(null);
  }

  /** Revela la transcripción manualmente si la política lo permite. */
  function showTranscriptNow() {
    if (!flowState || !flowPolicy) return;
    setFlowState(revealFull(flowState, flowPolicy));
  }

  async function load(
    levelOverride?: string | null,
    modeOverride?: ListeningQuestionMode,
  ) {
    if (!userId) return;
    setError(null);
    setResult(null);
    setSelected(null);
    setProductionResult(null);
    setDictationText("");
    setTranscribedText("");
    // Shadowing 2.0 (V3.28, Bloque E): al cambiar de pregunta se descarta la
    // grabación local anterior (revocando su objeto URL) y sus señales.
    setRecordingUrl((url) => {
      if (url) URL.revokeObjectURL(url);
      return null;
    });
    setShadowingDurationMs(null);
    setShadowingSpeechRate(null);
    setVariant("normal");
    // Controles A/B (V3.29, P5): nueva pregunta ⇒ sin marca ni bucle activo.
    audioController?.clearLoop();
    setAbLoop(EMPTY_AB_LOOP);
    // Sin override: sesión activa > ruta seleccionada > elección del backend
    // (modo adaptativo). V3.48.1: la ruta seleccionada es persistente.
    const level =
      levelOverride === undefined
        ? resolveRouteLevel(session?.level, selectedLevel, undefined)
        : levelOverride;
    const mode =
      modeOverride ??
      (session?.mode === "drill"
        ? "failed"
        : session?.mode === "mastered"
          ? "mastered"
          : "all");
    try {
      const next = await getListeningQuestion(userId, level, mode);
      setQuestion(next);
      // El micro-flujo arranca cuando el backend sirvió `flow` (adaptativo,
      // nivel y drill); el repaso mastered (compacto) no lo usa.
      setFlowState(hasFlow(next) ? initialFlow(next) : null);
      setStartedAt(Date.now());
      setReplayCount(0);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  /** Sesión focalizada: practicar/repasar una ruta completa (rotación LRU). */
  function startLevelSession(level: string, total: number) {
    if (session || !userId) return;
    setSession({ mode: "level", level, total, done: 0 });
    setExpandedLevel(null);
    void load(level);
  }

  /** Sesión drill: repetir las frases falladas del nivel hasta dominarlas. */
  function startFailedDrill(level: string, failedIds: string[]) {
    if (session || !userId || failedIds.length === 0) return;
    setSession({ mode: "drill", level, total: failedIds.length, remaining: failedIds });
    setExpandedLevel(null);
    void load(level, "failed");
  }

  /** Sesión de repaso de lo aprendido: rotación solo por las frases dominadas
   * de la ruta (consolidación y re-exposición, V3.6). */
  function startMasteredSession(level: string, total: number) {
    if (session || !userId || total === 0) return;
    setSession({ mode: "mastered", level, total, done: 0 });
    setExpandedLevel(null);
    void load(level, "mastered");
  }

  /** Cierra la sesión actual y vuelve a la ruta seleccionada (o al adaptativo). */
  function exitSession() {
    setSession(null);
    setExpandedLevel(selectedLevel ?? null);
    // `selectedLevel ?? null` explícito: el cierre aún conserva la `session`
    // vieja en el closure y sin override `load()` seguiría pidiendo frases del
    // nivel que se abandona.
    void load(selectedLevel ?? null, "all");
  }

  /** Abre/cierra el historial desplegable de un nivel (uno a la vez). */
  function toggleLevel(level: string) {
    if (session) return;
    setExpandedLevel((cur) => (cur === level ? null : level));
  }

  // Tras responder: avanza el progreso de la sesión (el contador solo avanza
  // cuando se responde, no al saltar). En drill se elimina la frase del pool
  // pendiente solo si se acertó.
  function applySessionOutcome(questionId: string, correct: boolean) {
    if (!session) return;
    if (session.mode === "drill") {
      if (correct) {
        setSession((s) =>
          s && s.mode === "drill"
            ? { ...s, remaining: drillAnswered(s.remaining, questionId, true) }
            : s,
        );
      }
      return;
    }
    // level y mastered (repaso de lo aprendido) rotan una vuelta completa.
    setSession((s) =>
      s && (s.mode === "level" || s.mode === "mastered")
        ? { ...s, done: s.done + 1 }
        : s,
    );
  }

  // --- Práctica extra generada (V3.6) ----------------------------------------
  // Añadir "X más" de práctica a una ruta crea un trabajo en el backend (la
  // generación con el modelo local tarda). `pollExtrasJob` consulta el estado
  // hasta `done`/`error` y refresca las métricas y el panel del nivel.
  async function startAddPractice(level: string, count: number) {
    if (!userId) return;
    if (extrasJobs[level]?.status === "running") return;
    setError(null);
    try {
      const job = await addRouteExtras(userId, level, count);
      setExtrasJobs((prev) => ({ ...prev, [level]: job }));
      pollExtrasJob(level, job.job_id);
    } catch (e) {
      // Fallo del POST (backend caído, petición rechazada…): se muestra como un
      // trabajo en error para que el bloque del nivel lo explique.
      setExtrasJobs((prev) => ({
        ...prev,
        [level]: {
          job_id: "",
          status: "error",
          level,
          requested: count,
          added: [],
          error: (e as Error).message,
        },
      }));
    }
  }

  function pollExtrasJob(level: string, jobId: string) {
    if (!userId) return;
    const timer = setTimeout(() => {
      void (async () => {
        let job: ListeningExtrasJob | null = null;
        try {
          job = await getRouteExtrasJob(userId, level, jobId);
        } catch {
          // Error de red transitorio: se reintenta en la siguiente ronda.
        }
        if (!job) {
          pollExtrasJob(level, jobId);
          return;
        }
        setExtrasJobs((prev) =>
          prev[level]?.job_id === jobId
            ? { ...prev, [level]: job }
            : prev,
        );
        if (job.status === "running") {
          pollExtrasJob(level, jobId);
          return;
        }
        delete pollTimersRef.current[level];
        setExtrasNonce((n) => n + 1);
        void refreshStats();
      })();
    }, 2500);
    pollTimersRef.current[level] = timer;
  }

  async function speakQuestion() {
    if (!question || speakingQuestion) return;
    setSpeakingQuestion(true);
    try {
      await speakWithVoice(question.question, userId);
    } catch {
      // TTS de la pregunta no disponible: se ignora, no bloquea la práctica.
    } finally {
      setSpeakingQuestion(false);
    }
  }

  // CTA del resultado: si el motor recomienda seguir escuchando, avanza a la
  // siguiente frase en esta misma pantalla (la sección ya está activa y no se
  // re-monta); en otro caso navega a la destreza/objetivo recomendado.
  function handleResultNext(section: Section | null, step: NextBestActivity) {
    if (step.skill === "listening" || section === "listening") {
      void load();
      return;
    }
    onNext(section, step);
  }

  async function refreshStats() {
    if (!userId) return;
    try {
      setStats(await getListeningStats(userId));
    } catch {
      /* backend no disponible */
    }
    try {
      setDiagnostic(await getListeningDiagnostic(userId));
    } catch {
      /* backend no disponible */
    }
  }

  // V3.48.1: al seleccionar (o hidratar) una ruta, se despliega su panel.
  useEffect(() => {
    if (selectedLevel) setExpandedLevel(selectedLevel);
  }, [selectedLevel]);

  useEffect(() => {
    void load();
    void refreshStats();
    // V3.52.1: al cambiar la ruta seleccionada se recarga la pregunta para
    // servirla del nivel elegido (antes solo se recargaba al cambiar de perfil,
    // así que seleccionar A2 no tenía efecto inmediato).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, selectedLevel]);

  // Voz TTS seleccionada del perfil (nombre amigable) para la etiqueta honesta de
  // los ítems sintéticos. V3.75.5: ya no se pide aquí el catálogo (lo trae el
  // store de acentos), así que la etiqueta sigue a la voz elegida en el «...» sin
  // volver a consultar el backend.

  async function play() {
    if (!question || !userId || playing) return;
    setReplayCount((count) => count + 1);
    try {
      if (question.audio_ready && audioController) {
        // Audio de referencia pre-renderizado (respeta speech_rate y repetición),
        // reproducido por el AudioController 4.0 (un solo elemento reutilizable).
        // `play()` resuelve cuando **empieza** a sonar: es el momento de abrir la
        // pregunta (V3.75.3), para poder leer las opciones mientras se escucha.
        // V3.75.5: PLAY suena siempre en la voz A (la del perfil); cambiar de voz
        // cambia la URL, y el controller recarga al no coincidir con la cargada,
        // así que nunca sirve el WAV del acento anterior.
        await audioController.play(
          getListeningAudioUrl(question.id, userId, variant, voiceChoice.primary),
        );
        markListened();
      } else {
        // Degradación: TTS en vivo con el script del ítem (o sin API Audio).
        setTtsLivePlaying(true);
        // `speakWithVoice` resuelve al **terminar** la locución, así que esperar
        // aquí retrasaría la pregunta todo el audio: se marca al lanzarlo.
        markListened();
        try {
          const voice = voiceChoice.voiceFor("a");
          if (voice) await speakWithVoice(question.script, userId, "en", { voice });
          else await speakWithVoice(question.script, userId);
        } finally {
          setTtsLivePlaying(false);
        }
      }
    } catch (e) {
      setTtsLivePlaying(false);
      setError((e as Error).message);
    }
  }

  /**
   * «Probar A» / «Probar B» del selector de voz (V3.75.5): reproduce ESTE ítem
   * con el acento pedido para poder comparar antes de elegir.
   *
   * No cuenta como repetición (`replayCount`): es configuración, no estudio, y
   * contarla inflaría la evidencia de apoyo del intento. La primera vez que se
   * pide la voz B, el backend sintetiza y alinea ese WAV (unos segundos); el chip
   * muestra su spinner y después queda cacheado.
   */
  async function previewVoice(accent: VoiceAccent) {
    if (!question || !userId) return;
    const voice = voiceChoice.voiceFor(accent);
    if (!voice) return;
    try {
      if (question.audio_ready && audioController) {
        await audioController.play(
          getListeningAudioUrl(question.id, userId, variant, voice),
        );
        return;
      }
      await speakWithVoice(question.script, userId, "en", { voice });
    } catch (e) {
      setError((e as Error).message);
    }
  }

async function choose(index: number) {
  if (!userId || !question || result || submitting) return;
  setSelected(index);
  setError(null);
  setSubmitting(true);
  try {
    const res = await submitListeningAnswer(
      userId,
      question.id,
      index,
      Date.now() - startedAt,
      replayCount,
      supportOpts(),
    );
    setResult(res);
    setReplayCount(0);
    // Micro-flujo: tras responder en while2, la máquina decide reintento (con o
    // sin apoyo según la política) o el avance al post.
    applyFlowAnswer(res.correct);
    applySessionOutcome(question.id, res.correct);
    onAttempt();
    void refreshStats();
  } catch (e) {
    // Fallo de red o timeout: se muestra el error y la opción de saltar a la
    // siguiente, para que la pantalla nunca se quede sin salida.
    setError((e as Error).message);
  } finally {
    setSubmitting(false);
  }
}

async function submitDictation() {
  if (!userId || !question || productionResult) return;
  const text = dictationText.trim();
  if (!text) return;
  setProcessing(true);
  setError(null);
  try {
    const res = await submitListeningDictation(
      userId,
      question.id,
      text,
      supportOpts(),
    );
    setProductionResult(res);
    applySessionOutcome(question.id, res.correct);
    onAttempt();
    void refreshStats();
  } catch (e) {
    setError((e as Error).message);
  } finally {
    setProcessing(false);
  }
}

  async function toggleRecording() {
    if (!userId || !question || productionResult) return;
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
      recordingStartedAtRef.current = performance.now();
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        if (blob.size === 0) return;
        if (!userId || !question) return;
        // Shadowing 2.0 (V3.28, Bloque E): conservar la grabación como objeto
        // URL local para su playback y calcular las señales auxiliares
        // informativas (duración real y velocidad proxy en wpm).
        const durationMs = Math.max(
          0,
          Math.round(performance.now() - recordingStartedAtRef.current),
        );
        setShadowingDurationMs(durationMs > 0 ? durationMs : null);
        setRecordingUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return URL.createObjectURL(blob);
        });
        setProcessing(true);
        setError(null);
        try {
          const text = await transcribe(blob);
          setTranscribedText(text);
          const words = text.trim().split(/\s+/).filter(Boolean).length;
          const rate =
            words > 0 && durationMs > 0
              ? Math.round((words * 60_000) / durationMs)
              : null;
          setShadowingSpeechRate(rate);
          // El envío con scoring determinista solo existe para ítems de
          // shadowing directos (skill=shadowing). En el paso shadowing del
          // micro-flujo de ítems receptivos la grabación es libre (playback
          // local + señales visibles, sin POST: el backend rechazaría un
          // shadowing cuyo ítem no es de shadowing).
          if (question.skill === "shadowing") {
            const res = await submitListeningShadowing(
              userId,
              question.id,
              text,
              supportOpts(),
              {
                durationMs: durationMs > 0 ? durationMs : undefined,
                speechRate: rate ?? undefined,
              },
            );
            setProductionResult(res);
            applySessionOutcome(question.id, res.correct);
            onAttempt();
            void refreshStats();
          }
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setProcessing(false);
        }
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (e) {
      setError(`${t("mic.accessError")}${(e as Error).message}`);
    }
  }

  // Resumen del encabezado del diagnóstico plegable: debilidad principal de
  // resiliencia auditiva cuando existe; si no, la recomendación recortada.
  const diagnosticSummary = diagnostic
    ? (() => {
        const main = diagnostic.resilience.dimensions.find(
          (d) => d.dimension === diagnostic.resilience.main_weakness,
        );
        return main
          ? `${t("listening.resilienceMainWeakness")}: ${t(
              resilienceLabel(main.dimension),
            )}${main.accuracy !== null ? ` · ${main.accuracy}%` : ""}`
          : diagnostic.recommendation;
      })()
    : "";

  // V3.52.1: la "ruta actual" es la que se está sirviendo de verdad, con la
  // MISMA prioridad que la carga de pregunta (sesión > ruta seleccionada >
  // recomendada por el motor). Antes el anillo leía `stats.level` (la primera
  // ruta no superada) y por eso seguía diciendo «Ruta actual A1» al elegir A2.
  const stageLevel = resolveRouteLevel(
    session?.level,
    selectedLevel,
    stats?.level,
  );
  const routeLevel = stageLevel ?? "";
  const currentLevelStat = routeLevel
    ? stats?.levels.find((lv) => lv.level === routeLevel) ?? null
    : null;
  const currentLevelPct =
    currentLevelStat && currentLevelStat.total > 0
      ? (currentLevelStat.mastered / currentLevelStat.total) * 100
      : 0;

  // Color del donut de precisión según el rendimiento global.
  function ringTone(accuracy: number | null): string {
    if (accuracy === null) return "text-muted-foreground";
    if (accuracy >= 80) return "text-success";
    if (accuracy >= 60) return "text-primary";
    return "text-warning";
  }

  return (
    <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-3 overflow-y-auto px-3 py-4 sm:gap-4 sm:px-6 sm:py-6">
      {error && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <span className="min-w-0 break-words">{error}</span>
            {question && !(result || productionResult) && (
              <button
                type="button"
                className="self-start rounded-md border border-destructive/40 px-3 py-1.5 text-xs font-medium text-destructive transition-colors hover:bg-destructive/15"
                onClick={() => void load()}
              >
                {t("listening.errorSkip")}
              </button>
            )}
          </div>
        </div>
      )}

      {micError && <MicUnavailableNotice reason={micError} />}

      {!session && (
        <AuditoryProfileCard profile={diagnostic?.profile ?? null} t={t} />
      )}

      {!question ? (
        <Card className="p-8">
          <p className="text-center text-sm text-muted-foreground">
            {t("listening.loading")}
          </p>
        </Card>
      ) : (
        <>
          {/* Cabecera de la pantalla (V3.75.4): antes el ítem empezaba en seco
              con tarjetas y la salida de emergencia vivía al pie, compitiendo
              con las opciones. Aquí va la destreza, el nivel por el que va la
              ruta con su cobertura, y «Otro ejercicio» (el antiguo
              `listening.skip`) como botón fantasma discreto. */}
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
            <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
              <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                {t("skill.listening")}
              </span>
              {routeLevel && <LevelBadge level={routeLevel} />}
              {currentLevelStat && currentLevelStat.total > 0 && (
                <span className="text-[11px] tabular-nums text-muted-foreground">
                  {t("listening.masteredOfTotal")
                    .replace("{mastered}", String(currentLevelStat.mastered))
                    .replace("{total}", String(currentLevelStat.total))}
                  {" · "}
                  {t("listening.coveragePct").replace(
                    "{pct}",
                    String(Math.round(currentLevelPct)),
                  )}
                </span>
              )}
            </div>
            {!(result || productionResult) && session?.mode !== "drill" && (
              <button
                type="button"
                className="inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-full px-2.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:opacity-60"
                onClick={() => void load()}
                disabled={!userId}
              >
                <RefreshCw className="size-3.5" aria-hidden="true" />
                {t("listening.anotherItem")}
              </button>
            )}
          </div>

          {session && (
            <Card className="flex flex-row flex-wrap items-center justify-between gap-3 p-4">
              <span className="text-sm text-muted-foreground">
                {session.mode === "drill"
                  ? t("listening.drillProgress")
                      .replace("{level}", session.level)
                      .replace("{done}", String(sessionDone(session)))
                      .replace("{total}", String(session.total))
                  : session.mode === "mastered"
                    ? t("listening.reviewLearnedProgress")
                        .replace("{level}", session.level)
                        .replace("{done}", String(session.done))
                        .replace("{total}", String(session.total))
                    : t("listening.reviewProgress")
                        .replace("{level}", session.level)
                        .replace("{done}", String(session.done))
                        .replace("{total}", String(session.total))}
              </span>
              <Button
                type="button"
                variant="outline"
                className="min-h-9 gap-2"
                onClick={exitSession}
              >
                {session.mode === "drill"
                  ? t("listening.exitSession")
                  : t("listening.exitReview")}
              </Button>
            </Card>
          )}

          {/* Micro-flujo (V3.27): tarjetas de etapa Shadowing del modo
              adaptativo. La tarjeta de audio queda siempre disponible; la pregunta
              solo se muestra en `while2`/`post`. */}
          {/* V3.48.1: la etapa `pre` («Antes de escuchar») se retira de la UI
              (microFlow salta los pasos `pre`); el contexto del ítem pasa a la
              tarjeta de audio como caption de una línea. */}
          {/* V3.75.3: la tarjeta `while1` («He escuchado — responder») también se
              retira. La señal de que se ha escuchado es pulsar PLAY (`play()` llama
              a `markListened`): así las opciones ocupan el hueco que gastaba ese
              paso y en móvil no hace falta desplazarse para responder. */}

          {micro?.stage === "shadowing" && (
            <Card className="gap-4 border-primary/25 p-5">
              <p className="text-sm font-semibold text-foreground">
                {t("listening.flow.shadowingTitle")}
              </p>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {t("listening.flow.shadowingHint")}
              </p>
              {/* Shadowing 2.0 (V3.28, Bloque E): en el paso shadowing del
                  micro-flujo la grabación es voluntaria y NO se puntúa (el
                  backend no admite shadowing de ítems receptivos). Sirve para
                  escucharse, con señales auxiliares informativas. */}
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant={recording ? "destructive" : "default"}
                  className="min-h-10 gap-2"
                  onClick={toggleRecording}
                  disabled={!userId || !!productionResult || processing}
                >
                  {processing ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  ) : recording ? (
                    <Square className="size-4" aria-hidden="true" />
                  ) : (
                    <Mic className="size-4" aria-hidden="true" />
                  )}
                  {processing
                    ? t("listening.evaluating")
                    : recording
                      ? t("listening.stop")
                      : t("listening.flow.recordShadowing")}
                </Button>
                {recording && (
                  <div className="flex items-center gap-2 text-xs font-medium text-destructive">
                    <motion.span
                      className="size-2 rounded-full bg-destructive"
                      animate={{ opacity: [1, 0.25, 1] }}
                      transition={{ duration: 1.2, repeat: Infinity }}
                      aria-hidden="true"
                    />
                    {t("listening.record")}
                  </div>
                )}
                {recordingUrl && (
                  <RecordingPlayButton
                    src={recordingUrl}
                    label={t("listening.flow.playRecording")}
                  />
                )}
              </div>
              {recordingUrl && shadowingDurationMs !== null && (
                <p className="text-xs tabular-nums text-muted-foreground">
                  {t("listening.flow.shadowingSignals")
                    .replace("{duration}", String(shadowingDurationMs ?? 0))
                    .replace("{wpm}", String(shadowingSpeechRate ?? 0))}
                </p>
              )}
              {transcribedText && (
                <p className="text-sm text-muted-foreground">
                  {t("listening.transcribed")}: {transcribedText}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  className="min-h-10 gap-2"
                  onClick={finishShadowingStage}
                >
                  {t("listening.flow.shadowingDone")}
                </Button>
                {flowSteps[micro.stepIndex]?.allow_skip && (
                  <Button
                    type="button"
                    variant="outline"
                    className="min-h-10 gap-2"
                    onClick={skipShadowingStage}
                  >
                    {t("listening.flow.skipStage")}
                  </Button>
                )}
              </div>
            </Card>
          )}

          {/* V3.75.4: la tarjeta de audio se separa del resto con un lavado suave
              del acento (`.listening-audio`, sin capa) en vez de un color plano,
              para que el PLAY sea el punto de mira de la pantalla. */}
          <Card className="listening-audio relative gap-4 p-4 sm:gap-5 sm:p-6">
            {/* V3.75.7: este desplegable sí trae **opciones** (velocidad, voz A/B,
                lectura al repetir), así que conserva la «...» por la convención de
                la app: (i) = solo información, (...) = información + opciones.
                No usa `InfoDisclosure` porque su panel es una zona centrada de la
                propia tarjeta, sin caja propia; el botón flota arriba a la derecha
                y el panel nace muy por debajo de él, así que no puede taparlo. */}
            <button
              type="button"
              onClick={() => setShowAudioSettings((s) => !s)}
              aria-expanded={showAudioSettings}
              aria-controls="listening-audio-settings"
              aria-label={t("listening.audioSettings")}
              title={t("listening.audioSettings")}
              className={cn(
                "absolute top-3 right-3 z-10 grid size-9 place-items-center rounded-full border transition-colors",
                showAudioSettings
                  ? "border-transparent bg-primary text-primary-foreground"
                  : "border-border bg-secondary text-secondary-foreground hover:border-primary/50 hover:text-foreground",
              )}
            >
              <MoreHorizontal className="size-4" aria-hidden="true" />
            </button>

            <div className="flex flex-col items-center gap-3 text-center sm:gap-4">
              <motion.button
                type="button"
                onClick={play}
                disabled={playing || !userId}
                whileTap={playing || !userId ? undefined : { scale: 0.94 }}
                aria-label={playing ? t("listening.playing") : t("listening.play")}
                className="grid size-16 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground shadow-md shadow-primary/20 ring-4 ring-primary/10 transition-colors hover:bg-primary/90 disabled:opacity-50 sm:size-20"
              >
                {playing ? (
                  <Loader2 className="size-7 animate-spin sm:size-8" aria-hidden="true" />
                ) : (
                  <Play className="size-7 translate-x-0.5 sm:size-8" aria-hidden="true" />
                )}
              </motion.button>

              {playing ? (
                <Waveform />
              ) : (
                <span className="text-sm font-medium text-muted-foreground">
                  {t("listening.play")}
                </span>
              )}
            </div>

            {/* V3.48.1: señal situacional del ítem (antes en la tarjeta «Antes
                de escuchar»), ahora caption compacta de una línea. */}
            {(question.context || question.topic) && (
              <p className="max-w-md self-center text-center text-xs leading-relaxed text-muted-foreground">
                {question.context || topicLabel(question.topic)}
              </p>
            )}

            {/* Controles precisos V3.29 (Fase 3, P5): seek slider continuo y
                bucle A/B. Solo cuando el audio de referencia está pre-renderizado
                y su duración real ya se conoce (loadedmetadata vía onDuration). */}
            {question.audio_ready &&
              audioDuration > 0 &&
              audioController && (
                <div className="flex w-full max-w-md flex-col gap-3 self-center">
                  <div className="flex items-center gap-2">
                    <span className="w-9 shrink-0 text-right text-[11px] tabular-nums text-muted-foreground">
                      {formatSeconds(audioTime)}
                    </span>
                    <input
                      type="range"
                      min={0}
                      max={audioDuration}
                      step={0.05}
                      value={Math.min(audioTime, audioDuration)}
                      onChange={(e) => seekTo(Number(e.target.value))}
                      aria-label={t("listening.audio.seekSlider")}
                      className="h-2 w-full cursor-pointer appearance-none rounded-full bg-secondary accent-primary"
                    />
                    <span className="w-9 shrink-0 text-[11px] tabular-nums text-muted-foreground">
                      {formatSeconds(audioDuration)}
                    </span>
                  </div>
                  {/* V3.75.3: los controles A/B son de precisión y en móvil
                      ocupan una fila entera de botones; se ocultan por debajo de
                      `sm` para dejar sitio a las opciones. El deslizador de
                      posición se conserva siempre: es una sola línea y sirve
                      para releer un tramo. */}
                  <div className="hidden flex-wrap items-center justify-center gap-2 sm:flex">
                    <Button
                      variant={markStart !== null ? "secondary" : "outline"}
                      size="sm"
                      onClick={() => {
                        // V3.52.1: la marca se toma del instante REAL del
                        // controller (no del estado React de ~4 Hz) y quitar la
                        // marca desarma también el bucle del controller.
                        if (markStart !== null) {
                          audioController.clearLoop();
                          setAbLoop(clearAbLoop());
                        } else {
                          setAbLoop((state) =>
                            toggleMark(state, audioController.currentTime),
                          );
                        }
                      }}
                      disabled={!question.audio_ready}
                    >
                      <Flag className="size-3.5" aria-hidden="true" />
                      {markStart !== null
                        ? t("listening.audio.clearMark")
                        : t("listening.audio.markStart")}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const next = armLoop(abLoop, audioController.currentTime);
                        if (!next) return;
                        audioController.loop(next.markStart!, next.loopEnd!);
                        setAbLoop(next);
                      }}
                      disabled={
                        markStart === null ||
                        audioTime - markStart < MIN_AB_LOOP_SECONDS
                      }
                    >
                      <Repeat2 className="size-3.5" aria-hidden="true" />
                      {t("listening.audio.loopAB")}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        audioController.clearLoop();
                        setAbLoop(clearAbLoop());
                      }}
                      disabled={!canClear(abLoop)}
                    >
                      <X className="size-3.5" aria-hidden="true" />
                      {t("listening.audio.clearLoop")}
                    </Button>
                  </div>
                  {isLooping && markStart !== null && loopEnd !== null && (
                    <p className="hidden text-center text-[11px] text-muted-foreground sm:block">
                      {t("listening.audio.loopingHint")
                        .replace("{start}", formatSeconds(markStart))
                        .replace("{end}", formatSeconds(loopEnd))}
                    </p>
                  )}
                </div>
              )}

            {showAudioSettings && (
              <div
                id="listening-audio-settings"
                className="flex flex-col items-center gap-4"
              >
                {question.audio_ready &&
                  question.audio_type === "tts" &&
                  question.variants.length > 1 && (
                    <div className="flex flex-wrap items-center justify-center gap-2">
                      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {t("listening.speed")}
                      </span>
                      {question.variants.map((v: ListeningAudioVariant) => (
                        <button
                          key={v.variant}
                          type="button"
                          className={cn(
                            "min-h-10 rounded-full border px-3 text-xs font-medium transition-colors",
                            v.variant === variant
                              ? "border-transparent bg-primary text-primary-foreground"
                              : "border-border bg-secondary text-secondary-foreground hover:border-primary/50",
                            "disabled:opacity-60",
                          )}
                          onClick={() => setVariant(v.variant)}
                          disabled={playing || !userId}
                        >
                          {v.label}
                        </button>
                      ))}
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {Math.round(
                          question.variants.find((v) => v.variant === variant)
                            ?.speech_rate ?? question.speech_rate,
                        )}{" "}
                        wpm
                      </span>
                    </div>
                  )}

                <div className="flex flex-col items-center gap-1.5 text-center">
                  <div className="flex items-center gap-1.5">
                    <p className="text-xs text-muted-foreground">
                      {audioTypeLabel(question.audio_type, t)}
                    </p>
                    {question.realized_difficulty < question.difficulty && (
                      <Tooltip
                        content={t("listening.audioGap")
                          .replace("{realized}", String(question.realized_difficulty))
                          .replace("{declared}", String(question.difficulty))}
                      >
                        <button
                          type="button"
                          className="inline-flex text-warning"
                          aria-label={t("listening.audioGapTitle")}
                        >
                          <AlertTriangle className="size-3.5" aria-hidden="true" />
                        </button>
                      </Tooltip>
                    )}
                  </div>
                  {!question.audio_ready && (
                    <p className="text-xs text-muted-foreground">
                      {t("listening.audioUnavailable")}
                    </p>
                  )}
                  {question.speech_rate > 0 && (
                    <p className="text-xs tabular-nums text-muted-foreground">
                      {question.audio_type === "tts" ? (
                        primaryVoiceName ? (
                          <span title={t("listening.ttsRealVoice")}>
                            {primaryVoiceName} ·{" "}
                          </span>
                        ) : null
                      ) : (
                        <span>{question.accent} · </span>
                      )}
                      {Math.round(question.speech_rate)} wpm ·{" "}
                      {question.duration.toFixed(1)}s
                    </p>
                  )}

                  {/* V3.75.5: el «...» deja de ser un cartel y pasa a configurar.
                      Antes solo leía «Voz sintética local (TTS)» + el nombre de la
                      voz: no había forma de cambiarla desde la práctica. */}
                  {question.audio_type === "tts" && (
                    <div className="mt-1 w-full max-w-md border-t border-border/60 pt-3 text-left">
                      <VoicePicker
                        userId={userId}
                        onPreview={previewVoice}
                        note={t("listening.ttsRealVoice")}
                      />
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>

          {(!micro ||
            (micro.stage !== "while1" && micro.stage !== "shadowing")) && (
            <Card className="gap-4 p-5">
              <div className="flex items-start justify-between gap-3">
                <p
                  className="text-base font-semibold leading-snug"
                  lang={questionPhrase.isSpanish ? "es" : "en"}
                >
                  {questionPhrase.display}
                </p>
              <div className="flex shrink-0 items-center gap-2">
                <PhraseTranslateButton
                  state={questionPhrase}
                  className="size-9"
                />
                <button
                  type="button"
                  onClick={() => void speakQuestion()}
                  disabled={speakingQuestion || !userId}
                  aria-label={t("listening.speakQuestion")}
                  className="grid size-9 shrink-0 place-items-center rounded-full border border-border bg-secondary text-secondary-foreground transition-colors hover:border-primary/50 hover:text-foreground disabled:opacity-60"
                >
                  {speakingQuestion ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Volume2 className="size-4" aria-hidden="true" />
                  )}
                </button>
              </div>
            </div>

            {question.skill === "dictation" && (
              <div className="flex flex-col gap-3">
                <textarea
                  className="min-h-24 w-full resize-y rounded-md border border-input bg-background px-3 py-2.5 text-sm leading-relaxed outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-70"
                  value={dictationText}
                  onChange={(e) => setDictationText(e.target.value)}
                  placeholder={t("listening.dictationPlaceholder")}
                  disabled={!!productionResult || processing}
                />
                <Button
                  className="min-h-10 gap-2 self-start"
                  onClick={submitDictation}
                  disabled={
                    !userId ||
                    !dictationText.trim() ||
                    !!productionResult ||
                    processing
                  }
                >
                  {processing ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Send className="size-4" aria-hidden="true" />
                  )}
                  {processing
                    ? t("listening.evaluating")
                    : t("listening.submitDictation")}
                </Button>
              </div>
            )}

            {question.skill === "shadowing" && (
              <div className="flex flex-col gap-3">
                <Button
                  variant={recording ? "destructive" : "default"}
                  className="min-h-10 gap-2 self-start"
                  onClick={toggleRecording}
                  disabled={!userId || !!productionResult || processing}
                >
                  {processing ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  ) : recording ? (
                    <Square className="size-4" aria-hidden="true" />
                  ) : (
                    <Mic className="size-4" aria-hidden="true" />
                  )}
                  {processing
                    ? t("listening.evaluating")
                    : recording
                      ? t("listening.stop")
                      : t("listening.record")}
                </Button>
                {recording && (
                  <div className="flex items-center gap-2 text-xs font-medium text-destructive">
                    <motion.span
                      className="size-2 rounded-full bg-destructive"
                      animate={{ opacity: [1, 0.25, 1] }}
                      transition={{ duration: 1.2, repeat: Infinity }}
                      aria-hidden="true"
                    />
                    {t("listening.record")}
                  </div>
                )}
                {transcribedText && (
                  <p className="text-sm text-muted-foreground">
                    {t("listening.transcribed")}: {transcribedText}
                  </p>
                )}
                {/* Shadowing 2.0 (V3.28, Bloque E): playback local de la
                    grabación del alumno + señales auxiliares informativas. */}
                {recordingUrl && (
                  <div className="flex flex-wrap items-center gap-2">
                    <RecordingPlayButton
                      src={recordingUrl}
                      label={t("listening.flow.playRecording")}
                    />
                    {shadowingDurationMs !== null && (
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {t("listening.flow.shadowingSignals")
                          .replace(
                            "{duration}",
                            String(shadowingDurationMs ?? 0),
                          )
                          .replace("{wpm}", String(shadowingSpeechRate ?? 0))}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}

            {question.skill !== "dictation" &&
              question.skill !== "shadowing" && (
                <div className="grid gap-2 sm:grid-cols-2">
                  {question.options.map((opt, i) => {
                    const isCorrect = result && i === result.correct_index;
                    const isWrong = result && i === selected && !result.correct;
                    return (
                      <button
                        key={opt}
                        type="button"
                        className={cn(
                          "flex min-h-10 items-start gap-2.5 rounded-md border px-3 py-2.5 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                          isCorrect
                            ? "border-success bg-success/15 text-foreground"
                            : isWrong
                              ? "border-destructive bg-destructive/10 text-foreground"
                              : "border-border bg-secondary text-secondary-foreground hover:border-primary/60 hover:bg-primary/10",
                          "disabled:cursor-default disabled:opacity-70",
                        )}
                        onClick={() => choose(i)}
                        disabled={!!result || submitting}
                      >
                        {/* Insignia de letra (V3.75.4): da un ancla visual a cada
                            opción y hace legible la referencia «A/B/C» al
                            corregir, sobre todo en móvil. */}
                        <span
                          aria-hidden="true"
                          className="mt-px grid size-6 shrink-0 place-items-center rounded-md bg-background/70 text-[11px] font-bold tabular-nums"
                        >
                          {String.fromCharCode(65 + i)}
                        </span>
                        <span className="min-w-0 flex-1">{opt}</span>
                      </button>
                    );
                  })}
                </div>
              )}

            {submitting && (
              <p
                role="status"
                aria-live="polite"
                className="flex items-center justify-center gap-2 py-1 text-xs text-muted-foreground"
              >
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                {t("listening.evaluating")}
              </p>
            )}
            </Card>
          )}

          {/* Transcript dinámico (V3.28/V3.29): karaoke palabra a palabra cuando
              el backend sirve `wordTimings` (sidecar word_alignment_proxy);
              si no, sync grueso de frase. `transcriptVisible` cubre el flujo
              receptivo (hidden/partial/full) y la revelación completa tras un
              resultado de producción (dictado/shadowing). */}
          {question &&
            transcriptVisible !== "hidden" &&
            micro?.stage !== "shadowing" &&
            ((question.wordTimings?.length ?? 0) > 0 ? (
              <KaraokeTranscript
                wordTimings={question.wordTimings ?? []}
                sentenceTimings={question.sentenceTimings ?? []}
                state={transcriptVisible}
                currentTime={audioTime}
                activeVariantFactor={variantTimeScale(question, variant)}
                onSeekToWord={(start) => seekTo(start)}
              />
            ) : (question.sentenceTimings?.length ?? 0) > 0 ? (
              <CoarseTranscript
                timings={question.sentenceTimings ?? []}
                state={transcriptVisible}
                currentTime={audioTime}
              />
            ) : null)}

          {(result || productionResult) &&
            !(micro?.stage === "shadowing") &&
            !(result && !result.correct && micro?.stage === "while2") && (
            <ActivityResult
              outcome={
                result
                  ? result.correct
                    ? "ok"
                    : "ko"
                  : productionResult?.correct
                    ? "ok"
                    : "ko"
              }
              title={
                result
                  ? result.correct
                    ? t("listening.correct")
                    : t("listening.incorrect")
                  : t("listening.dictationTitle").replace(
                      "{score}",
                      String(productionResult?.score ?? 0),
                    )
              }
              footer={
                micro?.stage === "post" ? (
                  <Button
                    type="button"
                    className="min-h-10 gap-2"
                    onClick={continueFromResult}
                  >
                    {t("listening.flow.continue")}
                  </Button>
                ) : session ? (
                  isSessionFinished(session) ? (
                    <Button
                      type="button"
                      className="min-h-10 gap-2"
                      onClick={exitSession}
                    >
                      {session.mode === "drill"
                        ? t("listening.drillFinish")
                        : t("listening.reviewFinish")}
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      className="min-h-10 gap-2"
                      onClick={() => void load()}
                    >
                      {t("listening.reviewNext")}
                    </Button>
                  )
                ) : (
                  <NextStep
                    userId={userId}
                    onNext={handleResultNext}
                    fallback={{
                      label: t("listening.next"),
                      onClick: () => void load(),
                    }}
                  />
                )
              }
            >
              {session?.mode === "drill" &&
                session.remaining.length === 0 && (
                  <p className="text-sm font-medium text-primary">
                    {t("listening.drillDone")
                      .replace("{total}", String(session.total))
                      .replace("{level}", session.level)}
                  </p>
                )}
              {result &&
                !(
                  micro?.stage === "while2" &&
                  !result.correct &&
                  micro.transcript !== "full"
                ) && (
                <div className="flex flex-col gap-2">
                  <span
                    className="text-foreground"
                    lang={scriptPhrase.isSpanish ? "es" : "en"}
                  >
                    {scriptPhrase.display}
                  </span>
                  <div className="flex items-center gap-2">
                    <PhraseTranslateButton state={scriptPhrase} />
                    {/* V3.75.5: era un altavoz que releía solo el script con la voz
                        del perfil. Ahora lee el ítem **compuesto** y ofrece los dos
                        acentos instalados.
                        V3.75.6: texto del ítem + clave, y la composición la elige el
                        perfil en el «...» (ítem / ítem + opciones / solo la clave). */}
                    <ItemReplayButton
                      prompt={question.question}
                      script={question.script}
                      options={question.options}
                      correctIndex={result.correct_index}
                      userId={userId}
                    />
                  </div>
                </div>
              )}
              {productionResult && (
                <>
                  <div className="flex flex-col gap-1 text-sm">
                    <div>
                      <span className="text-muted-foreground">
                        {t("listening.wordAccuracy")}:
                      </span>{" "}
                      {productionResult.word_accuracy}%
                    </div>
                    {productionResult.task_type !== "dictation" && (
                      <div>
                        <span className="text-muted-foreground">
                          {t("listening.phoneticScore")}:
                        </span>{" "}
                        {productionResult.phonetic_score}%
                      </div>
                    )}
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <span className="text-muted-foreground">
                          {t("listening.reference")}:
                        </span>{" "}
                        <span
                          className="text-foreground"
                          lang={referencePhrase.isSpanish ? "es" : "en"}
                        >
                          {referencePhrase.display}
                        </span>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <PhraseTranslateButton state={referencePhrase} />
                        {/* V3.75.5: la referencia se puede repetir en A o B. */}
                        <ItemReplayButton
                          prompt={productionResult.reference}
                          userId={userId}
                        />
                      </div>
                    </div>
                    {transcribedText && (
                      <div>
                        <span className="text-muted-foreground">
                          {t("listening.heard")}:
                        </span>{" "}
                        {transcribedText}
                      </div>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {t("listening.breakdownWords")
                      .replace(
                        "{correct}",
                        String(
                          Array.isArray(productionResult.breakdown.correct)
                            ? productionResult.breakdown.correct.length
                            : 0,
                        ),
                      )
                      .replace(
                        "{missing}",
                        String(
                          Array.isArray(productionResult.breakdown.missing)
                            ? productionResult.breakdown.missing.length
                            : 0,
                        ),
                      )
                      .replace(
                        "{extra}",
                        String(
                          Array.isArray(productionResult.breakdown.extra)
                            ? productionResult.breakdown.extra.length
                            : 0,
                        ),
                      )}
                  </p>
                  {/* Salto a la palabra fallada (V3.29, Fase 3, P6): en el
                      dictado fallado se repite en bucle la primera palabra que
                      el alumno no oyó (normal o slow), con seek al instante de
                      la palabra vía el sidecar word_alignment_proxy. */}
                  {(failedRefNormal || failedRefSlow) && (
                    <div className="flex flex-wrap items-center gap-2 border-t border-border/60 pt-3">
                      <span className="text-xs font-medium text-muted-foreground">
                        {t("listening.failedWord.repeatLabel")}
                      </span>
                      {failedRefNormal && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="gap-2"
                          onClick={() => void repeatFailedWord("normal")}
                        >
                          <RefreshCw className="size-3.5" aria-hidden="true" />
                          {t("listening.failedWord.repeatNormal")}
                        </Button>
                      )}
                      {failedRefSlow && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="gap-2"
                          onClick={() => void repeatFailedWord("slow")}
                        >
                          <RefreshCw className="size-3.5" aria-hidden="true" />
                          {t("listening.failedWord.repeatSlow")}
                        </Button>
                      )}
                    </div>
                  )}
                </>
              )}
            </ActivityResult>
          )}

          {result &&
            !result.correct &&
            micro?.stage === "while2" &&
            flowPolicy && (
              <Card className="gap-4 border-warning/30 p-5">
                <p className="text-sm font-semibold text-foreground">
                  {t("listening.flow.tryAgainTitle")}
                </p>
                <p className="text-sm text-muted-foreground">
                  {t("listening.flow.tryAgainAttempt")
                    .replace("{current}", String(micro.attemptCount + 1))
                    .replace("{total}", String(flowPolicy.max_attempts_per_stage))}
                </p>
                {micro.transcript === "full" && (
                  <p className="text-sm text-muted-foreground">
                    {t("listening.flow.withTranscript")}
                  </p>
                )}
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    className="min-h-10 gap-2"
                    onClick={retryQuestion}
                  >
                    <RefreshCw className="size-4" aria-hidden="true" />
                    {t("listening.flow.tryAgain")}
                  </Button>
                  {micro.transcript !== "full" &&
                    flowPolicy.allow_manual_reveal && (
                      <Button
                        type="button"
                        variant="outline"
                        className="min-h-10 gap-2"
                        onClick={showTranscriptNow}
                      >
                        {t("listening.flow.showTranscript")}
                      </Button>
                    )}
                </div>
                {/* Salto a la palabra fallada (V3.29, Fase 3, P6): repetir en
                    bucle el fragmento que contiene la palabra diana que el
                    alumno no eligió, en normal o en slow (cadena pedagógica de
                    la auditoría: palabra fallada → replay → slow). */}
                {(failedRefNormal || failedRefSlow) && (
                  <div className="flex flex-wrap items-center gap-2 border-t border-border/60 pt-3">
                    <span className="text-xs font-medium text-muted-foreground">
                      {t("listening.failedWord.repeatLabel")}
                    </span>
                    {failedRefNormal && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="gap-2"
                        onClick={() => void repeatFailedWord("normal")}
                      >
                        <RefreshCw className="size-3.5" aria-hidden="true" />
                        {t("listening.failedWord.repeatNormal")}
                      </Button>
                    )}
                    {failedRefSlow && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="gap-2"
                        onClick={() => void repeatFailedWord("slow")}
                      >
                        <RefreshCw className="size-3.5" aria-hidden="true" />
                        {t("listening.failedWord.repeatSlow")}
                      </Button>
                    )}
                  </div>
                )}
              </Card>
            )}

          {stats && (
            <Card className="relative gap-4 p-5">
              {/* V3.48.1: notas CEFR/honestidad de la ruta al desplegable.
                  V3.75.7: solo notas ⇒ el disparador es una **(i)**, no una «...»:
                  este panel no tiene nada que configurar. Y al abrirse reserva la
                  columna del botón (`pr-12` en `InfoDisclosure`), que si no la
                  primera línea quedaba tapada por el propio botón. */}
              <InfoDisclosure
                variant="corner"
                id="listening-route-notes"
                label={t("common.moreInfo")}
              >
                <p>
                  {t("listening.routeNote").replace("{level}", routeLevel)}
                </p>
                <p>{t("listening.routeCertNote")}</p>
                <p>{t("listening.routeRingHelp")}</p>
              </InfoDisclosure>
              <div className="flex flex-wrap items-center justify-around gap-6">
                <div className="flex flex-col items-center gap-1.5">
                  <ProgressRing
                    value={stats.accuracy ?? 0}
                    size={72}
                    strokeWidth={7}
                    className={ringTone(stats.accuracy)}
                    ariaLabel={`${t("listening.accuracy")}: ${
                      stats.accuracy !== null ? `${stats.accuracy}%` : "—"
                    }`}
                  >
                    <span className="text-lg font-bold tabular-nums text-foreground">
                      {stats.accuracy !== null ? `${stats.accuracy}%` : "—"}
                    </span>
                  </ProgressRing>
                  <span className="text-xs font-medium text-foreground">
                    {t("listening.accuracy")}
                  </span>
                  <span className="text-[11px] tabular-nums text-muted-foreground">
                    {stats.correct} {t("assessment.of")} {stats.attempts}
                  </span>
                </div>

                <div className="flex flex-col items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => toggleLevel(routeLevel)}
                    aria-expanded={expandedLevel === routeLevel}
                    aria-controls="listening-level-items"
                    aria-label={t("listening.levelHistoryTitle").replace(
                      "{level}",
                      routeLevel,
                    )}
                    disabled={!!session}
                    className={cn(
                      "flex flex-col items-center gap-1.5 rounded-lg p-1.5 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                      expandedLevel === routeLevel && "bg-accent",
                      session && "cursor-not-allowed opacity-60",
                    )}
                  >
                    <ProgressRing
                      value={currentLevelPct}
                      size={72}
                      strokeWidth={7}
                      className={cn(levelClass(routeLevel), "lv-ink")}
                      ariaLabel={`${t("listening.currentLevel")}: ${routeLevel}`}
                    >
                      <span className="text-sm font-bold text-foreground">
                        {routeLevel}
                      </span>
                    </ProgressRing>
                    <span className="text-xs font-medium text-foreground">
                      {t("listening.currentLevel")}
                    </span>
                    <span className="text-[11px] tabular-nums text-muted-foreground">
                      {currentLevelStat
                        ? t("listening.masteredOfTotal")
                            .replace(
                              "{mastered}",
                              String(currentLevelStat.mastered),
                            )
                            .replace("{total}", String(currentLevelStat.total))
                        : "—"}
                    </span>
                    {currentLevelStat?.state === "demonstrated" && (
                      <span className="text-[11px] font-semibold text-success">
                        {t("listening.demoTitle").replace(
                          "{level}",
                          routeLevel,
                        )}
                      </span>
                    )}
                    {currentLevelStat?.completed &&
                      currentLevelStat.state === "functional" && (
                        <>
                          <span className="text-[11px] font-semibold text-success">
                            {t("listening.routeCompleted").replace(
                              "{level}",
                              routeLevel,
                            )}
                          </span>
                          <span className="text-[11px] font-medium text-warning">
                            {t("listening.demoNotYet").replace(
                              "{level}",
                              routeLevel,
                            )}
                          </span>
                        </>
                      )}
                    {currentLevelStat?.completed &&
                      currentLevelStat.state !== "demonstrated" &&
                      currentLevelStat.state !== "functional" && (
                        <span className="text-[11px] font-semibold text-success">
                          {t("listening.routeCompleted").replace(
                            "{level}",
                            routeLevel,
                          )}
                        </span>
                      )}
                    {currentLevelStat &&
                      !currentLevelStat.completed &&
                      currentLevelStat.gate &&
                      currentLevelStat.gate.total > 0 &&
                      currentLevelStat.gate.mastered >=
                        currentLevelStat.gate.total && (
                        <span className="text-[11px] font-semibold text-warning">
                          {t("listening.routePendingCert")}
                        </span>
                      )}
                  </button>
                </div>
              </div>

              <div className="flex flex-col gap-3">
                {/* Separador fino entre el resumen (precisión · ruta actual) y
                    el selector de rutas. */}
                <div className="border-t border-border/60" aria-hidden="true" />

                {/* Las seis rutas, dos por fila (A1·A2, B1·B2, C1·C2). La celda
                    es horizontal —anillo + texto— para que quepa en dos columnas
                    hasta en móvil sin empujar nada fuera de pantalla. */}
                <div className="grid grid-cols-2 gap-2">
                  {stats.levels.map((lv) => {
                    const expanded = expandedLevel === lv.level;
                    const isSelected = selectedLevel === lv.level;
                    return (
                      <button
                        key={lv.level}
                        type="button"
                        onClick={() => {
                          setSelectedLevel(lv.level as SelectedRouteLevel);
                          setExpandedLevel(lv.level);
                        }}
                        aria-expanded={expanded}
                        aria-controls="listening-level-items"
                        aria-pressed={isSelected}
                        aria-label={t("listening.levelHistoryTitle").replace(
                          "{level}",
                          lv.level,
                        )}
                        disabled={!!session}
                        className={cn(
                          "flex items-center gap-2.5 rounded-xl border p-2 text-left transition-all hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 sm:p-2.5",
                          levelClass(lv.level),
                          "lv-outline",
                          (expanded || isSelected) && "ring-2 ring-current",
                          session && "cursor-not-allowed opacity-60",
                        )}
                      >
                        <ProgressRing
                          value={lv.total > 0 ? (lv.mastered / lv.total) * 100 : 0}
                          size={40}
                          strokeWidth={4.5}
                          className={cn(levelClass(lv.level), "lv-ink")}
                          ariaLabel={t("listening.masteredOfTotal")
                            .replace("{mastered}", String(lv.mastered))
                            .replace("{total}", String(lv.total))}
                        >
                          {lv.completed ? (
                            <Check className="size-4" aria-hidden="true" />
                          ) : (
                            <span className="text-[10px] font-semibold tabular-nums text-foreground">
                              {lv.mastered}
                            </span>
                          )}
                        </ProgressRing>
                        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                          <span className="truncate text-[11px] font-semibold text-foreground">
                            {t("listening.routeLabel").replace("{level}", lv.level)}
                          </span>
                          <span className="text-[10px] leading-snug tabular-nums text-muted-foreground">
                            {t("listening.masteredOfTotal")
                              .replace("{mastered}", String(lv.mastered))
                              .replace("{total}", String(lv.total))}
                          </span>
                          {lv.total > 0 && (
                            <span className="text-[10px] leading-snug tabular-nums text-muted-foreground">
                              {t("listening.coveragePct").replace(
                                "{pct}",
                                String(
                                  Math.round((lv.mastered / lv.total) * 100),
                                ),
                              )}
                            </span>
                          )}
                          {(lv.extras ?? 0) > 0 && (
                            <span className="text-[9px] leading-snug tabular-nums text-muted-foreground">
                              {t("listening.extraBreakdown")
                                .replace(
                                  "{base}",
                                  String(
                                    lv.base_total ?? lv.total - (lv.extras ?? 0),
                                  ),
                                )
                                .replace("{extras}", String(lv.extras))}
                            </span>
                          )}
                          {!lv.completed &&
                            lv.mastered > 0 &&
                            lv.gate &&
                            lv.gate.coverage_required_pct > 0 && (
                              <span className="text-[9px] leading-snug text-warning">
                                {t("listening.routeGateShort")
                                  .replace(
                                    "{coverage}",
                                    String(lv.gate.coverage_required_pct),
                                  )
                                  .replace(
                                    "{min}",
                                    String(
                                      Math.ceil(
                                        (lv.gate.total *
                                          lv.gate.coverage_required_pct) /
                                          100,
                                      ),
                                    ),
                                  )
                                  .replace("{total}", String(lv.gate.total))}
                              </span>
                            )}
                          {isSelected && (
                            <span className="text-[10px] font-semibold text-primary">
                              {t("learn.routeSelected")}
                            </span>
                          )}
                        </span>
                      </button>
                    );
                  })}
                </div>

                {/* «Auto» devuelve el nivel al motor (V3.48.1). Fila propia a
                    ancho completo: es la opción que **no** elige ruta, así que
                    no compite dentro de la rejilla con las seis rutas. */}
                <button
                  type="button"
                  onClick={() => setSelectedLevel(null)}
                  aria-pressed={selectedLevel === null}
                  aria-label={t("learn.routeAutoHint")}
                  title={t("learn.routeAutoHint")}
                  disabled={!!session}
                  className={cn(
                    "flex w-full items-center justify-center gap-2.5 rounded-xl border px-3 py-2 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                    selectedLevel === null
                      ? "border-primary/50 bg-primary/10 text-primary"
                      : "border-border text-muted-foreground",
                    session && "cursor-not-allowed opacity-60",
                  )}
                >
                  <span
                    className={cn(
                      "grid size-6 place-items-center rounded-full border-2 border-dashed",
                      selectedLevel === null
                        ? "border-primary text-primary"
                        : "border-border text-muted-foreground",
                    )}
                  >
                    <Sparkles className="size-3.5" aria-hidden="true" />
                  </span>
                  <span className="text-xs font-medium">
                    {t("learn.routeAuto")}
                  </span>
                  {selectedLevel === null && (
                    <span className="text-[10px] font-semibold">
                      {t("learn.routeSelected")}
                    </span>
                  )}
                </button>

                {expandedLevel !== null && !session && (
                  <div
                    id="listening-level-items"
                    className="border-t border-border/60 pt-3"
                  >
                    <ListeningLevelPanel
                      userId={userId}
                      level={expandedLevel}
                      routeState={
                        stats.levels.find((lv) => lv.level === expandedLevel)?.state
                      }
                      routeRetention={
                        stats.levels.find((lv) => lv.level === expandedLevel)
                          ?.retention ?? null
                      }
                      onPracticeLevel={startLevelSession}
                      onDrillFailed={startFailedDrill}
                      onReviewLearned={startMasteredSession}
                      onAddExtras={(level, count) =>
                        void startAddPractice(level, count)
                      }
                      extrasJob={extrasJobs[expandedLevel] ?? null}
                      refreshNonce={extrasNonce}
                    />
                  </div>
                )}
              </div>
            </Card>
          )}

          {diagnostic && (
            <>
              <button
                type="button"
                onClick={() => setShowAnalysis((s) => !s)}
                aria-expanded={showAnalysis}
                aria-label={
                  showAnalysis
                    ? t("listening.hideAnalysis")
                    : t("listening.showAnalysis")
                }
                className="flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-card px-5 py-4 text-left shadow-sm"
              >
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="text-sm font-semibold text-foreground">
                    {t("listening.diagnostic")}
                  </span>
                  {diagnosticSummary && (
                    <span className="truncate text-xs text-muted-foreground">
                      {diagnosticSummary}
                    </span>
                  )}
                </span>
                {showAnalysis ? (
                  <ChevronUp
                    className="size-4 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />
                ) : (
                  <ChevronDown
                    className="size-4 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />
                )}
              </button>
              <Card
                className={cn("gap-4 p-5", !showAnalysis && "hidden")}
              >
                <p className="text-sm text-foreground">
                  {diagnostic.recommendation}
                </p>

              {diagnostic.resilience.dimensions.length > 0 && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("listening.resilience")}
                  </p>
                  <ul className="flex flex-wrap gap-2">
                    {diagnostic.resilience.dimensions.map((r) => (
                      <li key={r.dimension}>
                        <Badge
                          variant={
                            r.dimension === diagnostic.resilience.main_weakness
                              ? "default"
                              : "outline"
                          }
                          className="gap-1.5"
                        >
                          {t(resilienceLabel(r.dimension))} ·{" "}
                          {r.accuracy !== null ? `${r.accuracy}%` : "—"}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                  {diagnostic.resilience.recommendation && (
                    <p className="text-sm text-muted-foreground">
                      {diagnostic.resilience.recommendation}
                    </p>
                  )}
                </div>
              )}

              <ul className="flex flex-col gap-1">
                {diagnostic.subskills.map((s) => (
                  <li
                    key={s.skill}
                    className={cn(
                      "text-xs text-muted-foreground",
                      s.review_due && "text-foreground",
                      s.realization_gap && "text-warning",
                    )}
                  >
                    {s.skill} · {s.attempts} ·{" "}
                    {s.accuracy !== null ? `${s.accuracy}%` : "—"}
                    {s.automaticity !== null
                      ? ` · ${t("listening.diagAuto").replace(
                          "{pct}",
                          String(Math.round(s.automaticity * 100)),
                        )}`
                      : ""}
                    {s.mean_score !== null
                      ? ` · ${t("listening.diagMean").replace(
                          "{pct}",
                          String(Math.round(s.mean_score)),
                        )}`
                      : ""}
                    {s.review_due ? ` · ${t("diag.review")}` : ""}
                    {s.realization_gap
                      ? ` · ${t("listening.diagAudioGap")}`
                      : ""}
                  </li>
                ))}
              </ul>

              {diagnostic.trend.direction !== "n/a" && (
                <p className="text-sm text-muted-foreground">
                  {t("diag.trend")}:{" "}
                  <strong
                    className={cn(
                      diagnostic.trend.direction === "up" && "text-success",
                      diagnostic.trend.direction === "down" && "text-destructive",
                      diagnostic.trend.direction === "flat" &&
                        "text-muted-foreground",
                    )}
                  >
                    {t(trendLabel(diagnostic.trend.direction))}
                  </strong>
                  {diagnostic.trend.delta !== null
                    ? ` (${diagnostic.trend.delta > 0 ? "+" : ""}${
                        diagnostic.trend.delta
                      })`
                    : ""}
                </p>
              )}

              {diagnostic.by_topic.length > 0 && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("listening.accuracyByTopic")}
                  </p>
                  <ul className="flex flex-wrap gap-2">
                    {diagnostic.by_topic.map((t) => (
                      <li key={t.topic}>
                        <Badge variant="outline" className="gap-1.5">
                          {topicLabel(t.topic)} ·{" "}
                          {t.accuracy !== null ? `${t.accuracy}%` : "—"}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {diagnostic.by_difficulty.length > 0 && (
                <div className="flex flex-col gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("listening.accuracyByDifficulty")}
                  </p>
                  <ul className="flex flex-wrap gap-2">
                    {diagnostic.by_difficulty.map((d) => (
                      <li key={d.difficulty}>
                        <Badge variant="outline" className="gap-1.5">
                          {t("pron.level")} {d.difficulty} ·{" "}
                          {d.accuracy !== null ? `${d.accuracy}%` : "—"}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {diagnostic.recurrence.questions_seen > 0 && (
                <p className="text-sm text-muted-foreground">
                  {t("listening.retries")}: {diagnostic.recurrence.retried}{" "}
                  {t("assessment.of")} {diagnostic.recurrence.questions_seen} ·{" "}
                  {t("listening.recovered")} {diagnostic.recurrence.recovered}
                </p>
              )}

              <div className="flex flex-col gap-2">
                <p className="text-sm text-muted-foreground">
                  {t("listening.retention")}:{" "}
                  {diagnostic.retention.immediate_accuracy !== null
                    ? `${diagnostic.retention.immediate_accuracy}%`
                    : "—"}{" "}
                  {t("listening.immediate")} →{" "}
                  {diagnostic.retention.delayed_accuracy !== null
                    ? `${diagnostic.retention.delayed_accuracy}%`
                    : "—"}{" "}
                  {t("listening.delayed")}
                  {diagnostic.retention.retention_rate !== null && (
                    <span
                      className={cn(
                        "ml-1 font-medium",
                        diagnostic.retention.retention_rate >= 0.9
                          ? "text-success"
                          : diagnostic.retention.retention_rate >= 0.7
                            ? "text-warning"
                            : "text-destructive",
                      )}
                    >
                      · {t("listening.retention")}{" "}
                      {Math.round(diagnostic.retention.retention_rate * 100)}%
                    </span>
                  )}
                </p>
                {diagnostic.retention.by_bucket.length > 0 && (
                  <ul className="flex flex-wrap gap-2">
                    {diagnostic.retention.by_bucket.map((b) => (
                      <li key={b.bucket}>
                        <Badge variant="outline" className="gap-1.5">
                          {retentionBucketLabel(b.bucket, t)} ·{" "}
                          {b.accuracy !== null ? `${b.accuracy}%` : "—"}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>
            </>
          )}

          {/* El «Saltar» ya no vive aquí: se reubicó en la cabecera de la
              pantalla como «Otro ejercicio» para no competir con las opciones
              (V3.75.4). Al pie sólo queda el aviso de ruta completada. */}
          {stats?.completed && (
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm font-semibold text-success">
                {t("listening.completed")}
              </p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
