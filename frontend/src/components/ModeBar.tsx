import type { ReactNode } from "react";
import { MODES, modeCefrLevel } from "../utils/modes";
import type { EstimatedBands, TutorMode } from "../types/api";

export type AppView = "chat" | "academy";

interface ModeBarProps {
  mode: TutorMode;
  view: AppView;
  bands: EstimatedBands | null | undefined;
  onSelectMode: (mode: TutorMode) => void;
  onSelectAcademy: () => void;
}

const MODE_ICONS: Record<TutorMode, ReactNode> = {
  conversation: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  grammar: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 6h16M4 12h16M4 18h10" />
    </svg>
  ),
  exercises: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  ),
  pronunciation: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2 10v4h4l5 5V5L6 10H2z" />
      <path d="M16 8a5 5 0 0 1 0 8" />
      <path d="M19 5a9 9 0 0 1 0 14" />
    </svg>
  ),
};

function AcademyIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M22 9L12 2 2 9l10 7 10-7z" />
      <path d="M6 10.5V16c0 1.5 2.7 3 6 3s6-1.5 6-3v-5.5" />
    </svg>
  );
}

export function ModeBar({
  mode,
  view,
  bands,
  onSelectMode,
  onSelectAcademy,
}: ModeBarProps) {
  return (
    <nav className="mode-bar" aria-label="Secciones de la app">
      {MODES.map((m) => {
        const active = view === "chat" && mode === m.id;
        const cefr = modeCefrLevel(m.id, bands);
        return (
          <button
            key={m.id}
            type="button"
            className={`mode-bar-button${active ? " active" : ""}`}
            aria-pressed={active}
            onClick={() => onSelectMode(m.id)}
          >
            <span className="mode-bar-icon">{MODE_ICONS[m.id]}</span>
            <span className="mode-bar-label">{m.label}</span>
            {cefr && <span className="mode-bar-cefr">{cefr}</span>}
          </button>
        );
      })}
      <button
        type="button"
        className={`mode-bar-button mode-bar-academy${
          view === "academy" ? " active" : ""
        }`}
        aria-pressed={view === "academy"}
        onClick={onSelectAcademy}
      >
        <span className="mode-bar-icon">
          <AcademyIcon />
        </span>
        <span className="mode-bar-label">Academy</span>
      </button>
    </nav>
  );
}
