/**
 * Normalización de contratos HTTP en runtime (V3.77.2).
 *
 * Lección de V3.77.0/V3.77.1: el frontend **no puede** asumir que un JSON HTTP
 * tiene exactamente la forma que declara su tipo. `as Lexicon` no valida nada en
 * runtime, así que un campo ausente llega al estado de React y revienta al
 * pintar (`undefined.map`, spread de `undefined`…). Y, sin `ErrorBoundary`, ese
 * throw desmontaba la app entera.
 *
 * La tubería correcta es:
 *
 *   HTTP → api client → normalización runtime → objeto de dominio → React
 *
 * Estas funciones hacen cumplir la forma en la **frontera** (el cliente de API),
 * de modo que el estado de React nunca recibe `undefined` donde el tipo promete
 * un array o un objeto. No "adivinan" datos: si algo falta, aplican el valor
 * neutro (array vacío, 0, "") y descartan los elementos que ni son objetos. El
 * contrato se degrada a un estado vacío honesto, nunca a un crash.
 *
 * Los campos desconocidos se conservan (`...raw`) para no romper el contrato
 * aditivo del backend conforme crece.
 */
import type {
  CefrBucket,
  DictionaryEntry,
  DictionaryExample,
  DictionaryMeaning,
  DictionarySurfaceUsage,
  DictionaryUnitUsage,
  DrillCandidates,
  FlashcardCard,
  FlashcardCardType,
  FlashcardCards,
  FlashcardDayCount,
  FlashcardDeck,
  FlashcardDeckDeleteResult,
  FlashcardDecks,
  FlashcardLimits,
  FlashcardQueue,
  FlashcardStats,
  FlashcardStudyItem,
  LexicalItem,
  LexicalStatus,
  Lexicon,
  RetentionCard,
  RetentionDue,
  ReviewActivity,
  ReviewQueue,
  ReviewQueueItem,
  VocabBulkAddResult,
  VocabCollection,
  VocabCollections,
  VocabEnrollResult,
  VocabItemAddResult,
} from "../types/api";

type Raw = Record<string, unknown>;

