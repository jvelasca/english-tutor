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

export interface PronunciationResponse {
  expected: string;
  heard: string;
  score: number;
  level: PronunciationLevel;
  ok: boolean;
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
