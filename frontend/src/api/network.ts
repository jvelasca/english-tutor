import { getJson } from "./client";

export interface NetworkInfo {
  ip: string;
  hostname: string;
  frontend_port: string;
  backend_port: string;
  /**
   * Modo LAN declarado (`ENGLISH_TUTOR_LAN`). Si es `false`, la app solo
   * escucha en loopback: la URL de acceso desde otro equipo **no responde**.
   */
  lan_mode: boolean;
  /** Interfaz a la que escucha el backend: `127.0.0.1` o `0.0.0.0`. */
  bind: string;
  /** URL de acceso desde otro equipo. **Vacía** si `lan_mode` es `false`. */
  url: string;
  local_url: string;
  local_url_available?: boolean;
}

export function getNetwork(): Promise<NetworkInfo> {
  return getJson<NetworkInfo>("/api/network");
}
