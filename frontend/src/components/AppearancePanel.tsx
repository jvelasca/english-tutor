import { useEffect } from "react";
import {
  ACCENTS,
  DENSITIES,
  FONT_SCALES,
  type AppearanceSettings,
} from "../utils/appearance";
import type { Theme } from "../utils/theme";

const THEME_OPTIONS: { id: Theme; label: string }[] = [
  { id: "light", label: "Claro" },
  { id: "dark", label: "Oscuro" },
];

interface AppearancePanelProps {
  appearance: AppearanceSettings;
  onUpdate: (patch: Partial<AppearanceSettings>) => void;
  onReset: () => void;
  onClose: () => void;
}

export function AppearancePanel({
  appearance,
  onUpdate,
  onReset,
  onClose,
}: AppearancePanelProps) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Apariencia"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="dialog-header">
          <h2>Apariencia</h2>
          <button
            type="button"
            className="dialog-close"
            onClick={onClose}
            aria-label="Cerrar"
          >
            ×
          </button>
        </header>

        <div className="dialog-body">
          <div className="field">
            <span className="field-label">Tema</span>
            <div className="seg" role="group" aria-label="Tema">
              {THEME_OPTIONS.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  className={`seg-option${appearance.theme === o.id ? " active" : ""}`}
                  onClick={() => onUpdate({ theme: o.id })}
                  aria-pressed={appearance.theme === o.id}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <span className="field-label">Color de acento</span>
            <div className="accent-grid" role="group" aria-label="Color de acento">
              {ACCENTS.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  className={`accent-swatch${
                    appearance.accent === a.id ? " active" : ""
                  }`}
                  style={{ background: a.swatch }}
                  onClick={() => onUpdate({ accent: a.id })}
                  title={a.label}
                  aria-label={a.label}
                  aria-pressed={appearance.accent === a.id}
                />
              ))}
            </div>
          </div>

          <div className="field">
            <span className="field-label">Tamaño de letra</span>
            <div className="seg" role="group" aria-label="Tamaño de letra">
              {FONT_SCALES.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  className={`seg-option${
                    appearance.fontScale === o.id ? " active" : ""
                  }`}
                  onClick={() => onUpdate({ fontScale: o.id })}
                  aria-pressed={appearance.fontScale === o.id}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <span className="field-label">Densidad</span>
            <div className="seg" role="group" aria-label="Densidad">
              {DENSITIES.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  className={`seg-option${
                    appearance.density === o.id ? " active" : ""
                  }`}
                  onClick={() => onUpdate({ density: o.id })}
                  aria-pressed={appearance.density === o.id}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <footer className="dialog-footer">
          <button type="button" className="dialog-secondary" onClick={onReset}>
            Restablecer
          </button>
          <button type="button" className="dialog-primary" onClick={onClose}>
            Listo
          </button>
        </footer>
      </div>
    </div>
  );
}
