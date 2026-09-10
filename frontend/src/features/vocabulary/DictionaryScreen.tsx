import { useState } from "react";
import { BookOpen, Search } from "lucide-react";
import { useI18n } from "../../hooks/useI18n";
import { cn } from "../../lib/utils";
import { PersonalDictionary } from "./PersonalDictionary";
import { DictionaryLookup } from "./DictionaryLookup";

type DictionaryView = "personal" | "lookup";

const VIEWS: {
  id: DictionaryView;
  labelKey: string;
  Icon: typeof BookOpen;
}[] = [
  { id: "personal", labelKey: "dictionary.tabs.personal", Icon: BookOpen },
  { id: "lookup", labelKey: "dictionary.tabs.lookup", Icon: Search },
];

/**
 * Pantalla dedicada del diccionario (ruta `/diccionario`, V3.38.1).
 *
 * Hasta V3.38 el diccionario solo era alcanzable como vista incrustada dentro
 * de Vocabulary (APRENDER). Es una herramienta AUXILIAR del núcleo, así que
 * ahora tiene su propio destino en la navegación (tras un separador) y esta
 * pantalla reutiliza las dos vistas ya existentes —diccionario personal y
 * consulta— sin duplicar lógica.
 */
export function DictionaryScreen({ userId }: { userId: string | null }) {
  const { t } = useI18n();
  const [view, setView] = useState<DictionaryView>("personal");

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-6 sm:px-6">
        <header className="mb-4 flex flex-col gap-1.5">
          <h1 className="text-lg font-bold tracking-tight">
            {t("dictionary.screen.title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("dictionary.screen.subtitle")}
          </p>
        </header>

        <div
          role="group"
          aria-label={t("dictionary.viewsLabel")}
          className="bg-secondary mb-4 flex w-fit items-center gap-1 rounded-md p-1"
        >
          {VIEWS.map((entry) => {
            const isActive = view === entry.id;
            const Icon = entry.Icon;
            return (
              <button
                key={entry.id}
                type="button"
                aria-pressed={isActive}
                onClick={() => setView(entry.id)}
                className={cn(
                  "inline-flex min-h-9 items-center gap-1.5 rounded px-3 text-xs font-semibold transition-colors",
                  isActive
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="size-3.5" aria-hidden="true" />
                {t(entry.labelKey)}
              </button>
            );
          })}
        </div>

        <div className="min-h-0 flex-1">
          {view === "personal" ? (
            <PersonalDictionary userId={userId} />
          ) : (
            <DictionaryLookup userId={userId} />
          )}
        </div>
      </div>
    </div>
  );
}
