import { getJson, postJson, withTimeout } from "./client";
import {
  normalizeDictionaryEntry,
  normalizeDrillCandidates,
  normalizeLexicon,
  normalizeRetentionDue,
  normalizeVocabBulkAdd,
  normalizeVocabCollections,
  normalizeVocabEnroll,
  normalizeVocabItemAdd,
} from "./normalize";
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
  RetentionDue,
  RetentionReviewResult,
  VocabBulkAddResult,
  VocabCollection,
  VocabCollections,
  VocabEnrollResult,
  VocabItemAddResult,
} from "../types/api";

/** Léxico personal del alumno (V2.3): resumen + ítems con estado y recall. */
export function getLexicon(__userId: string): Promise<Lexicon> {
  return getJson<unknown>("/api/vocabulary/lexicon").then(normalizeLexicon);
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
  _userId: string,
  word: string,
  direction: DictionaryDirection = "en-es",
): Promise<DictionaryEntry> {
  const body: DictionaryLookupRequest = { word, direction };
  return withTimeout(
    postJson<unknown>("/api/vocabulary/dictionary", body).then(
      normalizeDictionaryEntry,
    ),
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
  _userId: string,
  limit = 8,
): Promise<DrillCandidates> {
  const query = new URLSearchParams({
    limit: String(limit),
  }).toString();
  return getJson<unknown>(
    `/api/vocabulary/drill/candidates?${query}`,
  ).then(normalizeDrillCandidates);
}

/** Intento de speaking micro-drill: sube el audio de la palabra. Si el alumno
 * la dice (alineada como correcta), el servidor la marca `speaking_prod += 1`
 * y deja de ser candidata. No declara dominio (D5/E3). */
export async function submitDrillAttempt(
  _userId: string,
  word: string,
  audio: Blob,
): Promise<DrillAttempt> {
  const form = new FormData();
  form.append("file", audio, "audio.webm");
  form.append("word", word);

  const res = await fetch("/api/vocabulary/drill/attempt", {
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
 * read-aloud del nivel (o plantilla simple).
 *
 * V3.68 (P1-02): `decisionId` declara el servicio del peldaño en el servidor
 * (marca `served` y registra la actividad EJECUTADA). Sin él la petición es
 * idéntica a V3.67. */
export function getDrillSentenceContext(
  _userId: string,
  word: string,
  decisionId?: string,
): Promise<DrillSentenceContext> {
  const params: Record<string, string> = { word };
  if (decisionId) params.decision_id = decisionId;
  const query = new URLSearchParams(params).toString();
  return getJson<DrillSentenceContext>(
    `/api/vocabulary/drill/sentence-context?${query}`,
  );
}

/** Intento del paso Sentence del drill (V3.21/F6.1): sube el audio de la frase.
 * Acredita la palabra solo si quedó alineada dentro de una frase superada
 * (`passed`).
 *
 * V3.68 (P1-02): `decisionId` cierra la decisión con el `outcome` del intento. */
export async function submitDrillSentenceAttempt(
  _userId: string,
  word: string,
  audio: Blob,
  decisionId?: string,
): Promise<DrillSentenceAttempt> {
  const form = new FormData();
  form.append("file", audio, "audio.webm");
  form.append("word", word);
  if (decisionId) form.append("decision_id", decisionId);

  const res = await fetch("/api/vocabulary/drill/sentence-attempt", {
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
 * (rebaraja la posición de la correcta; no es la respuesta).
 *
 * V3.68 (P1-02): `decisionId` declara el servicio del peldaño. */
export function getDrillRecognitionQuestion(
  _userId: string,
  word: string,
  decisionId?: string,
): Promise<DrillRecognitionQuestion> {
  const params: Record<string, string> = { word };
  if (decisionId) params.decision_id = decisionId;
  const query = new URLSearchParams(params).toString();
  return getJson<DrillRecognitionQuestion>(
    `/api/vocabulary/drill/recognition?${query}`,
  );
}

/** Intento del paso Recognition del drill (V3.33): envía la opción elegida y
 * el servidor puntúa recomponiendo la pregunta (nunca se declara acierto en el
 * cliente). V3.33.1: reenvía el `questionId` servido por el GET para reconstruir
 * la misma permutación. Evidencia SOLO informativa: el acierto NO dispara
 * `onProduced`.
 *
 * V3.68 (P1-02): `decisionId` cierra la decisión con el `outcome` del intento. */
export function submitDrillRecognitionAttempt(
  _userId: string,
  word: string,
  selectedIndex: number,
  questionId: string,
  decisionId?: string,
): Promise<DrillRecognitionAttempt> {
  return postJson<DrillRecognitionAttempt>(
    "/api/vocabulary/drill/recognition-attempt",
    {
      word,
      selected_index: selectedIndex,
      question_id: questionId,
      decision_id: decisionId ?? "",
    },
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
 * `cloze`); sin él el servidor conserva la escalera por defecto de V3.34.
 *
 * V3.68 (P1-02): `decisionId` declara el servicio del peldaño. */
export function getDrillRecallPrompt(
  _userId: string,
  word: string,
  cue?: string,
  decisionId?: string,
): Promise<DrillRecallPrompt> {
  const params: Record<string, string> = { word };
  if (cue) params.cue = cue;
  if (decisionId) params.decision_id = decisionId;
  const query = new URLSearchParams(params).toString();
  return getJson<DrillRecallPrompt>(`/api/vocabulary/drill/recall?${query}`);
}

/** Intento del paso Recall del drill (V3.34): envía la palabra tecleada y el
 * servidor la compara con la diana (nunca se declara acierto en el cliente).
 * Un acierto deja señal léxica propia (recall + FSRS) pero NUNCA acredita
 * producción: no dispara `onProduced`.
 * V3.37: `cue` declara el peldaño que el cliente dice que le sirvieron
 * (premisa 21); el servidor lo re-deriva y puntúa igual.
 *
 * V3.68 (P1-02): `decisionId` cierra la decisión con el `outcome` del intento. */
export function submitDrillRecallAttempt(
  _userId: string,
  word: string,
  answer: string,
  responseTimeMs?: number,
  cue?: string,
  decisionId?: string,
): Promise<DrillRecallAttempt> {
  return postJson<DrillRecallAttempt>(
    "/api/vocabulary/drill/recall-attempt",
    {
      word,
      answer,
      cue: cue ?? "",
      response_time_ms: responseTimeMs ?? null,
      decision_id: decisionId ?? "",
    },
  );
}

/** Intento de la actividad de escritura del drill (V3.39, Fase 3): envía la
 * frase PROPIA que usa la palabra objetivo y el servidor la puntúa de forma
 * determinista (unidad alineada + longitud mínima, premisa 21). Un acierto
 * acredita la modalidad `written_production` (cierra el hueco `spoken ✓ /
 * written ✗` del motor de tarea óptima) y dispara `onProduced`; el fallo se
 * registra clasificado y nunca acredita.
 *
 * V3.68 (P1-02): `decisionId` cierra la decisión con el `outcome` del intento. */
export function submitDrillWriteAttempt(
  _userId: string,
  word: string,
  text: string,
  responseTimeMs?: number,
  decisionId?: string,
): Promise<DrillWriteAttempt> {
  return postJson<DrillWriteAttempt>(
    "/api/vocabulary/drill/write-attempt",
    {
      word,
      text,
      response_time_ms: responseTimeMs ?? null,
      decision_id: decisionId ?? "",
    },
  );
}

/** Consigna del paso Transfer del drill (V3.40, Fase 4): contexto NUEVO en el
 * que usar la unidad, elegido por el servidor entre los que el ítem aún no ha
 * usado. Solo lectura: no escribe evidencia. La consigna nunca da la forma
 * esperada (eso sería `sentence`), solo el escenario.
 *
 * V3.68 (P1-01/P1-02): `decisionId` declara el servicio del peldaño. El servidor
 * marca `served` DESPUÉS de resolver el contexto, para poder declarar la
 * INSTANCIA realmente servida (`context_id`/`context_instance`) y completar así
 * la clave de instancia de la decisión. */
export function getDrillTransferContext(
  _userId: string,
  word: string,
  decisionId?: string,
): Promise<DrillTransferContext> {
  const params: Record<string, string> = { word };
  if (decisionId) params.decision_id = decisionId;
  const query = new URLSearchParams(params).toString();
  return getJson<DrillTransferContext>(
    `/api/vocabulary/drill/transfer-context?${query}`,
  );
}

/** Intento del paso Transfer (V3.40, Fase 4): envía la producción propia en el
 * contexto servido. El servidor la puntúa (unidad alineada + longitud mínima) y
 * registra la evidencia como `spontaneous_use` con el `context_id` del contexto
 * nuevo: el éxito en >= 2 contextos distintos demuestra transferencia real. Un
 * acierto dispara `onProduced`; el fallo se registra clasificado.
 *
 * V3.68 (P1-02): `decisionId` cierra la decisión con el `outcome` del intento. */
export function submitDrillTransferAttempt(
  _userId: string,
  word: string,
  text: string,
  contextId: string,
  responseTimeMs?: number,
  // V3.61 (Instance-aware Evidence): slug INMUTABLE de la superficie que el
  // alumno respondió (`DrillTransferContext.context_instance`). El servidor
  // persiste la dificultad de ESA superficie y no la de la siguiente rotación.
  // Opcional: sin él el servidor degrada a la rotación de V3.60.
  contextInstance?: string,
  decisionId?: string,
): Promise<DrillTransferAttempt> {
  return postJson<DrillTransferAttempt>(
    "/api/vocabulary/drill/transfer-attempt",
    {
      word,
      text,
      context_id: contextId,
      context_instance: contextInstance ?? "",
      response_time_ms: responseTimeMs ?? null,
      decision_id: decisionId ?? "",
    },
  );
}

/** Evento del ciclo de vida de una decisión servida (V3.68, P1-02).
 *
 * Cubre los DOS estados que ningún POST de intento puede observar: el alumno
 * ABRE el peldaño (`started`) y lo ABANDONA sin completarlo (`abandoned`). La
 * FSM del servidor decide si la transición es válida: `applied=false` es la
 * respuesta normal de un evento que llega tarde (la decisión ya está
 * `completed`) y NUNCA es un error — el drill no puede romperse por telemetría
 * del ciclo de vida. */
export async function markDrillDecisionEvent(
  _userId: string,
  decisionId: string,
  event: "started" | "abandoned",
  options: { targetId?: string; activity?: string } = {},
): Promise<boolean> {
  if (!decisionId) return false;
  try {
    const out = await postJson<{ applied?: boolean }>(
      "/api/vocabulary/drill/decision-lifecycle",
      {
        decision_id: decisionId,
        event,
        target_id: options.targetId ?? "",
        activity: options.activity ?? "",
      },
    );
    return Boolean(out?.applied);
  } catch {
    // Best-effort declarado: un fallo de red no rompe el drill.
    return false;
  }
}

/** El alumno abrió el peldaño (V3.68, P1-02): `served → started`. */
export function markDrillStarted(
  _userId: string,
  decisionId: string,
  options: { targetId?: string; activity?: string } = {},
): Promise<boolean> {
  return markDrillDecisionEvent(_userId, decisionId, "started", options);
}

/** El alumno salió del peldaño sin completarlo (V3.68, P1-02):
 * `served|started → abandoned`. El servidor RECHAZA el abandono si la decisión
 * ya está `completed` (la terminalidad la decide la FSM, no el cliente), de modo
 * que un cierre tardío nunca borra una medición. */
export function markDrillAbandoned(
  _userId: string,
  decisionId: string,
  options: { targetId?: string; activity?: string } = {},
): Promise<boolean> {
  return markDrillDecisionEvent(_userId, decisionId, "abandoned", options);
}

/** Añade una palabra suelta al léxico personal + carta FSRS (sin mastery). */
export function addVocabularyItem(
  _userId: string,
  word: string,
  options: { translation?: string; collectionId?: number } = {},
): Promise<VocabItemAddResult> {
  return postJson<unknown>("/api/vocabulary/items", {
    word,
    translation: options.translation ?? "",
    collection_id: options.collectionId ?? null,
  }).then(normalizeVocabItemAdd);
}

/** Pega una lista de palabras (una por línea; opcional word,translation). */
export function addVocabularyBulk(
  _userId: string,
  text: string,
  options: { title?: string; collectionId?: number } = {},
): Promise<VocabBulkAddResult> {
  return postJson<unknown>("/api/vocabulary/items/bulk", {
    text,
    title: options.title ?? "",
    collection_id: options.collectionId ?? null,
  }).then(normalizeVocabBulkAdd);
}

export function listVocabCollections(
  _userId: string,
): Promise<VocabCollections> {
  return getJson<unknown>("/api/vocabulary/collections").then(
    normalizeVocabCollections,
  );
}

export function createVocabCollection(
  _userId: string,
  title: string,
): Promise<VocabCollection> {
  return postJson<VocabCollection>("/api/vocabulary/collections", { title });
}

export function enrollVocabCollection(
  _userId: string,
  collectionId: number,
): Promise<VocabEnrollResult> {
  return postJson<unknown>(
    `/api/vocabulary/collections/${collectionId}/enroll`,
    {},
  ).then(normalizeVocabEnroll);
}

/** Cola due de retención (sesión tarjetas estilo Anki). */
export function getRetentionDue(
  _userId: string,
  options: { limit?: number; collectionId?: number } = {},
): Promise<RetentionDue> {
  const params = new URLSearchParams();
  if (options.limit != null) params.set("limit", String(options.limit));
  if (options.collectionId != null) {
    params.set("collection_id", String(options.collectionId));
  }
  const q = params.toString();
  return getJson<unknown>(
    `/api/vocabulary/retention/due${q ? `?${q}` : ""}`,
  ).then(normalizeRetentionDue);
}

/** Grade 1–4 (Again/Hard/Good/Easy) → reprograma FSRS lexicon. */
export function reviewRetentionCard(
  _userId: string,
  word: string,
  grade: number,
): Promise<RetentionReviewResult> {
  return postJson<RetentionReviewResult>("/api/vocabulary/retention/review", {
    word,
    grade,
  });
}
