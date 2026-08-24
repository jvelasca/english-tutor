import type { EstimatedBands, TutorMode } from "../types/api";

export interface ModeOption {
  id: TutorMode;
  label: string;
}

export const MODES: ModeOption[] = [
  { id: "conversation", label: "Conversación" },
  { id: "grammar", label: "Gramática" },
  { id: "exercises", label: "Ejercicios" },
  { id: "pronunciation", label: "Pronunciación" },
];

export function isTutorMode(value: string): value is TutorMode {
  return MODES.some((m) => m.id === value);
}

// Banda CEFR asociada a cada modo, para mostrar el nivel estimado en el badge.
const MODE_BAND: Record<TutorMode, keyof EstimatedBands> = {
  conversation: "fluency",
  grammar: "grammar",
  exercises: "vocabulary",
  pronunciation: "pronunciation",
};

export function modeCefrBand(mode: TutorMode): keyof EstimatedBands {
  return MODE_BAND[mode];
}

export function modeCefrLevel(
  mode: TutorMode,
  bands: EstimatedBands | null | undefined,
): string | null {
  if (!bands) return null;
  const level = bands[modeCefrBand(mode)];
  return level || null;
}
