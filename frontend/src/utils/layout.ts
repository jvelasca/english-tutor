export interface LayoutState {
  sidebarWidth: number;
  rightWidth: number;
}

export const LAYOUT_DEFAULTS: LayoutState = {
  sidebarWidth: 280,
  rightWidth: 380,
};

export const SIDEBAR_MIN = 200;
export const SIDEBAR_MAX = 460;
export const RIGHT_MIN = 300;
// Máximo amplio para que en monitores de escritorio el panel de análisis pueda
// ensancharse lo suficiente como para ver todas sus pestañas sin scroll. En
// pantallas estrechas el asa se oculta y el panel pasa a drawer (≤1024px), y
// PracticeView aplica además un tope relativo al viewport.
export const RIGHT_MAX = 900;

function clampNumber(
  value: unknown,
  min: number,
  max: number,
  fallback: number,
): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.min(max, Math.max(min, value));
}

export function clampSidebar(value: number): number {
  return clampNumber(value, SIDEBAR_MIN, SIDEBAR_MAX, LAYOUT_DEFAULTS.sidebarWidth);
}

export function clampRight(value: number): number {
  return clampNumber(value, RIGHT_MIN, RIGHT_MAX, LAYOUT_DEFAULTS.rightWidth);
}

/** Parsea el layout persistido tolerando valores inválidos o corruptos. */
export function parseLayout(raw: string | null | undefined): LayoutState {
  if (!raw) return { ...LAYOUT_DEFAULTS };
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return {
      sidebarWidth: clampSidebar(parsed.sidebarWidth as number),
      rightWidth: clampRight(parsed.rightWidth as number),
    };
  } catch {
    return { ...LAYOUT_DEFAULTS };
  }
}

export function serializeLayout(layout: LayoutState): string {
  return JSON.stringify(layout);
}
