/**
 * APRENDER → Grammar por rutas (V3.12), migrada a la página compartida de quiz.
 *
 * V3.13 P2.1 (wave 1): la página única con scroll (escenario de práctica MC /
 * producción controlada, mapa A1–C2 con anillos, panel por nivel y bloque
 * «Demostrar el nivel») vive en `features/routes/QuizRoutePage.tsx` y se
 * parametriza con un `RouteQuizConfig`. Este archivo queda como wrapper fino
 * con el namespace i18n y la API de grammar.
 */
import {
  getGrammarQuestion,
  getGrammarStats,
  submitGrammarAttempt,
} from "../../api/grammarRoutes";
import { QuizRoutePage, type RouteQuizConfig } from "../routes/QuizRoutePage";
import { GrammarLevelPanel } from "./GrammarLevelPanel";
import type { LearnActivity } from "../../router/learnHub";
import type { NextBestActivity } from "../../types/api";
import type { Section } from "../../utils/sections";

const GRAMMAR_ROUTE_CONFIG: RouteQuizConfig = {
  ns: "gramRoutes",
  skillTitleKey: "skill.grammar",
  subtitleKey: "learn.grammarSubtitle",
  ariaLevelItemsId: "grammar-level-items",
  LevelPanel: GrammarLevelPanel,
  api: {
    getStats: (userId) => getGrammarStats(userId),
    getQuestion: (userId, level, mode) => getGrammarQuestion(userId, level, mode),
    submitAttempt: (userId, checkId, selectedIndex, typedAnswer) =>
      submitGrammarAttempt(
        userId,
        checkId,
        selectedIndex,
        typedAnswer ?? undefined,
      ),
  },
};

interface GrammarRoutesPracticeProps {
  userId: string | null;
  /** Actividad activa (Gramática) para el atajo de la franja superior. */
  active: LearnActivity;
  /** Navega de vuelta al hub de APRENDER (`#/aprender`). */
  onBack: () => void;
  /** La práctica registra un intento puntuado: el padre refresca métricas. */
  onAttempt: () => void;
  /** Recomendación de "siguiente mejor actividad" al terminar el examen. */
  onNext: (section: Section | null, step: NextBestActivity) => void;
}

export function GrammarRoutesPractice(props: GrammarRoutesPracticeProps) {
  return (
    <QuizRoutePage
      userId={props.userId}
      active={props.active}
      onBack={props.onBack}
      onAttempt={props.onAttempt}
      onNext={props.onNext}
      config={GRAMMAR_ROUTE_CONFIG}
    />
  );
}
