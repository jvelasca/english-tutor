import type { ComponentType } from "react";
import {
  GrammarIcon,
  ListeningIcon,
  PronunciationIcon,
  ReadingIcon,
  SpeakingIcon,
  WritingIcon,
} from "./Icons";
import type { Section } from "../utils/sections";
import { useI18n } from "../hooks/useI18n";

interface SectionNavProps {
  section: Section;
  onSelect: (section: Section) => void;
}

interface SectionEntry {
  id: Section;
  i18nKey: string;
}

// Cuatro destrezas primarias en la navegación; grammar y pronunciation son
// herramientas de apoyo (no compiten visualmente con las macro-destrezas).
const PRIMARY: SectionEntry[] = [
  { id: "listening", i18nKey: "skill.listening" },
  { id: "speaking", i18nKey: "skill.speaking" },
  { id: "reading", i18nKey: "skill.reading" },
  { id: "writing", i18nKey: "skill.writing" },
];

const SUPPORT: SectionEntry[] = [
  { id: "grammar", i18nKey: "skill.grammar" },
  { id: "pronunciation", i18nKey: "skill.pronunciation" },
];

const SECTION_ICONS: Record<Section, ComponentType<{ size?: number }>> = {
  listening: ListeningIcon,
  speaking: SpeakingIcon,
  reading: ReadingIcon,
  writing: WritingIcon,
  grammar: GrammarIcon,
  pronunciation: PronunciationIcon,
};

function SectionGroup({
  label,
  entries,
  section,
  onSelect,
}: {
  label: string;
  entries: SectionEntry[];
  section: Section;
  onSelect: (section: Section) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="section-nav__group">
      <span className="section-nav__group-label">{label}</span>
      <div className="section-nav__row">
        {entries.map((s) => {
          const Icon = SECTION_ICONS[s.id];
          const active = section === s.id;
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
              <span className="section-nav-label">{t(s.i18nKey)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function SectionNav({ section, onSelect }: SectionNavProps) {
  const { t } = useI18n();
  return (
    <nav className="section-nav" aria-label={t("nav.skills")}>
      <SectionGroup
        label={t("group.primary")}
        entries={PRIMARY}
        section={section}
        onSelect={onSelect}
      />
      <SectionGroup
        label={t("group.support")}
        entries={SUPPORT}
        section={section}
        onSelect={onSelect}
      />
    </nav>
  );
}
