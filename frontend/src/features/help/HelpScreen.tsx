import { useI18n } from "../../hooks/useI18n";

const DOCS_BASE = "https://github.com/jvelasca/english-tutor";
const DEV_DOCS = `${DOCS_BASE}/blob/main/docs/DESARROLLO.md`;

/**
 * Autoría de la app (sección final de Ayuda). Mismo autor canónico que el
 * launcher (`launcher/core.py`): José Alberto Velasco.
 */
const AUTHOR_NAME = "J. Alberto Velasco";
const AUTHOR_EMAIL = "josealberto.vel@gmail.com";

interface HelpItem {
  titleKey: string;
  bodyKey: string;
  /** Enlace de documentación opcional asociado al ítem. */
  doc?: string;
}

interface HelpGroup {
  /** Clave i18n de la etiqueta del grupo (p. ej. «Empezar»). */
  labelKey: string;
  items: HelpItem[];
}

/**
 * Guía de la app por grupos (Ayuda, ruta `help`). Cada grupo agrupa tarjetas
 * pregunta→respuesta; no duplica la documentación técnica, la enlaza (premisa
 * #17). Conectar otro dispositivo vive en Ajustes → Sistema, así que la ayuda
 * solo orienta hacia allí.
 */
const GROUPS: HelpGroup[] = [
  {
    labelKey: "help.groupStart",
    items: [
      { titleKey: "help.what.title", bodyKey: "help.what.body" },
      { titleKey: "help.start.title", bodyKey: "help.start.body" },
      { titleKey: "help.modes.title", bodyKey: "help.modes.body" },
    ],
  },
  {
    labelKey: "help.groupSkills",
    items: [
      { titleKey: "help.listening.title", bodyKey: "help.listening.body" },
      { titleKey: "help.speaking.title", bodyKey: "help.speaking.body" },
      { titleKey: "help.vocabulary.title", bodyKey: "help.vocabulary.body" },
      { titleKey: "help.grammar.title", bodyKey: "help.grammar.body" },
    ],
  },
  {
    labelKey: "help.groupJourney",
    items: [
      { titleKey: "help.course.title", bodyKey: "help.course.body" },
      { titleKey: "help.progress.title", bodyKey: "help.progress.body" },
    ],
  },
  {
    labelKey: "help.groupSupport",
    items: [
      {
        titleKey: "help.connectTitle",
        bodyKey: "help.connectBody",
      },
      {
        titleKey: "help.troubleshooting.title",
        bodyKey: "help.troubleshooting.body",
        doc: DEV_DOCS,
      },
    ],
  },
];

export function HelpScreen() {
  const { t } = useI18n();

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

      {GROUPS.map((group) => (
        <section
          key={group.labelKey}
          aria-label={t(group.labelKey)}
          className="mt-6 flex flex-col gap-4"
        >
          <h2 className="px-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {t(group.labelKey)}
          </h2>
          {group.items.map((item) => (
            <article
              key={item.titleKey}
              className="rounded-xl border border-border bg-card p-4"
            >
              <h3 className="text-base font-semibold text-foreground">
                {t(item.titleKey)}
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                {t(item.bodyKey)}
              </p>
              {item.doc && (
                <a
                  className="mt-2 inline-block text-sm font-medium text-primary underline-offset-2 hover:underline"
                  href={item.doc}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("help.viewDocs")}
                </a>
              )}
            </article>
          ))}
        </section>
      ))}

      {/* Autor (V3.27): autoría y contacto de la app. */}
      <section
        aria-label={t("help.author")}
        className="mt-6 rounded-xl border border-border bg-card p-4"
      >
        <h2 className="text-base font-semibold text-foreground">
          {t("help.author")}
        </h2>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          {t("help.authorBody")}
        </p>
        <p className="mt-2 text-sm font-semibold text-foreground">
          {AUTHOR_NAME}
        </p>
        <a
          className="mt-0.5 inline-block text-sm font-medium text-primary underline-offset-2 hover:underline"
          href={`mailto:${AUTHOR_EMAIL}`}
        >
          {AUTHOR_EMAIL}
        </a>
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
