import type { KeyboardEvent } from "react";
import { MicButton } from "./MicButton";
import { useI18n } from "../hooks/useI18n";

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
  const { t } = useI18n();
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
        placeholder={t("composer.placeholder")}
        rows={1}
        className="min-w-0"
        aria-label={t("composer.aria")}
      />
      <button className="send-button" onClick={onSend} disabled={disabled}>
        {t("composer.send")}
      </button>
    </footer>
  );
}
