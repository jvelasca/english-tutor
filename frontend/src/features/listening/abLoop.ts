/**
 * Máquina de estados PURA del bucle A/B del reproductor de listening (V3.52.1).
 *
 * El problema que resuelve: antes el estado React (`markStart`/`isLooping`) y el
 * segmento real del `AudioController` se mantenían por separado y podían
 * desincronizarse. Casos observados:
 *
 * - «Quitar marca» limpiaba el estado React pero NO llamaba a `clearLoop()`, así
 *   que el audio seguía en bucle sin indicarlo la UI.
 * - Al reanudar con el botón de reproducir se recargaba el audio y se perdía el
 *   bucle, pero la UI seguía mostrando «Repitiendo A → B».
 * - «Repetir palabra fallada» arrancaba un bucle invisible para la UI.
 *
 * Centralizar las transiciones aquí deja un único origen de verdad que el
 * componente aplica siempre al controller y al estado a la vez.
 */

/** Duración mínima de un segmento A/B para que sea reproducible (segundos). */
export const MIN_AB_LOOP_SECONDS = 0.05;

export interface AbLoopState {
  /** Instante A marcado (null = sin marca activa). */
  markStart: number | null;
  /** Instante B confirmado; solo existe con bucle armado. */
  loopEnd: number | null;
  /** Hay un segmento en bucle en el controller. */
  looping: boolean;
}

export const EMPTY_AB_LOOP: AbLoopState = {
  markStart: null,
  loopEnd: null,
  looping: false,
};

/** Redondea/valida un instante de audio (null si no es un número útil). */
function safeTime(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    return null;
  }
  return value;
}

/**
 * Alterna la marca A: sin marca la fija en `time`; con marca la quita y DESARMA
 * el bucle (el llamador debe aplicar `EMPTY_AB_LOOP` al controller).
 */
export function toggleMark(
  state: AbLoopState,
  time: number | null | undefined,
): AbLoopState {
  if (state.markStart !== null) return { ...EMPTY_AB_LOOP };
  const mark = safeTime(time);
  if (mark === null) return { ...state };
  return { markStart: mark, loopEnd: null, looping: false };
}

/**
 * Arma el bucle [A, `end`] con la marca actual. Devuelve `null` si no hay marca
 * válida o el segmento es demasiado corto (el llamador no toca nada).
 */
export function armLoop(
  state: AbLoopState,
  end: number | null | undefined,
): AbLoopState | null {
  const start = safeTime(state.markStart);
  const stop = safeTime(end);
  if (start === null || stop === null) return null;
  if (stop - start < MIN_AB_LOOP_SECONDS) return null;
  return { markStart: start, loopEnd: stop, looping: true };
}

/** Desarma el bucle y olvida la marca (equivale a «Quitar bucle»). */
export function clearLoop(): AbLoopState {
  return { ...EMPTY_AB_LOOP };
}

/**
 * Refleja en el estado un bucle armado FUERA de los botones A/B (p. ej.
 * «repetir palabra fallada»), para que la UI no oculte un bucle activo.
 */
export function loopFromSegment(
  start: number | null | undefined,
  end: number | null | undefined,
): AbLoopState {
  const from = safeTime(start);
  const to = safeTime(end);
  if (from === null || to === null || to - from < MIN_AB_LOOP_SECONDS) {
    return { ...EMPTY_AB_LOOP };
  }
  return { markStart: from, loopEnd: to, looping: true };
}

/** Límites [start, end] del bucle activo, o `null` si no hay bucle armado. */
export function loopBounds(state: AbLoopState): [number, number] | null {
  if (!state.looping || state.markStart === null || state.loopEnd === null) {
    return null;
  }
  return [state.markStart, state.loopEnd];
}

/** ¿El botón «Quitar bucle / Quitar marca» debe estar habilitado? */
export function canClear(state: AbLoopState): boolean {
  return state.markStart !== null || state.looping;
}
