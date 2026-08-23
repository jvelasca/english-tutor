import { getJson } from "./client";
import type { ProgressSummary } from "../types/api";

export function getProgress(userId: string): Promise<ProgressSummary> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<ProgressSummary>(`/api/progress?${query}`);
}
