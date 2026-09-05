/**
 * Sesiones de práctica de Grammar por rutas (V3.12), espejo de vocabulary.
 *
 * Tres modos de sesión focalizada sobre los checks MC de una ruta:
 * - `level`: rotación "toda la vuelta" por los checks de la ruta.
 * - `drill`: repetir las falladas (intentadas y nunca acertadas) hasta
 *   acertarlas todas; `remaining` son los ids aún por acertar.
 * - `mastered`: "repasar lo aprendido", rotación solo sobre los checks de la
 *   ruta ya acertados (consolidar/re-exponer lo dominado).
 */
export type GrammarSession =
  | { mode: "level"; level: string; total: number; done: number }
  | { mode: "drill"; level: string; total: number; remaining: string[] }
  | { mode: "mastered"; level: string; total: number; done: number };

/** Check fallado acertado: se elimina del pool restante del drill. */
export function drillAnswered(
  remaining: string[],
  checkId: string,
  passed: boolean,
): string[] {
  if (!passed) return remaining;
  return remaining.filter((id) => id !== checkId);
}

/** Checks del drill ya acertados (progreso de la sesión). */
export function drillDone(session: GrammarSession): number {
  return session.mode === "drill" ? session.total - session.remaining.length : 0;
}

/** Checks respondidos en los modos de rotación (nivel / repasar lo aprendido). */
export function sessionDone(session: GrammarSession): number {
  return session.mode === "drill" ? drillDone(session) : session.done;
}

/** True cuando la sesión ha completado su objetivo (acabó la vuelta / drill). */
export function isSessionFinished(session: GrammarSession): boolean {
  if (session.mode === "drill") return session.remaining.length === 0;
  return session.done >= session.total;
}
