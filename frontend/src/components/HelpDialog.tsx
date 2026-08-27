import { useEffect } from "react";
import { useI18n } from "../hooks/useI18n";

interface HelpSection {
  titleKey: string;
  bodyKey: string;
  doc?: string;
}

const DOCS_BASE = "https://github.com/jvelasca/english-tutor";

const SECTIONS: HelpSection[] = [
  { titleKey: "help.what.title", bodyKey: "help.what.body" },
  { titleKey: "help.start.title", bodyKey: "help.start.body" },
  { titleKey: "help.modes.title", bodyKey: "help.modes.body" },
  { titleKey: "help.course.title", bodyKey: "help.course.body" },
  { titleKey: "help.listening.title", bodyKey: "help.listening.body" },
  {
    titleKey: "help.troubleshooting.title",
    bodyKey: "help.troubleshooting.body",
    doc: `${DOCS_BASE}/blob/main/docs/DESARROLLO.md`,
  },
];

interface HelpDialogProps {
  onClose: () => void;
}

export function HelpDialog({ onClose }: HelpDialogProps) {
  const { t } = useI18n();
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
        aria-label={t("help.title")}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="dialog-header">
          <h2>{t("help.title")}</h2>
          <button
            type="button"
            className="dialog-close flex h-10 w-10 items-center justify-center"
            onClick={onClose}
            aria-label={t("common.close")}
          >
            ×
          </button>
        </header>

        <div className="dialog-body">
          {SECTIONS.map((s) => (
            <section key={s.titleKey} className="help-section">
              <h3>{t(s.titleKey)}</h3>
              <p>{t(s.bodyKey)}</p>
              {s.doc && (
                <a
                  className="help-link"
                  href={s.doc}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("help.viewDocs")}
                </a>
              )}
            </section>
          ))}
        </div>

        <footer className="dialog-footer help-footer">
          <span className="help-author">{t("help.author")}</span>
          <a
            className="dialog-secondary help-docs"
            href={DOCS_BASE}
            target="_blank"
            rel="noreferrer"
          >
            {t("help.documentation")}
          </a>
          <button type="button" className="dialog-primary" onClick={onClose}>
            {t("common.close")}
          </button>
        </footer>
      </div>
    </div>
  );
}
