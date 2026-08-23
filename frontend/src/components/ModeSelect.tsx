import { MODES } from "../utils/modes";
import type { TutorMode } from "../types/api";

interface ModeSelectProps {
  value: TutorMode;
  onChange: (mode: TutorMode) => void;
}

export function ModeSelect({ value, onChange }: ModeSelectProps) {
  return (
    <select
      className="mode-select"
      value={value}
      onChange={(e) => onChange(e.target.value as TutorMode)}
      title="Modo del tutor"
      aria-label="Modo del tutor"
    >
      {MODES.map((m) => (
        <option key={m.id} value={m.id}>
          {m.label}
        </option>
      ))}
    </select>
  );
}
