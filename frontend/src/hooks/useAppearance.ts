import { useCallback, useEffect, useState } from "react";
import { getSettings, saveSettings } from "../api/settings";
import {
  APPEARANCE_STORAGE_KEY,
  DEFAULT_APPEARANCE,
  appearanceFromSettings,
  appearanceToSettings,
  resolveAppearance,
  type AppearanceSettings,
} from "../utils/appearance";
import { THEME_STORAGE_KEY, type Theme } from "../utils/theme";

function readSystemTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const prefersLight = window.matchMedia?.("(prefers-color-scheme: light)");
  return prefersLight?.matches ? "light" : "dark";
}

function readStoredAppearance(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(APPEARANCE_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStoredAppearance(appearance: AppearanceSettings): void {
  try {
    window.localStorage.setItem(APPEARANCE_STORAGE_KEY, JSON.stringify(appearance));
  } catch {
    /* almacenamiento no disponible: la apariencia se mantiene solo en memoria */
  }
}

/** Tema heredado de la versión anterior (solo por compatibilidad). */
function readLegacyTheme(): Theme | null {
  if (typeof window === "undefined") return null;
  try {
    const v = window.localStorage.getItem(THEME_STORAGE_KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

function applyAppearance(appearance: AppearanceSettings): void {
  const root = document.documentElement;
  root.setAttribute("data-theme", appearance.theme);
  root.setAttribute("data-accent", appearance.accent);
  root.setAttribute("data-font", appearance.fontScale);
  root.setAttribute("data-density", appearance.density);
}

export function useAppearance(userId: string | null) {
  const [appearance, setAppearance] = useState<AppearanceSettings>(() => {
    const stored = readStoredAppearance();
    const resolved = resolveAppearance(stored, readSystemTheme());
    // Si no hay apariencia persistida pero sí un tema antiguo, se respeta.
    if (!stored) {
      const legacy = readLegacyTheme();
      if (legacy) resolved.theme = legacy;
    }
    return resolved;
  });

  useEffect(() => {
    applyAppearance(appearance);
  }, [appearance]);

  // Carga las preferencias de apariencia persistidas por usuario (backend).
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await getSettings(userId);
        if (cancelled) return;
        const fromServer = appearanceFromSettings(res.settings ?? {});
        if (Object.keys(fromServer).length > 0) {
          setAppearance((prev) => {
            const next = { ...prev, ...fromServer };
            writeStoredAppearance(next);
            return next;
          });
        }
      } catch {
        /* sin preferencias guardadas todavía */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const update = useCallback(
    (patch: Partial<AppearanceSettings>) => {
      setAppearance((prev) => {
        const next = { ...prev, ...patch };
        writeStoredAppearance(next);
        if (userId) {
          void saveSettings(userId, appearanceToSettings(next)).catch(() => {});
        }
        return next;
      });
    },
    [userId],
  );

  const reset = useCallback(() => {
    update({ ...DEFAULT_APPEARANCE, theme: readSystemTheme() });
  }, [update]);

  return { appearance, update, reset };
}
