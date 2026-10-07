import { saveSettings } from "../api/settings";
import {
  STUDY_PLACE_SETTING,
  mergeStudyPlace,
  readStudyPlace,
  type StudyPlace,
} from "./lastPlace";

/** Guarda un cambio del sitio de Estudiar (local y, si hay perfil, en settings). */
export function rememberStudyPlace(
  userId: string | null,
  patch: Partial<StudyPlace>,
): void {
  if (!userId) return;
  const prev = readStudyPlace(userId);
  const next = mergeStudyPlace(userId, patch);
  if (prev && JSON.stringify(prev) === JSON.stringify(next)) return;
  void saveSettings(userId, { [STUDY_PLACE_SETTING]: JSON.stringify(next) }).catch(() => {});
}
