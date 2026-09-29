/**
 * Sesiones de práctica de Listening bajo control del alumno (control de nivel).
 *
 * Tres modos de sesión focalizada, todos sobre frases de una ruta concreta:
 * - `level`: rotación "toda la vuelta" de la ruta (el antiguo repaso), ahora
 *   disponible para cualquier nivel, no solo los completados.
 * - `drill`: pasada ACOTADA sobre las frases falladas (intentadas y nunca
 *   acertadas). V3.89: la frase sale del pool al responderla, acierte o falle —
 *   ya no se repite «hasta acertar»—. Lo que no se acierte queda en la **cola
 *   de repaso persistente del backend** (`listening_review_queue`), que sí lo
 *   reabre más tarde con su propia prioridad.
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

/**
 * Frase respondida en el drill: sale del pool restante (V3.89).
 *
 * Antes solo salía al acertar, y eso era el bucle «hasta acertar». Ahora la
 * sesión avanza siempre y el fallo se registra en la cola de repaso, que es
 * donde debe vivir la repetición (espaciada y priorizada), no en la sesión.
 */
export function drillAnswered(
  remaining: string[],
  questionId: string,
): string[] {
  return remaining.filter((id) => id !== questionId);
}

/** Frases del drill ya respondidas (progreso de la sesión, V3.89). */
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
