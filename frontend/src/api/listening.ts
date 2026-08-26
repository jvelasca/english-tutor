import { getJson, postJson } from "./client";
import type {
  ListeningAnswerResponse,
  ListeningDiagnostic,
  ListeningQuestion,
  ListeningStats,
} from "../types/api";

export function getListeningQuestion(userId: string): Promise<ListeningQuestion> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<ListeningQuestion>(`/api/listening/question?${query}`);
}

export function submitListeningAnswer(
  userId: string,
  questionId: string,
  answerIndex: number,
  responseTimeMs: number | null = null,
  replayCount = 0,
): Promise<ListeningAnswerResponse> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return postJson<ListeningAnswerResponse>(`/api/listening/answer?${query}`, {
    question_id: questionId,
    answer_index: answerIndex,
    response_time_ms: responseTimeMs,
    replay_count: replayCount,
  });
}

export function getListeningStats(userId: string): Promise<ListeningStats> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<ListeningStats>(`/api/listening/stats?${query}`);
}

export function getListeningDiagnostic(
  userId: string,
): Promise<ListeningDiagnostic> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<ListeningDiagnostic>(`/api/listening/diagnostic?${query}`);
}

export function getListeningAudioUrl(questionId: string, userId: string): string {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return `/api/listening/audio/${questionId}?${query}`;
}
