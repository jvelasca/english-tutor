/**
 * Configuración de estudio del alumno (V3.87.0 · FASE 2, incremento 1).
 *
 * Es la preferencia con la que se construye la sesión de flashcards y la cola de
 * repaso léxico: dirección EN↔ES, reconocer/producir, ayudas y carga. Vive en el
 * perfil (tabla `settings` del backend), así que no se manda `user_id`: la
 * identidad sale de la sesión, como en `saveSettings`.
 */
import { getJson, putJson } from "./client";
import { normalizeStudyConfig } from "./normalize";
import type { StudyConfig } from "../types/api";

/** Configuración vigente (con los defectos si el alumno no ha guardado nunca). */
export function getStudyConfig(_userId: string): Promise<StudyConfig> {
  return getJson<unknown>("/api/study/config").then(normalizeStudyConfig);
}

/** Guarda un PATCH parcial: los campos omitidos NO se tocan. */
export function saveStudyConfig(
  _userId: string,
  patch: Partial<Omit<StudyConfig, "configured">>,
): Promise<StudyConfig> {
  return putJson<unknown>("/api/study/config", patch).then(normalizeStudyConfig);
}
