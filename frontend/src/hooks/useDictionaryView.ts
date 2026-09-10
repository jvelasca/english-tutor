import { useCallback, useEffect, useState } from "react";
import { getSettings, saveSettings } from "../api/settings";
import {
  DEFAULT_DICTIONARY_VIEW,
  DICTIONARY_VIEW_STORAGE_KEY,
  dictionaryViewFromSettings,
  dictionaryViewToSettings,
  parseDictionaryView,
  type DictionaryView,
} from "../utils/dictionaryView";

function readStoredView(): DictionaryView {
  if (typeof window === "undefined") return DEFAULT_DICTIONARY_VIEW;
  try {
    return parseDictionaryView(window.localStorage.getItem(DICTIONARY_VIEW_STORAGE_KEY));
  } catch {
    return DEFAULT_DICTIONARY_VIEW;
  }
}

function writeStoredView(view: DictionaryView): void {
  try {
    window.localStorage.setItem(DICTIONARY_VIEW_STORAGE_KEY, view);
  } catch {
    /* almacenamiento no disponible: la vista se mantiene solo en memoria */
  }
}

/**
 * V3.39: vista activa del diccionario con persistencia doble.
 *
 * - Arranca de `localStorage` (inmediato, sin parpadeo y válido sin perfil);
 * - al cambiar de usuario hidrata desde `GET /api/settings` (la preferencia
 *   viaja con el perfil; el servidor manda si tiene un valor válido);
 * - al cambiar de vista escribe `localStorage` y `PUT /api/settings`.
 *
 * Misma firma que un `useState`: `{ view, setView }`.
 */
export function useDictionaryView(userId: string | null) {
  const [view, setViewState] = useState<DictionaryView>(readStoredView);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await getSettings(userId);
        if (cancelled) return;
        const fromServer = dictionaryViewFromSettings(res.settings);
        if (fromServer) {
          setViewState(fromServer);
          writeStoredView(fromServer);
        }
      } catch {
        /* sin preferencias guardadas todavía: se mantiene la vista local */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const setView = useCallback(
    (next: DictionaryView) => {
      setViewState(next);
      writeStoredView(next);
      if (userId) {
        void saveSettings(userId, dictionaryViewToSettings(next)).catch(() => {});
      }
    },
    [userId],
  );

  return { view, setView };
}
