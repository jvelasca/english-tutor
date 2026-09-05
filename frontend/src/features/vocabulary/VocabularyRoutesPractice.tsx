/**
 * APRENDER → Vocabulary por rutas (V3.11), migrada a la página compartida de
 * quiz.
 *
 * V3.13 P2.1 (wave 1): la página única con scroll (escenario de práctica MC,
 * mapa A1–C2 con anillos, panel por nivel, diccionario personal y bloque
 * «Demostrar el nivel») vive en `features/routes/QuizRoutePage.tsx`. Este
 * archivo queda como wrapper fino con el namespace i18n, la API y la vista de
 * diccionario de vocabulary.
 */
import {
  getVocabularyQuestion,
  getVocabularyStats,
  submitVocabularyAttempt,
} from "../../api/vocabularyRoutes";
import { QuizRoutePage, type RouteQuizConfig } from "../routes/QuizRoutePage";
import { VocabularyLevelPanel } from "./VocabularyLevelPanel";
import { PersonalDictionary } from "./PersonalDictionary";
import type { LearnActivity } from "../../router/learnHub";
import type { NextBestActivity } from "../../types/api";
import type { Section } from "../../utils/sections";

const VOCABULARY_ROUTE_CONFIG: RouteQuizConfig = {
  ns: "vocRoutes",
  skillTitleKey: "skill.vocabulary",
  subtitleKey: "learn.vocabularySubtitle",
  ariaLevelItemsId: "vocabulary-level-items",
  LevelPanel: VocabularyLevelPanel,
  dictionary: {
    ctaKey: "vocRoutes.dictionaryCta",
    hintKey: "vocRoutes.dictionaryHint",
    View: PersonalDictionary,
  },
  api: {
    getStats: (userId) => getVocabularyStats(userId),
    getQuestion: (userId, level, mode) =>
      getVocabularyQuestion(userId, level, mode),
    submitAttempt: (userId, checkId, selectedIndex) =>
      submitVocabularyAttempt(userId, checkId, selectedIndex),
  },
};

interface VocabularyRoutesPracticeProps {
  userId: string | null;
  /** Actividad activa (Vocabulario) para el atajo de la franja superior. */
  active: LearnActivity;
  /** Navega de vuelta al hub de APRENDER (`#/aprender`). */
  onBack: () => void;
  /** La práctica registra un intento puntuado: el padre refresca métricas. */
  onAttempt: () => void;
  /** Recomendación de "siguiente mejor actividad" al terminar el examen. */
  onNext: (section: Section | null, step: NextBestActivity) => void;
}

export function VocabularyRoutesPractice(props: VocabularyRoutesPracticeProps) {
  return (
    <QuizRoutePage
      userId={props.userId}
      active={props.active}
      onBack={props.onBack}
      onAttempt={props.onAttempt}
      onNext={props.onNext}
      config={VOCABULARY_ROUTE_CONFIG}
    />
  );
}
