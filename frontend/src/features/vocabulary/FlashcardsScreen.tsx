/**
 * Modo Flashcards del diccionario (V3.78.0): la ÚNICA superficie de estudio.
 *
 * Cuatro subpestañas, en el orden en que se usan:
 *
 * - **Estudiar**: la cola unificada (léxico + tarjetas a mano) con los límites
 *   del día. Es lo que antes hacía la sesión de retención incrustada en
 *   Personal y lo que hacía la sesión acotada de «Mis listas»; ahora hay una
 *   sola.
 * - **Mazos**: el mazo automático (todo el léxico, no editable ni borrable) y
 *   los manuales, con sus límites.
 * - **Tarjetas**: navegador y CRUD de las tarjetas de un mazo manual.
 * - **Estadísticas**: repasos por día, acierto y previsión.
 *
 * El contenedor es quien pide la cola y quien califica: `StudySession` solo
 * pinta y avisa. Así el mismo componente sirve para el mazo automático y para
 * uno manual sin saber cuál es.
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
  Library,
  Layers,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
} from "lucide-react";
import {
  addFlashcardsBulk,
  createFlashcard,
  createFlashcardDeck,
  deleteFlashcard,
  deleteFlashcardDeck,
  enrollVocabCollection,
  getFlashcardQueue,
  getFlashcardStats,
  listFlashcardCards,
  listFlashcardDecks,
  listVocabCollections,
  reviewFlashcard,
  updateFlashcard,
  updateFlashcardDeck,
} from "../../api/vocabulary";
import type {
  FlashcardCard,
  FlashcardDeck,
  FlashcardDecks,
  FlashcardQueue,
  FlashcardStats,
  FlashcardStudyItem,
  VocabCollection,
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { useTabList } from "../../hooks/useTabList";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { cn } from "../../lib/utils";
import { StudySession } from "./StudySession";

const INPUT =
  "rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground";

type Tab = "study" | "decks" | "cards" | "stats";

const TABS: { id: Tab; labelKey: string; Icon: typeof Layers }[] = [
  { id: "study", labelKey: "flashcards.tabs.study", Icon: Layers },
  { id: "decks", labelKey: "flashcards.tabs.decks", Icon: Library },
  { id: "cards", labelKey: "flashcards.tabs.cards", Icon: BookOpen },
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
  /** Cambia en cada petición de estudio, para reabrir aunque sea el mismo foco. */
  focusNonce?: number;
}

