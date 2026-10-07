/**
 * Último sitio del alumno, por usuario.
 *
 * La ruta (hash) y el sitio de Estudiar no viajan en la URL de arranque: el
 * lanzador abre la raíz. Se guardan en localStorage para volver al momento y
 * en settings para que sigan a la cuenta.
 */
import type { StudyQueueMode, StudyScope } from "../types/api";
import { normalizeHash, splitQuery } from "../router/hash";

export type StudyTabId = "study" | "lexicon" | "decks" | "cards" | "stats";

export interface StudyPlace {
  tab: StudyTabId;
  scope: StudyScope;
  pick: StudyQueueMode;
  level: string;
  deckId: number | null;
}

export const LAST_PATH_SETTING = "last_path";
export const STUDY_PLACE_SETTING = "study_place";

const LEVELS = new Set(["A1", "A2", "B1", "B2", "C1", "C2"]);
const ROOTS = new Set([
  "formacion",
  "aprender",
  "diccionario",
  "traductor",
  "progreso",
  "chat",
  "ayuda",
  "analisis",
]);

const DEFAULT_PLACE: StudyPlace = {
  tab: "study",
  scope: "all",
  pick: "pending",
  level: "A1",
  deckId: null,
};

function pathKey(userId: string): string {
  return `english-tutor.last-path:${userId}`;
}

function placeKey(userId: string): string {
  return `english-tutor.study-place:${userId}`;
}

export function canonicalPath(raw: string): string {
  const bare = raw.startsWith("#") ? raw.slice(1) : raw;
  return normalizeHash(splitQuery(bare).path);
}

/** Rutas de estudio. Las de cuenta (correo) no se recuerdan. */
export function isRememberablePath(raw: string): boolean {
  const path = canonicalPath(raw);
  if (path === "/") return true;
  const root = path.slice(1).split("/")[0] ?? "";
  return ROOTS.has(root);
}

export function readLastPath(userId: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(pathKey(userId));
    if (!raw || !isRememberablePath(raw)) return null;
    return canonicalPath(raw);
  } catch {
    return null;
  }
}

export function writeLastPath(userId: string, raw: string): void {
  const path = canonicalPath(raw);
  if (!isRememberablePath(path)) return;
  try {
    window.localStorage.setItem(pathKey(userId), path);
  } catch {
    /* sin almacenamiento: el sitio vive solo en esta visita */
  }
}

/**
 * Ruta a la que volver al abrir la raíz. Un enlace concreto (no es `/`) manda
 * sobre el recuerdo. `/` guardado no desplaza a nadie.
 */
export function pathToRestore(current: string, saved: string | null): string | null {
  if (canonicalPath(current) !== "/") return null;
  if (!saved || !isRememberablePath(saved)) return null;
  const next = canonicalPath(saved);
  if (next === "/") return null;
  return next;
}

function isTab(value: unknown): value is StudyTabId {
  return (
    value === "study" ||
    value === "lexicon" ||
    value === "decks" ||
    value === "cards" ||
    value === "stats"
  );
}

function isScope(value: unknown): value is StudyScope {
  return value === "all" || value === "level" || value === "deck";
}

function isPick(value: unknown): value is StudyQueueMode {
  return (
    value === "pending" ||
    value === "unlearned" ||
    value === "hard" ||
    value === "good" ||
    value === "failed" ||
    value === "all"
  );
}

export function parseStudyPlace(raw: string | null | undefined): StudyPlace | null {
  if (!raw) return null;
  try {
    const data = JSON.parse(raw) as Record<string, unknown>;
    const deck = data.deckId;
    const deckId =
      typeof deck === "number" && Number.isInteger(deck) && deck >= 0 ? deck : null;
    if (!isTab(data.tab) || !isScope(data.scope) || !isPick(data.pick)) return null;
    const level = typeof data.level === "string" && LEVELS.has(data.level) ? data.level : "A1";
    const pick = data.pick === "failed" ? "unlearned" : data.pick;
    return { tab: data.tab, scope: data.scope, pick, level, deckId };
  } catch {
    return null;
  }
}

export function readStudyPlace(userId: string): StudyPlace | null {
  if (typeof window === "undefined") return null;
  try {
    return parseStudyPlace(window.localStorage.getItem(placeKey(userId)));
  } catch {
    return null;
  }
}

export function studyPlaceFromSettings(
  settings: Record<string, string> | undefined,
): StudyPlace | null {
  return parseStudyPlace(settings?.[STUDY_PLACE_SETTING]);
}

/** Mezcla un cambio con lo ya guardado y lo deja en localStorage. */
export function mergeStudyPlace(userId: string, patch: Partial<StudyPlace>): StudyPlace {
  const next: StudyPlace = { ...DEFAULT_PLACE, ...readStudyPlace(userId), ...patch };
  try {
    window.localStorage.setItem(placeKey(userId), JSON.stringify(next));
  } catch {
    /* igual que la ruta */
  }
  return next;
}
