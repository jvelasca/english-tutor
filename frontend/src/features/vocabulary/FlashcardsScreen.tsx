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
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  BookOpen,
  Library,
  Layers,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import {
  createFlashcard,
  createFlashcardDeck,
  deleteFlashcard,
  deleteFlashcardDeck,
  getFlashcardQueue,
  getFlashcardStats,
  listFlashcardCards,
  listFlashcardDecks,
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
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
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
  const [decks, setDecks] = useState<FlashcardDecks | null>(null);
  const [deckId, setDeckId] = useState<number | null>(null);
  const [collection, setCollection] = useState<CollectionFilter | null>(null);
  const [autoStart, setAutoStart] = useState(false);
  const [reloadNonce, setReloadNonce] = useState(0);
  const [error, setError] = useState(false);

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
        role="group"
        aria-label={t("flashcards.viewsLabel")}
        className="flex flex-wrap items-center gap-1"
      >
        {TABS.map((entry) => {
          const Icon = entry.Icon;
          const active = tab === entry.id;
          return (
            <button
              key={entry.id}
              type="button"
              aria-pressed={active}
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
          onStudyDeck={(id) => {
            setDeckId(id);
            setCollection(null);
            setAutoStart(true);
            setTab("study");
          }}
        />
      ) : tab === "cards" ? (
        <CardsTab userId={userId} decks={decks} reloadNonce={reloadNonce} />
      ) : (
        <StatsTab userId={userId} decks={decks} deckId={deckId} onPick={setDeckId} />
      )}
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
            <p className="text-sm text-muted-foreground">
              {t("flashcards.study.empty")}
            </p>
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
}: {
  userId: string;
  decks: FlashcardDecks | null;
  reloadNonce: number;
  onChanged: () => void;
  onStudyDeck: (id: number) => void;
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
      await createFlashcardDeck(userId, { name: name.trim() });
      setName("");
      onChanged();
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
  reloadNonce,
}: {
  userId: string;
  decks: FlashcardDecks | null;
  reloadNonce: number;
}) {
  const { t } = useI18n();
  const manual = useMemo(
    () => (decks?.decks ?? []).filter((d) => !d.is_auto),
    [decks],
  );
  const [deckId, setDeckId] = useState<number | null>(null);
  const [cards, setCards] = useState<FlashcardCard[]>([]);
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState<string>("all");
  const [order, setOrder] = useState<CardOrder>("recent");
  const [newFront, setNewFront] = useState("");
  const [newBack, setNewBack] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    setDeckId((current) =>
      current != null && manual.some((d) => d.id === current)
        ? current
        : manual[0]?.id ?? null,
    );
  }, [manual]);

  const loadCards = useCallback(async () => {
    if (deckId == null) {
      setCards([]);
      return;
    }
    setError(false);
    try {
      const data = await listFlashcardCards(userId, deckId);
      setCards(data.cards);
    } catch {
      setError(true);
      setCards([]);
    }
  }, [userId, deckId]);

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
    if (deckId == null || !newFront.trim() || busy) return;
    setBusy(true);
    setError(false);
    try {
      await createFlashcard(userId, deckId, {
        front: newFront.trim(),
        back: newBack.trim(),
      });
      setNewFront("");
      setNewBack("");
      await loadCards();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(card: FlashcardCard) {
    if (deckId == null || busy) return;
    setBusy(true);
    setError(false);
    try {
      await deleteFlashcard(userId, deckId, card.id);
      await loadCards();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  if (manual.length === 0 || deckId == null) {
    return (
      <Card className="p-5">
        <p className="text-sm text-muted-foreground">
          {t("flashcards.cards.pickDeck")}
        </p>
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

        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            aria-label={t("flashcards.study.deck")}
            value={deckId ?? ""}
            onChange={(e) => setDeckId(Number(e.target.value))}
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
                    deckId={deckId}
                    card={card}
                    onSaved={async () => {
                      setEditingId(null);
                      await loadCards();
                    }}
                  />
                ) : (
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="flex min-w-0 flex-col">
                      <span className="text-sm font-semibold" lang="en">
                        {card.front}
                      </span>
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
            value={newFront}
            onChange={(e) => setNewFront(e.target.value)}
            placeholder={t("flashcards.cards.frontPlaceholder")}
            maxLength={400}
            className={cn(INPUT, "flex-1")}
            lang="en"
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
        lang="en"
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
