import { getJson, postJson, withTimeout } from "./client";
import type {
  DictionaryEntry,
  DictionaryLookupRequest,
  DrillAttempt,
  DrillCandidates,
  DrillSentenceAttempt,
  DrillSentenceContext,
  Lexicon,
} from "../types/api";

/** Léxico personal del alumno (V2.3): resumen + ítems con estado y recall. */
export function getLexicon(userId: string): Promise<Lexicon> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<Lexicon>(`/api/vocabulary/lexicon?${query}`);
}

/** Entrada del diccionario de consulta (V3.30): definición/traducción cacheada
 * (generada por el modelo local) o `definition_source="none"`, frase de ejemplo
 * determinista y marca de uso/aprendizaje de la palabra. Solo lectura (D3): no
 * registra evidencia. `word` puede ser cualquier palabra (esté o no en el
 * léxico del alumno). */
export function lookupDictionaryWord(
  userId: string,
  word: string,
): Promise<DictionaryEntry> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  const body: DictionaryLookupRequest = { word };
  return withTimeout(
    postJson<DictionaryEntry>(`/api/vocabulary/dictionary?${query}`, body),
    // La primera consulta de una palabra paga la generación del modelo local
    // en CPU (el servidor además acota la espera de los waiters del
    // single-flight a 60 s); este tope evita que la tarjeta se quede en
    // "cargando" para siempre si Ollama se cuelga.
    120_000,
    "dictionary lookup",
  );
}

/** Candidatas al speaking micro-drill (V3.19): señal determinista en servidor
 * (expuestas y nunca producidas en speaking), por recuerdo ascendente. */
export function getDrillCandidates(
  userId: string,
  limit = 8,
): Promise<DrillCandidates> {
  const query = new URLSearchParams({
    user_id: userId,
    limit: String(limit),
  }).toString();
  return getJson<DrillCandidates>(`/api/vocabulary/drill/candidates?${query}`);
}

/** Intento de speaking micro-drill: sube el audio de la palabra. Si el alumno
 * la dice (alineada como correcta), el servidor la marca `speaking_prod += 1`
 * y deja de ser candidata. No declara dominio (D5/E3). */
export async function submitDrillAttempt(
  userId: string,
  word: string,
  audio: Blob,
): Promise<DrillAttempt> {
  const form = new FormData();
  form.append("file", audio, "audio.webm");
  form.append("word", word);

  const query = new URLSearchParams({ user_id: userId }).toString();
  const res = await fetch(`/api/vocabulary/drill/attempt?${query}`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as DrillAttempt;
}

/** Contexto del paso Sentence del micro-drill (V3.21/F6.1): frase determinista
 * que contiene la palabra objetivo. El servidor la deriva del banco oficial de
 * read-aloud del nivel (o plantilla simple). */
export function getDrillSentenceContext(
  userId: string,
  word: string,
): Promise<DrillSentenceContext> {
  const query = new URLSearchParams({
    user_id: userId,
    word,
  }).toString();
  return getJson<DrillSentenceContext>(
    `/api/vocabulary/drill/sentence-context?${query}`,
  );
}

/** Intento del paso Sentence del drill (V3.21/F6.1): sube el audio de la frase.
 * Acredita la palabra solo si quedó alineada dentro de una frase superada
 * (`passed`). */
export async function submitDrillSentenceAttempt(
  userId: string,
  word: string,
  audio: Blob,
): Promise<DrillSentenceAttempt> {
  const form = new FormData();
  form.append("file", audio, "audio.webm");
  form.append("word", word);

  const query = new URLSearchParams({ user_id: userId }).toString();
  const res = await fetch(`/api/vocabulary/drill/sentence-attempt?${query}`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as DrillSentenceAttempt;
}
