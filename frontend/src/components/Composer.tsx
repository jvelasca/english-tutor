import type { KeyboardEvent } from "react";
import { MicButton } from "./MicButton";

interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onTranscribed: (text: string) => void;
  disabled: boolean;
  busy: boolean;
}

export function Composer({
  value,
  onChange,
  onSend,
  onTranscribed,
  disabled,
  busy,
}: ComposerProps) {
  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  }

  return (
    <footer className="composer">
      <MicButton onTranscribed={onTranscribed} disabled={busy} />
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Escribe tu mensaje…"
        rows={1}
      />
      <button onClick={onSend} disabled={disabled}>
        Enviar
      </button>
    </footer>
  );
}
