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
import { LexiconInventory } from "./LexiconInventory";
import { DictionaryLookup } from "./DictionaryLookup";
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
    View: LexiconInventory,
  },
  // V3.30 (D2): vista alterna «Consultar» junto al diccionario personal.
  // V3.86.0: el diccionario de CONSULTA incrustado en la práctica de rutas puede
  // saltar a la pantalla central de Flashcards cuando la palabra ya está
  // rastreada (su única salida). El panel no hospeda la sesión, así que el salto
  // persiste la vista y navega; el mazo elegido viaja en el recado de un solo uso.
  dictionaryLookup: {
    ctaKey: "vocRoutes.dictionaryLookupCta",
    hintKey: "vocRoutes.dictionaryLookupHint",
    View: DictionaryLookup,
    allowFlashcardsJump: true,
  },
  // V3.85.1 (D4): APRENDER → Vocabulario perdió el drill de repaso al retirar
  // `ReviewQueueSection`. Recupera la puerta con UN solo CTA que lleva a la
  // superficie central (Flashcards → Estudiar) en vez de duplicar la sesión.
  reviewCta: {
    ctaKey: "vocRoutes.reviewCta",
    hintKey: "vocRoutes.reviewHint",
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
