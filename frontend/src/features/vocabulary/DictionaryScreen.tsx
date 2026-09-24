import { BookOpen, Layers, Search } from "lucide-react";
import { useCallback, useState } from "react";
import { useI18n } from "../../hooks/useI18n";
import { useDictionaryView } from "../../hooks/useDictionaryView";
import { useTabList } from "../../hooks/useTabList";
import type { DictionaryView } from "../../utils/dictionaryView";
import { cn } from "../../lib/utils";
import { PersonalDictionary } from "./PersonalDictionary";
import { DictionaryLookup } from "./DictionaryLookup";
import { FlashcardsScreen } from "./FlashcardsScreen";

const VIEWS: {
  id: DictionaryView;
  labelKey: string;
  Icon: typeof BookOpen;
}[] = [
  { id: "lookup", labelKey: "dictionary.tabs.lookup", Icon: Search },
  { id: "personal", labelKey: "dictionary.tabs.personal", Icon: BookOpen },
  {
    id: "flashcards",
    labelKey: "dictionary.tabs.flashcards",
    Icon: Layers,
  },
];

/** Ids estables (a nivel de módulo) para el roving tabindex del hook. */
const VIEW_IDS = VIEWS.map((entry) => entry.id);

/** Petición de estudio: qué mazo/léxico abrir en Flashcards y con qué etiqueta. */
interface StudyFocus {
  collectionId: number | null;
  label: string;
  /** Cambia en cada petición para que un segundo clic vuelva a abrir la sesión. */
  nonce: number;
}

const NO_FOCUS: StudyFocus = { collectionId: null, label: "", nonce: 0 };

/**
 * Pantalla dedicada del diccionario (ruta `/diccionario`, V3.38.1).
 *
 * Hasta V3.38 el diccionario solo era alcanzable como vista incrustada dentro
 * de Vocabulary (APRENDER). Es una herramienta AUXILIAR del núcleo, así que
 * ahora tiene su propio destino en la navegación (tras un separador) y esta
 * pantalla reutiliza las vistas ya existentes sin duplicar lógica.
 *
 * V3.39: la vista activa se persiste (localStorage + settings por usuario) con
 * `useDictionaryView`, así que al volver a abrir la app se recuerda la última
 * pestaña usada.
 *
 * V3.78.0: los dos modos pasan a TRES, en el orden en que se usan —Consultar ·
 * Personal · Flashcards— y la pantalla se convierte en el punto de encuentro
 * entre posesión y estudio: PERSONAL ya no estudia, gestiona, y su botón
 * «Estudiar» (igual que el de una lista o un pack en «Añadir») cambia a
 * Flashcards con el foco puesto. El foco vive aquí, no en la vista, porque es
 * un encargo de una sola pantalla y no una preferencia que deba persistirse.
 */
export function DictionaryScreen({ userId }: { userId: string | null }) {
  const { t } = useI18n();
  const { view, setView } = useDictionaryView(userId);
  const [focus, setFocus] = useState<StudyFocus>(NO_FOCUS);
  const { onKeyDown, register } = useTabList(VIEW_IDS, view, setView);

  const openStudy = useCallback(
    (opts: { collectionId?: number | null; label?: string } = {}) => {
      setFocus((prev) => ({
        collectionId: opts.collectionId ?? null,
        label: opts.label ?? "",
        nonce: prev.nonce + 1,
      }));
      setView("flashcards");
    },
    [setView],
  );

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
          role="tablist"
          aria-label={t("dictionary.viewsLabel")}
          className="bg-secondary mb-4 flex w-fit items-center gap-1 rounded-md p-1"
          onKeyDown={onKeyDown}
        >
          {VIEWS.map((entry) => {
            const isActive = view === entry.id;
            const Icon = entry.Icon;
            return (
              <button
                key={entry.id}
                type="button"
                role="tab"
                id={`dictionary-tab-${entry.id}`}
                aria-selected={isActive}
                aria-controls={`dictionary-panel-${entry.id}`}
                tabIndex={isActive ? 0 : -1}
                ref={register(entry.id)}
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

        <div
          role="tabpanel"
          id={`dictionary-panel-${view}`}
          aria-labelledby={`dictionary-tab-${view}`}
          tabIndex={0}
          className="min-h-0 flex-1 focus:outline-none"
        >
          {view === "lookup" ? (
            /* V3.75.8: la pantalla ya trae su `h1` y su subtítulo, así que la
               vista de consulta no repite cabecera (antes había dos `h1` en la
               misma página) ni vuelve a aplicar el ancho y el relleno de
               página, que ya pone este contenedor. */
            <DictionaryLookup
              userId={userId}
              showHeader={false}
              /* V3.83.0: tras añadir (o si la palabra ya está en el léxico), el
                 panel ofrece estudiar. El destino es el modo Flashcards de esta
                 misma pantalla: el foco no persiste, es un salto de un clic. */
              onOpenFlashcards={() => setView("flashcards")}
            />
          ) : view === "personal" ? (
            /* V3.77.2: la pantalla es la única dueña del layout (un solo `h1`
               y un solo contenedor de ancho). V3.78.0: PERSONAL ya no estudia;
               `onStudy` es el puente al modo Flashcards. */
            <PersonalDictionary
              userId={userId}
              showHeader={false}
              onStudy={openStudy}
            />
          ) : (
            <FlashcardsScreen
              userId={userId}
              focusCollectionId={focus.collectionId}
              focusCollectionLabel={focus.label}
              focusNonce={focus.nonce}
            />
          )}
        </div>
      </div>
    </div>
  );
}
