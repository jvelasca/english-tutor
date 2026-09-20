import { useCallback, useEffect, useMemo, useSyncExternalStore } from "react";
import { getSettings, saveSettings } from "../api/settings";
import { getVoices } from "../api/voices";
import type { VoiceInfo } from "../types/api";
import {
  replayScope,
  suggestAltVoice,
  voiceDisplayName,
  voiceLanguage,
  type ReplayScope,
} from "../utils/voices";

/**
 * Voz A, voz B y lectura de la repetición (V3.75.5 / V3.75.6): estado compartido
 * de toda la app.
 *
 * El alumno pidió oír el mismo ítem con **dos acentos** (p. ej. una voz de
 * Inglaterra y otra de EE. UU.). Eso convierte a la voz en una preferencia con
 * dos valores (`tts_voice` y `tts_voice_alt`), y a la vez en algo que muchos
 * componentes distintos necesitan a la vez (la tarjeta de audio, el «...» de la
 * tarjeta, el altavoz de después de responder, los escenarios de las rutas de
 * quiz). Por eso vive en un **store de módulo** y no en un contexto React: igual
 * que `useVoiceDownload`, así hay **una sola** lectura de catálogo y ajustes para
 * toda la app aunque haya varios altavoces en pantalla.
 *
 * V3.75.6 añade `replay_scope` («todo el ítem» o «solo la respuesta correcta») al
 * mismo store porque lo elige el mismo «...» y lo consume el mismo altavoz: dos
 * lecturas de ajustes para la misma preferencia serían dos verdades distintas.
 *
 * Reglas del contrato:
 * - **Voz A** = `tts_voice` (el perfil, ya existente). **Voz B** = `tts_voice_alt`.
 * - Si no hay B guardada (o apunta a una voz que ya no está instalada), se
 *   **sugiere** la mejor candidata del mismo idioma y distinta locale
 *   (`suggestAltVoice`), de modo que «dos acentos» funciona recién instalada la
 *   app sin obligar a configurar nada.
 * - `savedAlt` distingue la B elegida por el alumno de la sugerida.
 * - Si el catálogo no responde, el store queda en `error` y **nadie** deja de
 *   reproducir audio: sin voz resuelta se llama a `speak()` sin `voice` y manda
 *   el perfil (fail-open, como el resto de la capa de voz).
 */

export type VoiceAccent = "a" | "b";

export interface VoiceChoiceState {
  status: "idle" | "loading" | "ready" | "error";
  /** Voz A: la preferida del perfil (`tts_voice`); `""` si aún no se sabe. */
  primary: string;
  /** Voz B efectiva (elegida o sugerida); `""` si solo hay una voz instalada. */
  alt: string;
  /** Voz B **elegida** por el alumno; `""` cuando la B es solo una sugerencia. */
  savedAlt: string;
  /** Voces instaladas del idioma de la voz A (las que el selector ofrece). */
  voices: VoiceInfo[];
  /** Qué lee el altavoz de repetición (`replay_scope`); `"item"` por defecto. */
  replayScope: ReplayScope;
}

const INITIAL: VoiceChoiceState = {
  status: "idle",
  primary: "",
  alt: "",
  savedAlt: "",
  voices: [],
  replayScope: "item",
};

let state: VoiceChoiceState = INITIAL;
let loadedFor: string | null | undefined;
let inFlight: Promise<void> | null = null;
let inFlightFor: string | null | undefined;
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Estado actual sin suscribirse (para resolver una voz en un `onClick`). */
export function getVoiceChoice(): VoiceChoiceState {
  return state;
}

/** Voz de un acento en el estado actual; `""` si todavía no se ha resuelto. */
export function accentVoice(accent: VoiceAccent): string {
  return accent === "b" ? state.alt : state.primary;
}

/** Nombre legible de una voz del catálogo cargado (o el propio id). */
export function voiceChoiceLabel(voiceId: string): string {
  return labelFrom(state.voices, voiceId);
}

function labelFrom(voices: VoiceInfo[], voiceId: string): string {
  const voice = voices.find((item) => item.id === voiceId);
  return voice ? voiceDisplayName(voice) : voiceId;
}

