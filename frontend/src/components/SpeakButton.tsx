import { useState } from "react";
import { speak } from "../api/voz";
import { useI18n } from "../hooks/useI18n";

export function SpeakButton({ text }: { text: string }) {
  const { t } = useI18n();
  const [loading, setLoading] = useState(false);

  async function onClick() {
    setLoading(true);
    try {
      await speak(text);
    } catch (e) {
      alert(t("speak.error") + (e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      type="button"
      className={`speak-button${loading ? " speaking" : ""}`}
      onClick={onClick}
      disabled={loading}
      title={t("speak.listen")}
      aria-label={t("speak.listen")}
      aria-busy={loading}
    >
      <SpeakerIcon />
    </button>
  );
}

function SpeakerIcon() {
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
    >
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
  );
}
