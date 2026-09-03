/**
 * Sesiones de práctica de Listening bajo control del alumno (control de nivel).
 *
 * Dos modos de sesión focalizada, ambos sobre frases de un nivel concreto:
 * - `level`: rotación "toda la vuelta" del nivel (el antiguo repaso), ahora
 *   disponible para cualquier nivel, no solo los completados.
 * - `drill`: repetición de las frases falladas (intentadas y nunca acertadas)
 *   hasta dominarlas todas; `remaining` son los ids aún por acertar.
 *
 * El resto de la práctica (sin sesión) sigue guiada por el Adaptive Engine.
 */
export type ListeningSession =
  | { mode: "level"; level: string; total: number; done: number }
  | { mode: "drill"; level: string; total: number; remaining: string[] };

/** Frasa fallada superada (acertada): se elimina del pool restante del drill. */
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

/** Frases correctas respondidas en el modo nivel (progreso de la sesión). */
export function sessionDone(session: ListeningSession): number {
  return session.mode === "level" ? session.done : drillDone(session);
}

/** True cuando la sesión ha completado su objetivo (acabó la vuelta / drill). */
export function isSessionFinished(session: ListeningSession): boolean {
  if (session.mode === "level") return session.done >= session.total;
  return session.remaining.length === 0;
}
