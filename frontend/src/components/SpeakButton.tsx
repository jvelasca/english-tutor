import { useState } from "react";
import { speak } from "../api/voz";

export function SpeakButton({ text }: { text: string }) {
  const [loading, setLoading] = useState(false);

  async function onClick() {
    setLoading(true);
    try {
      await speak(text);
    } catch (e) {
      alert(`Error al reproducir: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      type="button"
      className="speak-button"
      onClick={onClick}
      disabled={loading}
      title="Escuchar respuesta"
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
