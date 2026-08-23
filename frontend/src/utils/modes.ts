import type { TutorMode } from "../types/api";

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