export function FlashcardsScreen({
  userId,
  focusCollectionId = null,
  focusCollectionLabel = "",
  focusNonce = 0,
}: FlashcardsScreenProps) {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("study");
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
  const openCardsFor = useCallback((id: number) => {
    setDeckId(id);
    setCollection(null);
    setTab("cards");
    setAddCardsNonce((n) => n + 1);
  }, []);

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
    [],
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
    setDeckId(decks?.auto_deck_id ?? 0);
    setCollection(
      focusCollectionId != null
        ? { id: focusCollectionId, label: focusCollectionLabel }
        : null,
    );
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
        className="flex flex-wrap items-center gap-1"
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
                "inline-flex min-h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-semibold transition-colors",
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
        {error ? (
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
  /** V3.80.0: abre Tarjetas con este mazo listo para escribir su primera carta. */
  onAddCards: (id: number) => void;
  onExit: () => void;
}) {
  const { t } = useI18n();
  const [queue, setQueue] = useState<FlashcardQueue | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [studying, setStudying] = useState(false);
  const [sessionNonce, setSessionNonce] = useState(0);

  const deck = deckId ?? 0;
  const isAuto = deck === (decks?.auto_deck_id ?? 0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const data = await getFlashcardQueue(userId, deck, {
        collectionId: isAuto ? collection?.id ?? null : null,
      });
      setQueue(data);
      return data;
    } catch {
      setError(true);
      setQueue(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, [userId, deck, isAuto, collection?.id]);

  useEffect(() => {
    void load();
  }, [load, reloadNonce]);

  const items = queue?.items ?? [];

  // El arranque automático espera a que la cola esté cargada: si se abriera la
  // sesión con la lista vacía, el alumno vería el resumen de «0 repasadas».
  useEffect(() => {
    if (autoStart && !loading && queue) {
      onAutoStarted();
      if (items.length > 0) {
        setStudying(true);
        setSessionNonce((n) => n + 1);
      }
    }
    // `items` se deriva de `queue`, que ya está en las dependencias.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart, loading, queue]);

  const deckName = useMemo(() => {
    if (queue?.deck) {
      return queue.deck.is_auto ? t("flashcards.decks.auto") : queue.deck.name;
    }
    const found = decks?.decks.find((d) => d.id === deck);
    return found?.is_auto ? t("flashcards.decks.auto") : found?.name ?? "";
  }, [queue?.deck, decks, deck, t]);

  const handleGrade = useCallback(
    async (item: FlashcardStudyItem, grade: number) => {
      // La cola es de UN mazo, así que el endpoint es el mismo para el léxico y
      // para las tarjetas a mano: lo que cambia es `card_type`.
      await reviewFlashcard(userId, deck, {
        card_type: item.card_type,
        card_id: item.card_id,
        grade,
      });
    },
    [userId, deck],
  );

  if (studying && queue) {
    return (
      <StudySession
        key={sessionNonce}
        userId={userId}
        items={queue.items}
        deckName={deckName}
        onGrade={handleGrade}
        onRestart={async () => {
          // La sesión NO se reinicia sobre la cola vieja: se pide una nueva y,
          // si aún queda algo, se abre otra sesión con la `key` remontada. Si no
          // queda nada, se queda el panel con el recuento, que es la respuesta.
          setStudying(false);
          const data = await load();
          if (data && data.items.length > 0) {
            setSessionNonce((n) => n + 1);
            setStudying(true);
          }
        }}
        onExit={() => {
          setStudying(false);
          onExit();
        }}
      />
    );
  }

  return (
    <Card className="gap-3 p-5">
      <div className="flex flex-col gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Layers className="size-4 text-primary" aria-hidden="true" />
          {t("flashcards.study.title")}
        </h2>
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("flashcards.study.hint")}
        </p>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <DeckSelect decks={decks} value={deck} onChange={onPick} />
        {collection ? (
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
        {!isAuto ? (
          <p className="text-[11px] text-muted-foreground">
            {t("flashcards.study.deckHint")}
          </p>
        ) : null}
      </div>

      {error ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          {t("dictionary.loadError")}
          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium hover:border-primary/50"
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            {t("common.retry")}
          </button>
        </p>
      ) : loading ? (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      ) : (
        <>
          <p className="text-sm font-medium">
            {t("flashcards.study.pendingToday").replace(
              "{n}",
              String(items.length),
            )}
          </p>
          {queue ? (
            <p className="text-[11px] text-muted-foreground">
              {t("flashcards.study.limitsNote")
                .replace("{new}", String(queue.limits.new_remaining))
                .replace("{review}", String(queue.limits.review_remaining))}
            </p>
          ) : null}
          {items.length === 0 ? (
            // V3.80.0: «no hay nada pendiente» y «el mazo está vacío» son cosas
            // distintas y solo una tiene arreglo aquí. Un mazo manual sin
            // tarjetas ofrece el camino para meterlas; el automático vacío manda
            // al diccionario, que es donde se añaden palabras. Decir «nada
            // pendiente» en los dos casos dejaba al alumno sin saber qué hacer.
            queue && queue.deck.card_count === 0 ? (
              isAuto ? (
                <p className="text-sm text-muted-foreground">
                  {t("flashcards.study.emptyAuto")}
                </p>
              ) : (
                <div className="flex flex-col gap-2">
                  <p className="text-sm text-muted-foreground">
                    {t("flashcards.study.emptyDeck")}
                  </p>
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
              )
            ) : (
              <p className="text-sm text-muted-foreground">
                {t("flashcards.study.empty")}
              </p>
            )
          ) : (
            <Button
              type="button"
              size="sm"
              className="w-fit"
              onClick={() => {
                setSessionNonce((n) => n + 1);
                setStudying(true);
              }}
            >
              {t("flashcards.study.start").replace("{n}", String(items.length))}
            </Button>
          )}
        </>
      )}
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
  const [error, setError] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);

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
    if (busy) return;
    const ok = window.confirm(
      t("flashcards.decks.deleteConfirm")
        .replace("{name}", deck.name)
        .replace("{n}", String(deck.card_count)),
    );
    if (!ok) return;
    setBusy(true);
    setError(false);
    try {
      await deleteFlashcardDeck(userId, deck.id);
      onChanged();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
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

        {auto ? (
          <div className="flex flex-col gap-1 rounded-lg border border-border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-semibold">
                <DeckLabel deck={auto} />
              </span>
              <div className="flex items-center gap-2">
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
                      disabled={busy}
                      onClick={() => void handleDelete(deck)}
                    >
                      <Trash2 className="size-3.5" aria-hidden="true" />
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
            <Plus className="size-3.5" aria-hidden="true" />
            {t("flashcards.decks.create")}
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
                    <Plus className="size-3.5" aria-hidden="true" />
                    {t("flashcards.decks.readyAdd")}
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
        {t("flashcards.decks.save")}
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
  /** V3.80.0: la selección compartida de la pantalla (una sola, como en Anki). */
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
  /**
   * Si la selección compartida es un mazo manual, manda ella. Si no (p. ej. el
   * automático, que es el defecto al abrir), Tarjetas mira el primero editable
   * en su propio estado y **sin tocar la selección compartida**: asomarse a
   * Tarjetas no debe cambiar por sorpresa el mazo que se estudia. Cuando el
   * alumno elige en el desplegable, su elección sí se propaga a toda la pantalla.
   */
  const [localDeckId, setLocalDeckId] = useState<number | null>(null);
  const shared = manual.find((d) => d.id === deckId) ?? null;
  const local = manual.find((d) => d.id === localDeckId) ?? null;
  const active = shared ?? local ?? manual[0] ?? null;
  const activeId = active?.id ?? null;

  const [cards, setCards] = useState<FlashcardCard[]>([]);
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState<string>("all");
  const [order, setOrder] = useState<CardOrder>("recent");
  const [newFront, setNewFront] = useState("");
  const [newBack, setNewBack] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  // V3.80.0: pegado masivo. `bulkResult` guarda cuántas entraron de verdad, que
  // es lo único honesto que se puede decir después de pegar 40 líneas.
  const [bulkText, setBulkText] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkError, setBulkError] = useState(false);
  const [bulkResult, setBulkResult] = useState<number | null>(null);
  const frontRef = useRef<HTMLInputElement | null>(null);

  // Al llegar desde «crear mazo» o «Añadir tarjetas», el anverso se enfoca solo:
  // el siguiente paso del alumno es escribir, y pedirle un clic extra era parte
  // del «creo un mazo y no sé cómo seguir».
  useEffect(() => {
    if (addCardsNonce > 0) frontRef.current?.focus();
  }, [addCardsNonce, activeId]);

  const loadCards = useCallback(async () => {
    if (activeId == null) {
      setCards([]);
      return;
    }
    setError(false);
    try {
      const data = await listFlashcardCards(userId, activeId);
      setCards(data.cards);
    } catch {
      setError(true);
      setCards([]);
    }
  }, [userId, activeId]);

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
        card.back.toLowerCase().includes(needle)
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

  async function handleAdd() {
    if (activeId == null || !newFront.trim() || busy) return;
    setBusy(true);
    setError(false);
    try {
      await createFlashcard(userId, activeId, {
        front: newFront.trim(),
        back: newBack.trim(),
      });
      setNewFront("");
      setNewBack("");
      await loadCards();
      frontRef.current?.focus();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(card: FlashcardCard) {
    if (activeId == null || busy) return;
    setBusy(true);
    setError(false);
    try {
      await deleteFlashcard(userId, activeId, card.id);
      await loadCards();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  async function handleBulkAdd() {
    if (activeId == null || !bulkText.trim() || bulkBusy) return;
    setBulkBusy(true);
    setBulkError(false);
    setBulkResult(null);
    try {
      const result = await addFlashcardsBulk(userId, activeId, bulkText);
      setBulkText("");
      setBulkResult(result.count);
      await loadCards();
    } catch {
      setBulkError(true);
    } finally {
      setBulkBusy(false);
    }
  }

  if (manual.length === 0 || activeId == null) {
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
            aria-label={t("flashcards.study.deck")}
            value={active.id}
            onChange={(e) => {
              const id = Number(e.target.value);
              setLocalDeckId(id);
              onPick(id);
            }}
            className={cn(INPUT, "sm:w-64")}
          >
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

        {visible.length === 0 ? (
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
                    deckId={active.id}
                    card={card}
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
                        disabled={busy}
                        onClick={() => void handleDelete(card)}
                      >
                        <Trash2 className="size-3.5" aria-hidden="true" />
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

      <Card className="gap-2 p-5">
        <h3 className="text-sm font-semibold">{t("flashcards.cards.add")}</h3>
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            void handleAdd();
          }}
        >
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
          <Button type="submit" size="sm" disabled={busy || !newFront.trim()}>
            <Plus className="size-3.5" aria-hidden="true" />
            {t("flashcards.cards.save")}
          </Button>
        </form>
      </Card>

      {/* V3.80.0: pegar una lista. La sintaxis es la MISMA que la del léxico
          («una por línea, anverso,reverso»), y se dice con un ejemplo, porque un
          formato que hay que adivinar es un formato que nadie usa. */}
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
            <Button type="submit" size="sm" disabled={bulkBusy || !bulkText.trim()}>
              <Plus className="size-3.5" aria-hidden="true" />
              {t("flashcards.cards.bulkAdd")}
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

function CardEditor({
  userId,
  deckId,
  card,
  onSaved,
}: {
  userId: string;
  deckId: number;
  card: FlashcardCard;
  onSaved: () => void | Promise<void>;
}) {
  const { t } = useI18n();
  const [front, setFront] = useState(card.front);
  const [back, setBack] = useState(card.back);
  const [busy, setBusy] = useState(false);

  return (
    <form
      className="flex flex-col gap-2 sm:flex-row"
      onSubmit={(e) => {
        e.preventDefault();
        if (busy || !front.trim()) return;
        setBusy(true);
        void updateFlashcard(userId, deckId, card.id, {
          front: front.trim(),
          back: back.trim(),
        })
          .then(() => onSaved())
          .finally(() => setBusy(false));
      }}
    >
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
      <Button type="submit" size="sm" disabled={busy}>
        {t("flashcards.cards.save")}
      </Button>
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
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
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
