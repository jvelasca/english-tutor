import { getJson } from "./client";

export interface NetworkInfo {
  ip: string;
  hostname: string;
  frontend_port: string;
  backend_port: string;
  url: string;
  local_url: string;
}

export function getNetwork(): Promise<NetworkInfo> {
  return getJson<NetworkInfo>("/api/network");
}
