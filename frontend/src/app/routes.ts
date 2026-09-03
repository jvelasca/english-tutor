export type Route =
  | "home"
  | "learn"
  | "course"
  | "progress"
  | "journey"
  | "vocabulary"
  | "chat"
  | "help";

export interface RouteOption {
  id: Route;
  i18nKey: string;
}

/**
 * Destinos raíz de la navegación (decisión D1, UI V3.1): solo los 3 mundos.
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
];
