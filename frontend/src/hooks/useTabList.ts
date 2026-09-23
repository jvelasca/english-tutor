import { useCallback, useRef, type KeyboardEvent } from "react";

/**
 * Semántica y teclado de un `role="tablist"` real (V3.80.1).
 *
 * Los dos selectores que parecían pestañas —los tres modos del diccionario y
 * las cuatro vistas de Flashcards— eran grupos de botones (`role="group"` +
 * `aria-pressed`) pintados como pestañas. Esta casa decidió que, si parecen
 * pestañas, lo sean también para un lector de pantalla: `tablist`/`tab`/
 * `tabpanel`, `aria-selected` y `aria-controls`.
 *
 * El hook aporta la mitad que las pestañas necesitan y es fácil de olvidar: el
 * **roving tabindex** (solo la activa es tabulable) y las flechas/Home/End.
 * El estado sigue viviendo en el contenedor, que es su dueño.
 *
 * La activación es automática al mover el foco (como las pestañas nativas del
 * navegador): no hay que pulsar Enter, que es lo que espera quien usa flechas.
 */
export function useTabList<T extends string>(
  ids: readonly T[],
  active: T,
  onSelect: (id: T) => void,
) {
  const refs = useRef<Partial<Record<T, HTMLButtonElement | null>>>({});

  const register = useCallback(
    (id: T) => (element: HTMLButtonElement | null) => {
      refs.current[id] = element;
    },
    [],
  );

  const onKeyDown = useCallback(
    (event: KeyboardEvent) => {
      const index = ids.indexOf(active);
      if (index < 0) return;
      let next: T | undefined;
      if (event.key === "ArrowRight" || event.key === "ArrowDown") {
        next = ids[(index + 1) % ids.length];
      } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
        next = ids[(index - 1 + ids.length) % ids.length];
      } else if (event.key === "Home") {
        next = ids[0];
      } else if (event.key === "End") {
        next = ids[ids.length - 1];
      }
      if (next === undefined || next === active) return;
      event.preventDefault();
      onSelect(next);
      refs.current[next]?.focus();
    },
    [active, ids, onSelect],
  );

  return { onKeyDown, register };
}
