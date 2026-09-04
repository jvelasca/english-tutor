/**
 * Sesiones de práctica de Speaking por rutas (V3.7), espejo de listening.
 *
 * Tres modos de sesión focalizada sobre las frases modelo de una ruta:
 * - `level`: rotación "toda la vuelta" por las frases de la ruta.
 * - `drill`: repetir las falladas (intentadas y nunca superadas) hasta
 *   dominarlas todas; `remaining` son los ids aún por superar.
 * - `mastered`: "repasar lo aprendido", rotación solo sobre las frases de la
 *   ruta ya superadas (consolidar/re-exponer lo dominado).
 */
export type SpeakingSession =
  | { mode: "level"; level: string; total: number; done: number }
  | { mode: "drill"; level: string; total: number; remaining: string[] }
  | { mode: "mastered"; level: string; total: number; done: number };

/** Frase fallada superada: se elimina del pool restante del drill. */
export function drillAnswered(
  remaining: string[],
  phraseId: string,
  passed: boolean,
): string[] {
  if (!passed) return remaining;
  return remaining.filter((id) => id !== phraseId);
}

/** Frases del drill ya dominadas (progreso de la sesión). */
export function drillDone(session: SpeakingSession): number {
  return session.mode === "drill" ? session.total - session.remaining.length : 0;
}

/** Frases respondidas en los modos de rotación (nivel / repasar lo aprendido). */
export function sessionDone(session: SpeakingSession): number {
  return session.mode === "drill" ? drillDone(session) : session.done;
}

/** True cuando la sesión ha completado su objetivo (acabó la vuelta / drill). */
export function isSessionFinished(session: SpeakingSession): boolean {
  if (session.mode === "drill") return session.remaining.length === 0;
  return session.done >= session.total;
}
