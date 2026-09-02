import { formatPath } from "./hash";
import type { Path } from "./hash";

/** Ruta raíz del mundo Inicio (home): "/". */
export const HOME_PATH: Path = "/";

/** Ruta raíz del mundo Formación (course/niveles): "/formacion". */
export const FORMATION_PATH: Path = "/formacion";

/** Ruta raíz del mundo Aprender (actividades por habilidad): "/aprender". */
export const LEARN_PATH: Path = "/aprender";

/** Ruta raíz del mundo Progreso: "/progreso". */
export const PROGRESS_PATH: Path = "/progreso";

/** Ruta raíz de Ayuda: "/ayuda". */
export const HELP_PATH: Path = "/ayuda";

/**
 * Ruta canónica de un nivel dentro de Formación para deep links, por ejemplo
 * formationLevelPath("b1") -> "/formacion/b1". El `levelId` se percent-codifica.
 */
export function formationLevelPath(levelId: string): Path {
  return formatPath(["formacion", levelId]);
}

/**
 * Ruta canónica de una actividad dentro de Aprender para deep links, por
 * ejemplo learnActivityPath("listening") -> "/aprender/listening". El
 * `activity` debe pasarse en minúsculas ASCII y se percent-codifica.
 */
export function learnActivityPath(activity: string): Path {
  return formatPath(["aprender", activity]);
}

/**
 * Alias del mundo actual "learn" en la nueva IA de navegación: las secciones
 * que hoy viven bajo "learn" dejan de ser mundos raíz y se reubican bajo
 * Aprender. Por ahora señala a `LEARN_PATH` para que las oleadas posteriores
 * puedan migrar referencias sin romper el código.
 */
export const LEGACY_LEARN_ALIAS = LEARN_PATH;

/** Actividad legada "chat" reubicada como "/aprender/conversar". */
export const LEGACY_CHAT_ACTIVITY = "conversar";

/** Actividad legada "vocabulary" reubicada como "/aprender/vocabulario". */
export const LEGACY_VOCABULARY_ACTIVITY = "vocabulario";
