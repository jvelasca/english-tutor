import { getJson } from "./client";
import type { Bucket, ProgressHistory, ProgressSummary } from "../types/api";

export function getProgress(userId: string): Promise<ProgressSummary> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<ProgressSummary>(`/api/progress?${query}`);
}

export function getProgressHistory(
  userId: string,
  bucket: Bucket,
): Promise<ProgressHistory> {
  const query = new URLSearchParams({ user_id: userId, bucket }).toString();
  return getJson<ProgressHistory>(`/api/progress/history?${query}`);
}