/** Empareja `primary`/`alt` con el catálogo y la preferencia guardada. */
function pairFrom(
  voices: VoiceInfo[],
  primary: string,
  savedAlt: string,
): Pick<VoiceChoiceState, "primary" | "alt" | "savedAlt"> {
  const ids = voices.map((voice) => voice.id);
  const chosen = ids.includes(savedAlt) && savedAlt !== primary ? savedAlt : "";
  const alt = chosen || suggestAltVoice(ids, primary) || "";
  return { primary, alt, savedAlt: alt === chosen ? chosen : "" };
}

async function fetchChoice(userId: string | null): Promise<void> {
  const [catalog, settings] = await Promise.all([
    getVoices(userId),
    userId
      ? getSettings(userId)
          // Los ajustes caídos no impiden tener voz B: se sugiere y ya está.
          .catch(() => ({ settings: {} as Record<string, string> }))
      : Promise.resolve({ settings: {} as Record<string, string> }),
  ]);
  const installed = catalog?.voices ?? [];
  const primary = catalog?.selected || catalog?.default || installed[0]?.id || "";
  const language = voiceLanguage(primary);
  // Solo se ofrecen voces del mismo idioma que la voz A: mezclar idiomas en el
  // selector de acentos haría que la B leyera el ítem en otro idioma.
  const voices = installed.filter(
    (voice) => !language || voiceLanguage(voice.id) === language,
  );
  state = {
    status: "ready",
    ...pairFrom(voices, primary, settings?.settings?.tts_voice_alt ?? ""),
    voices,
    // Una preferencia ausente o desconocida cae a `"item"` (el defecto nuevo); el
    // valor histórico `"all"` —la única lectura que existió— se conserva como
    // `"withOptions"`, que es exactamente lo que ese perfil había elegido.
    replayScope: replayScope(settings?.settings?.replay_scope),
  };
  emit();
}

/**
 * Carga (una sola vez por perfil) el catálogo y la pareja de voces. Idempotente
 * y a prueba de carreras: varias llamadas simultáneas comparten la misma
 * promesa. Nunca lanza: un fallo deja el estado en `error` y la app sigue
 * reproduciendo con la voz del perfil.
 */
export function ensureVoiceChoice(userId: string | null): Promise<void> {
  if (loadedFor === userId && state.status === "ready") return Promise.resolve();
  if (inFlight && inFlightFor === userId) return inFlight;
  // Cambio de perfil: el catálogo, la voz A y la B son de cada alumno, así que no
  // se reutiliza nada del anterior (nunca se muestra ni se usa la voz de otro).
  if (loadedFor !== undefined && loadedFor !== userId) {
    state = { ...INITIAL, status: "loading" };
  }
  loadedFor = userId;
  inFlightFor = userId;
  state = state.status === "ready" ? state : { ...state, status: "loading" };
  emit();
  let task: Promise<void>;
  task = fetchChoice(userId)
    .catch(() => {
      // Si ya había datos buenos se conservan (un fallo puntual no vacía la UI).
      state = state.status === "ready" ? state : { ...state, status: "error" };
      emit();
    })
    .finally(() => {
      if (inFlight === task) {
        inFlight = null;
        inFlightFor = undefined;
      }
    });
  inFlight = task;
  return task;
}

/** Guarda la voz A del perfil y reajusta la B si ya no tiene sentido. */
export async function setPrimaryVoice(
  userId: string | null,
  voiceId: string,
): Promise<void> {
  const ids = state.voices.map((voice) => voice.id);
  if (ids.length > 0 && !ids.includes(voiceId)) return;
  if (ids.length === 0) {
    // El catálogo aún no está cargado (Ajustes → Voces sin pasar por el store):
    // se guarda la preferencia igual y se olvida lo cacheado para releerlo.
    state = { ...state, primary: voiceId };
    loadedFor = undefined;
    emit();
    if (userId) {
      await saveSettings(userId, { tts_voice: voiceId }).catch(() => undefined);
    }
    return;
  }
  const chosen = state.savedAlt;
  const next = pairFrom(state.voices, voiceId, chosen);
  // La B elegida deja de servir (era la nueva A o ya no está): se limpia la clave
  // para que la próxima B vuelva a ser una sugerencia honesta.
  const clearingStale = chosen !== "" && next.savedAlt === "";
  state = { ...state, ...next };
  emit();
  if (!userId) return;
  const payload: Record<string, string> = { tts_voice: voiceId };
  if (clearingStale) payload.tts_voice_alt = "";
  await saveSettings(userId, payload).catch(() => undefined);
}

