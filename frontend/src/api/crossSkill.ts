import { getJson } from "./client";
import type { CrossSkillMatrix } from "../types/api";

/**
 * Matriz cross-skill por estructura (V3.13, P1.2, solo lectura).
 *
 * Prototipo B1: por cada estructura gramatical del nivel, qué instrumentos
 * ofrece el currículo por destreza (recognition/production/listening/speaking/
 * transfer) y qué evidencia correcta acumula el usuario. Nunca escribe.
 */
export function getCrossSkillMatrix(
  userId: string,
  level = "b1",
): Promise<CrossSkillMatrix> {
  const query = new URLSearchParams({ user_id: userId, level }).toString();
  return getJson<CrossSkillMatrix>(`/api/cross-skill?${query}`);
}
