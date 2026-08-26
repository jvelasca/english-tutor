export type Section =
  | "listening"
  | "speaking"
  | "reading"
  | "writing"
  | "grammar"
  | "pronunciation";

export interface SectionOption {
  id: Section;
  label: string;
}

export const SECTIONS: SectionOption[] = [
  { id: "listening", label: "Listening" },
  { id: "speaking", label: "Speaking" },
  { id: "reading", label: "Reading" },
  { id: "writing", label: "Writing" },
  { id: "grammar", label: "Grammar" },
  { id: "pronunciation", label: "Pronunciation" },
];

export const DEFAULT_SECTION: Section = "speaking";

export function isSection(value: unknown): value is Section {
  return SECTIONS.some((s) => s.id === value);
}
