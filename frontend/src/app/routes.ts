export type Route =
  | "home"
  | "learn"
  | "course"
  | "progress"
  | "journey"
  | "vocabulary"
  | "chat"
  | "help"
  // V3.38.1: destino AUXILIAR del diccionario (ruta `/diccionario`), separado
  // del núcleo de aprendizaje en la navegación.
  | "dictionary";

export interface RouteOption {
  id: Route;
  i18nKey: string;
}

/**
 * Destinos raíz de la navegación (decisión D1, UI V3.1): los 3 mundos, más el
 * diccionario AUXILIAR (V3.38.1), que se pinta tras un separador porque no es
 * parte del núcleo de aprendizaje.
 *
 * El resto de rutas del tipo `Route` (progress, journey, vocabulary, chat,
 * help) siguen siendo válidas por URL — `Workspace` y `routeMap` las resuelven
 * igual — pero dejan de ser destinos raíz en V3.1 y se re-hospedarán dentro de
 * los mundos en oleadas posteriores.
 */
export const ROUTES: RouteOption[] = [
  { id: "home", i18nKey: "nav.home" },
  { id: "course", i18nKey: "nav.formation" },
  { id: "learn", i18nKey: "nav.learn" },
  { id: "dictionary", i18nKey: "nav.dictionary" },
];
