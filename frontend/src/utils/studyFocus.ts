/**
 * V3.86.0: encargo de un solo salto del diccionario INCRUSTADO a la pantalla
 * central de Flashcards.
 *
 * El panel de APRENDER → Vocabulario no hospeda la sesión de estudio —el modo
 * `flashcards` se proyecta con `toPanelView`—, así que la salida «Estudiar en
 * Flashcards» cruza de pantalla: persiste la vista y navega a `#/diccionario`.
 *
 * El mazo elegido tiene que viajar con ella. Si se quedara por el camino, el
 * alumno aterrizaría en el mazo automático y creería que su tarjeta no entró
 * —que es exactamente la clase de fallo que esta release cierra—, y las dos
 * pantallas no comparten ningún estado. El encargo se deja aquí, es de UN solo
 * uso (al consumirlo se borra) y no toca ni `localStorage` ni los ajustes del
 * perfil: es un recado de un clic, no una preferencia.
 */

/** Mazo pedido por el salto. `null` significa «el automático, a propósito». */
export interface PendingStudyFocus {
  deckId: number | null;
}

let pending: PendingStudyFocus | null = null;

/** Deja anotado el mazo que debe abrir la pantalla central (`deckId` ausente = automático). */
export function setPendingStudyFocus(deckId?: number | null): void {
  pending = { deckId: typeof deckId === "number" ? deckId : null };
}

/**
 * Consume el encargo y lo borra. Devuelve `null` si no había ninguno.
 *
 * Se consume en el MONTAJE de la pantalla central, una sola vez: si quedara
 * vivo, una visita posterior abriría un mazo que nadie volvió a pedir.
 */
export function takePendingStudyFocus(): PendingStudyFocus | null {
  const value = pending;
  pending = null;
  return value;
}
