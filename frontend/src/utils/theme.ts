export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "english-tutor.theme";

/**
 * Resuelve el tema inicial combinando un valor persistido y la preferencia
 * del sistema. Prioriza el valor guardado por el usuario cuando es válido;
 * en caso contrario cae a la preferencia del sistema. Siempre devuelve un
 * valor válido (`"light"` o `"dark"`).
 */
export function resolveInitialTheme(
  stored: string | null,
  system: Theme,
): Theme {
  if (stored === "light" || stored === "dark") return stored;
  return system;
}
