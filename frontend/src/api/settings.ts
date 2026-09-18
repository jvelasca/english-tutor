import { getJson, putJson } from "./client";
import type { Settings, SettingsResponse } from "../types/api";

export function getSettings(_userId: string): Promise<SettingsResponse> {
  return getJson<SettingsResponse>("/api/settings");
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
