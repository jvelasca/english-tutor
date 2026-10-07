/**
 * Modo Flashcards del diccionario (V3.78.0): la ÚNICA superficie de estudio.
 *
 * Cinco subpestañas, en el orden en que se usan:
 *
 * - **Estudiar**: el banco (todas, un nivel o un mazo), los contadores de ese
 *   ámbito y una sola lección —profunda si la palabra es nueva, corta si ya
 *   está en seguimiento—.
 * - **Mi léxico**: resumen de lo aprendido y lo pendiente, con acceso a Estudiar.
 * - **Mazos**: temas del diccionario (no se borran) y mazos del alumno.
 * - **Tarjetas**: palabras de cada mazo.
 * - **Estadísticas**: el aprendizaje del diccionario entero.
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
  ChevronLeft,
  Eraser,
  Library,
  Layers,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import {
  addFlashcardsBulk,
  addVocabularyBulk,
  createFlashcardDeck,
  createVocabularyCard,
  deleteFlashcardDeck,
  deleteVocabularyCard,
  completeStudyLesson,
  getFlashcardStats,
  getStudyQueue,
  listFlashcardDecks,
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
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { useTabList } from "../../hooks/useTabList";
import { getSettings } from "../../api/settings";
import { getStudyConfig, saveStudyConfig } from "../../api/study";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { InfoDisclosure } from "../../components/InfoDisclosure";
import { LoadingNotice } from "../../components/LoadingNotice";
import { cn } from "../../lib/utils";
import { deckIcon } from "./deckIcon";
import {
  readStudyPlace,
  studyPlaceFromSettings,
  mergeStudyPlace,
  type StudyPlace,
} from "../../utils/lastPlace";
import { rememberStudyPlace } from "../../utils/studyPlaceMemory";
import { DIRECTION_OPTIONS, directionClass } from "../../utils/dictionaryDirection";
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
  const [internalTab, setInternalTab] = useState<FlashcardsTab>(
    () => (userId ? readStudyPlace(userId)?.tab : null) ?? "study",
  );
  const tab = controlledTab ?? internalTab;
  const placeTouched = useRef(false);
  const setTab = useCallback(
    (next: FlashcardsTab) => {
      placeTouched.current = true;
      setInternalTab(next);
      onTabChange?.(next);
    },
    [onTabChange],
  );
  const { onKeyDown, register } = useTabList(TAB_IDS, tab, setTab);
  const [decks, setDecks] = useState<FlashcardDecks | null>(null);
  const [deckId, setDeckId] = useState<number | null>(() =>
    userId ? (readStudyPlace(userId)?.deckId ?? null) : null,
  );
  const [restoredPlace, setRestoredPlace] = useState<StudyPlace | null>(() =>
    userId ? readStudyPlace(userId) : null,
  );
  const [collection, setCollection] = useState<CollectionFilter | null>(null);
  const [autoStart, setAutoStart] = useState(false);
  /** Desde Mi léxico: abrir Estudiar en un donut, sin empezar la carta. */
  const [reviewRequest, setReviewRequest] = useState<{
    pick: StudyQueueMode;
    nonce: number;
  } | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);
  const [error, setError] = useState(false);
  /**
   * V3.80.0: cuántas veces se ha pedido «abre Tarjetas listo para escribir».
   * Sube al crear un mazo y al pulsar «Añadir tarjetas»; Tarjetas lo usa para
   * enfocar el anverso y declarar qué hacer ahora. Un nonce y no un booleano
   * porque dos peticiones seguidas deben volver a enfocar.
   */
  const [addCardsNonce, setAddCardsNonce] = useState(0);
  /** Petición desde Estudiar: abrir el editor de esta ficha manual. */
  const [editCard, setEditCard] = useState<{ id: number; nonce: number } | null>(null);
  /** La lección sigue montada mientras se edita la ficha, para volver al mismo sitio. */
  const [heldLesson, setHeldLesson] = useState(false);

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

  const openCardEditor = useCallback(
    (cardId: number) => {
      setHeldLesson(true);
      setEditCard((current) => ({ id: cardId, nonce: (current?.nonce ?? 0) + 1 }));
      setTab("cards");
    },
    [setTab],
  );
  const returnToLesson = useCallback(() => {
    setTab("study");
  }, [setTab]);

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

  const rememberPlace = useCallback(
    (patch: Partial<StudyPlace>) => rememberStudyPlace(userId, patch),
    [userId],
  );
  const touchPlace = useCallback(() => {
    placeTouched.current = true;
  }, []);

  // El mazo y la sub-pestaña se guardan al cambiar. El primer valor (el que
  // acaba de leerse) no se reescribe, para no pisar el del perfil.
  const seenPlace = useRef<string | null>(null);
  useEffect(() => {
    if (!userId || deckId == null) return;
    const key = `${tab}:${deckId}`;
    if (seenPlace.current == null) {
      seenPlace.current = key;
      return;
    }
    if (seenPlace.current === key) return;
    seenPlace.current = key;
    rememberStudyPlace(userId, { tab, deckId });
  }, [userId, tab, deckId]);

  useEffect(() => {
    if (!userId) return;
    let cancel = false;
    void getSettings(userId)
      .then((res) => {
        if (cancel || placeTouched.current) return;
        const place = studyPlaceFromSettings(res.settings);
        if (!place) return;
        mergeStudyPlace(userId, place);
        setRestoredPlace(place);
        if (place.deckId != null) setDeckId(place.deckId);
      })
      .catch(() => {});
    return () => {
      cancel = true;
    };
  }, [userId]);

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
            onReview={(mode) => {
              setDeckId(decks?.auto_deck_id ?? 0);
              setCollection(null);
              setAutoStart(false);
              setReviewRequest({ pick: mode, nonce: Date.now() });
              setTab("study");
            }}
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
      ) : tab === "study" || heldLesson ? (
        <div className={tab === "study" ? "contents" : "hidden"} hidden={tab !== "study"}>
          <StudyTab
            userId={userId}
            decks={decks}
            deckId={deckId}
            onPick={(id) => {
              placeTouched.current = true;
              setDeckId(id);
            }}
            collection={collection}
            autoStart={autoStart}
            onOpenTab={setTab}
            onAutoStarted={() => setAutoStart(false)}
            onClearCollection={() => setCollection(null)}
            reloadNonce={reloadNonce}
            onAddCards={openCardsFor}
            onEditCard={openCardEditor}
            restoredPlace={restoredPlace}
            onRemember={rememberPlace}
            onTouch={touchPlace}
            reviewRequest={reviewRequest}
            onExit={() => {
              setHeldLesson(false);
              setAutoStart(false);
              reload();
            }}
          />
        </div>
      ) : null}
      {error || !userId || tab === "lexicon" ? null : tab === "decks" ? (
        <DecksTab
          userId={userId}
          decks={decks}
          deckId={deckId}
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
        />
      ) : tab === "cards" ? (
        <CardsTab
          userId={userId}
          decks={decks}
          deckId={deckId}
          onPick={setDeckId}
          reloadNonce={reloadNonce}
          addCardsNonce={addCardsNonce}
          editCard={editCard}
          onGoToDecks={() => setTab("decks")}
          onBackToLesson={heldLesson ? returnToLesson : undefined}
        />
      ) : tab === "stats" ? (
        <StatsTab userId={userId} />
      ) : null}
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
      {(decks?.decks ?? [])
        .filter((deck) => !deck.is_auto)
        .map((deck) => (
          <option key={deck.id} value={deck.id}>
            {deck.name}
          </option>
        ))}
    </select>
  );
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

