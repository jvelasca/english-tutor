/**
 * Pila de pantallas de esta visita, para las flechas de atrás y adelante.
 *
 * El navegador ya guarda el hash. Esta pila solo dice si cada flecha tiene
 * a dónde ir: una visita nueva corta el tramo de adelante, y un atrás o
 * adelante del navegador mueve el índice si cae en el vecino.
 */
export interface HistoryTrail {
  entries: string[];
  index: number;
}

export function startTrail(path: string): HistoryTrail {
  return { entries: [path], index: 0 };
}

/** Visita nueva: se olvida lo que había por delante. */
export function pushTrail(trail: HistoryTrail, path: string): HistoryTrail {
  if (trail.entries[trail.index] === path) return trail;
  const entries = trail.entries.slice(0, trail.index + 1);
  entries.push(path);
  return { entries, index: entries.length - 1 };
}

/**
 * El hash cambió sin una visita nuestra (atrás o adelante del navegador).
 * Si no es el vecino, se toma como visita nueva.
 */
export function followTrail(trail: HistoryTrail, path: string): HistoryTrail {
  if (trail.entries[trail.index] === path) return trail;
  if (trail.index > 0 && trail.entries[trail.index - 1] === path) {
    return { entries: trail.entries, index: trail.index - 1 };
  }
  const next = trail.index + 1;
  if (next < trail.entries.length && trail.entries[next] === path) {
    return { entries: trail.entries, index: next };
  }
  return pushTrail(trail, path);
}

export function canGoBack(trail: HistoryTrail): boolean {
  return trail.index > 0;
}

export function canGoForward(trail: HistoryTrail): boolean {
  return trail.index < trail.entries.length - 1;
}
