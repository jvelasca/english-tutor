import { deleteJson, getJson, postForm } from "./client";
import type {
  AudioLibrarySlotsResponse,
  AudioLibraryStatusResponse,
  AudioUploadResult,
  ContentValidationReport,
} from "../types/api";

const PIN_KEY = "adminPin";

/**
 * Almacén del PIN de administración: **sesión**, no equipo.
 *
 * El PIN es una credencial, y en `localStorage` quedaba en claro y para siempre,
 * compartido por todos los perfiles del navegador y arrastrado en cualquier
 * copia/exportación de su almacenamiento. En `sessionStorage` muere al cerrar la
 * pestaña: como mucho hay que volver a teclearlo, y solo para las operaciones de
 * administración (biblioteca de audio, backups).
 */
function safeStorage(): Storage | null {
  try {
    return typeof sessionStorage === "undefined" ? null : sessionStorage;
  } catch {
    return null;
  }
}

/** Borra la copia que versiones anteriores dejaban en `localStorage`. */
function dropLegacyPin(): void {
  try {
    if (typeof localStorage !== "undefined") localStorage.removeItem(PIN_KEY);
  } catch {
    /* almacenamiento no disponible */
  }
}

export function getAdminPin(): string {
  // Migración: la copia heredada en `localStorage` se borra al primer uso.
  dropLegacyPin();
  return safeStorage()?.getItem(PIN_KEY) ?? "";
}

export function setAdminPin(pin: string): void {
  dropLegacyPin();
  const storage = safeStorage();
  if (!storage) return;
  if (pin) storage.setItem(PIN_KEY, pin);
  else storage.removeItem(PIN_KEY);
}

function adminHeaders(): Record<string, string> {
  const pin = getAdminPin();
  return pin ? { "X-Admin-Pin": pin } : {};
}

export function getAudioLibrarySlots(): Promise<AudioLibrarySlotsResponse> {
  return getJson<AudioLibrarySlotsResponse>("/api/audio-library/slots");
}

export function getAudioLibraryStatus(): Promise<AudioLibraryStatusResponse> {
  return getJson<AudioLibraryStatusResponse>("/api/audio-library/status");
}

export function getAudioLibraryAudit(): Promise<ContentValidationReport> {
  return getJson<ContentValidationReport>(
    "/api/audio-library/audit",
    adminHeaders(),
  );
}

export async function fetchAudioLibraryBlob(audioId: string): Promise<string> {
  const res = await fetch(
    `/api/audio-library/${encodeURIComponent(audioId)}/audio`,
    { headers: adminHeaders() },
  );
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return URL.createObjectURL(await res.blob());
}

export interface AudioUploadFields {
  audio_id: string;
  speaker_id?: string;
  accent?: string;
  speaker_count?: number;
  noise_level?: number;
  transcript?: string;
  gender?: string;
  age_band?: string;
  region?: string;
  speech_rate?: number | null;
  spontaneity?: string;
  recording_environment?: string;
  overlap?: boolean;
  connected_speech?: boolean;
  prosody?: string;
  task_type?: string;
  cefr?: string;
  context?: string;
}

export function uploadAudioLibraryWav(
  file: File,
  fields: AudioUploadFields,
): Promise<AudioUploadResult> {
  const form = new FormData();
  form.append("file", file);
  for (const [key, value] of Object.entries(fields)) {
    if (value === undefined || value === null || value === "") continue;
    form.append(key, String(value));
  }
  return postForm<AudioUploadResult>(
    "/api/audio-library/upload",
    form,
    adminHeaders(),
  );
}

export function deleteAudioLibraryEntry(
  audioId: string,
): Promise<{ removed: boolean; audio_id: string }> {
  return deleteJson<{ removed: boolean; audio_id: string }>(
    `/api/audio-library/${encodeURIComponent(audioId)}`,
    adminHeaders(),
  );
}
