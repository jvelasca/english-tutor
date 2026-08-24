export type Role = "user" | "assistant";

export type TutorMode = "conversation" | "grammar" | "exercises" | "pronunciation";

export type PronunciationLevel = "good" | "fair" | "needs_practice";

export interface Message {
  id?: string;
  role: Role;
  content: string;
  mode?: TutorMode;
}

export interface ChatResponse {
  model: string;
  content: string;
}

export interface ModelsResponse {
  models?: string[];
}

export interface User {
  id: string;
  name: string;
  created_at: string;
}

export interface ConversationMeta {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  user_id: string;
}

export interface Conversation extends ConversationMeta {
  messages: Message[];
}

export interface WordSubstitution {
  expected: string;
  heard: string;
}

export interface PronunciationBreakdown {
  correct: string[];
  missing: string[];
  extra: string[];
  substituted: WordSubstitution[];
  total: number;
}

export interface FluencyStats {
  word_count: number;
  duration_seconds: number | null;
  wpm: number | null;
  level: string;
}

export interface PronunciationResponse {
  expected: string;
  heard: string;
  score: number;
  level: PronunciationLevel;
  ok: boolean;
  word_accuracy: number;
  phonetic_score: number;
  breakdown: PronunciationBreakdown;
  fluency: FluencyStats;
}

export interface PronunciationStats {
  attempts: number;
  best: number | null;
  average: number | null;
  last_score: number | null;
  last_level: PronunciationLevel | null;
}

export interface ProgressSummary {
  user_id: string;
  conversations: number;
  messages: number;
  exercises: number;
  corrections: number;
  pronunciation: PronunciationStats;
}

export type EstimatedLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export interface EstimatedBands {
  vocabulary: string;
  grammar: string;
  fluency: string;
  pronunciation: string;
}

export interface GrammarRecurringError {
  rule: string;
  message: string;
  count: number;
  last_example: string;
  last_seen: string;
}

export interface LearningProfile {
  user_id: string;
  estimated_level: EstimatedLevel;
  estimated_bands: EstimatedBands;
  estimated_descriptor: string;
  vocabulary_size: number;
  top_words: string[];
  recurring_errors: GrammarRecurringError[];
  pronunciation_average: number | null;
  recommendations: string[];
}

export type Bucket = "day" | "week" | "month";

export type LearningEventType =
  | "message"
  | "exercise"
  | "correction"
  | "pronunciation"
  | "conversation";

export interface LearningEvent {
  id: number;
  user_id: string;
  type: LearningEventType;
  detail: string;
  created_at: string;
}

export interface SeriesPoint {
  bucket: string;
  messages: number;
  exercises: number;
  corrections: number;
  pronunciation: number;
}

export interface Streak {
  current_days: number;
  best_days: number;
  last_active_date: string | null;
}

export interface ErrorMastery {
  active: GrammarRecurringError[];
  resolved: GrammarRecurringError[];
}

export interface Milestone {
  id: string;
  label: string;
  achieved: boolean;
}

export interface ProgressHistory {
  user_id: string;
  bucket: Bucket;
  series: SeriesPoint[];
  streak: Streak;
  mastery: ErrorMastery;
  milestones: Milestone[];
}

export interface ListeningQuestion {
  id: string;
  level: string;
  script: string;
  question: string;
  options: string[];
}

export interface ListeningAnswerResponse {
  question_id: string;
  correct: boolean;
  correct_index: number;
  level: string;
}

export interface ListeningStats {
  attempts: number;
  correct: number;
  accuracy: number | null;
}
