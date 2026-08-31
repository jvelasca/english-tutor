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

export const ROUTES: RouteOption[] = [
  { id: "home", i18nKey: "nav.home" },
  { id: "learn", i18nKey: "nav.learn" },
  { id: "course", i18nKey: "nav.course" },
  { id: "progress", i18nKey: "nav.progress" },
  { id: "journey", i18nKey: "nav.journey" },
  { id: "vocabulary", i18nKey: "nav.vocabulary" },
  { id: "chat", i18nKey: "nav.chat" },
];
