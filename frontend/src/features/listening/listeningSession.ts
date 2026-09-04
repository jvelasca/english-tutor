/**
 * Sesiones de práctica de Listening bajo control del alumno (control de nivel).
 *
 * Tres modos de sesión focalizada, todos sobre frases de una ruta concreta:
 * - `level`: rotación "toda la vuelta" de la ruta (el antiguo repaso), ahora
 *   disponible para cualquier nivel, no solo los completados.
 * - `drill`: repetición de las frases falladas (intentadas y nunca acertadas)
 *   hasta dominarlas todas; `remaining` son los ids aún por acertar.
 * - `mastered`: "repasar lo aprendido", rotación solo sobre las frases de la
 *   ruta ya acertadas (misma mecánica LRU que `level`, con menos candidatos);
 *   sirve para consolidar y re-exponer lo dominado (V3.6).
 *
 * El resto de la práctica (sin sesión) sigue guiada por el Adaptive Engine.
 */
export type ListeningSession =
  | { mode: "level"; level: string; total: number; done: number }
  | { mode: "drill"; level: string; total: number; remaining: string[] }
  | { mode: "mastered"; level: string; total: number; done: number };

/** Frase fallada superada (acertada): se elimina del pool restante del drill. */
export function drillAnswered(
  remaining: string[],
  questionId: string,
  correct: boolean,
): string[] {
  if (!correct) return remaining;
  return remaining.filter((id) => id !== questionId);
}

/** Frases del drill ya dominadas (progreso de la sesión). */
export function drillDone(session: ListeningSession): number {
  return session.mode === "drill" ? session.total - session.remaining.length : 0;
}

/** Frases respondidas en los modos de rotación (nivel / repasar lo aprendido). */
export function sessionDone(session: ListeningSession): number {
  return session.mode === "drill" ? drillDone(session) : session.done;
}

/** True cuando la sesión ha completado su objetivo (acabó la vuelta / drill). */
export function isSessionFinished(session: ListeningSession): boolean {
  if (session.mode === "drill") return session.remaining.length === 0;
  return session.done >= session.total;
}
