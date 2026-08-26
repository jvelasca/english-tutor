import { getJson } from "./client";

export interface HealthInfo {
  status: string;
  service: string;
  version: string;
}

export interface DependencyStatus {
  api: string;
  database: string;
  ollama: string;
  stt: string;
  tts: string;
}

export function getHealth(): Promise<HealthInfo> {
  return getJson<HealthInfo>("/api/health");
}

export function getDependencies(): Promise<DependencyStatus> {
  return getJson<DependencyStatus>("/api/health/dependencies");
}
