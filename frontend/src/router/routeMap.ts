import type { Route } from "../app/routes";
import type { Path } from "./hash";
import { joinPath, parseSegments, splitQuery } from "./hash";
import { isChatSkillSlug } from "./chat";
import {
  ACCOUNT_ACTIVATE_PATH,
  ACCOUNT_RESET_PATH,
  ACCOUNT_VERIFY_PATH,
  ANALYSIS_PATH,
  CHAT_PATH,
  DICTIONARY_PATH,
  FORMATION_PATH,
  HELP_PATH,
  HOME_PATH,
  LEARN_PATH,
  LEGACY_VOCABULARY_ACTIVITY,
  PROGRESS_PATH,
  TRANSLATOR_PATH,
  learnActivityPath,
} from "./paths";

/**
 * Tabla reversible Route -> Path canónica. Es el único punto donde cada valor
 * del tipo `Route` ("home" | "learn" | ... ) queda ligado a su URL. Desde
 * V3.10 el chat libre (Route "chat") tiene su propia raíz `/chat`, y las
 * actividades "learn" cuelgan de Aprender como sub-rutas. V3.38.1 añade el
 * destino auxiliar "dictionary" con raíz propia `/diccionario`.
 */
const ROUTE_TO_PATH: Record<Route, Path> = {
  home: HOME_PATH,
  course: FORMATION_PATH,
  learn: LEARN_PATH,
  progress: PROGRESS_PATH,
  journey: joinPath(PROGRESS_PATH, "trayectoria"),
  vocabulary: learnActivityPath(LEGACY_VOCABULARY_ACTIVITY),
  chat: CHAT_PATH,
  help: HELP_PATH,
  dictionary: DICTIONARY_PATH,
  translator: TRANSLATOR_PATH,
  // V3.75.3: destino auxiliar de análisis, sin píldora de navegación.
  analysis: ANALYSIS_PATH,
  // V3.82: páginas de cuenta que llegan por correo.
  accountActivate: ACCOUNT_ACTIVATE_PATH,
  accountReset: ACCOUNT_RESET_PATH,
  accountVerify: ACCOUNT_VERIFY_PATH,
};

/**
 * Devuelve la ruta canónica de una pantalla. Es la función "hacia delante" del
 * mapeo reversible: `pathToRoute(routeToPath(route))` siempre devuelve el
 * mismo `route`. Se usa para navegar desde los handlers internos sin exponer
 * strings de URL.
 */
export function routeToPath(route: Route): Path {
  return ROUTE_TO_PATH[route];
}

/**
 * Devuelve la pantalla que corresponde a una ruta de la URL. Es la función
 * "inversa" del mapeo: normaliza la entrada y compara segmentos decodificados
 * (con `parseSegments`), de modo que no depende de trailing slashes ni de
 * cadenas exactas. Las hojas tienen precedencia sobre los prefijos:
 * "/progreso/trayectoria" es journey aunque comparta el prefijo de progress y
 * "/aprender/vocabulario" es una hoja de learn. El chat libre tiene raíz
 * propia "/chat" (V3.10). `/formacion*` siempre es course (cualquier
 * sub-nivel). Toda ruta desconocida cae en home.
 */
export function pathToRoute(path: Path): Route {
  // V3.82: los enlaces de correo traen la consulta dentro del hash
  // (`#/cuenta/activar?token=…`). Se separa antes de trocear, o el token
  // acabaría pegado al segmento y la ruta caería en home.
  const segments = parseSegments(splitQuery(path).path);
  if (segments.length === 0) return "home";
  const [root, leaf] = segments;
  switch (root) {
    case "formacion":
      return "course";
    case "cuenta":
      // V3.82: páginas de cuenta abiertas desde un enlace de correo. Sin
      // sub-rutas válidas, cualquier otra hoja degrada a home como el resto.
      if (segments.length !== 2) return "home";
      if (leaf === "activar") return "accountActivate";
      if (leaf === "restablecer") return "accountReset";
      if (leaf === "verificar") return "accountVerify";
      return "home";
    case "progreso":
      return segments.length === 2 && leaf === "trayectoria"
        ? "journey"
        : "progress";
    case "aprender":
      if (segments.length === 2 && leaf === "vocabulario") return "vocabulary";
      return "learn";
    case "chat":
      // V3.73.1: el chat libre tiene raíz propia `/chat` y sub-rutas canónicas
      // por destreza (`/chat/lectura`, `/chat/escritura`) para las prácticas
      // conversacionales sin motor propio (Reading/Writing, D4). Cualquier otra
      // hoja bajo `/chat` sigue degradando a home.
      if (segments.length === 1) return "chat";
      if (segments.length === 2 && isChatSkillSlug(leaf)) return "chat";
      return "home";
    case "ayuda":
      return segments.length === 1 ? "help" : "home";
    case "diccionario":
      return segments.length === 1 ? "dictionary" : "home";
    case "traductor":
      return segments.length === 1 ? "translator" : "home";
    case "analisis":
      // V3.75.3: destino auxiliar sin sub-rutas, igual que diccionario/traductor.
      return segments.length === 1 ? "analysis" : "home";
    default:
      return "home";
  }
}
