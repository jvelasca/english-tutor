/**
 * Modo Flashcards del diccionario (V3.78.0): la ÚNICA superficie de estudio.
 *
 * Cinco subpestañas, en el orden en que se usan:
 *
 * - **Estudiar**: el banco (todas, un nivel o un mazo), los contadores de ese
 *   ámbito y una sola lección —profunda si la palabra es nueva, corta si ya
 *   está en seguimiento—.
 * - **Mi léxico** (V3.85.0): el inventario que antes era la pestaña PERSONAL
 *   del diccionario (buscador, filtros, estadísticas, añadir).
 * - **Mazos**: el mazo automático (todo el léxico, no editable ni borrable) y
 *   los manuales, con sus límites.
 * - **Tarjetas**: navegador y CRUD de las tarjetas de un mazo manual.
 * - **Estadísticas**: repasos por día, acierto y previsión.
 *
 * El contenedor pide la cola del ámbito y cierra cada palabra (`complete`):
 * `WordLesson` pinta los pasos y la nota. El mazo elegido sigue siendo uno
 * solo para Tarjetas, Mazos y el ámbito «Por mazo».
 *
 * V3.80.0 — **el mazo es UNA selección, no una por pestaña.** Antes `deckId`
 * vivía en Estudiar/Estadísticas y `CardsTab` tenía el suyo, que además
 * arrancaba en `manual[0]` (el primero por orden alfabético, no el que el
 * alumno acababa de crear). Eso es exactamente lo que producía el «creo un mazo
 * y no sé cómo añadir palabras»: el mazo recién creado no era el que Tarjetas
 * miraba. Ahora la selección se sube a la pantalla —como en Anki: el mazo es
 * global, no un estado por pestaña— y crear un mazo salta a Tarjetas con él
 * seleccionado y el campo del anverso enfocado.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3,
  BookOpen,
  CalendarClock,
  Eraser,
  Library,
  Layers,
  Loader2,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
} from "lucide-react";
import {
  addFlashcardsBulk,
  createFlashcardDeck,
  createVocabularyCard,
  deleteFlashcardDeck,
  deleteVocabularyCard,
  completeStudyLesson,
  enrollVocabCollection,
  getFlashcardStats,
  getStudyQueue,
  listFlashcardDecks,
  listVocabCollections,
  listVocabularyCards,
  updateFlashcardDeck,
  updateVocabularyCard,
} from "../../api/vocabulary";
import type {
  FlashcardCard,
  FlashcardDeck,
  FlashcardDeckDeleteResult,
  FlashcardDecks,
  FlashcardStats,
  StudyConfig,
  StudyQueue,
  StudyQueueMode,
  StudyScope,
  VocabCollection,
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { useTabList } from "../../hooks/useTabList";
import { getStudyConfig, saveStudyConfig } from "../../api/study";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { InfoDisclosure } from "../../components/InfoDisclosure";
import { LoadingNotice } from "../../components/LoadingNotice";
import { cn } from "../../lib/utils";
import { LexiconInventory } from "./LexiconInventory";
import { WordLesson } from "./wordLesson";

const STUDY_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"] as const;

const INPUT =
  "rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground";

/**
 * V3.88.0: icono de espera para los botones que hoy solo se deshabilitaban.
 * Sustituye al icono de la acción (o lo acompaña) mientras la petición vuela,
 * de modo que un botón apagado sin más no se lea como «roto».
 */
function BusyIcon() {
  return <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />;
}

export type FlashcardsTab = "study" | "lexicon" | "decks" | "cards" | "stats";

const TABS: { id: FlashcardsTab; labelKey: string; Icon: typeof Layers }[] = [
  // V3.85.0: «Mi léxico» (el inventario que vivía en la pestaña PERSONAL) entra
  // como sub-pestaña, y el icono de Estudiar pasa a `CalendarClock`: `Layers`
  // identifica mejor «Tarjetas» y así los cinco iconos no se repiten.
  { id: "study", labelKey: "flashcards.tabs.study", Icon: CalendarClock },
  { id: "lexicon", labelKey: "dictionary.myLexicon", Icon: BookOpen },
  { id: "decks", labelKey: "flashcards.tabs.decks", Icon: Library },
  { id: "cards", labelKey: "flashcards.tabs.cards", Icon: Layers },
  { id: "stats", labelKey: "flashcards.tabs.stats", Icon: BarChart3 },
];

/** Ids estables (a nivel de módulo) para el roving tabindex del hook. */
const TAB_IDS = TABS.map((entry) => entry.id);

/** Filtro por colección: solo aplica al mazo automático. */
interface CollectionFilter {
  id: number;
  label: string;
}

interface FlashcardsScreenProps {
  userId: string | null;
  /** Lista o pack con el que abrir el estudio (desde «Mis listas»/packs). */
  focusCollectionId?: number | null;
  focusCollectionLabel?: string;
  /** V3.84.0: mazo manual concreto al que saltar (desde el alta del diccionario). */
  focusDeckId?: number | null;
  /** Cambia en cada petición de estudio, para reabrir aunque sea el mismo foco. */
  focusNonce?: number;
  /**
   * V3.85.0: sub-pestaña activa. La pantalla pasa a estar CONTROLADA porque su
   * padre (`DictionaryScreen`) tiene que poder abrirla directamente en «Mi
   * léxico» cuando el valor persistido es el antiguo `"personal"`, y porque el
   * padre es quien decide qué valor se guarda al navegar. Sin `tab` funciona en
   * modo libre (uso interno de tests), con estado propio.
   */
  tab?: FlashcardsTab;
  onTabChange?: (tab: FlashcardsTab) => void;
}

