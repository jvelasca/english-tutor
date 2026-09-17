import type { Path } from "./hash";
import { formatPath, parseSegments } from "./hash";
import { CHAT_PATH } from "./paths";

/**
 * Habilidad del chat libre por destreza (D4, revisado en V3.73.1).
 *
 * Reading y Writing no tienen tarjeta de primer nivel en el hub de APRENDER
 * porque no tienen motor propio de rutas; su práctica es conversacional, con el
 * tutor. Para que dejen de ser un cajón indiferenciado en `/chat` (donde antes
 * caían y además el workspace forzaba `speaking`), cada una tiene su URL
 * canónica — `/chat/lectura` y `/chat/escritura` — de modo que la URL sigue
 * siendo la fuente de verdad (F4) y el tutor abre con el contexto de la
 * destreza. Es la misma relación que Speaking mantiene con sus modos: raíz +
 * sub-ruta canónica.
 */
export type ChatSkill = "reading" | "writing";

/** Segmento canónico de cada destreza bajo `/chat` (vocabulario es). */
const CHAT_SKILL_SLUG: Record<ChatSkill, string> = {
  reading: "lectura",
  writing: "escritura",
};

const SLUG_TO_SKILL: Record<string, ChatSkill> = {
  [CHAT_SKILL_SLUG.reading]: "reading",
  [CHAT_SKILL_SLUG.writing]: "writing",
};

/**
 * Ruta canónica del chat libre con una destreza activa, p. ej.
 * `chatSkillPath("writing")` -> "/chat/escritura".
 */
export function chatSkillPath(skill: ChatSkill): Path {
  return formatPath([...parseSegments(CHAT_PATH), CHAT_SKILL_SLUG[skill]]);
}

/** Comprueba si un valor desconocido es una destreza de chat reconocida. */
export function isChatSkill(value: unknown): value is ChatSkill {
  return value === "reading" || value === "writing";
}

/** Comprueba si una hoja de `/chat/<hoja>` es un slug canónico de destreza. */
export function isChatSkillSlug(value: unknown): boolean {
  return typeof value === "string" && Object.hasOwn(SLUG_TO_SKILL, value);
}

/**
 * Destreza de chat que trae la ruta, o `null` si la ruta no es la sub-ruta de
 * una destreza. Solo se reconoce la raíz `/chat/<slug canónico>`; cualquier
 * otra hoja bajo `/chat` no es una destreza (la resolución de ruta decide si
 * degrada a home).
 */
export function chatSkillFromPath(path: Path): ChatSkill | null {
  const segments = parseSegments(path);
  if (segments.length !== 2 || segments[0] !== "chat") return null;
  return SLUG_TO_SKILL[segments[1]] ?? null;
}
