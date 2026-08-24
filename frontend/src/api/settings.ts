import { getJson, putJson } from "./client";
import type { Settings, SettingsResponse } from "../types/api";

export function getSettings(userId: string): Promise<SettingsResponse> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<SettingsResponse>(`/api/settings?${query}`);
}

export function saveSettings(
  userId: string,
  settings: Settings,
): Promise<SettingsResponse> {
  return putJson<SettingsResponse>("/api/settings", {
    user_id: userId,
    settings,
  });
}
