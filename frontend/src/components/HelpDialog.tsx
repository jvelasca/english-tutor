import { useEffect } from "react";

interface HelpSection {
  title: string;
  body: string;
  doc?: string;
}

const DOCS_BASE = "https://github.com/jvelasca/english-tutor";

const SECTIONS: HelpSection[] = [
  {
    title: "¿Qué es English Tutor?",
    body: "Un profesor de inglés que conversa contigo por texto o voz. Funciona 100% en tu ordenador, sin Internet ni cuentas: tu privacidad está garantizada.",
  },
  {
    title: "Cómo empezar",
    body: "Elige tu perfil arriba a la derecha y escribe o pulsa el micrófono. Puedes cambiar de modo de práctica en cualquier momento.",
  },
  {
    title: "Modos de práctica",
    body: "Conversación (charlar libre), Gramática (corregir frases), Ejercicios (práctica guiada) y Pronunciación (hablar y medir tu acento).",
  },
  {
    title: "Academia CEFR",
    body: "Un recorrido por niveles (A1, A2, B1…) con objetivos, evaluaciones rápidas y un examen final. Avanzas nivel a nivel a tu ritmo.",
  },
  {
    title: "Comprensión auditiva",
    body: "Escucha una frase, responde la pregunta y supera cada nivel. Tus aciertos se guardan por perfil y te indican cuándo avanzas.",
  },
  {
    title: "Problemas frecuentes",
    body: "Si el profesor no responde, asegúrate de que Ollama esté arrancado. Los detalles técnicos y la guía completa están en la documentación.",
    doc: `${DOCS_BASE}/blob/main/docs/DESARROLLO.md`,
  },
];

interface HelpDialogProps {
  onClose: () => void;
}

export function HelpDialog({ onClose }: HelpDialogProps) {
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
        className="dialog dialog--help"
        role="dialog"
        aria-modal="true"
        aria-label="Ayuda"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="dialog-header">
          <h2>Ayuda</h2>
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
          {SECTIONS.map((s) => (
            <section key={s.title} className="help-section">
              <h3>{s.title}</h3>
              <p>{s.body}</p>
              {s.doc && (
                <a
                  className="help-link"
                  href={s.doc}
                  target="_blank"
                  rel="noreferrer"
                >
                  Ver en la documentación
                </a>
              )}
            </section>
          ))}
        </div>

        <footer className="dialog-footer help-footer">
          <span className="help-author">
            Autor: José Alberto Velasco · josealberto.vel@gmail.com
          </span>
          <a
            className="dialog-secondary help-docs"
            href={DOCS_BASE}
            target="_blank"
            rel="noreferrer"
          >
            Documentación
          </a>
          <button type="button" className="dialog-primary" onClick={onClose}>
            Cerrar
          </button>
        </footer>
      </div>
    </div>
  );
}
