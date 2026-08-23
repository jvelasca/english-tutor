import { useCallback, useEffect, useState } from "react";
import {
  resolveInitialTheme,
  THEME_STORAGE_KEY,
  type Theme,
} from "../utils/theme";

function readSystemTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const prefersLight = window.matchMedia?.("(prefers-color-scheme: light)");
  return prefersLight?.matches ? "light" : "dark";
}

function readStoredTheme(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(THEME_STORAGE_KEY);
  } catch {
    return null;
  }
}

function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() =>
    resolveInitialTheme(readStoredTheme(), readSystemTheme()),
  );

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next: Theme = prev === "dark" ? "light" : "dark";
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, next);
      } catch {
        /* almacenamiento no disponible: el tema se mantiene solo en memoria */
      }
      return next;
    });
  }, []);

  return { theme, toggleTheme };
}
