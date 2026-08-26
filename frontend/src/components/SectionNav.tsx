import type { ComponentType } from "react";
import {
  GrammarIcon,
  ListeningIcon,
  PronunciationIcon,
  ReadingIcon,
  SpeakingIcon,
  WritingIcon,
} from "./Icons";
import { SECTIONS, type Section } from "../utils/sections";
import type { EstimatedBands } from "../types/api";

interface SectionNavProps {
  section: Section;
  bands: EstimatedBands | null | undefined;
  onSelect: (section: Section) => void;
}

const SECTION_ICONS: Record<Section, ComponentType<{ size?: number }>> = {
  listening: ListeningIcon,
  speaking: SpeakingIcon,
  reading: ReadingIcon,
  writing: WritingIcon,
  grammar: GrammarIcon,
  pronunciation: PronunciationIcon,
};

export function SectionNav({ section, bands, onSelect }: SectionNavProps) {
  return (
    <nav className="section-nav" aria-label="Destrezas">
      {SECTIONS.map((s) => {
        const Icon = SECTION_ICONS[s.id];
        const active = section === s.id;
        const cefr = bands?.[s.id] || null;
        return (
          <button
            key={s.id}
            type="button"
            className={`section-nav-button${active ? " active" : ""}`}
            aria-pressed={active}
            onClick={() => onSelect(s.id)}
          >
            <span className="section-nav-icon">
              <Icon size={17} />
            </span>
            <span className="section-nav-label">{s.label}</span>
            {cefr && <span className="section-nav-cefr">{cefr}</span>}
          </button>
        );
      })}
    </nav>
  );
}
