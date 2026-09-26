import { Layers, Search } from "lucide-react";
import { useCallback, useState } from "react";
import { useI18n } from "../../hooks/useI18n";
import { useDictionaryView } from "../../hooks/useDictionaryView";
import { useTabList } from "../../hooks/useTabList";
import { cn } from "../../lib/utils";
import { takePendingStudyFocus } from "../../utils/studyFocus";
import { DictionaryLookup } from "./DictionaryLookup";
import { FlashcardsScreen, type FlashcardsTab } from "./FlashcardsScreen";

/**
 * V3.85.0: dos pestañas. El inventario del léxico deja de ser una pestaña de
 * primer nivel («Personal») y pasa a ser la sub-pestaña «Mi léxico» de
 * Flashcards, que es donde vive el estudio. Una pestaña de primer nivel para
 * mirar y otra para trabajar.
 */
type DictionaryTab = "lookup" | "flashcards";

const TABS: {
  id: DictionaryTab;
  labelKey: string;
  Icon: typeof Search;
}[] = [
  { id: "lookup", labelKey: "dictionary.tabs.lookup", Icon: Search },
  {
    id: "flashcards",
    labelKey: "dictionary.tabs.flashcards",
    Icon: Layers,
  },
];

/** Ids estables (a nivel de módulo) para el roving tabindex del hook. */
const TAB_IDS = TABS.map((entry) => entry.id);

/**
 * Petición de estudio: qué mazo abrir en Flashcards. El `nonce` cambia en cada
 * petición para que un segundo clic vuelva a abrir la sesión aunque sea el mismo
 * mazo.
 */
interface StudyFocus {
  /** V3.84.0: mazo manual concreto al que saltar (si se eligió uno al añadir). */
  deckId: number | null;
  nonce: number;
}

const NO_FOCUS: StudyFocus = {
  deckId: null,
  nonce: 0,
};

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
 * V3.85.0: las tres pestañas de V3.78 pasan a DOS —Consultar · Flashcards— y el
 * inventario se convierte en la sub-pestaña «Mi léxico» de Flashcards. La
 * persistencia NO se migra: el valor `"personal"` sigue siendo válido y ahora
 * **proyecta** a Flashcards abierto en «Mi léxico», de modo que un valor guardado
 * antes de esta versión abre exactamente donde el alumno lo dejó. Al revés,
 * elegir «Mi léxico» vuelve a persistir `"personal"`; cualquier otra sub-pestaña
 * persiste `"flashcards"`. El diccionario incrustado en la práctica de rutas
 * (APRENDER → Vocabulario) sigue funcionando sin cambios vía `toPanelView`.
 */
export function DictionaryScreen({ userId }: { userId: string | null }) {
  const { t } = useI18n();
  const { view, setView } = useDictionaryView(userId);
  /**
   * V3.86.0: el salto desde el diccionario INCRUSTADO (APRENDER → Vocabulario)
   * cruza de pantalla y deja aquí el mazo elegido. Se consume en el montaje, una
   * sola vez: es un recado de un clic, no una preferencia. `nonce` a 1 para que
   * Flashcards lo aplique como un encargo nuevo.
   */
  const [focus, setFocus] = useState<StudyFocus>(() => {
    const pending = takePendingStudyFocus();
    return pending ? { deckId: pending.deckId, nonce: 1 } : NO_FOCUS;
  });
  /**
   * Sub-pestaña REAL de Flashcards. `view` solo guarda la proyección
   * (`"personal"` = léxico, `"flashcards"` = estudio), así que «Mazos»,
   * «Tarjetas» y «Estadísticas» no se pueden derivar de él: sin este estado,
   * pasar de «Mazos» a la pestaña Consultar y volver caería en «Estudiar». Se
   * inicializa desde el valor persistido para que un `"personal"` guardado
   * abra directamente en «Mi léxico».
   */
  const [flashcardsTab, setFlashcardsTab] = useState<FlashcardsTab>(() =>
    view === "personal" ? "lexicon" : "study",
  );

  const activeTab: DictionaryTab = view === "lookup" ? "lookup" : "flashcards";

  /** Persiste la sub-pestaña: «Mi léxico» es `"personal"`, el resto `"flashcards"`. */
  const changeFlashcardsTab = useCallback(
    (next: FlashcardsTab) => {
      setFlashcardsTab(next);
      setView(next === "lexicon" ? "personal" : "flashcards");
    },
    [setView],
  );

  /** Pestaña de primer nivel: recuerda la sub-pestaña de Flashcards al volver. */
  const selectTab = useCallback(
    (next: DictionaryTab) => {
      setView(
        next === "lookup"
          ? "lookup"
          : flashcardsTab === "lexicon"
            ? "personal"
            : "flashcards",
      );
    },
    [flashcardsTab, setView],
  );

  const { onKeyDown, register } = useTabList(TAB_IDS, activeTab, selectTab);

  /**
   * V3.84.0: salta a Flashcards desde el diccionario de consulta. Si el alta
   * archivó la palabra en un mazo manual, se abre ESE mazo; sin argumento, se
   * abre el automático (el comportamiento de V3.83.0).
   *
   * V3.85.0: el salto a estudio con una lista o un pack («Repasar» en «Mi
   * léxico») ya no pasa por aquí —ocurre dentro de `FlashcardsScreen`, que es
   * quien conoce el mazo automático—, así que el foco solo transporta el mazo
   * manual del alta.
   */
  const openFlashcards = useCallback(
    (deckId?: number) => {
      setFocus((prev) => ({
        deckId: deckId ?? null,
        nonce: prev.nonce + 1,
      }));
      setFlashcardsTab("study");
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
          className="bg-secondary mb-4 flex w-fit max-w-full flex-wrap items-center gap-1 rounded-md p-1"
          onKeyDown={onKeyDown}
        >
          {TABS.map((entry) => {
            const isActive = activeTab === entry.id;
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
                onClick={() => selectTab(entry.id)}
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
          id={`dictionary-panel-${activeTab}`}
          aria-labelledby={`dictionary-tab-${activeTab}`}
          tabIndex={0}
          className="min-h-0 flex-1 focus:outline-none"
        >
          {activeTab === "lookup" ? (
            /* V3.75.8: la pantalla ya trae su `h1` y su subtítulo, así que la
               vista de consulta no repite cabecera (antes había dos `h1` en la
               misma página) ni vuelve a aplicar el ancho y el relleno de
               página, que ya pone este contenedor. */
            <DictionaryLookup
              userId={userId}
              showHeader={false}
              /* V3.83.0: tras añadir (o si la palabra ya está en el léxico), el
                 panel ofrece estudiar. El destino es el modo Flashcards de esta
                 misma pantalla: el foco no persiste, es un salto de un clic.
                 V3.84.0: si el alta guardó la palabra en un mazo manual, se
                 abre ese mazo. */
              onOpenFlashcards={openFlashcards}
            />
          ) : (
            /* V3.85.0: Flashcards es el dueño de las cinco sub-pestañas y esta
               pantalla controla cuál está activa y qué valor se persiste. */
            <FlashcardsScreen
              userId={userId}
              focusDeckId={focus.deckId}
              focusNonce={focus.nonce}
              tab={flashcardsTab}
              onTabChange={changeFlashcardsTab}
            />
          )}
        </div>
      </div>
    </div>
  );
}
