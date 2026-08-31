import { deleteJson, getJson, postForm } from "./client";
import type {
  AudioLibraryEntry,
  AudioLibrarySlotsResponse,
} from "../types/api";

export function getAudioLibrarySlots(): Promise<AudioLibrarySlotsResponse> {
  return getJson<AudioLibrarySlotsResponse>("/api/audio-library/slots");
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
): Promise<AudioLibraryEntry> {
  const form = new FormData();
  form.append("file", file);
  for (const [key, value] of Object.entries(fields)) {
    if (value === undefined || value === null || value === "") continue;
    form.append(key, String(value));
  }
  return postForm<AudioLibraryEntry>("/api/audio-library/upload", form);
}

export function deleteAudioLibraryEntry(
  audioId: string,
): Promise<{ removed: boolean; audio_id: string }> {
  return deleteJson<{ removed: boolean; audio_id: string }>(
    `/api/audio-library/${encodeURIComponent(audioId)}`,
  );
}
