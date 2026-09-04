/**
 * Máquina de sesión de las rutas de conversation (V3.10), espejo de la de
 * speaking/pronunciation: la sesión puede ser una vuelta del nivel ("level"),
 * un drill de diálogos fallidos ("drill") o un repaso de los dominados
 * ("mastered"). El "ítem" de la sesión es un `dialogue_id`.
 */
export type ConversationSession =
  | { mode: "level"; level: string; total: number; done: number }
  | { mode: "drill"; level: string; total: number; remaining: string[] }
  | { mode: "mastered"; level: string; total: number; done: number };

/** Elimina un id de diálogo del drill solo si se dominó en el intento. */
export function drillAnswered(
  remaining: string[],
  dialogueId: string,
  passed: boolean,
): string[] {
  if (!passed) return remaining;
  return remaining.filter((id) => id !== dialogueId);
}

/** Diálogos resueltos de una sesión (en drill, los quitados del remanente). */
export function drillDone(session: ConversationSession): number {
  if (session.mode !== "drill") return session.done;
  return session.total - session.remaining.length;
}

/** Progreso de la sesión (diálogos hechos del total). */
export function sessionDone(session: ConversationSession): number {
  return session.mode === "drill" ? drillDone(session) : session.done;
}

/** True cuando la sesión ha terminado (no quedan diálogos por conversar). */
export function isSessionFinished(session: ConversationSession): boolean {
  if (session.mode === "drill") return session.remaining.length === 0;
  return session.done >= session.total;
}
