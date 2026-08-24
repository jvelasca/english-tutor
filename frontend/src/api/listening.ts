import { getJson, postJson } from "./client";
import type {
  ListeningAnswerResponse,
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
): Promise<ListeningAnswerResponse> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return postJson<ListeningAnswerResponse>(`/api/listening/answer?${query}`, {
    question_id: questionId,
    answer_index: answerIndex,
  });
}

export function getListeningStats(userId: string): Promise<ListeningStats> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<ListeningStats>(`/api/listening/stats?${query}`);
}