export function FlashcardsScreen({
  userId,
  focusCollectionId = null,
  focusCollectionLabel = "",
  focusDeckId = null,
  focusNonce = 0,
  tab: controlledTab,
  onTabChange,
}: FlashcardsScreenProps) {
  const { t } = useI18n();
  const [internalTab, setInternalTab] = useState<FlashcardsTab>("study");
  const tab = controlledTab ?? internalTab;
  const setTab = useCallback(
    (next: FlashcardsTab) => {
      setInternalTab(next);
      onTabChange?.(next);
    },
    [onTabChange],
  );
  const { onKeyDown, register } = useTabList(TAB_IDS, tab, setTab);
  const [decks, setDecks] = useState<FlashcardDecks | null>(null);
  const [deckId, setDeckId] = useState<number | null>(null);
  const [collection, setCollection] = useState<CollectionFilter | null>(null);
  const [autoStart, setAutoStart] = useState(false);
  const [reloadNonce, setReloadNonce] = useState(0);
  const [error, setError] = useState(false);
  /**
   * V3.80.0: cuántas veces se ha pedido «abre Tarjetas listo para escribir».
   * Sube al crear un mazo y al pulsar «Añadir tarjetas»; Tarjetas lo usa para
   * enfocar el anverso y declarar qué hacer ahora. Un nonce y no un booleano
   * porque dos peticiones seguidas deben volver a enfocar.
   */
  const [addCardsNonce, setAddCardsNonce] = useState(0);

  /** Abre Tarjetas con `id` seleccionado y el campo del anverso listo. */
  const openCardsFor = useCallback(
    (id: number) => {
      setDeckId(id);
      setCollection(null);
      setTab("cards");
      setAddCardsNonce((n) => n + 1);
    },
    [setTab],
  );

  /**
   * Abre Estudiar con un mazo (y, si procede, filtrado por una lista o pack) y
   * arranca la sesión. Es el camino que comparten «Estudiar» de una fila de mazo
   * y «Estudiar» de un mazo listo: la misma cola, el mismo motor.
   */
  const openStudy = useCallback(
    (id: number, filter: CollectionFilter | null) => {
      setDeckId(id);
      setCollection(filter);
      setAutoStart(true);
      setTab("study");
    },
    [setTab],
  );

  /**
   * V3.85.0: «Mis listas» y los packs se estudian en el mazo AUTOMÁTICO filtrado
   * por la colección —son sus palabras, no una copia—, igual que hace una fila
   * de mazo listo en la sub-pestaña Mazos. Vive aquí y no en
   * `LexiconInventory` porque el salto necesita el mazo automático, que solo
   * esta pantalla conoce.
   */
  const studyCollection = useCallback(
    (opts: { collectionId: number; label: string }) => {
      openStudy(decks?.auto_deck_id ?? 0, {
        id: opts.collectionId,
        label: opts.label,
      });
    },
    [decks?.auto_deck_id, openStudy],
  );

  const loadDecks = useCallback(async () => {
    if (!userId) return;
    setError(false);
    try {
      const data = await listFlashcardDecks(userId);
      setDecks(data);
      setDeckId((current) => {
        if (current != null && data.decks.some((d) => d.id === current)) {
          return current;
        }
        return data.auto_deck_id;
      });
    } catch {
      setError(true);
      setDecks(null);
    }
  }, [userId]);

  useEffect(() => {
    void loadDecks();
  }, [loadDecks]);

  // V3.78.0: llegada desde «Mis listas»/packs o desde el botón «Estudiar» de
  // Personal. El foco NO se persiste: es un encargo de un solo salto, no una
  // preferencia, así que vive en el estado del contenedor y muere al salir.
  useEffect(() => {
    if (focusNonce <= 0) return;
    setTab("study");
    if (focusDeckId != null) {
      // V3.84.0: el alta del diccionario eligió un mazo manual concreto: se abre
      // ESE mazo, no el automático. Sin filtro de colección (el filtro es cosa
      // del mazo automático).
      setDeckId(focusDeckId);
      setCollection(null);
    } else {
      setDeckId(decks?.auto_deck_id ?? 0);
      setCollection(
        focusCollectionId != null
          ? { id: focusCollectionId, label: focusCollectionLabel }
          : null,
      );
    }
    setAutoStart(true);
    // `decks` se lee pero no debe re-disparar el efecto: el foco se aplica una
    // vez por petición (focusNonce), no cada vez que llega la lista de mazos.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusNonce]);

  const reload = useCallback(() => setReloadNonce((n) => n + 1), []);

  return (
    <div className="flex min-h-0 flex-col gap-4">
      <div
        role="tablist"
        aria-label={t("flashcards.viewsLabel")}
        className="flex items-center gap-1 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:flex-wrap sm:overflow-x-visible sm:pb-0"
        onKeyDown={onKeyDown}
      >
        {TABS.map((entry) => {
          const Icon = entry.Icon;
          const active = tab === entry.id;
          return (
            <button
              key={entry.id}
              type="button"
              role="tab"
              id={`flashcards-tab-${entry.id}`}
              aria-selected={active}
              aria-controls={`flashcards-panel-${entry.id}`}
              tabIndex={active ? 0 : -1}
              ref={register(entry.id)}
              onClick={() => setTab(entry.id)}
              className={cn(
                "inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-md px-2.5 text-xs font-semibold transition-colors",
                active
                  ? "bg-secondary text-foreground"
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
        id={`flashcards-panel-${tab}`}
        aria-labelledby={`flashcards-tab-${tab}`}
        tabIndex={0}
        className="focus:outline-none"
      >
        {tab === "lexicon" ? (
          /* V3.85.0: el inventario que vivía en la pestaña PERSONAL. Se resuelve
             ANTES de los estados de error/perfil porque no depende de la carga
             de mazos: un fallo al listar mazos no puede tumbar «Mi léxico».
             Sin cabecera propia (`showHeader={false}`): el `h1` y el ancho los
             pone `DictionaryScreen`, igual que con `DictionaryLookup`. */
          <LexiconInventory
            userId={userId}
            showHeader={false}
            onStudyCollection={studyCollection}
          />
        ) : error ? (
        <Card className="gap-2 p-4">
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            {t("dictionary.loadError")}
            <button
              type="button"
              onClick={() => void loadDecks()}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium hover:border-primary/50"
            >
              <RefreshCw className="size-3.5" aria-hidden="true" />
              {t("common.retry")}
            </button>
          </p>
        </Card>
      ) : !userId ? (
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">{t("dictionary.noProfile")}</p>
        </Card>
      ) : tab === "study" ? (
        <StudyTab
          userId={userId}
          decks={decks}
          deckId={deckId}
          onPick={setDeckId}
          collection={collection}
          autoStart={autoStart}
          onOpenTab={setTab}
          onAutoStarted={() => setAutoStart(false)}
          onClearCollection={() => setCollection(null)}
          reloadNonce={reloadNonce}
          onAddCards={openCardsFor}
          onExit={() => {
            setAutoStart(false);
            reload();
          }}
        />
      ) : tab === "decks" ? (
        <DecksTab
          userId={userId}
          decks={decks}
          reloadNonce={reloadNonce}
          onChanged={() => {
            void loadDecks();
            reload();
          }}
          onAddCards={openCardsFor}
          onDeckCreated={(id) => {
            // V3.80.0: el mazo recién creado pasa a ser LA selección y se salta
            // a Tarjetas con el anverso enfocado. Antes se creaba y el alumno se
            // quedaba en Mazos sin saber cómo meterle palabras.
            void loadDecks();
            openCardsFor(id);
            reload();
          }}
          onStudyDeck={(id) => {
            openStudy(id, null);
          }}
          onStudyCollection={(id, label) => {
            // Un mazo listo se estudia en el mazo AUTOMÁTICO filtrado por el
            // pack: son sus palabras, no una copia. No se duplica contenido.
            openStudy(decks?.auto_deck_id ?? 0, { id, label });
          }}
        />
      ) : tab === "cards" ? (
        <CardsTab
          userId={userId}
          decks={decks}
          deckId={deckId}
          onPick={setDeckId}
          reloadNonce={reloadNonce}
          addCardsNonce={addCardsNonce}
          onGoToDecks={() => setTab("decks")}
        />
      ) : (
        <StatsTab userId={userId} decks={decks} deckId={deckId} onPick={setDeckId} />
      )}
      </div>
    </div>
  );
}

/** Selector de mazo, compartido por Estudiar y Estadísticas. */
function DeckSelect({
  decks,
  value,
  onChange,
}: {
  decks: FlashcardDecks | null;
  value: number | null;
  onChange: (id: number) => void;
}) {
  const { t } = useI18n();
  return (
    <select
      aria-label={t("flashcards.study.deck")}
      value={value ?? ""}
      onChange={(e) => onChange(Number(e.target.value))}
      className={cn(INPUT, "w-full sm:w-64")}
    >
      {(decks?.decks ?? []).map((deck) => (
        <option key={deck.id} value={deck.id}>
          {deck.is_auto ? t("flashcards.decks.auto") : deck.name}
        </option>
      ))}
    </select>
  );
}

function DeckLabel({ deck }: { deck: FlashcardDeck }) {
  const { t } = useI18n();
  return <>{deck.is_auto ? t("flashcards.decks.auto") : deck.name}</>;
}

// --- Estudiar ---------------------------------------------------------------

/** Defectos del panel cuando la cola aún no ha traído su `study_config`. */
const STUDY_CONFIG_FALLBACK: StudyConfig = {
  direction: "en-es",
  mode: "recognition",
  hints: "off",
  difficulty: "auto",
  words_per_day: 20,
  required_facets: [],
  configured: false,
};

const REQUIRED_FACET_OPTIONS = [
  ["pronunciation", "flashcards.study.requirePronunciation"],
  ["context", "flashcards.study.requireContext"],
  ["senses", "flashcards.study.requireSenses"],
  ["related", "flashcards.study.requireRelated"],
] as const;

/**
 * Configuración de estudio (V3.87.0 · FASE 2, incremento 1), **plegada** tras el
 * disparador «...» (V3.87.1).
 *
 * Cuatro decisiones, no un panel de control: en qué dirección se pregunta
 * (EN↔ES), si se reconoce o se produce, qué ayuda se ve antes de voltear y
 * cuánta carga entra. Cada cambio se guarda en el perfil y recarga la cola; la
 * sesión en curso no se reescribe por detrás.
 *
 * Arranca **cerrado**: en la pestaña Estudiar lo que el alumno viene a pulsar son
 * las dos acciones de estudio, y cuatro selectores abiertos por defecto empujaban
 * esos botones fuera de la primera pantalla del móvil. La divulgación reutiliza
 * `InfoDisclosure` con `content="options"` para que el disparador sea el «...»
 * que en esta app ya significa «abre para configurar» (V3.75.7), y así no hay que
 * inventar una segunda convención para lo mismo.
 */
function StudyConfigPanel({
  config,
  onChange,
}: {
  config: StudyConfig | null;
  onChange: (patch: Partial<Omit<StudyConfig, "configured">>) => void;
}) {
  const { t } = useI18n();
  const value = config ?? STUDY_CONFIG_FALLBACK;
  return (
    <InfoDisclosure
      label={t("flashcards.study.configTitle")}
      content="options"
      align="end"
      id="study-config-panel"
    >
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
          {t("flashcards.study.direction")}
          <select
            value={value.direction}
            onChange={(e) =>
              onChange({ direction: e.target.value as StudyConfig["direction"] })
            }
            className={cn(INPUT, "w-full")}
          >
            <option value="en-es">{t("flashcards.study.directionEnEs")}</option>
            <option value="es-en">{t("flashcards.study.directionEsEn")}</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
          {t("flashcards.study.mode")}
          <select
            value={value.mode}
            onChange={(e) =>
              onChange({ mode: e.target.value as StudyConfig["mode"] })
            }
            className={cn(INPUT, "w-full")}
          >
            <option value="recognition">
              {t("flashcards.study.modeRecognition")}
            </option>
            <option value="production">
              {t("flashcards.study.modeProduction")}
            </option>
            <option value="mixed">{t("flashcards.study.modeMixed")}</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
          {t("flashcards.study.hints")}
          <select
            value={value.hints}
            onChange={(e) =>
              onChange({ hints: e.target.value as StudyConfig["hints"] })
            }
            className={cn(INPUT, "w-full")}
          >
            <option value="off">{t("flashcards.study.hintsOff")}</option>
            <option value="definition">
              {t("flashcards.study.hintsDefinition")}
            </option>
            <option value="mnemonic">
              {t("flashcards.study.hintsMnemonic")}
            </option>
            <option value="all">{t("flashcards.study.hintsAll")}</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
          {t("flashcards.study.difficulty")}
          <select
            value={value.difficulty}
            onChange={(e) =>
              onChange({
                difficulty: e.target.value as StudyConfig["difficulty"],
              })
            }
            className={cn(INPUT, "w-full")}
          >
            <option value="gentle">{t("flashcards.study.difficultyGentle")}</option>
            <option value="auto">{t("flashcards.study.difficultyAuto")}</option>
            <option value="intensive">
              {t("flashcards.study.difficultyIntensive")}
            </option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
          {t("flashcards.study.wordsToday")}
          <input
            type="number"
            min={1}
            max={200}
            aria-label={t("flashcards.study.wordsToday")}
            defaultValue={value.words_per_day}
            key={value.words_per_day}
            onBlur={(e) => {
              const parsed = Number.parseInt(e.target.value, 10);
              if (!Number.isFinite(parsed)) return;
              onChange({ words_per_day: Math.max(1, Math.min(200, parsed)) });
            }}
            className={cn(INPUT, "w-full")}
          />
        </label>
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="text-[11px] font-medium text-foreground">
          {t("flashcards.study.requiredTitle")}
        </legend>
        <p className="text-[11px] text-muted-foreground">
          {t("flashcards.study.meaningAlways")}
        </p>
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          {REQUIRED_FACET_OPTIONS.map(([name, labelKey]) => (
            <label key={name} className="inline-flex items-center gap-2 text-[11px]">
              <input
                type="checkbox"
                checked={value.required_facets.includes(name)}
                onChange={() => {
                  const next = value.required_facets.includes(name)
                    ? value.required_facets.filter((facet) => facet !== name)
                    : [...value.required_facets, name];
                  onChange({ required_facets: next });
                }}
              />
              {t(labelKey)}
            </label>
          ))}
        </div>
      </fieldset>
      <p className="text-[11px] leading-relaxed text-muted-foreground">
        {t("flashcards.study.configHint")}
      </p>
    </InfoDisclosure>
  );
}

function StudyTab({
  userId,
  decks,
  deckId,
  onPick,
  collection,
  autoStart,
  onAutoStarted,
  onClearCollection,
  reloadNonce,
  onAddCards,
  onExit,
  onOpenTab,
}: {
  userId: string;
  decks: FlashcardDecks | null;
  deckId: number | null;
  onPick: (id: number) => void;
  collection: CollectionFilter | null;
  autoStart: boolean;
  onAutoStarted: () => void;
  onClearCollection: () => void;
  reloadNonce: number;
  onAddCards: (id: number) => void;
  onExit: () => void;
  onOpenTab: (tab: FlashcardsTab) => void;
}) {
  const { t } = useI18n();
  const autoId = decks?.auto_deck_id ?? 0;
  const deck = deckId ?? autoId;
  const isAuto = deck === autoId;
  const [scope, setScope] = useState<StudyScope>(
    () => (autoStart && !isAuto && !collection ? "deck" : "all"),
  );
  const [pick, setPick] = useState<StudyQueueMode>("pending");
  const [level, setLevel] = useState("A1");
  const [queue, setQueue] = useState<StudyQueue | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [studying, setStudying] = useState(false);
  const [sessionNonce, setSessionNonce] = useState(0);
  const [studyConfig, setStudyConfig] = useState<StudyConfig | null>(null);
  const requestId = useRef(0);

  const launchScope: StudyScope = collection ? "all" : !isAuto && autoStart ? "deck" : scope;

  useEffect(() => {
    if (!autoStart) return;
    const next: StudyScope = collection ? "all" : !isAuto ? "deck" : "all";
    setScope(next);
    setPick("pending");
  }, [autoStart, collection, isAuto]);

  const wantedCollection =
    scope === "deck" && !isAuto ? null : collection?.id ?? null;

  const load = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    setError(false);
    try {
      const data = await getStudyQueue(userId, {
        scope,
        mode: pick,
        level: scope === "level" ? level : null,
        deckId: scope === "deck" ? deck : 0,
        collectionId: wantedCollection,
      });
      if (id !== requestId.current) return null;
      setQueue(data);
      return data;
    } catch {
      if (id === requestId.current) {
        setError(true);
        setQueue(null);
      }
      return null;
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [userId, scope, pick, level, deck, wantedCollection]);

  useEffect(() => {
    void load();
  }, [load, reloadNonce]);

  useEffect(() => {
    if (queue?.study_config) {
      setStudyConfig(queue.study_config);
      return;
    }
    let alive = true;
    void (async () => {
      try {
        const config = await getStudyConfig(userId);
        if (alive) setStudyConfig(config);
      } catch {
        /* defectos */
      }
    })();
    return () => {
      alive = false;
    };
  }, [queue?.study_config, userId]);

  const changeStudyConfig = useCallback(
    async (patch: Partial<Omit<StudyConfig, "configured">>) => {
      try {
        setStudyConfig(await saveStudyConfig(userId, patch));
        await load();
      } catch {
        setError(true);
      }
    },
    [userId, load],
  );

  const queueMatches =
    queue != null &&
    queue.scope === scope &&
    queue.mode === pick &&
    (scope !== "level" || queue.level === level) &&
    (scope !== "deck" || queue.deck_id === deck) &&
    (queue.collection_id ?? null) === wantedCollection;

  useEffect(() => {
    if (!autoStart || loading || !queueMatches || !queue) return;
    if (scope !== launchScope) return;
    onAutoStarted();
    if (queue.items.length > 0) {
      setStudying(true);
      setSessionNonce((n) => n + 1);
    }
  }, [autoStart, loading, queueMatches, queue, onAutoStarted, scope, launchScope]);

  const deckName = useMemo(() => {
    if (scope !== "deck") return t("flashcards.study.wholeDictionary");
    const found = decks?.decks.find((item) => item.id === deck);
    return found?.is_auto ? t("flashcards.decks.auto") : found?.name ?? "";
  }, [scope, decks, deck, t]);

  const scopeTitle =
    scope === "level" ? level : scope === "deck" ? deckName : t("flashcards.study.scopeAll");

  if (studying && queue && queue.items.length > 0) {
    return (
      <WordLesson
        key={sessionNonce}
        userId={userId}
        items={queue.items}
        deckName={deckName}
        onComplete={async (close) => {
          await completeStudyLesson(userId, {
            item_id: close.item_id,
            grade: close.grade,
            translation: close.translation,
            facets: close.facets,
          });
        }}
        onExit={() => {
          setStudying(false);
          onExit();
        }}
      />
    );
  }

  const items = queueMatches ? queue?.items ?? [] : [];
  const total = queueMatches ? queue?.total ?? 0 : 0;

  return (
    <Card className="gap-5 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {t("flashcards.study.scopeLabel")}
          </p>
          <h2 className="text-xl font-semibold tracking-tight">{scopeTitle}</h2>
          <p className="max-w-prose text-xs leading-relaxed text-muted-foreground">
            {t("flashcards.study.hint")}
          </p>
        </div>
        <StudyConfigPanel
          config={studyConfig}
          onChange={(patch) => void changeStudyConfig(patch)}
        />
      </div>

      <div
        className="grid grid-cols-3 gap-1 rounded-xl bg-secondary p-1"
        role="group"
        aria-label={t("flashcards.study.scopeLabel")}
      >
        {(
          [
            ["all", "flashcards.study.scopeAll"],
            ["level", "flashcards.study.scopeLevel"],
            ["deck", "flashcards.study.scopeDeck"],
          ] as const
        ).map(([id, labelKey]) => (
          <button
            key={id}
            type="button"
            aria-pressed={scope === id}
            onClick={() => setScope(id)}
            className={cn(
              "min-h-11 rounded-lg px-2 py-2 text-sm",
              scope === id
                ? "bg-background font-semibold text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t(labelKey)}
          </button>
        ))}
      </div>

      {scope === "level" ? (
        <div
          className="flex flex-wrap gap-2"
          role="group"
          aria-label={t("flashcards.study.levelChips")}
        >
          {STUDY_LEVELS.map((code) => (
            <button
              key={code}
              type="button"
              aria-pressed={level === code}
              onClick={() => setLevel(code)}
              className={cn(
                "min-h-11 rounded-full border px-3 py-2 text-sm",
                level === code
                  ? "border-primary bg-primary/10 font-semibold text-primary"
                  : "border-border",
              )}
            >
              {code}
            </button>
          ))}
        </div>
      ) : null}

      {scope === "deck" ? <DeckSelect decks={decks} value={deck} onChange={onPick} /> : null}

      <div
        className="grid grid-cols-3 gap-1 rounded-xl bg-secondary p-1"
        role="group"
        aria-label={t("flashcards.study.pickLabel")}
      >
        {(
          [
            ["pending", "flashcards.study.pickPending"],
            ["failed", "flashcards.study.pickFailed"],
            ["all", "flashcards.study.pickAll"],
          ] as const
        ).map(([id, labelKey]) => (
          <button
            key={id}
            type="button"
            aria-pressed={pick === id}
            onClick={() => setPick(id)}
            className={cn(
              "min-h-11 rounded-lg px-2 py-2 text-sm",
              pick === id
                ? "bg-background font-semibold text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t(labelKey)}
          </button>
        ))}
      </div>

      {collection && scope !== "deck" ? (
        <span className="inline-flex items-center gap-2 rounded-md bg-secondary px-2 py-1 text-xs">
          {t("flashcards.study.filtered").replace("{name}", collection.label)}
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground"
            onClick={onClearCollection}
          >
            {t("flashcards.study.clearFilter")}
          </button>
        </span>
      ) : null}

      <dl className="grid grid-cols-2 overflow-hidden rounded-xl border border-border sm:grid-cols-5">
        {(
          [
            ["flashcards.study.statTotal", queueMatches ? queue?.total : null, false],
            ["flashcards.study.statStudied", queueMatches ? queue?.studied : null, false],
            ["flashcards.study.statLearned", queueMatches ? queue?.learned : null, false],
            ["flashcards.study.statDue", queueMatches ? queue?.due : null, true],
            ["flashcards.study.statTimes", queueMatches ? queue?.times_studied : null, false],
          ] as const
        ).map(([labelKey, value, accent]) => (
          <div
            key={labelKey}
            className={cn(
              "flex flex-col gap-1 border-border/70 px-3 py-3 [&:nth-child(n+3)]:border-t sm:border-t-0 sm:[&:not(:first-child)]:border-l",
              accent && "bg-primary/10",
            )}
          >
            <dt className="text-[11px] text-muted-foreground">{t(labelKey)}</dt>
            <dd className="text-2xl font-semibold tabular-nums tracking-tight">
              {loading && !queueMatches ? "…" : String(value ?? 0)}
            </dd>
          </div>
        ))}
      </dl>

      {error ? (
        <Button type="button" size="sm" variant="outline" onClick={() => void load()}>
          <RefreshCw className="size-3.5" aria-hidden="true" />
          {t("common.retry")}
        </Button>
      ) : loading && !queue ? (
        <LoadingNotice className="text-[11px]" />
      ) : items.length > 0 ? (
        <Button
          type="button"
          size="lg"
          className="w-full sm:w-auto"
          onClick={() => {
            setSessionNonce((n) => n + 1);
            setStudying(true);
          }}
        >
          {t("flashcards.study.start").replace("{n}", String(items.length))}
        </Button>
      ) : !loading && queueMatches && total === 0 && scope === "deck" && !isAuto ? (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">{t("flashcards.study.emptyDeck")}</p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="w-fit"
            onClick={() => onAddCards(deck)}
          >
            <Plus className="size-3.5" aria-hidden="true" />
            {t("flashcards.study.addCards")}
          </Button>
        </div>
      ) : !loading && queueMatches && total === 0 ? (
        <p className="text-sm text-muted-foreground">{t("flashcards.study.emptyAuto")}</p>
      ) : !loading && queueMatches && pick === "failed" ? (
        <p className="text-sm text-muted-foreground">{t("flashcards.study.emptyFailed")}</p>
      ) : !loading && queueMatches ? (
        <p className="text-sm text-muted-foreground">{t("flashcards.study.empty")}</p>
      ) : null}

      <div
        className="flex items-center gap-1 border-t border-border/70 pt-3"
        role="group"
        aria-label={t("flashcards.study.shortcuts")}
      >
        {(
          [
            ["lexicon", "dictionary.myLexicon", BookOpen],
            ["decks", "flashcards.tabs.decks", Library],
            ["cards", "flashcards.tabs.cards", Layers],
            ["stats", "flashcards.tabs.stats", BarChart3],
          ] as const
        ).map(([id, labelKey, Icon]) => (
          <button
            key={id}
            type="button"
            aria-label={t(labelKey)}
            title={t(labelKey)}
            onClick={() => onOpenTab(id)}
            className="inline-flex size-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground"
          >
            <Icon className="size-4" aria-hidden="true" />
          </button>
        ))}
      </div>
    </Card>
  );
}

// --- Mazos ------------------------------------------------------------------

function DecksTab({
  userId,
  decks,
  reloadNonce,
  onChanged,
  onStudyDeck,
  onAddCards,
  onDeckCreated,
  onStudyCollection,
}: {
  userId: string;
  decks: FlashcardDecks | null;
  reloadNonce: number;
  onChanged: () => void;
  onStudyDeck: (id: number) => void;
  /** V3.80.0: ir a Tarjetas con ese mazo seleccionado y el anverso enfocado. */
  onAddCards: (id: number) => void;
  /** V3.80.0: el mazo recién creado, para seleccionarlo y saltar a Tarjetas. */
  onDeckCreated: (id: number) => void;
  /** V3.80.0: estudiar el mazo automático filtrado por un pack listo. */
  onStudyCollection: (id: number, label: string) => void;
}) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  // V3.88.0: el borrado tiene su propio indicador. Compartía `busy` con el alta,
  // así que borrar un mazo habría hecho girar el botón de crear.
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  // V3.86.0: qué se borró de verdad en el último borrado de mazo, para poder
  // decir cuántas fichas se conservaron por estar compartidas.
  const [lastDeleted, setLastDeleted] = useState<FlashcardDeckDeleteResult | null>(
    null,
  );

  const manual = useMemo(
    () => (decks?.decks ?? []).filter((d) => !d.is_auto),
    [decks],
  );
  const auto = (decks?.decks ?? []).find((d) => d.is_auto) ?? null;

  async function handleCreate() {
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(false);
    try {
      const created = await createFlashcardDeck(userId, { name: name.trim() });
      setName("");
      onChanged();
      // El mazo creado se abre directamente en Tarjetas: es donde se le meten
      // palabras, y sin este salto el alumno se quedaba en Mazos mirando una
      // fila vacía.
      onDeckCreated(created.id);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(deck: FlashcardDeck) {
    if (busy || deletingId != null) return;
    // V3.86.0: el aviso dice qué pasa con las fichas COMPARTIDAS, que es la
    // información que faltaba: borrar un mazo ya no borra una ficha que vive en
    // otro. Solo se promete lo que se sabe (`shared_count`).
    const shared = deck.shared_count;
    const kept = Math.min(shared, deck.card_count);
    const removed = Math.max(0, deck.card_count - kept);
    const ok = window.confirm(
      shared > 0
        ? t("flashcards.decks.deleteConfirmShared")
            .replace("{name}", deck.name)
            .replace("{n}", String(removed))
            .replace("{kept}", String(kept))
        : t("flashcards.decks.deleteConfirm")
            .replace("{name}", deck.name)
            .replace("{n}", String(deck.card_count)),
    );
    if (!ok) return;
    setDeletingId(deck.id);
    setError(false);
    try {
      const result = await deleteFlashcardDeck(userId, deck.id);
      setLastDeleted(result);
      onChanged();
    } catch {
      setError(true);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="gap-3 p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Library className="size-4 text-primary" aria-hidden="true" />
          {t("flashcards.decks.title")}
        </h2>

        {error ? (
          <p className="text-sm text-destructive">{t("flashcards.decks.error")}</p>
        ) : null}

        {/* V3.86.0: qué pasó con las fichas compartidas al borrar el mazo. */}
        {lastDeleted && lastDeleted.shared_count > 0 ? (
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {t("flashcards.decks.deletedKept")
              .replace("{deleted}", String(lastDeleted.deleted_count))
              .replace("{kept}", String(lastDeleted.shared_count))}
          </p>
        ) : null}

        {auto ? (
          <div className="flex flex-col gap-1 rounded-lg border border-border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-semibold">
                <DeckLabel deck={auto} />
              </span>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">
                  {t("flashcards.decks.cards").replace(
                    "{n}",
                    String(auto.card_count),
                  )}
                </Badge>
                <Badge variant="secondary">
                  {t("flashcards.decks.due").replace(
                    "{n}",
                    String(auto.due_count + auto.new_count),
                  )}
                </Badge>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => onStudyDeck(auto.id)}
                >
                  {t("flashcards.decks.study")}
                </Button>
              </div>
            </div>
            <p className="text-[11px] text-muted-foreground">
              {t("flashcards.decks.autoHint")}
            </p>
            <p className="text-[11px] text-muted-foreground">
              {t("flashcards.decks.notEditable")}
            </p>
          </div>
        ) : null}

        {manual.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("flashcards.decks.empty")}
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {manual.map((deck) => (
              <li
                key={deck.id}
                className="flex flex-col gap-2 rounded-lg border border-border p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-semibold">{deck.name}</span>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">
                      {t("flashcards.decks.cards").replace(
                        "{n}",
                        String(deck.card_count),
                      )}
                    </Badge>
                    {/* V3.86.0: cuántas de esas fichas viven además en otro
                        mazo. Es la información que hace honesto el borrado. */}
                    {deck.shared_count > 0 ? (
                      <Badge variant="outline" className="text-[10px]">
                        {t("flashcards.decks.shared").replace(
                          "{n}",
                          String(deck.shared_count),
                        )}
                      </Badge>
                    ) : null}
                    <Badge variant="secondary">
                      {t("flashcards.decks.due").replace(
                        "{n}",
                        String(deck.due_count + deck.new_count),
                      )}
                    </Badge>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => onStudyDeck(deck.id)}
                    >
                      {t("flashcards.decks.study")}
                    </Button>
                    {/* V3.80.0: el camino que faltaba. Estudiar y Añadir
                        tarjetas son acciones distintas y las dos se necesitan. */}
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => onAddCards(deck.id)}
                    >
                      <Plus className="size-3.5" aria-hidden="true" />
                      {t("flashcards.decks.addCards")}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      aria-expanded={editing === deck.id}
                      onClick={() =>
                        setEditing((current) =>
                          current === deck.id ? null : deck.id,
                        )
                      }
                    >
                      {t("flashcards.decks.settings")}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="text-destructive"
                      disabled={busy || deletingId != null}
                      onClick={() => void handleDelete(deck)}
                    >
                      {deletingId === deck.id ? (
                        <BusyIcon />
                      ) : (
                        <Trash2 className="size-3.5" aria-hidden="true" />
                      )}
                      {t("flashcards.decks.delete")}
                    </Button>
                  </div>
                </div>
                {editing === deck.id ? (
                  <DeckEditor
                    userId={userId}
                    deck={deck}
                    key={`${deck.id}-${reloadNonce}-${deck.new_per_day}-${deck.review_per_day}`}
                    onSaved={() => {
                      setEditing(null);
                      onChanged();
                    }}
                  />
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* V3.80.0: los packs que ya existen, ofrecidos como mazos. Va pegado a la
          lista de mazos porque es otra forma de conseguir uno. */}
      <ReadyDecks
        userId={userId}
        reloadNonce={reloadNonce}
        onChanged={onChanged}
        onStudyCollection={onStudyCollection}
      />

      <Card className="gap-2 p-5">
        <h3 className="text-sm font-semibold">{t("flashcards.decks.new")}</h3>
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            void handleCreate();
          }}
        >
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("flashcards.decks.namePlaceholder")}
            maxLength={120}
            className={cn(INPUT, "flex-1")}
          />
          <Button type="submit" size="sm" disabled={busy || !name.trim()}>
            {busy ? (
              <BusyIcon />
            ) : (
              <Plus className="size-3.5" aria-hidden="true" />
            )}
            {busy ? t("common.saving") : t("flashcards.decks.create")}
          </Button>
        </form>
      </Card>
    </div>
  );
}

/**
 * «Mazos listos»: los packs globales que YA existen (`theme_pack`), ofrecidos
 * como mazos (V3.80.0).
 *
 * No crea contenido nuevo ni copia nada: **añadir** un pack materializa sus
 * palabras en el léxico con su carta FSRS (lo que ya hacía `enroll`), y
 * **estudiar** abre la sesión del mazo automático filtrada por ese pack, con el
 * `collection_id` que la cola ya soporta.
 *
 * El mismo pack sigue apareciendo en el bloque «Añadir» de PERSONAL. No es
 * duplicación accidental y por eso se declara aquí: uno es «añadir a mi
 * diccionario» y el otro «empezar a estudiar»; consolidarlo queda aparcado.
 */
function ReadyDecks({
  userId,
  reloadNonce,
  onChanged,
  onStudyCollection,
}: {
  userId: string;
  reloadNonce: number;
  onChanged: () => void;
  onStudyCollection: (id: number, label: string) => void;
}) {
  const { t, lang } = useI18n();
  const [packs, setPacks] = useState<VocabCollection[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState(false);
  const [lastAdded, setLastAdded] = useState<{ id: number; n: number } | null>(
    null,
  );

  const load = useCallback(async () => {
    setError(false);
    try {
      const data = await listVocabCollections(userId);
      setPacks(data.collections.filter((c) => c.kind === "theme_pack"));
    } catch {
      setError(true);
      setPacks([]);
    }
  }, [userId]);

  useEffect(() => {
    void load();
  }, [load, reloadNonce]);

  async function handleEnroll(pack: VocabCollection) {
    if (busyId != null) return;
    setBusyId(pack.id);
    setError(false);
    try {
      const result = await enrollVocabCollection(userId, pack.id);
      setLastAdded({ id: pack.id, n: result.count });
      await load();
      // El léxico ha crecido: el mazo automático y las estadísticas cambian.
      onChanged();
    } catch {
      setError(true);
    } finally {
      setBusyId(null);
    }
  }

  // Sin packs en el catálogo no se pinta un bloque vacío que prometa mazos.
  if (packs.length === 0) return null;

  return (
    <Card className="gap-3 p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold">
        <Sparkles className="size-4 text-primary" aria-hidden="true" />
        {t("flashcards.decks.readyTitle")}
      </h2>
      <p className="text-[11px] leading-relaxed text-muted-foreground">
        {t("flashcards.decks.readyHint")}
      </p>
      {error ? (
        <p className="text-sm text-muted-foreground">{t("dictionary.loadError")}</p>
      ) : null}
      <ul className="flex flex-col gap-2">
        {packs.map((pack) => {
          const label =
            lang === "es" && pack.title_es ? pack.title_es : pack.title;
          const justAdded = lastAdded?.id === pack.id;
          return (
            <li
              key={pack.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border p-3"
            >
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="truncate text-sm font-semibold">{label}</span>
                <span className="text-[11px] text-muted-foreground">
                  {t("flashcards.decks.readyItems")
                    .replace("{n}", String(pack.item_count))
                    .replace("{cefr}", pack.cefr_hint || "—")}
                  {justAdded
                    ? ` · ${t("flashcards.decks.readyAdded").replace(
                        "{n}",
                        String(lastAdded?.n ?? 0),
                      )}`
                    : ""}
                </span>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {pack.enrolled ? (
                  <>
                    <Badge
                      variant="secondary"
                      className={cn(
                        "border-transparent bg-success/15 text-success",
                      )}
                    >
                      {t("flashcards.decks.readyEnrolled")}
                    </Badge>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => onStudyCollection(pack.id, label)}
                    >
                      {t("flashcards.decks.study")}
                    </Button>
                  </>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    disabled={busyId != null}
                    onClick={() => void handleEnroll(pack)}
                  >
                    {busyId === pack.id ? (
                      <BusyIcon />
                    ) : (
                      <Plus className="size-3.5" aria-hidden="true" />
                    )}
                    {busyId === pack.id
                      ? t("common.saving")
                      : t("flashcards.decks.readyAdd")}
                  </Button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function DeckEditor({
  userId,
  deck,
  onSaved,
}: {
  userId: string;
  deck: FlashcardDeck;
  onSaved: () => void;
}) {
  const { t } = useI18n();
  const [name, setName] = useState(deck.name);
  const [newPerDay, setNewPerDay] = useState(String(deck.new_per_day));
  const [reviewPerDay, setReviewPerDay] = useState(String(deck.review_per_day));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  async function save() {
    if (busy) return;
    setBusy(true);
    setError(false);
    try {
      await updateFlashcardDeck(userId, deck.id, {
        name: name.trim() || deck.name,
        new_per_day: Number.parseInt(newPerDay, 10) || 0,
        review_per_day: Number.parseInt(reviewPerDay, 10) || 0,
      });
      onSaved();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="flex flex-col gap-2 border-t border-border pt-2 sm:flex-row sm:items-end"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <label className="flex flex-1 flex-col gap-1 text-[11px] text-muted-foreground">
        {t("flashcards.decks.rename")}
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={120}
          className={INPUT}
        />
      </label>
      <label className="flex w-28 flex-col gap-1 text-[11px] text-muted-foreground">
        {t("flashcards.decks.limitsNew")}
        <input
          type="number"
          min={0}
          max={9999}
          value={newPerDay}
          onChange={(e) => setNewPerDay(e.target.value)}
          className={INPUT}
        />
      </label>
      <label className="flex w-32 flex-col gap-1 text-[11px] text-muted-foreground">
        {t("flashcards.decks.limitsReview")}
        <input
          type="number"
          min={0}
          max={9999}
          value={reviewPerDay}
          onChange={(e) => setReviewPerDay(e.target.value)}
          className={INPUT}
        />
      </label>
      <Button type="submit" size="sm" disabled={busy}>
        {busy ? <BusyIcon /> : null}
        {busy ? t("common.saving") : t("flashcards.decks.save")}
      </Button>
      {error ? (
        <span className="text-[11px] text-destructive">
          {t("flashcards.decks.error")}
        </span>
      ) : null}
    </form>
  );
}

// --- Tarjetas ---------------------------------------------------------------

const CARD_STATES = ["new", "learning", "review"] as const;

/** Órdenes del navegador de tarjetas. */
type CardOrder = "recent" | "front" | "due";

const CARD_ORDERS: { id: CardOrder; labelKey: string }[] = [
  { id: "recent", labelKey: "flashcards.cards.orderRecent" },
  { id: "front", labelKey: "flashcards.cards.orderFront" },
  { id: "due", labelKey: "flashcards.cards.orderDue" },
];

/**
 * Pestaña Fichas (V3.86.0).
 *
 * Antes forzaba un mazo manual y solo mostraba SUS tarjetas: con la ficha en
 * varios mazos eso miente (una ficha compartida aparece una vez por mazo y no se
 * sabe de quién es). Ahora se listan TODAS las fichas del alumno —con sus mazos
 * como etiquetas— y el mazo solo se elige para **filtrar** y para **añadir**.
 * Cada ficha expone su **recordatorio**, editable y borrable.
 */
function CardsTab({
  userId,
  decks,
  deckId,
  onPick,
  reloadNonce,
  addCardsNonce,
  onGoToDecks,
}: {
  userId: string;
  decks: FlashcardDecks | null;
  /** La selección compartida de la pantalla (sigue siendo la que estudia). */
  deckId: number | null;
  onPick: (id: number) => void;
  reloadNonce: number;
  /** Sube al crear un mazo o al pulsar «Añadir tarjetas»: enfoca el anverso. */
  addCardsNonce: number;
  onGoToDecks: () => void;
}) {
  const { t } = useI18n();
  const manual = useMemo(
    () => (decks?.decks ?? []).filter((d) => !d.is_auto),
    [decks],
  );
  const deckName = useCallback(
    (id: number) => manual.find((d) => d.id === id)?.name ?? "",
    [manual],
  );

  /** Filtro por mazo: `"all"` = todas las fichas (el defecto, sin mazo forzado). */
  const [filter, setFilter] = useState<number | "all">("all");
  const [cards, setCards] = useState<FlashcardCard[]>([]);
  // V3.88.0: la lista se pintaba vacía mientras la petición viajaba y decía
  // «no hay fichas» antes de saberlo. Ahora el vacío se declara cuando de
  // verdad se ha respondido.
  const [cardsLoading, setCardsLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState<string>("all");
  const [order, setOrder] = useState<CardOrder>("recent");
  const [newFront, setNewFront] = useState("");
  const [newBack, setNewBack] = useState("");
  const [newMnemonic, setNewMnemonic] = useState("");
  /** Mazos en los que nace la ficha nueva (casillas; vacío = el primero). */
  const [formDecks, setFormDecks] = useState<number[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  // V3.88.0: el borrado de una ficha tiene su propio indicador (antes compartía
  // `busy` con el alta y el spinner habría caído en el botón equivocado).
  const [deletingCardId, setDeletingCardId] = useState<number | null>(null);
  const [error, setError] = useState(false);
  // V3.80.0: pegado masivo. `bulkResult` guarda cuántas entraron de verdad, que
  // es lo único honesto que se puede decir después de pegar 40 líneas.
  const [bulkText, setBulkText] = useState("");
  const [bulkDeck, setBulkDeck] = useState<number | "">("");
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkError, setBulkError] = useState(false);
  const [bulkResult, setBulkResult] = useState<number | null>(null);
  const frontRef = useRef<HTMLInputElement | null>(null);

  /** Cambia el filtro. Elegir un mazo concreto también lo deja como LA selección
   *  compartida (es el mazo que estudiará Estudiar); «Todos» solo filtra. */
  const applyFilter = useCallback(
    (next: number | "all") => {
      setFilter(next);
      if (next !== "all") onPick(next);
    },
    [onPick],
  );

  // Al llegar desde «crear mazo» o «Añadir tarjetas», el anverso se enfoca solo
  // y el mazo pedido queda marcado para el alta y como filtro.
  useEffect(() => {
    if (addCardsNonce <= 0) return;
    frontRef.current?.focus();
    const preferred = manual.find((d) => d.id === deckId) ?? manual[0] ?? null;
    if (!preferred) return;
    setFormDecks((current) => (current.length > 0 ? current : [preferred.id]));
    applyFilter(preferred.id);
    // Solo al recibir una petición nueva; `manual`/`deckId` se leen, no mandan.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addCardsNonce]);

  const loadCards = useCallback(async () => {
    setError(false);
    setCardsLoading(true);
    try {
      const data = await listVocabularyCards(userId, {
        deckId: filter === "all" ? null : filter,
      });
      setCards(data.cards);
    } catch {
      setError(true);
      setCards([]);
    } finally {
      setCardsLoading(false);
    }
  }, [userId, filter]);

  useEffect(() => {
    void loadCards();
  }, [loadCards, reloadNonce]);

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const filtered = cards.filter((card) => {
      if (stateFilter !== "all" && card.state !== stateFilter) return false;
      if (!needle) return true;
      return (
        card.front.toLowerCase().includes(needle) ||
        card.back.toLowerCase().includes(needle) ||
        card.mnemonic.toLowerCase().includes(needle)
      );
    });
    if (order === "front") {
      return [...filtered].sort((a, b) => a.front.localeCompare(b.front));
    }
    if (order === "due") {
      // Sin carta programada (`due_at` vacío) va al final: no es «vence ya»,
      // es «aún no está en el scheduler».
      return [...filtered].sort((a, b) => {
        if (a.due_at === b.due_at) return a.front.localeCompare(b.front);
        if (!a.due_at) return 1;
        if (!b.due_at) return -1;
        return a.due_at < b.due_at ? -1 : 1;
      });
    }
    return [...filtered].sort((a, b) => b.id - a.id);
  }, [cards, search, stateFilter, order]);

  /** Mazos en los que se guardará la ficha nueva: los marcados o, si no hay
   *  ninguno, el primero disponible (así «Guardar» nunca queda muerto). */
  const targetDecks = useMemo(
    () => (formDecks.length > 0 ? formDecks : manual[0] ? [manual[0].id] : []),
    [formDecks, manual],
  );

  async function handleAdd() {
    if (!newFront.trim() || busy || targetDecks.length === 0) return;
    setBusy(true);
    setError(false);
    try {
      await createVocabularyCard(userId, {
        front: newFront.trim(),
        back: newBack.trim(),
        mnemonic: newMnemonic.trim(),
        deckIds: targetDecks,
      });
      setNewFront("");
      setNewBack("");
      setNewMnemonic("");
      await loadCards();
      frontRef.current?.focus();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(card: FlashcardCard) {
    if (busy || deletingCardId != null) return;
    setDeletingCardId(card.id);
    setError(false);
    try {
      await deleteVocabularyCard(userId, card.id);
      await loadCards();
    } catch {
      setError(true);
    } finally {
      setDeletingCardId(null);
    }
  }

  const bulkTargetDeck =
    bulkDeck !== ""
      ? bulkDeck
      : filter !== "all"
        ? filter
        : (manual[0]?.id ?? 0);

  async function handleBulkAdd() {
    if (bulkTargetDeck === 0 || !bulkText.trim() || bulkBusy) return;
    setBulkBusy(true);
    setBulkError(false);
    setBulkResult(null);
    try {
      const result = await addFlashcardsBulk(userId, bulkTargetDeck, bulkText);
      setBulkText("");
      setBulkResult(result.count);
      await loadCards();
    } catch {
      setBulkError(true);
    } finally {
      setBulkBusy(false);
    }
  }

  if (manual.length === 0) {
    return (
      <Card className="flex flex-col gap-3 p-5">
        <p className="text-sm text-muted-foreground">
          {t("flashcards.cards.pickDeck")}
        </p>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="w-fit"
          onClick={onGoToDecks}
        >
          <Plus className="size-3.5" aria-hidden="true" />
          {t("flashcards.cards.goToDecks")}
        </Button>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="gap-3 p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <BookOpen className="size-4 text-primary" aria-hidden="true" />
          {t("flashcards.cards.title")}
        </h2>

        {addCardsNonce > 0 ? (
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {t("flashcards.cards.createdHint")}
          </p>
        ) : null}

        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            aria-label={t("flashcards.cards.deckFilter")}
            value={filter === "all" ? "all" : String(filter)}
            onChange={(e) =>
              applyFilter(
                e.target.value === "all" ? "all" : Number(e.target.value),
              )
            }
            className={cn(INPUT, "sm:w-56")}
          >
            <option value="all">{t("flashcards.cards.allDecks")}</option>
            {manual.map((deck) => (
              <option key={deck.id} value={deck.id}>
                {deck.name}
              </option>
            ))}
          </select>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("flashcards.cards.searchPlaceholder")}
            className={cn(INPUT, "flex-1")}
          />
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {["all", ...CARD_STATES].map((state) => (
            <button
              key={state}
              type="button"
              aria-pressed={stateFilter === state}
              onClick={() => setStateFilter(state)}
              className={cn(
                "inline-flex min-h-8 items-center rounded-md px-2 text-xs font-semibold transition-colors",
                stateFilter === state
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {state === "all"
                ? t("dictionary.inventory.sourceAll")
                : cardStateLabel(t, state)}
            </button>
          ))}
          <span className="ml-1 text-[11px] text-muted-foreground">
            {t("flashcards.cards.order")}
          </span>
          {CARD_ORDERS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              aria-pressed={order === entry.id}
              onClick={() => setOrder(entry.id)}
              className={cn(
                "inline-flex min-h-8 items-center rounded-md px-2 text-xs font-semibold transition-colors",
                order === entry.id
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t(entry.labelKey)}
            </button>
          ))}
        </div>

        {error ? (
          <p className="text-sm text-destructive">{t("flashcards.cards.error")}</p>
        ) : null}

        {cardsLoading ? (
          <LoadingNotice />
        ) : visible.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {cards.length === 0
              ? t("flashcards.cards.empty")
              : t("flashcards.cards.noMatches")}
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {visible.map((card) => (
              <li
                key={card.id}
                className="flex flex-col gap-2 rounded-lg border border-border p-3"
              >
                {editingId === card.id ? (
                  <CardEditor
                    userId={userId}
                    card={card}
                    decks={manual}
                    onSaved={async () => {
                      setEditingId(null);
                      await loadCards();
                    }}
                  />
                ) : (
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="flex min-w-0 flex-col">
                      <span className="text-sm font-semibold">{card.front}</span>
                      {card.back ? (
                        <span className="text-sm text-muted-foreground">
                          {card.back}
                        </span>
                      ) : null}
                      {card.mnemonic ? (
                        <span className="text-[11px] text-muted-foreground">
                          {t("flashcards.cards.mnemonic")}: {card.mnemonic}
                        </span>
                      ) : null}
                      <span className="mt-0.5 flex flex-wrap items-center gap-1">
                        {card.deck_ids.length === 0 ? (
                          <Badge variant="outline" className="text-[10px]">
                            {t("flashcards.cards.noDecks")}
                          </Badge>
                        ) : (
                          card.deck_ids.map((id) => (
                            <Badge
                              key={id}
                              variant="secondary"
                              className="text-[10px]"
                            >
                              {deckName(id) || `#${id}`}
                            </Badge>
                          ))
                        )}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="secondary">
                        {cardStateLabel(t, card.state)}
                      </Badge>
                      {/* Fuerza de memoria de la tarjeta: sin ella el navegador
                          no distingue una tarjeta recién creada de una que ya
                          se ha repasado cinco veces. */}
                      <span className="text-[11px] text-muted-foreground">
                        {card.reps > 0
                          ? t("flashcards.cards.cardMemory")
                              .replace("{reps}", String(card.reps))
                              .replace(
                                "{due}",
                                card.due_at ? card.due_at.slice(0, 10) : "—",
                              )
                          : t("flashcards.cards.cardNew")}
                      </span>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          setEditingId((current) =>
                            current === card.id ? null : card.id,
                          )
                        }
                      >
                        {t("flashcards.cards.edit")}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="text-destructive"
                        disabled={busy || deletingCardId != null}
                        onClick={() => void handleDelete(card)}
                      >
                        {deletingCardId === card.id ? (
                          <BusyIcon />
                        ) : (
                          <Trash2 className="size-3.5" aria-hidden="true" />
                        )}
                        {t("flashcards.cards.delete")}
                      </Button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="flex flex-col gap-3 p-5">
        <h3 className="text-sm font-semibold">{t("flashcards.cards.add")}</h3>
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void handleAdd();
          }}
        >
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              ref={frontRef}
              value={newFront}
              onChange={(e) => setNewFront(e.target.value)}
              placeholder={t("flashcards.cards.frontPlaceholder")}
              maxLength={400}
              className={cn(INPUT, "flex-1")}
            />
            <input
              value={newBack}
              onChange={(e) => setNewBack(e.target.value)}
              placeholder={t("flashcards.cards.backPlaceholder")}
              maxLength={2000}
              className={cn(INPUT, "flex-1")}
            />
          </div>
          <input
            value={newMnemonic}
            onChange={(e) => setNewMnemonic(e.target.value)}
            placeholder={t("flashcards.cards.mnemonicPlaceholder")}
            maxLength={400}
            className={INPUT}
          />
          {/* V3.86.0: la ficha nace en TODOS los mazos marcados. */}
          <fieldset className="flex flex-wrap items-center gap-2">
            <legend className="text-[11px] font-medium text-muted-foreground">
              {t("flashcards.cards.decksLabel")}
            </legend>
            {manual.map((deck) => (
              <label
                key={deck.id}
                className="inline-flex min-h-8 items-center gap-1.5 rounded-md border border-border px-2.5 text-xs font-medium"
              >
                <input
                  type="checkbox"
                  checked={formDecks.includes(deck.id)}
                  onChange={() =>
                    setFormDecks((current) =>
                      current.includes(deck.id)
                        ? current.filter((x) => x !== deck.id)
                        : [...current, deck.id],
                    )
                  }
                />
                {deck.name}
              </label>
            ))}
          </fieldset>
          <Button
            type="submit"
            size="sm"
            className="w-fit"
            disabled={busy || !newFront.trim() || targetDecks.length === 0}
          >
            {busy ? (
              <BusyIcon />
            ) : (
              <Plus className="size-3.5" aria-hidden="true" />
            )}
            {busy ? t("common.saving") : t("flashcards.cards.save")}
          </Button>
        </form>
      </Card>

      {/* V3.80.0: pegar una lista. La sintaxis es la MISMA que la del léxico
          («una por línea, anverso,reverso[,recordatorio]»), y se dice con un
          ejemplo, porque un formato que hay que adivinar es un formato que nadie
          usa. V3.86.0: el pegado va a UN mazo (el filtrado o el elegido). */}
      <Card className="gap-2 p-5">
        <h3 className="text-sm font-semibold">{t("flashcards.cards.bulkTitle")}</h3>
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("flashcards.cards.bulkHint")}
        </p>
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void handleBulkAdd();
          }}
        >
          <textarea
            value={bulkText}
            onChange={(e) => setBulkText(e.target.value)}
            placeholder={t("flashcards.cards.bulkPlaceholder")}
            maxLength={20000}
            rows={4}
            className={cn(INPUT, "w-full font-mono text-xs")}
          />
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label={t("flashcards.cards.decksLabel")}
              value={bulkDeck === "" ? String(bulkTargetDeck) : String(bulkDeck)}
              onChange={(e) => setBulkDeck(Number(e.target.value))}
              className={cn(INPUT, "w-full sm:w-56")}
            >
              {manual.map((deck) => (
                <option key={deck.id} value={deck.id}>
                  {deck.name}
                </option>
              ))}
            </select>
            <Button type="submit" size="sm" disabled={bulkBusy || !bulkText.trim()}>
              {bulkBusy ? (
                <BusyIcon />
              ) : (
                <Plus className="size-3.5" aria-hidden="true" />
              )}
              {bulkBusy ? t("common.saving") : t("flashcards.cards.bulkAdd")}
            </Button>
            {bulkResult != null ? (
              <span className="text-xs text-muted-foreground">
                {t("flashcards.cards.bulkDone").replace(
                  "{n}",
                  String(bulkResult),
                )}
              </span>
            ) : null}
            {bulkError ? (
              <span className="text-xs text-destructive">
                {t("flashcards.cards.error")}
              </span>
            ) : null}
          </div>
        </form>
      </Card>
    </div>
  );
}

/**
 * Editor de una ficha (V3.86.0): anverso, reverso, **recordatorio** (se puede
 * dejar vacío para borrarlo) y los **mazos** con casillas. Se guarda con el
 * parcheo parcial: lo que no cambia no se reenvía.
 */
function CardEditor({
  userId,
  card,
  decks,
  onSaved,
}: {
  userId: string;
  card: FlashcardCard;
  decks: FlashcardDeck[];
  onSaved: () => void | Promise<void>;
}) {
  const { t } = useI18n();
  const [front, setFront] = useState(card.front);
  const [back, setBack] = useState(card.back);
  const [mnemonic, setMnemonic] = useState(card.mnemonic);
  const [deckIds, setDeckIds] = useState<number[]>(card.deck_ids);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  function toggleDeck(id: number) {
    setDeckIds((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id],
    );
  }

  function submit() {
    if (busy || !front.trim()) return;
    // Sin mazos la ficha no se puede guardar: `deck_ids` no puede quedar vacío.
    if (deckIds.length === 0) {
      setError(true);
      return;
    }
    setBusy(true);
    setError(false);
    void updateVocabularyCard(userId, card.id, {
      front: front.trim(),
      back: back.trim(),
      mnemonic: mnemonic.trim(),
      deckIds,
    })
      .then(() => onSaved())
      .catch(() => setError(true))
      .finally(() => setBusy(false));
  }

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          value={front}
          onChange={(e) => setFront(e.target.value)}
          aria-label={t("flashcards.cards.front")}
          maxLength={400}
          className={cn(INPUT, "flex-1")}
        />
        <input
          value={back}
          onChange={(e) => setBack(e.target.value)}
          aria-label={t("flashcards.cards.back")}
          maxLength={2000}
          className={cn(INPUT, "flex-1")}
        />
        {/* El recordatorio es editable Y borrable: vaciarlo lo retira de la
            ficha (y del reverso del estudio). El botón solo existe cuando hay
            algo que borrar, para no ofrecer una acción vacía. */}
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <input
            value={mnemonic}
            onChange={(e) => setMnemonic(e.target.value)}
            aria-label={t("flashcards.cards.mnemonic")}
            placeholder={t("flashcards.cards.mnemonicPlaceholder")}
            maxLength={400}
            className={cn(INPUT, "min-w-0 flex-1")}
          />
          {mnemonic ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="shrink-0 gap-1.5"
              onClick={() => setMnemonic("")}
            >
              <Eraser className="size-3.5" aria-hidden="true" />
              {t("flashcards.cards.mnemonicClear")}
            </Button>
          ) : null}
        </div>
      </div>
      <fieldset className="flex flex-wrap items-center gap-2">
        <legend className="text-[11px] font-medium text-muted-foreground">
          {t("flashcards.cards.decksLabel")}
        </legend>
        {decks.map((deck) => (
          <label
            key={deck.id}
            className="inline-flex min-h-8 items-center gap-1.5 rounded-md border border-border px-2.5 text-xs font-medium"
          >
            <input
              type="checkbox"
              checked={deckIds.includes(deck.id)}
              onChange={() => toggleDeck(deck.id)}
            />
            {deck.name}
          </label>
        ))}
      </fieldset>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" size="sm" disabled={busy}>
          {busy ? <BusyIcon /> : null}
          {busy ? t("common.saving") : t("flashcards.cards.save")}
        </Button>
        {error ? (
          <span className="text-[11px] text-destructive" role="alert">
            {deckIds.length === 0
              ? t("flashcards.cards.noDeckSelected")
              : t("flashcards.cards.error")}
          </span>
        ) : null}
      </div>
    </form>
  );
}

function cardStateLabel(t: (key: string) => string, state: string): string {
  if (state === "new") return t("flashcards.cards.stateNew");
  if (state === "review") return t("flashcards.cards.stateReview");
  return t("flashcards.cards.stateLearning");
}

// --- Estadísticas -----------------------------------------------------------

function StatsTab({
  userId,
  decks,
  deckId,
  onPick,
}: {
  userId: string;
  decks: FlashcardDecks | null;
  deckId: number | null;
  onPick: (id: number) => void;
}) {
  const { t } = useI18n();
  const [stats, setStats] = useState<FlashcardStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const deck = deckId ?? 0;

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      setStats(await getFlashcardStats(userId, deck));
    } catch {
      setError(true);
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [userId, deck]);

  useEffect(() => {
    void load();
  }, [load]);

  const hasData = Boolean(stats && stats.reviews_30d > 0);
  const maxDay = Math.max(1, ...(stats?.by_day ?? []).map((d) => d.total));
  const maxForecast = Math.max(1, ...(stats?.forecast ?? []).map((d) => d.count));

  return (
    <Card className="gap-3 p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold">
        <BarChart3 className="size-4 text-primary" aria-hidden="true" />
        {t("flashcards.stats.title")}
      </h2>

      <DeckSelect decks={decks} value={deck} onChange={onPick} />

      {error ? (
        <p className="text-sm text-muted-foreground">{t("dictionary.loadError")}</p>
      ) : loading ? (
        <LoadingNotice />
      ) : !stats ? null : !hasData ? (
        <p className="text-sm text-muted-foreground">
          {t("flashcards.stats.empty")}
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Tile
              label={t("flashcards.stats.today")}
              value={String(stats.reviewed_today)}
            />
            <Tile
              label={t("flashcards.stats.total")}
              value={String(stats.reviews_30d)}
            />
            <Tile
              label={t("flashcards.stats.accuracy")}
              value={`${stats.accuracy_30d}%`}
            />
            <Tile
              label={t("flashcards.stats.dueToday")}
              value={String(stats.forecast[0]?.count ?? 0)}
            />
          </div>

          <p className="text-[11px] text-muted-foreground">
            {t("flashcards.stats.accuracyHint")}
          </p>

          <div className="flex flex-col gap-1">
            <h3 className="text-xs font-semibold">
              {t("flashcards.stats.byDay")}
            </h3>
            {stats.by_day.length === 0 ? (
              <p className="text-[11px] text-muted-foreground">
                {t("flashcards.stats.noData")}
              </p>
            ) : (
              <ul className="flex flex-col gap-1">
                {stats.by_day.map((day) => (
                  <li key={day.day} className="flex items-center gap-2 text-xs">
                    <span className="w-20 shrink-0 text-muted-foreground">
                      {day.day.slice(5)}
                    </span>
                    <span
                      className="h-2 rounded bg-primary"
                      style={{ width: `${(day.total / maxDay) * 100}%` }}
                      aria-hidden="true"
                    />
                    <span className="text-muted-foreground">{day.total}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <h3 className="text-xs font-semibold">
              {t("flashcards.stats.forecast")}
            </h3>
            <ul className="flex flex-col gap-1">
              {stats.forecast.map((day) => (
                <li key={day.day} className="flex items-center gap-2 text-xs">
                  <span className="w-20 shrink-0 text-muted-foreground">
                    {day.day.slice(5)}
                  </span>
                  <span
                    className="h-2 rounded bg-secondary"
                    style={{ width: `${(day.count / maxForecast) * 100}%` }}
                    aria-hidden="true"
                  />
                  <span className="text-muted-foreground">{day.count}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </Card>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col rounded-lg border border-border p-2">
      <span className="text-lg font-bold">{value}</span>
      <span className="text-[11px] text-muted-foreground">{label}</span>
    </div>
  );
}