/** Guarda la voz B (segundo acento) del perfil. */
export async function setAltVoice(
  userId: string | null,
  voiceId: string,
): Promise<void> {
  const ids = state.voices.map((voice) => voice.id);
  if (ids.length > 0 && !ids.includes(voiceId)) return;
  if (voiceId === state.primary) return;
  state = { ...state, alt: voiceId, savedAlt: voiceId };
  emit();
  if (!userId) return;
  await saveSettings(userId, { tts_voice_alt: voiceId }).catch(() => undefined);
}

/**
 * Guarda qué lee el altavoz de repetición (`replay_scope`, V3.75.6).
 *
 * El estado se actualiza **siempre** (la UI responde al instante); la escritura
 * en el perfil es best-effort, como el resto de preferencias: un backend caído no
 * puede impedir elegir cómo se repite el ítem en esta sesión.
 */
export async function setReplayScope(
  userId: string | null,
  scope: ReplayScope,
): Promise<void> {
  if (scope === state.replayScope) return;
  state = { ...state, replayScope: scope };
  emit();
  if (!userId) return;
  await saveSettings(userId, { replay_scope: scope }).catch(() => undefined);
}

/** Vuelve al estado inicial (cierre de sesión, tests). */
export function resetVoiceChoice(): void {
  state = INITIAL;
  loadedFor = undefined;
  inFlight = null;
  inFlightFor = undefined;
  emit();
}

/**
 * Fuerza una relectura del catálogo y de la pareja A/B (V3.75.5). Se usa cuando
 * la voz se cambia **fuera** del store (Configuración → Voces escribe `tts_voice`
 * con su propia llamada) o cuando se acaba de instalar una voz: sin esto la voz A
 * quedaría desincronizada y la B sugerida seguiría calculada sobre el catálogo
 * viejo. Si ya hay una lectura en curso se espera y se repite después.
 */
export function refreshVoiceChoice(userId: string | null): Promise<void> {
  loadedFor = undefined;
  const pending = inFlight && inFlightFor === userId ? inFlight : null;
  if (!pending) return ensureVoiceChoice(userId);
  return pending.then(() => ensureVoiceChoice(userId));
}

export interface UseVoiceChoiceResult extends VoiceChoiceState {
  /** Voz de un acento (`"a"` = perfil, `"b"` = segundo acento); `""` si no hay. */
  voiceFor: (accent: VoiceAccent) => string;
  /** Nombre legible de una voz del catálogo cargado. */
  labelOf: (voiceId: string) => string;
  setPrimary: (voiceId: string) => Promise<void>;
  setAlt: (voiceId: string) => Promise<void>;
  /** Cambia qué lee el altavoz de repetición y lo guarda en el perfil. */
  setReplayScope: (scope: ReplayScope) => Promise<void>;
}

/**
 * Lector React del store: carga la pareja de voces al montar y devuelve el
 * estado vivo. Pensado para los componentes que **muestran o cambian** la voz
 * (selector y altavoz de repetición); un `ListenButton` sin acento no lo usa, así
 * que su comportamiento y sus tests siguen intactos.
 */
export function useVoiceChoice(userId: string | null): UseVoiceChoiceResult {
  const snapshot = useSyncExternalStore(
    subscribe,
    getVoiceChoice,
    () => INITIAL,
  );
  useEffect(() => {
    void ensureVoiceChoice(userId);
  }, [userId]);
  const setPrimary = useCallback(
    (voiceId: string) => setPrimaryVoice(userId, voiceId),
    [userId],
  );
  const setAlt = useCallback(
    (voiceId: string) => setAltVoice(userId, voiceId),
    [userId],
  );
  const setScope = useCallback(
    (scope: ReplayScope) => setReplayScope(userId, scope),
    [userId],
  );
  return useMemo(
    () => ({
      ...snapshot,
      voiceFor: (accent: VoiceAccent) =>
        accent === "b" ? snapshot.alt : snapshot.primary,
      labelOf: (voiceId: string) => labelFrom(snapshot.voices, voiceId),
      setPrimary,
      setAlt,
      setReplayScope: setScope,
    }),
    [snapshot, setPrimary, setAlt, setScope],
  );
}
