import { getJson } from "./client";
import type { Bucket, ProgressHistory, ProgressSummary } from "../types/api";

export function getProgress(_userId: string): Promise<ProgressSummary> {
  return getJson<ProgressSummary>("/api/progress");
}

export function getProgressHistory(
  _userId: string,
  bucket: Bucket,
): Promise<ProgressHistory> {
  const query = new URLSearchParams({ bucket }).toString();
  return getJson<ProgressHistory>(`/api/progress/history?${query}`);
}
