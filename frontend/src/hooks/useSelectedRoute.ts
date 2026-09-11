import { useCallback, useEffect, useState } from "react";
import { getSettings, saveSettings } from "../api/settings";
import {
  parseSelectedRouteLevel,
  selectedRouteFromSettings,
  selectedRouteToSettings,
  SELECTED_ROUTE_SETTING_KEY,
  SELECTED_ROUTE_STORAGE_KEY,
  type SelectedRouteLevel,
} from "../utils/selectedRoute";

function readStoredLevel(): SelectedRouteLevel | null {
  if (typeof window === "undefined") return null;
  try {
    return parseSelectedRouteLevel(
      window.localStorage.getItem(SELECTED_ROUTE_STORAGE_KEY),
    );
  } catch {
    return null;
  }
}

function writeStoredLevel(level: SelectedRouteLevel | null): void {
  try {
    if (level) {
      window.localStorage.setItem(SELECTED_ROUTE_STORAGE_KEY, level);
    } else {
      window.localStorage.removeItem(SELECTED_ROUTE_STORAGE_KEY);
    }
  } catch {
    /* almacenamiento no disponible: la selección se mantiene en memoria */
  }
}

/**
 * V3.48.1: ruta CEFR seleccionada con persistencia doble.
 *
 * - Arranca de `localStorage` (inmediato, sin parpadeo y válido sin perfil);
 * - al cambiar de usuario hidrata desde `GET /api/settings` (la preferencia
 *   viaja con el perfil; el servidor manda si tiene un valor válido);
 * - al seleccionar escribe `localStorage` y `PUT /api/settings`.
 *
 * `selectedLevel === null` significa «Auto» (nivel recomendado por el motor).
 */
export function useSelectedRoute(userId: string | null) {
  const [selectedLevel, setLevelState] =
    useState<SelectedRouteLevel | null>(readStoredLevel);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await getSettings(userId);
        if (cancelled) return;
        // Solo se aplica si el perfil declara la clave (aunque sea «Auto» con
        // cadena vacía); si no consta, se respeta la selección local.
        if (!(SELECTED_ROUTE_SETTING_KEY in res.settings)) return;
        const fromServer = selectedRouteFromSettings(res.settings);
        setLevelState(fromServer);
        writeStoredLevel(fromServer);
      } catch {
        /* sin preferencias guardadas todavía: se mantiene la selección local */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const setSelectedLevel = useCallback(
    (next: SelectedRouteLevel | null) => {
      setLevelState(next);
      writeStoredLevel(next);
      if (userId) {
        void saveSettings(userId, selectedRouteToSettings(next)).catch(
          () => {},
        );
      }
    },
    [userId],
  );

  return { selectedLevel, setSelectedLevel };
}
