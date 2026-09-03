import { useI18n } from "../../hooks/useI18n";

const DOCS_BASE = "https://github.com/jvelasca/english-tutor";
const DEV_DOCS = `${DOCS_BASE}/blob/main/docs/DESARROLLO.md`;

/**
 * Ayuda general (ruta `help`): una guía breve de los tres mundos (INICIO /
 * FORMACIÓN / APRENDER) con preguntas frecuentes. No duplica la documentación
 * técnica: la enlaza (premisa #17). Conectar otro dispositivo vive en Ajustes →
 * Sistema, así que esta pantalla solo orienta hacia allí.
 */
export function HelpScreen() {
  const { t } = useI18n();

  const faqs = [
    { titleKey: "help.what.title", bodyKey: "help.what.body" },
    { titleKey: "help.start.title", bodyKey: "help.start.body" },
    { titleKey: "help.modes.title", bodyKey: "help.modes.body" },
    { titleKey: "help.course.title", bodyKey: "help.course.body" },
    { titleKey: "help.listening.title", bodyKey: "help.listening.body" },
    {
      titleKey: "help.troubleshooting.title",
      bodyKey: "help.troubleshooting.body",
      doc: DEV_DOCS,
    },
  ];

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
          {t("help.title")}
        </h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          {t("help.subtitle")}
        </p>
      </header>

      <div className="mt-6 flex flex-col gap-4">
        {faqs.map((faq) => (
          <section
            key={faq.titleKey}
            className="rounded-xl border border-border bg-card p-4"
          >
            <h2 className="text-base font-semibold text-foreground">
              {t(faq.titleKey)}
            </h2>
            <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
              {t(faq.bodyKey)}
            </p>
            {faq.doc && (
              <a
                className="mt-2 inline-block text-sm font-medium text-primary underline-offset-2 hover:underline"
                href={faq.doc}
                target="_blank"
                rel="noreferrer"
              >
                {t("help.viewDocs")}
              </a>
            )}
          </section>
        ))}
      </div>

      <section
        aria-label={t("help.connectTitle")}
        className="mt-4 rounded-xl border border-border bg-card p-4"
      >
        <h2 className="text-base font-semibold text-foreground">
          {t("help.connectTitle")}
        </h2>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          {t("help.connectBody")}
        </p>
      </section>

      <footer className="mt-8 text-center">
        <a
          className="text-sm font-medium text-primary underline-offset-2 hover:underline"
          href={DOCS_BASE}
          target="_blank"
          rel="noreferrer"
        >
          {t("help.documentation")}
        </a>
      </footer>
    </div>
  );
}
