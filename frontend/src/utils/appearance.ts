import type { Theme } from "./theme";

export type AccentId =
  | "indigo"
  | "violet"
  | "blue"
  | "teal"
  | "emerald"
  | "rose"
  | "amber";

export type FontScale = "small" | "medium" | "large";

export type Density = "compact" | "comfortable";

export interface AppearanceSettings {
  theme: Theme;
  accent: AccentId;
  fontScale: FontScale;
  density: Density;
}

export interface AccentOption {
  id: AccentId;
  label: string;
  swatch: string;
}

export interface ChoiceOption<T extends string> {
  id: T;
  label: string;
}

/** Colores de acento disponibles en el panel de apariencia. */
export const ACCENTS: AccentOption[] = [
  { id: "indigo", label: "Índigo", swatch: "#6366f1" },
  { id: "violet", label: "Violeta", swatch: "#a855f7" },
  { id: "blue", label: "Azul", swatch: "#3b82f6" },
  { id: "teal", label: "Turquesa", swatch: "#14b8a6" },
  { id: "emerald", label: "Esmeralda", swatch: "#10b981" },
  { id: "rose", label: "Rosa", swatch: "#f43f5e" },
  { id: "amber", label: "Ámbar", swatch: "#f59e0b" },
];

export const FONT_SCALES: ChoiceOption<FontScale>[] = [
  { id: "small", label: "Pequeño" },
  { id: "medium", label: "Normal" },
  { id: "large", label: "Grande" },
];

export const DENSITIES: ChoiceOption<Density>[] = [
  { id: "compact", label: "Compacto" },
  { id: "comfortable", label: "Cómodo" },
];

export const APPEARANCE_STORAGE_KEY = "english-tutor.appearance";

export const DEFAULT_APPEARANCE: AppearanceSettings = {
  theme: "dark",
  accent: "indigo",
  fontScale: "medium",
  density: "comfortable",
};

const ACCENT_IDS: readonly string[] = ACCENTS.map((a) => a.id);
const FONT_SCALE_IDS: readonly string[] = FONT_SCALES.map((f) => f.id);
const DENSITY_IDS: readonly string[] = DENSITIES.map((d) => d.id);

function isAccent(value: unknown): value is AccentId {
  return typeof value === "string" && ACCENT_IDS.includes(value);
}

function isFontScale(value: unknown): value is FontScale {
  return typeof value === "string" && FONT_SCALE_IDS.includes(value);
}

function isDensity(value: unknown): value is Density {
  return typeof value === "string" && DENSITY_IDS.includes(value);
}

function isTheme(value: unknown): value is Theme {
  return value === "light" || value === "dark";
}

/** Tema persistido válido, o `null` si no hay o es inválido. */
function readStoredTheme(raw: string | null | undefined): Theme | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return isTheme(parsed.theme) ? parsed.theme : null;
  } catch {
    return null;
  }
}

/**
 * Resuelve la apariencia inicial combinando un valor persistido (localStorage)
 * y la preferencia de tema del sistema. El tema solo usa el sistema cuando no
 * hay un tema persistido válido; el resto de campos cae al valor por defecto.
 */
export function resolveAppearance(
  storedRaw: string | null,
  systemTheme: Theme,
): AppearanceSettings {
  const stored = parseAppearance(storedRaw);
  return {
    theme: readStoredTheme(storedRaw) ?? systemTheme,
    accent: stored.accent,
    fontScale: stored.fontScale,
    density: stored.density,
  };
}

/** Parsea el JSON persistido de apariencia de forma tolerante (sin lanzar). */
export function parseAppearance(raw: string | null | undefined): AppearanceSettings {
  if (!raw) return { ...DEFAULT_APPEARANCE };
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return {
      theme: isTheme(parsed.theme) ? parsed.theme : DEFAULT_APPEARANCE.theme,
      accent: isAccent(parsed.accent) ? parsed.accent : DEFAULT_APPEARANCE.accent,
      fontScale: isFontScale(parsed.fontScale)
        ? parsed.fontScale
        : DEFAULT_APPEARANCE.fontScale,
      density: isDensity(parsed.density)
        ? parsed.density
        : DEFAULT_APPEARANCE.density,
    };
  } catch {
    return { ...DEFAULT_APPEARANCE };
  }
}

export function serializeAppearance(appearance: AppearanceSettings): string {
  return JSON.stringify(appearance);
}

/** Claves de settings (backend) que representan la apariencia de un usuario. */
export function appearanceToSettings(
  appearance: AppearanceSettings,
): Record<string, string> {
  return {
    theme: appearance.theme,
    accent: appearance.accent,
    font_scale: appearance.fontScale,
    density: appearance.density,
  };
}

/**
 * Extrae los campos de apariencia válidos de un mapa de settings del backend.
 * Devuelve un objeto parcial: solo los campos reconocidos y bien formados.
 */
export function appearanceFromSettings(
  settings: Record<string, string>,
): Partial<AppearanceSettings> {
  const result: Partial<AppearanceSettings> = {};
  if (isTheme(settings.theme)) result.theme = settings.theme;
  if (isAccent(settings.accent)) result.accent = settings.accent;
  if (isFontScale(settings.font_scale)) result.fontScale = settings.font_scale;
  if (isDensity(settings.density)) result.density = settings.density;
  return result;
}
