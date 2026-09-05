/**
 * Máquina de sesión compartida de las rutas de práctica (V3.13, P2.1).
 *
 * Consolida los seis módulos espejo (`grammarSession`, `vocabularySession`,
 * `pronunciationSession`, `conversationSession`, …) que antes duplicaban el
 * mismo autómata con nombres renombrados. Tres modos de sesión focalizada:
 *
 * - `level`:    rotación "toda la vuelta" por los ítems de la ruta.
 * - `drill`:    repetir los fallados (intentados y nunca acertados) hasta
 *               acertarlos todos; `remaining` son los ids aún por acertar.
 * - `mastered`: "repasar lo aprendido", rotación solo sobre los ítems ya
 *               acertados (consolidar/re-exponer lo dominado).
 *
 * Cada módulo por destreza re-exporta estos tipos/funciones para no romper sus
 * imports y tests existentes (las páginas y paneles se migran por oleadas).
 */
export type RouteSessionMode = "level" | "drill" | "mastered";

export type RouteSession =
  | { mode: "level"; level: string; total: number; done: number }
  | { mode: "drill"; level: string; total: number; remaining: string[] }
  | { mode: "mastered"; level: string; total: number; done: number };

/** Ítem fallado acertado: se elimina del pool restante del drill. */
export function drillAnswered(
  remaining: string[],
  itemId: string,
  passed: boolean,
): string[] {
  if (!passed) return remaining;
  return remaining.filter((id) => id !== itemId);
}

/** Ítems del drill ya acertados (progreso de la sesión). */
export function drillDone(session: RouteSession): number {
  return session.mode === "drill" ? session.total - session.remaining.length : 0;
}

/** Ítems respondidos en los modos de rotación (nivel / repasar lo aprendido). */
export function sessionDone(session: RouteSession): number {
  return session.mode === "drill" ? drillDone(session) : session.done;
}

/** True cuando la sesión ha completado su objetivo (acabó la vuelta / drill). */
export function isSessionFinished(session: RouteSession): boolean {
  if (session.mode === "drill") return session.remaining.length === 0;
  return session.done >= session.total;
}
