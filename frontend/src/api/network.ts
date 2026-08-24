import { getJson } from "./client";
import type { NetworkInfo } from "../types/api";

export function getNetwork(): Promise<NetworkInfo> {
  return getJson<NetworkInfo>("/api/network");
}