export function isRecord(value: unknown): value is Raw {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Array garantizado: lo que no sea array se convierte en `[]`. */
export function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

/** Array de objetos: descarta los elementos que no son registros. */
function asRecordArray(value: unknown): Raw[] {
  return asArray<unknown>(value).filter(isRecord);
}

export function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

/** `string | null`: conserva el null (distinto de "ausente" en varios contratos). */
export function asNullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

/** `string[]` garantizado: descarta elementos no-cadena. */
export function asStringArray(value: unknown): string[] {
  return asArray<unknown>(value).filter(
    (item): item is string => typeof item === "string",
  );
}

function asRecordOrNull(value: unknown): Raw | null {
  return isRecord(value) ? value : null;
}

const LEXICAL_STATUSES: readonly LexicalStatus[] = [
  "mastered",
  "known",
  "learning",
  "weak",
];

function asLexicalStatus(value: unknown): LexicalStatus {
  return LEXICAL_STATUSES.includes(value as LexicalStatus)
    ? (value as LexicalStatus)
    : "learning";
}

const REVIEW_ACTIVITIES: readonly ReviewActivity[] = [
  "recognition",
  "recall",
  "sentence",
  "write",
  "transfer",
];

function asReviewActivity(value: unknown): ReviewActivity {
  return REVIEW_ACTIVITIES.includes(value as ReviewActivity)
    ? (value as ReviewActivity)
    : "recognition";
}

// --- Léxico personal -------------------------------------------------------

function normalizeLexicalItem(raw: Raw): LexicalItem {
  const out = {
    ...(raw as unknown as LexicalItem),
    word: asString(raw.word),
    lemma: asString(raw.lemma),
    cefr: asString(raw.cefr),
    kind: asString(raw.kind, "word"),
    source: asString(raw.source),
    status: asLexicalStatus(raw.status),
    recall: asNumber(raw.recall),
    next_review_days: asNumber(raw.next_review_days),
    production_count: asNumber(raw.production_count),
    exposure_count: asNumber(raw.exposure_count),
    chat_prod: asNumber(raw.chat_prod),
    speaking_prod: asNumber(raw.speaking_prod),
    writing_prod: asNumber(raw.writing_prod),
    conversation_prod: asNumber(raw.conversation_prod),
  };
  // Los campos opcionales solo se tocan si vienen: así no se convierte
  // «ausente» en `undefined`/`null` y el contrato aditivo se conserva.
  if ("lexical_unit" in raw) out.lexical_unit = asString(raw.lexical_unit);
  if ("competence" in raw) {
    out.competence = asRecordOrNull(raw.competence) as LexicalItem["competence"];
  }
  // V3.78.0: la fuerza de memoria solo se toca si viene. Si el backend no la
  // manda (contrato viejo) la fila sale sin ella y PERSONAL pinta «sin
  // estudiar», que es la lectura honesta de «no consta».
  if ("memory" in raw) {
    const memory = asRecordOrNull(raw.memory);
    out.memory = memory
      ? {
          ...(memory as unknown as LexicalItem["memory"]),
          state: asString(memory.state, "new"),
          due_at: asString(memory.due_at),
          due: asBoolean(memory.due),
          reps: asNumber(memory.reps),
          stability: asNumber(memory.stability),
          retrievability: asNumber(memory.retrievability),
          next_in_days: asNumber(memory.next_in_days),
        }
      : null;
  }
  // V3.80.0: la traducción propia solo se toca si viene, por el mismo motivo
  // que `memory`: un contrato viejo no debe inventar un reverso que el alumno
  // no escribió.
  if ("translation" in raw) out.translation = asString(raw.translation);
  return out;
}

function normalizeCefrBucket(raw: Raw): CefrBucket {
  return { cefr: asString(raw.cefr), count: asNumber(raw.count) };
}

/** `GET /api/vocabulary/lexicon`: `summary` e `items` siempre presentes. */
export function normalizeLexicon(raw: unknown): Lexicon {
  const data = isRecord(raw) ? raw : {};
  const summary = asRecordOrNull(data.summary) ?? {};
  const out = {
    ...(data as unknown as Lexicon),
    summary: {
      ...(summary as unknown as Lexicon["summary"]),
      total: asNumber(summary.total),
      known: asNumber(summary.known),
      learning: asNumber(summary.learning),
      weak: asNumber(summary.weak),
      mastered: asNumber(summary.mastered),
      by_cefr: asRecordArray(summary.by_cefr).map(normalizeCefrBucket),
      recognized: asNumber(summary.recognized),
      produced: asNumber(summary.produced),
      transfer: asNumber(summary.transfer),
      retention: asNumber(summary.retention),
      spaced_exposure: asNumber(summary.spaced_exposure),
      production_gap: asNumber(summary.production_gap),
      transfer_gap: asNumber(summary.transfer_gap),
    },
    items: asRecordArray(data.items).map(normalizeLexicalItem),
  };
  if ("coverage" in data) {
    out.coverage = asRecordOrNull(data.coverage) as Lexicon["coverage"];
  }
  return out;
}

/** `GET /api/vocabulary/drill/candidates`: `words` siempre es un array de cadenas. */
export function normalizeDrillCandidates(raw: unknown): DrillCandidates {
  const data = isRecord(raw) ? raw : {};
  return { ...(data as unknown as DrillCandidates), words: asStringArray(data.words) };
}

// --- Colecciones léxicas ---------------------------------------------------

function normalizeVocabCollection(raw: Raw): VocabCollection {
  return {
    ...(raw as unknown as VocabCollection),
    id: asNumber(raw.id),
    kind: asString(raw.kind),
    slug: asString(raw.slug),
    title: asString(raw.title),
    title_es: asString(raw.title_es),
    cefr_hint: asString(raw.cefr_hint),
    item_count: asNumber(raw.item_count),
    enrolled: asBoolean(raw.enrolled),
    is_global: asBoolean(raw.is_global),
  };
}

/** `GET /api/vocabulary/collections`: el fallo de V3.77.0 nace aquí. */
export function normalizeVocabCollections(raw: unknown): VocabCollections {
  const data = isRecord(raw) ? raw : {};
  return { collections: asRecordArray(data.collections).map(normalizeVocabCollection) };
}

/** `POST /api/vocabulary/items`: `added` siempre array. */
export function normalizeVocabItemAdd(raw: unknown): VocabItemAddResult {
  const data = isRecord(raw) ? raw : {};
  const item = asRecordOrNull(data.item);
  return {
    ...(data as unknown as VocabItemAddResult),
    added: asStringArray(data.added),
    item: {
      word: asString(item?.word),
      translation: asString(item?.translation),
      definition: asString(item?.definition),
    },
  };
}

/** `POST /api/vocabulary/items/bulk`. */
export function normalizeVocabBulkAdd(raw: unknown): VocabBulkAddResult {
  const data = isRecord(raw) ? raw : {};
  return {
    ...(data as unknown as VocabBulkAddResult),
    added: asStringArray(data.added),
    count: asNumber(data.count),
  };
}

/** `POST /api/vocabulary/collections/{id}/enroll`. */
export function normalizeVocabEnroll(raw: unknown): VocabEnrollResult {
  const data = isRecord(raw) ? raw : {};
  return {
    ...(data as unknown as VocabEnrollResult),
    added: asStringArray(data.added),
    count: asNumber(data.count),
  };
}

// --- Retención -------------------------------------------------------------

function normalizeRetentionCard(raw: Raw): RetentionCard {
  return {
    ...(raw as unknown as RetentionCard),
    word: asString(raw.word),
    translation: asString(raw.translation),
    definition: asString(raw.definition),
    due_at: asString(raw.due_at),
    stability: asNumber(raw.stability),
    retrievability: asNumber(raw.retrievability),
    why: asString(raw.why),
    reps: asNumber(raw.reps),
  };
}

/** `GET /api/vocabulary/retention/due`: `items` siempre array. */
export function normalizeRetentionDue(raw: unknown): RetentionDue {
  const data = isRecord(raw) ? raw : {};
  return {
    ...(data as unknown as RetentionDue),
    due_count: asNumber(data.due_count),
    limit: asNumber(data.limit),
    items: asRecordArray(data.items).map(normalizeRetentionCard),
    fsrs_version: asString(data.fsrs_version),
  };
}

// --- V3.78.0: modo Flashcards ----------------------------------------------

const CARD_TYPES: readonly FlashcardCardType[] = ["lexicon", "flashcard"];

function asCardType(value: unknown): FlashcardCardType {
  return CARD_TYPES.includes(value as FlashcardCardType)
    ? (value as FlashcardCardType)
    : "lexicon";
}

function normalizeFlashcardLimits(raw: unknown): FlashcardLimits {
  const data = asRecordOrNull(raw) ?? {};
  return {
    new_per_day: asNumber(data.new_per_day),
    review_per_day: asNumber(data.review_per_day),
    new_remaining: asNumber(data.new_remaining),
    review_remaining: asNumber(data.review_remaining),
  };
}

function normalizeFlashcardDeck(raw: Raw): FlashcardDeck {
  const out = {
    ...(raw as unknown as FlashcardDeck),
    id: asNumber(raw.id),
    name: asString(raw.name),
    slug: asString(raw.slug),
    is_auto: asBoolean(raw.is_auto),
    new_per_day: asNumber(raw.new_per_day),
    review_per_day: asNumber(raw.review_per_day),
    card_count: asNumber(raw.card_count),
    shared_count: asNumber(raw.shared_count),
    due_count: asNumber(raw.due_count),
    new_count: asNumber(raw.new_count),
    reviewed_today: asNumber(raw.reviewed_today),
  };
  if ("limits" in raw) out.limits = normalizeFlashcardLimits(raw.limits);
  return out;
}

/** `GET /api/vocabulary/decks`: `decks` siempre array. */
export function normalizeDeckList(raw: unknown): FlashcardDecks {
  const data = isRecord(raw) ? raw : {};
  return {
    ...(data as unknown as FlashcardDecks),
    decks: asRecordArray(data.decks).map(normalizeFlashcardDeck),
    auto_deck_id: asNumber(data.auto_deck_id),
    fsrs_version: asString(data.fsrs_version),
  };
}

function normalizeFlashcardCard(raw: Raw): FlashcardCard {
  // V3.86.0: la pertenencia REAL. Si el backend no la manda (rows viejas), se
  // degrada al «mazo principal», que es la única información que había.
  const deckIds = asArray<unknown>(raw.deck_ids)
    .map((v) => asNumber(v, -1))
    .filter((n) => n >= 0);
  return {
    ...(raw as unknown as FlashcardCard),
    id: asNumber(raw.id),
    deck_id: asNumber(raw.deck_id),
    deck_ids:
      deckIds.length > 0
        ? deckIds
        : raw.deck_id != null
          ? [asNumber(raw.deck_id)]
          : [],
    front: asString(raw.front),
    back: asString(raw.back),
    mnemonic: asString(raw.mnemonic),
    state: asString(raw.state, "new"),
    reps: asNumber(raw.reps),
    due_at: asString(raw.due_at),
    created_at: asString(raw.created_at),
  };
}

/** `GET /api/vocabulary/decks/{id}/cards`. */
export function normalizeFlashcardList(raw: unknown): FlashcardCards {
  const data = isRecord(raw) ? raw : {};
  return {
    ...(data as unknown as FlashcardCards),
    cards: asRecordArray(data.cards).map(normalizeFlashcardCard),
  };
}

/** `DELETE /api/vocabulary/decks/{id}` (V3.86.0): cuántas fichas se fueron y
 * cuántas se conservaron por estar compartidas con otro mazo. */
export function normalizeFlashcardDeckDelete(
  raw: unknown,
): FlashcardDeckDeleteResult {
  const data = isRecord(raw) ? raw : {};
  return {
    deleted_count: asNumber(data.deleted_count),
    shared_count: asNumber(data.shared_count),
  };
}

function normalizeStudyItem(raw: Raw): FlashcardStudyItem {
  return {
    ...(raw as unknown as FlashcardStudyItem),
    card_type: asCardType(raw.card_type),
    card_id: asString(raw.card_id),
    front: asString(raw.front),
    back: asString(raw.back),
    definition: asString(raw.definition),
    // V3.86.0: recordatorio de la ficha manual, si lo tiene.
    mnemonic: asString(raw.mnemonic),
    is_new: asBoolean(raw.is_new),
    state: asString(raw.state, "new"),
    due_at: asString(raw.due_at),
    reps: asNumber(raw.reps),
    retrievability: asNumber(raw.retrievability),
  };
}

/** `GET /api/vocabulary/decks/{id}/queue`: `items` y `limits` siempre presentes. */
export function normalizeStudyQueue(raw: unknown): FlashcardQueue {
  const data = isRecord(raw) ? raw : {};
  const deck = asRecordOrNull(data.deck);
  return {
    ...(data as unknown as FlashcardQueue),
    deck: deck
      ? normalizeFlashcardDeck(deck)
      : normalizeFlashcardDeck({ is_auto: true, id: 0 }),
    items: asRecordArray(data.items).map(normalizeStudyItem),
    due_count: asNumber(data.due_count),
    new_count: asNumber(data.new_count),
    reviewed_today: asNumber(data.reviewed_today),
    new_today: asNumber(data.new_today),
    limits: normalizeFlashcardLimits(data.limits),
    fsrs_version: asString(data.fsrs_version),
  };
}

function normalizeDayCount(raw: Raw): FlashcardDayCount {
  return {
    day: asString(raw.day),
    total: asNumber(raw.total),
    good: asNumber(raw.good),
    count: asNumber(raw.count),
  };
}

/** `GET /api/vocabulary/decks/{id}/stats`: los dos ejes siempre array. */
export function normalizeFlashcardStats(raw: unknown): FlashcardStats {
  const data = isRecord(raw) ? raw : {};
  const deck = asRecordOrNull(data.deck);
  return {
    ...(data as unknown as FlashcardStats),
    deck: deck
      ? normalizeFlashcardDeck(deck)
      : normalizeFlashcardDeck({ is_auto: true, id: 0 }),
    cards_total: asNumber(data.cards_total),
    reviewed_today: asNumber(data.reviewed_today),
    new_today: asNumber(data.new_today),
    reviews_30d: asNumber(data.reviews_30d),
    new_cards_30d: asNumber(data.new_cards_30d),
    accuracy_30d: asNumber(data.accuracy_30d),
    by_day: asRecordArray(data.by_day).map(normalizeDayCount),
    forecast: asRecordArray(data.forecast).map(normalizeDayCount),
  };
}

// --- Diccionario de consulta -----------------------------------------------

function normalizeDictionaryExample(raw: Raw): DictionaryExample {
  return {
    phrase: asString(raw.phrase),
    source: asString(raw.source),
    level: asString(raw.level),
  };
}

function normalizeSurfaceUsage(raw: Raw): DictionarySurfaceUsage {
  return {
    ...(raw as unknown as DictionarySurfaceUsage),
    status: raw.status == null ? null : asLexicalStatus(raw.status),
    mastery: asNumber(raw.mastery),
    recall: asNumber(raw.recall),
    next_review_days: asNumber(raw.next_review_days),
    production_count: asNumber(raw.production_count),
    exposure_count: asNumber(raw.exposure_count),
    production_channels: asStringArray(raw.production_channels),
    competence:
      asRecordOrNull(raw.competence) as DictionarySurfaceUsage["competence"],
    last_activity_at: asString(raw.last_activity_at),
  };
}

function normalizeUnitUsage(raw: Raw): DictionaryUnitUsage {
  return {
    ...(raw as unknown as DictionaryUnitUsage),
    lexical_unit: asString(raw.lexical_unit),
    status: raw.status == null ? null : asLexicalStatus(raw.status),
    mastery: asNumber(raw.mastery),
    recall: asNumber(raw.recall),
    surface_count: asNumber(raw.surface_count),
    mastered_surfaces: asNumber(raw.mastered_surfaces),
    recognized: asBoolean(raw.recognized),
    produced: asBoolean(raw.produced),
    transfer: asBoolean(raw.transfer),
    production_count: asNumber(raw.production_count),
    exposure_count: asNumber(raw.exposure_count),
  };
}

/** `POST /api/vocabulary/dictionary`: la tarjeta de resultado lee `usage.*` y
 *  `pos[0]`; `usage` siempre sale como objeto y `alternatives` como array.
 *  V3.86.0: `meanings` se normaliza como array de significados elegibles
 *  (`[]` si falta o no es array), de modo que la UI nunca pinta `undefined`. */
export function normalizeDictionaryMeaning(raw: Raw): DictionaryMeaning {
  return {
    term: asString(raw.term),
    pos: asString(raw.pos),
    gloss: asString(raw.gloss),
    domain: asString(raw.domain),
    proper_noun: asBoolean(raw.proper_noun),
  };
}

export function normalizeDictionaryEntry(raw: unknown): DictionaryEntry {
  const data = isRecord(raw) ? raw : {};
  const usage = asRecordOrNull(data.usage) ?? {};
  const surface = asRecordOrNull(usage.surface);
  const unit = asRecordOrNull(usage.unit);
  const example = asRecordOrNull(data.example);
  const direction = data.direction === "es-en" ? "es-en" : "en-es";
  return {
    ...(data as unknown as DictionaryEntry),
    word: asString(data.word),
    kind: asString(data.kind, "word"),
    cefr: asString(data.cefr),
    definition_source: data.definition_source === "llm" ? "llm" : "none",
    pos: asString(data.pos),
    definition: asNullableString(data.definition),
    translation: asNullableString(data.translation),
    direction,
    alternatives: asStringArray(data.alternatives),
    meanings: Array.isArray(data.meanings)
      ? data.meanings
          .filter((item): item is Raw => isRecord(item))
          .map(normalizeDictionaryMeaning)
          .filter((item) => item.term.length > 0)
      : [],
    example: example ? normalizeDictionaryExample(example) : null,
    usage: {
      tracked: asBoolean(usage.tracked),
      surface: surface ? normalizeSurfaceUsage(surface) : null,
      unit: unit ? normalizeUnitUsage(unit) : null,
    },
  };
}

// --- Cola de repaso (learning) ---------------------------------------------

function normalizeReviewQueueItem(raw: Raw): ReviewQueueItem {
  const out = {
    ...(raw as unknown as ReviewQueueItem),
    word: asString(raw.word),
    lexical_unit: asString(raw.lexical_unit),
    cefr: asString(raw.cefr),
    kind: asString(raw.kind, "word"),
    due_at: asString(raw.due_at),
    state: asString(raw.state),
    stability: asNumber(raw.stability),
    retrievability:
      typeof raw.retrievability === "number" ? raw.retrievability : null,
    elapsed_days: typeof raw.elapsed_days === "number" ? raw.elapsed_days : null,
    activity: asReviewActivity(raw.activity),
    reason: asString(raw.reason),
  };
  // Opcionales: solo se tocan si vienen (no se inventa su presencia).
  if ("why" in raw) out.why = asString(raw.why) || undefined;
  if ("competence" in raw) {
    out.competence = asRecordOrNull(raw.competence) as ReviewQueueItem["competence"];
  }
  if ("transfer_confidence" in raw) {
    out.transfer_confidence = asRecordOrNull(
      raw.transfer_confidence,
    ) as ReviewQueueItem["transfer_confidence"];
  }
  if ("decision" in raw) {
    out.decision = asRecordOrNull(raw.decision) as ReviewQueueItem["decision"];
  }
  return out;
}

/** `GET /api/learning/review`: `items` siempre array (el `?? []` anterior no
 *  protegía contra un `items` no-array pero *truthy*). */
export function normalizeReviewQueue(raw: unknown): ReviewQueue {
  const data = isRecord(raw) ? raw : {};
  return {
    ...(data as unknown as ReviewQueue),
    due_count: asNumber(data.due_count),
    items: asRecordArray(data.items).map(normalizeReviewQueueItem),
    fsrs_version: asString(data.fsrs_version),
  };
}