/** Anillo de un contador de Estudiar. Pulsarlo elige esa cola. El arco es la parte sobre el total. */
function StatDonut({
  label,
  value,
  total,
  kind,
  pressed,
  onSelect,
}: {
  label: string;
  value: number | null;
  total: number;
  kind: "whole" | "share" | "due";
  pressed: boolean;
  onSelect: () => void;
}) {
  const size = 44;
  const stroke = 4;
  const radius = (size - stroke) / 2;
  const center = size / 2;
  const turn = 2 * Math.PI * radius;
  const share = kind === "whole" ? 1 : total > 0 ? Math.min(1, (value ?? 0) / total) : 0;
  const drawn = share * turn;
  const ink = pressed ? "var(--primary)" : "var(--foreground)";
  const name = value == null ? label : `${label}, ${value}`;
  return (
    <button
      type="button"
      aria-pressed={pressed}
      aria-label={name}
      onClick={onSelect}
      className={cn(
        "flex min-w-0 flex-col items-center gap-1 rounded-lg px-1 py-1",
        pressed ? "bg-primary/10" : "hover:bg-secondary",
      )}
    >
      <span className="relative grid place-items-center">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="var(--border)"
            strokeWidth={stroke}
          />
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={ink}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${drawn} ${turn}`}
            transform={`rotate(-90 ${center} ${center})`}
          />
        </svg>
        <span className="absolute text-xs font-semibold tabular-nums leading-none">
          {value == null ? "…" : String(value)}
        </span>
      </span>
      <span
        className={cn(
          "text-balance text-center text-[11px] leading-tight",
          pressed ? "font-semibold text-foreground" : "text-muted-foreground",
        )}
      >
        {label}
      </span>
    </button>
  );
}

/**
 * Configuración de estudio (V3.87.0 · FASE 2, incremento 1), **plegada** tras el
 * disparador «...» (V3.87.1).
 *
 * El sentido se elige en la cabecera. Aquí quedan el modo, la ayuda, la carga,
 * las palabras de hoy y los pasos. Cada cambio se guarda en el perfil y recarga
 * la cola; la sesión en curso no se reescribe por detrás.
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
      variant="corner"
      id="study-config-panel"
    >
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
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
  onEditCard,
  onExit,
  onOpenTab,
  restoredPlace,
  onRemember,
  onTouch,
  reviewRequest,
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
  onEditCard: (cardId: number) => void;
  onExit: () => void;
  onOpenTab: (tab: FlashcardsTab) => void;
  restoredPlace: StudyPlace | null;
  onRemember: (patch: Partial<StudyPlace>) => void;
  onTouch: () => void;
  reviewRequest: { pick: StudyQueueMode; nonce: number } | null;
}) {
  const { t } = useI18n();
  const autoId = decks?.auto_deck_id ?? 0;
  const deck = deckId ?? autoId;
  const isAuto = deck === autoId;
  const opening = readStudyPlace(userId);
  const [scope, setScope] = useState<StudyScope>(() => {
    const saved =
      opening?.scope ?? (autoStart && !isAuto && !collection ? "deck" : "all");
    // El diccionario entero es Todas. Un sitio guardado en el mazo automático
    // no es un mazo.
    if (saved === "deck" && isAuto && !autoStart) return "all";
    return saved;
  });
  const [pick, setPick] = useState<StudyQueueMode>(() => opening?.pick ?? "pending");
  const [level, setLevel] = useState(() => opening?.level ?? "A1");
  const userTouched = useRef(false);
  const skipPlaceWrite = useRef(true);
  const [queue, setQueue] = useState<StudyQueue | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [studying, setStudying] = useState(false);
  const [sessionNonce, setSessionNonce] = useState(0);
  const [studyConfig, setStudyConfig] = useState<StudyConfig | null>(null);
  const requestId = useRef(0);

  const launchScope: StudyScope = collection ? "all" : !isAuto && autoStart ? "deck" : scope;

  useEffect(() => {
    if (!restoredPlace || userTouched.current) return;
    setScope(restoredPlace.scope);
    setPick(restoredPlace.pick);
    setLevel(restoredPlace.level);
  }, [restoredPlace]);

  useEffect(() => {
    if (skipPlaceWrite.current) {
      skipPlaceWrite.current = false;
      return;
    }
    onRemember({ scope, pick, level });
  }, [scope, pick, level, onRemember]);

  useEffect(() => {
    if (!autoStart) return;
    onTouch();
    const next: StudyScope = collection ? "all" : !isAuto ? "deck" : "all";
    setScope(next);
    setPick("pending");
  }, [autoStart, collection, isAuto, onTouch]);

  useEffect(() => {
    if (!reviewRequest) return;
    userTouched.current = true;
    setScope("all");
    setPick(reviewRequest.pick);
  }, [reviewRequest]);

  useEffect(() => {
    if (scope !== "deck" || !isAuto) return;
    const first = (decks?.decks ?? []).find((entry) => !entry.is_auto);
    if (first) onPick(first.id);
  }, [scope, isAuto, decks, onPick]);

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
        direction={studyConfig?.direction ?? "en-es"}
        onComplete={async (close) => {
          await completeStudyLesson(userId, {
            item_id: close.item_id,
            grade: close.grade,
            translation: close.translation,
            facets: close.facets,
          });
        }}
        onEditCard={(cardId) => {
          onEditCard(cardId);
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
    <Card className="relative gap-5 p-5">
      <StudyConfigPanel
        config={studyConfig}
        onChange={(patch) => void changeStudyConfig(patch)}
      />
      <div className="flex min-w-0 flex-col gap-2 pr-12">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div className="flex min-w-0 flex-col gap-1">
              <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                {t("flashcards.study.scopeLabel")}
              </p>
              <h2 className="text-xl font-semibold tracking-tight">{scopeTitle}</h2>
            </div>
            <div
              className="flex flex-wrap gap-1"
              role="group"
              aria-label={t("flashcards.study.direction")}
            >
              {DIRECTION_OPTIONS.map((option) => {
                const active = (studyConfig?.direction ?? "en-es") === option.id;
                return (
                  <button
                    key={option.id}
                    type="button"
                    aria-pressed={active}
                    onClick={() => {
                      if (!active) void changeStudyConfig({ direction: option.id });
                    }}
                    className={cn(
                      "inline-flex min-h-9 items-center rounded-full border px-3 text-xs font-semibold",
                      active
                        ? cn(directionClass(option.id), "dir-chip")
                        : "border-border text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {t(option.labelKey)}
                  </button>
                );
              })}
            </div>
          </div>
        <p className="max-w-prose text-xs leading-relaxed text-muted-foreground">
          {t("flashcards.study.hint")}
        </p>
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
            onClick={() => {
              userTouched.current = true;
              onTouch();
              setScope(id);
            }}
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
              onClick={() => {
                userTouched.current = true;
                onTouch();
                setLevel(code);
              }}
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

      <div
        className="grid grid-cols-3 gap-x-2 gap-y-2 sm:grid-cols-5"
        role="group"
        aria-label={t("flashcards.study.pickLabel")}
      >
        {(
          [
            ["pending", "flashcards.study.statDue", queue?.due ?? 0, "due"],
            ["unlearned", "flashcards.study.statUnlearned", queue?.unlearned ?? 0, "share"],
            ["hard", "flashcards.study.statHard", queue?.hard ?? 0, "share"],
            ["good", "flashcards.study.statGood", queue?.good ?? 0, "share"],
            ["all", "flashcards.study.statTotal", queue?.total ?? 0, "whole"],
          ] as const
        ).map(([id, labelKey, value, kind]) => (
          <StatDonut
            key={id}
            label={t(labelKey)}
            value={loading && !queueMatches ? null : value}
            total={queueMatches ? queue?.total ?? 0 : 0}
            kind={kind}
            pressed={pick === id}
            onSelect={() => {
              userTouched.current = true;
              onTouch();
              setPick(id);
            }}
          />
        ))}
      </div>

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
      ) : !loading && queueMatches && items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t(
            pick === "unlearned"
              ? "flashcards.study.emptyUnlearned"
              : pick === "hard"
                ? "flashcards.study.emptyHard"
                : pick === "good"
                  ? "flashcards.study.emptyGood"
                  : pick === "failed"
                    ? "flashcards.study.emptyFailed"
                    : "flashcards.study.empty",
          )}
        </p>
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

/** Rejilla de mazos: icono, nombre y cuántas palabras. La elegida lleva el anillo. */
function DeckGrid({
  decks,
  selectedId,
  onSelect,
  label,
  dense = false,
  leading,
}: {
  decks: FlashcardDeck[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  label: string;
  dense?: boolean;
  /** Primera ficha, para «todas las tarjetas» en la pestaña Tarjetas. */
  leading?: { label: string; pressed: boolean; onSelect: () => void };
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn(
        "grid grid-cols-3 gap-2",
        dense ? "sm:grid-cols-4 lg:grid-cols-6" : "sm:grid-cols-4 lg:grid-cols-5",
      )}
    >
      {leading ? (
        <button
          type="button"
          aria-pressed={leading.pressed}
          aria-label={leading.label}
          onClick={leading.onSelect}
          className={cn(
            "flex min-w-0 flex-col items-center gap-1 rounded-xl border px-2 text-center",
            dense ? "py-1.5" : "py-2",
            leading.pressed
              ? "border-primary bg-primary/10 ring-2 ring-primary"
              : "border-border hover:bg-secondary",
          )}
        >
          <Layers
            className={cn("text-primary", dense ? "size-4" : "size-5")}
            aria-hidden="true"
          />
          <span
            className={cn(
              "line-clamp-2 text-[11px] leading-tight",
              leading.pressed
                ? "font-semibold text-foreground"
                : "text-muted-foreground",
            )}
          >
            {leading.label}
          </span>
        </button>
      ) : null}
      {decks.map((deck) => {
        const Icon = deckIcon(deck);
        const pressed = deck.id === selectedId;
        return (
          <button
            key={deck.id}
            type="button"
            aria-pressed={pressed}
            aria-label={deck.name}
            onClick={() => onSelect(deck.id)}
            className={cn(
              "flex min-w-0 flex-col items-center gap-1 rounded-xl border px-2 text-center",
              dense ? "py-1.5" : "py-2",
              pressed
                ? "border-primary bg-primary/10 ring-2 ring-primary"
                : "border-border hover:bg-secondary",
            )}
          >
            <Icon
              className={cn("text-primary", dense ? "size-4" : "size-5")}
              aria-hidden="true"
            />
            <span
              className={cn(
                "line-clamp-2 text-[11px] leading-tight",
                pressed ? "font-semibold text-foreground" : "text-muted-foreground",
              )}
            >
              {deck.name}
            </span>
            <span className="text-[10px] tabular-nums text-muted-foreground">
              {deck.card_count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function DecksTab({
  userId,
  decks,
  deckId,
  reloadNonce,
  onChanged,
  onStudyDeck,
  onAddCards,
  onDeckCreated,
}: {
  userId: string;
  decks: FlashcardDecks | null;
  /** Mazo que Estudiar y Tarjetas ya tienen elegido, para abrir el panel en él. */
  deckId: number | null;
  reloadNonce: number;
  onChanged: () => void;
  onStudyDeck: (id: number) => void;
  /** V3.80.0: ir a Tarjetas con ese mazo seleccionado y el anverso enfocado. */
  onAddCards: (id: number) => void;
  /** V3.80.0: el mazo recién creado, para seleccionarlo y saltar a Tarjetas. */
  onDeckCreated: (id: number) => void;
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
  const [picked, setPicked] = useState<number | null>(null);
  const selected =
    manual.find((deck) => deck.id === picked) ??
    manual.find((deck) => deck.id === deckId) ??
    manual[0] ??
    null;
  const [listName, setListName] = useState("");
  const [listText, setListText] = useState("");
  const [listBusy, setListBusy] = useState(false);
  const [listNote, setListNote] = useState<number | null>(null);

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

        {manual.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("flashcards.decks.empty")}
          </p>
        ) : (
          <DeckGrid
            decks={manual}
            selectedId={selected?.id ?? null}
            onSelect={setPicked}
            label={t("flashcards.decks.pick")}
          />
        )}
      </Card>

      {selected ? (
        <Card className="gap-3 p-5">
          <div className="flex flex-wrap items-center gap-2">
            {(() => {
              const Icon = deckIcon(selected);
              return <Icon className="size-5 text-primary" aria-hidden="true" />;
            })()}
            <h3 className="text-sm font-semibold">{selected.name}</h3>
            {selected.source_collection_id != null ? (
              <Badge variant="outline" className="text-[10px]">
                {t("flashcards.decks.theme")}
              </Badge>
            ) : null}
          </div>
          <div className="grid grid-cols-3 gap-2">
            <Tile
              label={t("flashcards.decks.words")}
              value={String(selected.card_count)}
            />
            <Tile
              label={t("flashcards.stats.dueToday")}
              value={String(selected.due_count + selected.new_count)}
            />
            <Tile
              label={t("flashcards.decks.sharedShort")}
              value={String(selected.shared_count)}
            />
          </div>
          {selected.shared_count > 0 ? (
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              {t("flashcards.decks.shared").replace(
                "{n}",
                String(selected.shared_count),
              )}
            </p>
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => onStudyDeck(selected.id)}
            >
              {t("flashcards.decks.study")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => onAddCards(selected.id)}
            >
              <Plus className="size-3.5" aria-hidden="true" />
              {t("flashcards.decks.addCards")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              aria-expanded={editing === selected.id}
              onClick={() =>
                setEditing((current) =>
                  current === selected.id ? null : selected.id,
                )
              }
            >
              {t("flashcards.decks.settings")}
            </Button>
            {selected.source_collection_id == null ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="text-destructive hover:text-destructive"
                disabled={deletingId === selected.id}
                onClick={() => void handleDelete(selected)}
              >
                {deletingId === selected.id ? (
                  <BusyIcon />
                ) : (
                  <Trash2 className="size-3.5" aria-hidden="true" />
                )}
                {t("flashcards.decks.delete")}
              </Button>
            ) : null}
          </div>
          {editing === selected.id ? (
            <DeckEditor
              userId={userId}
              deck={selected}
              key={`${selected.id}-${reloadNonce}-${selected.new_per_day}-${selected.review_per_day}`}
              onSaved={() => {
                setEditing(null);
                onChanged();
              }}
            />
          ) : null}
        </Card>
      ) : null}

      <InfoDisclosure
        label={t("flashcards.decks.addLabel")}
        content="options"
        id="decks-add"
      >
        <Card className="gap-2 p-5">
          <h3 className="text-sm font-semibold">{t("dictionary.add.listTitle")}</h3>
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {t("flashcards.decks.pasteHint")}
          </p>
          <form
            className="flex flex-col gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (!listText.trim() || listBusy) return;
              setListBusy(true);
              setError(false);
              setListNote(null);
              void addVocabularyBulk(userId, listText, { title: listName.trim() })
                .then((result) => {
                  setListText("");
                  setListName("");
                  setListNote(result.count);
                  onChanged();
                  if (result.deck_id != null) onDeckCreated(result.deck_id);
                })
                .catch(() => setError(true))
                .finally(() => setListBusy(false));
            }}
          >
            <input
              value={listName}
              onChange={(e) => setListName(e.target.value)}
              placeholder={t("dictionary.add.listNamePlaceholder")}
              maxLength={120}
              className={INPUT}
            />
            <textarea
              value={listText}
              onChange={(e) => setListText(e.target.value)}
              placeholder={t("dictionary.add.listPlaceholder")}
              rows={4}
              className={cn(INPUT, "min-h-24")}
            />
            <Button type="submit" size="sm" className="w-fit" disabled={listBusy || !listText.trim()}>
              {listBusy ? t("common.saving") : t("dictionary.add.listCta")}
            </Button>
          </form>
          {listNote != null ? (
            <p className="text-[11px] text-muted-foreground">
              {t("dictionary.add.bulkOk").replace("{n}", String(listNote))}
            </p>
          ) : null}
        </Card>

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
      </InfoDisclosure>
    </div>
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
  editCard,
  onGoToDecks,
  onBackToLesson,
}: {
  userId: string;
  decks: FlashcardDecks | null;
  /** La selección compartida de la pantalla (sigue siendo la que estudia). */
  deckId: number | null;
  onPick: (id: number) => void;
  reloadNonce: number;
  /** Sube al crear un mazo o al pulsar «Añadir tarjetas»: enfoca el anverso. */
  addCardsNonce: number;
  /** Desde Estudiar: abrir el editor de esta ficha, con todas visibles. */
  editCard: { id: number; nonce: number } | null;
  onGoToDecks: () => void;
  /** Si la lección sigue abierta, vuelve a la misma palabra. */
  onBackToLesson?: () => void;
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
  const focusedEdit = useRef(0);
  const editorRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    if (!editCard) return;
    setFilter("all");
    setStateFilter("all");
    setEditingId(editCard.id);
  }, [editCard]);

  useEffect(() => {
    if (!editCard || focusedEdit.current === editCard.nonce) return;
    const card = cards.find((entry) => entry.id === editCard.id);
    if (!card) return;
    focusedEdit.current = editCard.nonce;
    setSearch(card.front);
  }, [editCard, cards]);

  useEffect(() => {
    if (editingId == null) return;
    editorRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [editingId, search, cards]);
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
    let ordered: FlashcardCard[];
    if (order === "front") {
      ordered = [...filtered].sort((a, b) => a.front.localeCompare(b.front));
    } else if (order === "due") {
      // Sin carta programada (`due_at` vacío) va al final: no es «vence ya»,
      // es «aún no está en el scheduler».
      ordered = [...filtered].sort((a, b) => {
        if (a.due_at === b.due_at) return a.front.localeCompare(b.front);
        if (!a.due_at) return 1;
        if (!b.due_at) return -1;
        return a.due_at < b.due_at ? -1 : 1;
      });
    } else {
      ordered = [...filtered].sort((a, b) => b.id - a.id);
    }
    if (editingId == null) return ordered;
    return [...ordered].sort((a, b) => {
      if (a.id === editingId) return -1;
      if (b.id === editingId) return 1;
      return 0;
    });
  }, [cards, search, stateFilter, order, editingId]);

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

  const shownDeck =
    filter === "all" ? null : (manual.find((deck) => deck.id === filter) ?? null);
  const HeaderIcon = shownDeck ? deckIcon(shownDeck) : BookOpen;

  return (
    <div className="flex flex-col gap-4">
      {onBackToLesson ? (
        <button
          type="button"
          onClick={onBackToLesson}
          className="inline-flex w-fit items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium hover:border-primary/50"
        >
          <ChevronLeft className="size-4" aria-hidden="true" />
          {t("flashcards.cards.backToLesson")}
        </button>
      ) : null}
      <Card className="gap-3 p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <HeaderIcon className="size-4 text-primary" aria-hidden="true" />
          {shownDeck ? shownDeck.name : t("flashcards.cards.title")}
        </h2>

        {addCardsNonce > 0 ? (
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {t("flashcards.cards.createdHint")}
          </p>
        ) : null}

        <DeckGrid
          dense
          decks={manual}
          selectedId={shownDeck?.id ?? null}
          onSelect={(id) => applyFilter(id)}
          label={t("flashcards.cards.deckFilter")}
          leading={{
            label: t("flashcards.cards.allDecks"),
            pressed: filter === "all",
            onSelect: () => applyFilter("all"),
          }}
        />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("flashcards.cards.searchPlaceholder")}
          aria-label={t("flashcards.cards.searchPlaceholder")}
          className={INPUT}
        />

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
                ref={card.id === editingId ? editorRef : undefined}
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
      </div>
      {/* El recordatorio va en su propia línea: en la fila de anverso/reverso
          el botón de borrar le quitaba el ancho y no se podía escribir. */}
      <div className="flex min-w-0 items-center gap-2">
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
            size="icon"
            variant="ghost"
            className="shrink-0"
            aria-label={t("flashcards.cards.mnemonicClear")}
            title={t("flashcards.cards.mnemonicClear")}
            onClick={() => setMnemonic("")}
          >
            <Eraser className="size-3.5" aria-hidden="true" />
          </Button>
        ) : null}
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

function StatsTab({ userId }: { userId: string }) {
  const { t } = useI18n();
  const [stats, setStats] = useState<FlashcardStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      setStats(await getFlashcardStats(userId, 0));
    } catch {
      setError(true);
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [userId]);

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
