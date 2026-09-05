/**
 * Tipos compartidos de las rutas de quiz MC/producción controlada (V3.13 P2.1).
 *
 * Grammar y Vocabulary comparten página única con checks del currículo
 * (pregunta MC o producción controlada escrita). Estos tipos son un subconjunto
 * estructural de `VocabularyStats`/`GrammarStats` y sus ítems, para que la
 * página compartida `QuizRoutePage` pueda tipar cualquier destreza sin acoplarse
 * a un módulo de API concreto.
 */
export interface RouteQuestion {
  check_id: string;
  level: string;
  topic: string;
  prompt: string;
  options: string[];
  type?: "mcq" | "controlled_production";
}

export interface RouteAttempt {
  check_id: string;
  level?: string;
  topic?: string;
  prompt: string;
  options: string[];
  score: number;
  passed: boolean;
  correct_index?: number;
  selected_index?: number;
  type?: string;
  typed_answer?: string;
  expected_answers?: string[];
}

export interface RouteLevelProgress {
  level: string;
  total: number;
  mastered: number;
  completed: boolean;
}

export interface RouteStats {
  level: string;
  accuracy: number | null;
  attempts: number;
  passed: number;
  levels: RouteLevelProgress[];
}

export type RouteQuestionMode = "all" | "failed" | "mastered";
