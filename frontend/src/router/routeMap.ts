import type { Route } from "../app/routes";
import type { Path } from "./hash";
import { joinPath, normalizeHash, parseSegments } from "./hash";
import {
  FORMATION_PATH,
  HELP_PATH,
  HOME_PATH,
  LEARN_PATH,
  LEGACY_CHAT_ACTIVITY,
  LEGACY_VOCABULARY_ACTIVITY,
  PROGRESS_PATH,
  learnActivityPath,
} from "./paths";

/**
 * Tabla reversible Route -> Path canónica. Es el único punto donde cada valor
 * del tipo `Route` ("home" | "learn" | ... ) queda ligado a su URL: la pantalla
 * Course vive por ahora en el mundo Formación y las actividades "learn"
 * (conversar, vocabulario) cuelgan de Aprender como sub-rutas legadas.
 */
const ROUTE_TO_PATH: Record<Route, Path> = {
  home: HOME_PATH,
  course: FORMATION_PATH,
  learn: LEARN_PATH,
  progress: PROGRESS_PATH,
  journey: joinPath(PROGRESS_PATH, "trayectoria"),
  vocabulary: learnActivityPath(LEGACY_VOCABULARY_ACTIVITY),
  chat: learnActivityPath(LEGACY_CHAT_ACTIVITY),
  help: HELP_PATH,
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
 * "/aprender/conversar" y "/aprender/vocabulario" son hojas de learn.
 * `/formacion*` siempre es course (cualquier sub-nivel). Toda ruta
 * desconocida cae en home.
 */
export function pathToRoute(path: Path): Route {
  const segments = parseSegments(normalizeHash(path));
  if (segments.length === 0) return "home";
  const [root, leaf] = segments;
  switch (root) {
    case "formacion":
      return "course";
    case "progreso":
      return segments.length === 2 && leaf === "trayectoria"
        ? "journey"
        : "progress";
    case "aprender":
      if (segments.length === 2 && leaf === "conversar") return "chat";
      if (segments.length === 2 && leaf === "vocabulario") return "vocabulary";
      return "learn";
    case "ayuda":
      return segments.length === 1 ? "help" : "home";
    default:
      return "home";
  }
}
