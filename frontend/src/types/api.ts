export type Role = "user" | "assistant";

export type TutorMode = "conversation" | "grammar" | "exercises" | "pronunciation";

export interface Message {
  role: Role;
  content: string;
}

export interface ChatResponse {
  model: string;
  content: string;
}

export interface ModelsResponse {
  models?: string[];
}

export interface ConversationMeta {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Conversation extends ConversationMeta {
  messages: Message[];
}

export interface PronunciationResponse {
  expected: string;
  heard: string;
  score: number;
  level: "good" | "fair" | "needs_practice";
  ok: boolean;
}
