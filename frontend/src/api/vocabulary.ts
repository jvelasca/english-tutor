import { getJson, postJson, withTimeout } from "./client";
import type {
  DictionaryDirection,
  DictionaryEntry,
  DictionaryLookupRequest,
  DrillAttempt,
  DrillCandidates,
  DrillRecallAttempt,
  DrillRecallPrompt,
  DrillRecognitionAttempt,
  DrillRecognitionQuestion,
  DrillSentenceAttempt,
  DrillSentenceContext,
  DrillTransferAttempt,
  DrillTransferContext,
  DrillWriteAttempt,
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
 * léxico del alumno).
 *
 * V3.39: `direction` (`en-es` por defecto) permite la búsqueda inversa ES→EN,
 * en la que `word` es el término español y `translation` el equivalente inglés. */
export function lookupDictionaryWord(
  userId: string,
  word: string,
  direction: DictionaryDirection = "en-es",
): Promise<DictionaryEntry> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  const body: DictionaryLookupRequest = { word, direction };
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

/** Pregunta del paso Recognition del drill (V3.33, eslabón 2 del puente).

 * MCQ definición ↔ palabra determinista por (palabra, question_id) (premisa
 * 21): la correcta nunca viaja en el GET. `available=false` con `options=[]` es
 * la degradación controlada cuando la palabra aún no tiene significado cacheado
 * o no hay distractores: el peldaño muestra aviso y no rompe la escalera.
 * V3.33.1: `question_id` es un nonce por intento que hay que reenviar en el POST
 * (rebaraja la posición de la correcta; no es la respuesta). */
export function getDrillRecognitionQuestion(
  userId: string,
  word: string,
): Promise<DrillRecognitionQuestion> {
  const query = new URLSearchParams({
    user_id: userId,
    word,
  }).toString();
  return getJson<DrillRecognitionQuestion>(
    `/api/vocabulary/drill/recognition?${query}`,
  );
}

/** Intento del paso Recognition del drill (V3.33): envía la opción elegida y
 * el servidor puntúa recomponiendo la pregunta (nunca se declara acierto en el
 * cliente). V3.33.1: reenvía el `questionId` servido por el GET para reconstruir
 * la misma permutación. Evidencia SOLO informativa: el acierto NO dispara
 * `onProduced`. */
export function submitDrillRecognitionAttempt(
  userId: string,
  word: string,
  selectedIndex: number,
  questionId: string,
): Promise<DrillRecognitionAttempt> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return postJson<DrillRecognitionAttempt>(
    `/api/vocabulary/drill/recognition-attempt?${query}`,
    { word, selected_index: selectedIndex, question_id: questionId },
  );
}

/** Cue del paso Recall del drill (V3.34, Recall 2.0; peldaños graduados V3.37).
 *
 * Camino inverso a Recognition: el alumno ve el SIGNIFICADO (traducción,
 * definición o frase en blanco) y debe teclear la palabra. Puro y determinista
 * en el servidor (premisa 21): el GET nunca incluye la palabra esperada.
 * `available=false` con `cue=""` es la degradación controlada (palabra sin
 * entrada, cue circular o peldaño sin contenido): el peldaño muestra aviso y no
 * rompe Sentence. `cue` pide un peldaño concreto (`translation`/`definition`/
 * `cloze`); sin él el servidor conserva la escalera por defecto de V3.34. */
export function getDrillRecallPrompt(
  userId: string,
  word: string,
  cue?: string,
): Promise<DrillRecallPrompt> {
  const params: Record<string, string> = { user_id: userId, word };
  if (cue) params.cue = cue;
  const query = new URLSearchParams(params).toString();
  return getJson<DrillRecallPrompt>(`/api/vocabulary/drill/recall?${query}`);
}

/** Intento del paso Recall del drill (V3.34): envía la palabra tecleada y el
 * servidor la compara con la diana (nunca se declara acierto en el cliente).
 * Un acierto deja señal léxica propia (recall + FSRS) pero NUNCA acredita
 * producción: no dispara `onProduced`.
 * V3.37: `cue` declara el peldaño que el cliente dice que le sirvieron
 * (premisa 21); el servidor lo re-deriva y puntúa igual. */
export function submitDrillRecallAttempt(
  userId: string,
  word: string,
  answer: string,
  responseTimeMs?: number,
  cue?: string,
): Promise<DrillRecallAttempt> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return postJson<DrillRecallAttempt>(
    `/api/vocabulary/drill/recall-attempt?${query}`,
    { word, answer, cue: cue ?? "", response_time_ms: responseTimeMs ?? null },
  );
}

/** Intento de la actividad de escritura del drill (V3.39, Fase 3): envía la
 * frase PROPIA que usa la palabra objetivo y el servidor la puntúa de forma
 * determinista (unidad alineada + longitud mínima, premisa 21). Un acierto
 * acredita la modalidad `written_production` (cierra el hueco `spoken ✓ /
 * written ✗` del motor de tarea óptima) y dispara `onProduced`; el fallo se
 * registra clasificado y nunca acredita. */
export function submitDrillWriteAttempt(
  userId: string,
  word: string,
  text: string,
  responseTimeMs?: number,
): Promise<DrillWriteAttempt> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return postJson<DrillWriteAttempt>(
    `/api/vocabulary/drill/write-attempt?${query}`,
    { word, text, response_time_ms: responseTimeMs ?? null },
  );
}

/** Consigna del paso Transfer del drill (V3.40, Fase 4): contexto NUEVO en el
 * que usar la unidad, elegido por el servidor entre los que el ítem aún no ha
 * usado. Solo lectura: no escribe evidencia. La consigna nunca da la forma
 * esperada (eso sería `sentence`), solo el escenario. */
export function getDrillTransferContext(
  userId: string,
  word: string,
): Promise<DrillTransferContext> {
  const query = new URLSearchParams({ user_id: userId, word }).toString();
  return getJson<DrillTransferContext>(
    `/api/vocabulary/drill/transfer-context?${query}`,
  );
}

/** Intento del paso Transfer (V3.40, Fase 4): envía la producción propia en el
 * contexto servido. El servidor la puntúa (unidad alineada + longitud mínima) y
 * registra la evidencia como `spontaneous_use` con el `context_id` del contexto
 * nuevo: el éxito en >= 2 contextos distintos demuestra transferencia real. Un
 * acierto dispara `onProduced`; el fallo se registra clasificado. */
export function submitDrillTransferAttempt(
  userId: string,
  word: string,
  text: string,
  contextId: string,
  responseTimeMs?: number,
): Promise<DrillTransferAttempt> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return postJson<DrillTransferAttempt>(
    `/api/vocabulary/drill/transfer-attempt?${query}`,
    {
      word,
      text,
      context_id: contextId,
      response_time_ms: responseTimeMs ?? null,
    },
  );
}
