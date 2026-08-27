import type { HandsFreeStatus } from "../hooks/useHandsFree";

interface HandsFreeToggleProps {
  enabled: boolean;
  status: HandsFreeStatus;
  onToggle: () => void;
}

const STATUS_LABELS: Record<HandsFreeStatus, string> = {
  idle: "Inactivo",
  listening: "Escuchando…",
  transcribing: "Transcribiendo…",
  thinking: "Pensando…",
  speaking: "Hablando…",
};

export function HandsFreeToggle({
  enabled,
  status,
  onToggle,
}: HandsFreeToggleProps) {
  return (
    <div className="hands-free">
      <button
        type="button"
        className={`hands-free-toggle${enabled ? " active" : ""}`}
        onClick={onToggle}
        aria-pressed={enabled}
        aria-label={
          enabled ? "Desactivar modo manos libres" : "Activar modo manos libres"
        }
        title={
          enabled ? "Desactivar modo manos libres" : "Activar modo manos libres"
        }
      >
        <MicIcon />
        <span className="hands-free-label">Manos libres</span>
      </button>
      {enabled && (
        <span
          className={`hands-free-status max-sm:hidden! hands-free-status--${status}`}
          role="status"
          aria-live="polite"
        >
          {STATUS_LABELS[status]}
        </span>
      )}
    </div>
  );
}

function MicIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}
