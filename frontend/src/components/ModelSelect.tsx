import { useEffect, useRef, useState } from "react";
import { useI18n } from "../hooks/useI18n";

export function ModelSelect({
  model,
  models,
  favoriteModel,
  onSelect,
  onFavorite,
}: {
  model: string;
  models: string[];
  favoriteModel: string | null;
  onSelect: (m: string) => void;
  onFavorite: (m: string) => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const list = models.length ? models : [model];

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="model-picker" ref={ref}>
      <span className="model-picker-label">{t("settings.model")}:</span>
      <button
        type="button"
        className="model-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        title="Elegir modelo de Ollama"
      >
        <span>{model}</span>
        <CaretIcon />
      </button>
      {open && (
        <ul className="model-menu" role="listbox">
          {list.map((m) => (
            <li
              key={m}
              className="model-menu-item"
              role="option"
              aria-selected={m === model}
            >
              <button
                type="button"
                className="model-option"
                onClick={() => {
                  onSelect(m);
                  setOpen(false);
                }}
              >
                {m}
              </button>
              <button
                type="button"
                className={`model-star${favoriteModel === m ? " active" : ""}`}
                onClick={() => onFavorite(m)}
                aria-pressed={favoriteModel === m}
                title="Marcar como favorito y activo"
              >
                <StarIcon filled={favoriteModel === m} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

function CaretIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}
