import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { motion } from "motion/react";
import {
  AlertTriangle,
  ArrowLeftRight,
  BookOpen,
  Check,
  Languages,
  Layers,
  Loader2,
  Mic,
  Plus,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { ApiError } from "../../api/client";
import { normalizeDictionaryEntry } from "../../api/normalize";
import {
  addVocabularyItem,
  createFlashcardDeck,
  createVocabularyCard,
  listFlashcardDecks,
  lookupDictionaryWord,
} from "../../api/vocabulary";
import type {
  DictionaryDirection,
  DictionaryEntry,
  DictionaryMeaning,
  DictionarySurfaceUsage,
  DictionaryUnitUsage,
  FlashcardDeck,
  LexicalCompetence,
  LexicalStatus,
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { LevelBadge } from "../../components/LevelBadge";
import { ItemReplayButton } from "../../components/ItemReplayButton";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Progress } from "../../components/ui/progress";
import { cn } from "../../lib/utils";
import {
  DIRECTION_EXAMPLES,
  DIRECTION_OPTIONS,
  directionClass,
  directionLabelKey,
} from "../../utils/dictionaryDirection";
import { WordDrill } from "./wordDrill";

/** Colores de estado: misma taxonomía y paleta que `PersonalDictionary`. */
const STATUS_TONE: Record<LexicalStatus, string> = {
  mastered: "border-transparent bg-success/15 text-success",
  known: "border-transparent bg-primary/15 text-primary",
  learning: "border-transparent bg-warning/15 text-warning",
  weak: "border-transparent bg-destructive/10 text-destructive",
};

const MAX_QUERY_LENGTH = 80;

/** Destino de la tarjeta manual del alta (V3.84.1/V3.86.0): lo que queda por
 *  guardar si la SEGUNDA escritura falla, para poder reintentarla sin repetir el
 *  alta. V3.86.0: la tarjeta nace en N mazos a la vez (n: m real). */
interface DeckCardTarget {
  deckIds: number[];
  deckName: string;
  front: string;
  back: string;
  mnemonic: string;
}

/** V3.84.1: el nombre de mazo ya existe para este alumno —el backend lo
 *  distingue con `DECK_NAME_TAKEN`—, frente a cualquier otro fallo de creación. */
type DeckCreateError = "duplicate" | "generic" | null;

interface DictionaryLookupProps {
  userId: string | null;
  /**
   * Cabecera propia (`h1` + subtítulo). Por defecto `true`, que es lo que
   * necesitan las superficies que montan la vista suelta. `DictionaryScreen`
   * la apaga (`false`) porque la pantalla ya trae su `h1` y su subtítulo: sin
   * esto habría **dos `h1`** en `/diccionario` y el título repetido dos veces.
   */
  showHeader?: boolean;
  /**
   * V3.83.0: puente a la única superficie de estudio. Tras añadir una palabra
   * —o si la consultada ya está en el léxico—, el panel ofrece «Estudiar en
   * Flashcards». Quien monta la vista dice cómo se llega allí; si no se ofrece,
   * el botón no se pinta (no se promete un destino que no existe).
   *
   * V3.84.0: recibe el mazo con el que abrir el estudio. Si la palabra se
   * archivó en un mazo manual, se abre ESE mazo; sin argumento, el automático.
   */
  onOpenFlashcards?: (deckId?: number) => void;
}

/** Diccionario de consulta (V3.30, D2/D3): busca CUALQUIER palabra (esté o no
 * en el léxico del alumno) y muestra definición/traducción cacheadas del modelo
 * local (o degradación a `definition_source="none"`), una frase de ejemplo
 * determinista del banco y la marca de uso/aprendizaje. La consulta es solo
 * lectura: nunca registra evidencia.
 * V3.32: el botón «Practicar esta palabra» abre la escalera de drill oral
 * (Recall → Sentence, `./wordDrill`) sobre la palabra consultada. Practicar es
 * una acción explícita del alumno: solo su resultado escribe evidencia.
 *
 * V3.75.8: el buscador pasa a ser el protagonista de la vista —campo grande,
 * marco y botón de borrado, con el **color de la dirección** (azul EN→ES,
 * fucsia ES→EN)— y el conmutador de sentido vive DENTRO del buscador, para no
 * confundirse con las pestañas de la pantalla. Sin consulta todavía, la vista
 * ofrece ejemplos para arrancar.
 *
 * V3.83.0: «Añadir a Flashcards» deja de ser un botón de un solo uso. Abre un
 * panel que declara qué significa añadir —la palabra pasa a APRENDIZAJE, con su
 * carta FSRS, y por eso aparece también en PERSONAL y en el mazo automático «Mi
 * diccionario»— y permite archivarla además en una lista propia. El alta sigue
 * siendo `addVocabularyItem` (léxico + FSRS + estado `learning`), así que el
 * diccionario, PERSONAL y Flashcards pasan a ser un solo proceso de estudio. */
export function DictionaryLookup({
  userId,
  showHeader = true,
  onOpenFlashcards,
}: DictionaryLookupProps) {
  const { t } = useI18n();
  const [direction, setDirection] = useState<DictionaryDirection>("en-es");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [networkError, setNetworkError] = useState(false);
  const [invalidError, setInvalidError] = useState(false);
  const [entry, setEntry] = useState<DictionaryEntry | null>(null);
  // Palabra y dirección de la consulta actual (para el retry tras un error de
  // red: reintentar con la dirección con la que se buscó, no con la activa).
  const [lastQuery, setLastQuery] = useState("");
  const [lastDirection, setLastDirection] = useState<DictionaryDirection>("en-es");
  // V3.32: palabra en drill oral («Practicar esta palabra») lanzado desde la
  // tarjeta. La escalera vive debajo de la tarjeta de resultado. V3.39: en
  // ES→EN se practica siempre el EQUIVALENTE INGLÉS, nunca el término español.
  const [practiceWord, setPracticeWord] = useState<string | null>(null);
  // V3.86.0: significado ELEGIDO dentro de `entry.meanings`. `-1` = el defecto
  // (primer significado que NO es nombre propio). Se resetea en cada consulta
  // para que elegir «Lima (capital)» no se arrastre a la palabra siguiente.
  const [meaningIndex, setMeaningIndex] = useState(-1);
  const [addStatus, setAddStatus] = useState<
    "idle" | "ok" | "partial" | "error"
  >("idle");
  const [adding, setAdding] = useState(false);
  const [creatingDeck, setCreatingDeck] = useState(false);
  // V3.84.1: fallo al CREAR un mazo, separado de `deckError` (fallo al CARGAR la
  // lista). Antes compartían estado y un nombre duplicado ocultaba el selector.
  const [deckCreateError, setDeckCreateError] =
    useState<DeckCreateError>(null);
  // V3.83.0: el panel de alta. V3.84.0: el destino es un MAZO manual (no una
  // lista): `decks` es `null` mientras no se ha pedido (carga perezosa al abrir
  // el panel, para no pagar una consulta en cada búsqueda).
  // V3.86.0: `selectedDecks` es un CONJUNTO: la ficha nace en todos a la vez, y
  // vacío significa «solo léxico, sin mazo» (ya no hay supresión por `tracked`).
  const [addOpen, setAddOpen] = useState(false);
  const [decks, setDecks] = useState<FlashcardDeck[] | null>(null);
  const [deckError, setDeckError] = useState(false);
  const [selectedDecks, setSelectedDecks] = useState<number[]>([]);
  const [addMnemonic, setAddMnemonic] = useState("");
  const [addBack, setAddBack] = useState("");
  // Nombres de los mazos donde se guardó de verdad (para declararlo y abrirlos).
  const [savedDecks, setSavedDecks] = useState<
    { id: number; name: string }[]
  >([]);
  // V3.84.1: la tarjeta que quedó pendiente cuando el léxico ya entró y el mazo
  // falló. Es lo que declara el estado PARCIAL y lo que reintenta el botón: sin
  // esto la UI diría «error» sobre una operación que ya está a medias.
  const [pendingDeck, setPendingDeck] = useState<DeckCardTarget | null>(null);

  async function runLookup(raw: string, dir: DictionaryDirection = direction) {
    if (!userId) return;
    const word = raw.trim();
    // Validación local espejo del backend (422): vacía tras recortar, solo
    // puntuación o demasiado larga. Así el error de «palabra inválida» es
    // determinista y nunca depende de la lengua del detalle del servidor.
    if (!word || word.length > MAX_QUERY_LENGTH || !/[\p{L}\p{N}]/u.test(word)) {
      setInvalidError(true);
      setNetworkError(false);
      setEntry(null);
      setPracticeWord(null);
      return;
    }
    setInvalidError(false);
    setNetworkError(false);
    setLoading(true);
    setLastQuery(word);
    setLastDirection(dir);
    setPracticeWord(null);
    setMeaningIndex(-1);
    setAddStatus("idle");
    setAddOpen(false);
    setSelectedDecks([]);
    setSavedDecks([]);
    setPendingDeck(null);
    setDeckCreateError(null);
    try {
      const data = await lookupDictionaryWord(userId, word, dir);
      setEntry(normalizeDictionaryEntry(data));
    } catch {
      setEntry(null);
      setNetworkError(true);
    } finally {
      setLoading(false);
    }
  }

  /** Abre el panel y, la primera vez, carga los mazos manuales del alumno.
   *  El mazo automático (id 0) no se ofrece: es una vista del léxico, no un
   *  destino; y los packs temáticos tampoco, porque son contenido curado.
   *  V3.86.0: un fallo de red NO cierra el panel ni esconde el selector —el
   *  alumno puede seguir añadiendo solo al léxico—; se ofrece reintentar. */
  async function openAddPanel() {
    setAddOpen(true);
    setAddStatus("idle");
    setSavedDecks([]);
    setPendingDeck(null);
    setDeckCreateError(null);
    if (!userId || decks !== null) return;
    await loadDecks();
  }

  /** Carga (o reintenta cargar) los mazos manuales del panel de alta. */
  async function loadDecks() {
    if (!userId) return;
    setDeckError(false);
    try {
      const data = await listFlashcardDecks(userId);
      const all = Array.isArray(data?.decks) ? data.decks : [];
      setDecks(all.filter((d) => !d.is_auto));
    } catch {
      setDeckError(true);
      setDecks(null);
    }
  }

  function closeAddPanel() {
    setAddOpen(false);
    setAddStatus("idle");
    setSelectedDecks([]);
    setSavedDecks([]);
    setPendingDeck(null);
    setDeckCreateError(null);
  }

  function toggleAddPanel() {
    if (addOpen) {
      closeAddPanel();
      return;
    }
    void openAddPanel();
  }

  /** Crea un mazo desde el propio panel y lo deja seleccionado (V3.84.0).
   *  Sin este camino, elegir mazo obligaba a salir a Flashcards.
   *  V3.84.1: un nombre duplicado se declara como tal (el backend lo distingue
   *  con `DECK_NAME_TAKEN`) y NO oculta el selector, que es lo que hacía al
   *  compartir estado con el fallo de carga de mazos. */
  async function handleCreateDeck(name: string) {
    if (!userId || creatingDeck) return;
    setCreatingDeck(true);
    setDeckCreateError(null);
    try {
      const created = await createFlashcardDeck(userId, { name });
      setDecks((current) => [...(current ?? []), created]);
      setSelectedDecks((current) =>
        current.includes(created.id) ? current : [...current, created.id],
      );
      setDeckError(false);
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : "";
      setDeckCreateError(detail === "DECK_NAME_TAKEN" ? "duplicate" : "generic");
    } finally {
      setCreatingDeck(false);
    }
  }

  /** V3.84.1: SEGUNDA escritura del alta, aislada para poder reintentarla sola.
   *  Devuelve si la tarjeta entró de verdad; nunca lanza. V3.86.0: una sola
   *  llamada crea la ficha en TODOS los mazos marcados (tabla puente). */
  async function saveDeckCard(target: DeckCardTarget): Promise<boolean> {
    if (!userId) return false;
    try {
      await createVocabularyCard(userId, {
        front: target.front,
        back: target.back,
        mnemonic: target.mnemonic,
        deckIds: target.deckIds,
      });
      setSavedDecks(
        target.deckIds.map((id) => ({
          id,
          name: decks?.find((d) => d.id === id)?.name ?? target.deckName,
        })),
      );
      return true;
    } catch {
      return false;
    }
  }

  /** V3.84.1: reintenta SOLO la tarjeta del mazo tras un alta parcial. El
   *  aprendizaje ya está escrito, así que no se repite `addVocabularyItem`. */
  async function handleRetryDeckCard() {
    if (!pendingDeck || adding) return;
    setAdding(true);
    const target = pendingDeck;
    const saved = await saveDeckCard(target);
    setAdding(false);
    if (!saved) {
      setAddStatus("partial");
      return;
    }
    setPendingDeck(null);
    setAddStatus("ok");
    setSelectedDecks([]);
  }

  /**
   * Alta del diccionario (V3.83.0; V3.86.0: sin supresión por `tracked`).
   *
   * El panel decide el conjunto de mazos, el recordatorio y —si no hay
   * equivalente— el reverso escrito a mano. La palabra SIEMPRE entra en el
   * léxico (estado `learning`, con su carta FSRS) **salvo** que ya estuviera
   * rastreada: entonces no se reescribe y solo se guarda la ficha.
   */
  async function handleAddToFlashcards(payload: {
    deckIds: number[];
    mnemonic: string;
    back: string;
  }) {
    if (!userId || !cardFront || adding) return;
    setAdding(true);
    setAddStatus("idle");
    setSavedDecks([]);
    setPendingDeck(null);
    const term = cardFront;
    const back = payload.back.trim() || cardBack;
    // 1) El alta del léxico + carta FSRS + estado `learning`. Si la palabra ya
    //    está rastreada, NO se reescribe: solo se añade la ficha a sus mazos.
    if (!tracked) {
      const translation =
        entry?.direction === "en-es" ? equivalent : entry?.word ?? "";
      try {
        await addVocabularyItem(userId, term, { translation });
      } catch {
        setAddStatus("error");
        setAdding(false);
        return;
      }
      // El alta deja la palabra en el léxico: se refresca en silencio para que
      // la marca de uso lo refleje sin desmontar la tarjeta.
      void refreshEntry(lastQuery, lastDirection);
    }
    // 2) La tarjeta manual: una sola escritura crea la ficha en TODOS los mazos
    //    marcados (V3.86.0, tabla puente). Si falla, el aprendizaje YA está
    //    hecho: se declara el estado PARCIAL y se ofrece reintentar solo esto.
    if (payload.deckIds.length > 0) {
      const target: DeckCardTarget = {
        deckIds: payload.deckIds,
        deckName:
          decks?.find((d) => d.id === payload.deckIds[0])?.name ?? term,
        front: term,
        back,
        mnemonic: payload.mnemonic.trim(),
      };
      const saved = await saveDeckCard(target);
      setAdding(false);
      if (!saved) {
        setPendingDeck(target);
        setAddStatus("partial");
        return;
      }
    }
    setAdding(false);
    setAddStatus("ok");
    setSelectedDecks([]);
    setAddMnemonic("");
    setAddBack("");
  }

  // V3.32: tras producir la palabra en el drill, refresca la entrada en silencio
  // (sin togglear `loading`, para no desmontar la tarjeta ni el drill) para
  // actualizar la marca de uso (p. ej. una palabra nueva pasa a tracked).
  async function refreshEntry(word: string, dir: DictionaryDirection) {
    if (!userId) return;
    try {
      const data = await lookupDictionaryWord(userId, word, dir);
      setEntry(normalizeDictionaryEntry(data));
    } catch {
      /* conserva la entrada actual */
    }
  }

  // V3.39: cambiar de dirección invalida el resultado anterior (la palabra
  // buscada era de la otra lengua). Se conserva el texto para editarlo.
  function changeDirection(next: DictionaryDirection) {
    if (next === direction) return;
    setDirection(next);
    setEntry(null);
    setPracticeWord(null);
    setInvalidError(false);
    setNetworkError(false);
    setAddOpen(false);
    setAddStatus("idle");
    setSelectedDecks([]);
    setSavedDecks([]);
    setPendingDeck(null);
    setDeckCreateError(null);
    setMeaningIndex(-1);
    setAddMnemonic("");
    setAddBack("");
  }

  // ---------------------------------------------------------------------------
  // V3.86.0: el SIGNIFICADO elegido manda sobre todo lo demás.
  //
  // `entry.meanings` trae los candidatos y el `translation` sigue siendo el del
  // significado por defecto (primer no-nombre-propio), así que el índice -1 se
  // resuelve a ese mismo. Un nombre propio NUNCA es el defecto: «lima» ofrece
  // «file (herramienta)» primero y «Lima (capital)» el último, marcado.
  // ---------------------------------------------------------------------------
  const meanings = entry?.meanings ?? [];
  const defaultMeaningIndex = useMemo(() => {
    const idx = meanings.findIndex((m) => !m.proper_noun);
    return idx >= 0 ? idx : 0;
  }, [meanings]);
  const activeMeaningIndex =
    meaningIndex >= 0 && meaningIndex < meanings.length
      ? meaningIndex
      : defaultMeaningIndex;
  const chosenMeaning: DictionaryMeaning | null =
    meanings.length > 0 ? meanings[activeMeaningIndex] ?? null : null;
  /** Equivalente mostrado: el significado elegido o, si no hay, el de siempre. */
  const equivalent = chosenMeaning?.term ?? entry?.translation ?? "";

  const isReverse = entry?.direction === "es-en";
  // Cara de la ficha: en ES→EN es el equivalente inglés elegido (o el término
  // buscado si la consulta no encontró equivalente, para poder escribir el
  // reverso a mano); en EN→ES es la palabra inglesa consultada.
  const cardFront = entry
    ? isReverse
      ? equivalent || entry.word
      : entry.word
    : null;
  // Reverso de la ficha: en EN→ES el equivalente español; en ES→EN el término
  // español buscado. Vacío = hay que escribirlo (no se inventa nada).
  const cardBack = entry
    ? isReverse
      ? equivalent
        ? entry.word
        : ""
      : equivalent
    : "";
  /** El reverso se pide a mano cuando la consulta no dio equivalente. */
  const manualBack = Boolean(entry) && cardBack === "";

  // V3.32: práctica oral sobre el INGLÉS. Sin equivalente inglés (ES→EN) no hay
  // nada que practicar.
  const practiceTerm = entry
    ? isReverse
      ? equivalent || null
      : entry.word
    : null;
  // V3.83.0: `tracked` significa que la palabra YA está en el léxico del alumno.
  // V3.86.0: eso ya NO esconde el alta: la ficha manual se puede crear igual, y
  // el panel lo declara («solo se guardan la tarjeta y sus mazos»).
  const tracked = Boolean(entry?.usage.tracked);

  // V3.75.8: color de la dirección ACTIVA (la del conmutador). El resultado usa
  // el de SU dirección (`entry.direction`), que es la que produjo la tarjeta.
  const activeDirClass = directionClass(direction);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void runLookup(query);
  }

  // V3.80.1: la X limpia la búsqueda Y su resultado. Antes vaciaba el campo pero
  // dejaba a la vista la tarjeta anterior, un estado que miente (parece que la
  // búsqueda sigue viva). Al limpiar del todo vuelven a verse los ejemplos.
  function clearQuery() {
    setQuery("");
    setEntry(null);
    setPracticeWord(null);
    setMeaningIndex(-1);
    setInvalidError(false);
    setNetworkError(false);
    setAddStatus("idle");
    setAddOpen(false);
    setSelectedDecks([]);
    setSavedDecks([]);
    setPendingDeck(null);
    setDeckCreateError(null);
    setAddMnemonic("");
    setAddBack("");
    setLastQuery("");
  }

  function searchExample(word: string) {
    setQuery(word);
    void runLookup(word);
  }

  /** Nada que mostrar todavía: ni resultado, ni carga, ni error. */
  const showExamples =
    Boolean(userId) && !loading && !entry && !networkError && !invalidError;

  return (
    <div className="flex flex-col gap-5">
      {showHeader && (
        <header className="flex flex-col gap-1.5">
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight sm:text-3xl">
            <Search className="size-6 text-primary" aria-hidden="true" />
            {t("dictionary.lookup.title")}
          </h1>
          <p className="text-muted-foreground">{t("dictionary.lookup.subtitle")}</p>
        </header>
      )}

      {/* ---------------------------------------------------------------
          El buscador. El color de la dirección vive aquí: barra superior,
          borde y anillo de foco (`.dir-field`) y las dos pastillas del
          conmutador de sentido, que se ofrecen dentro del propio buscador
          para que no compitan con las pestañas de la pantalla.
          --------------------------------------------------------------- */}
      <form
        role="search"
        onSubmit={onSubmit}
        className={cn(
          "relative overflow-hidden rounded-2xl border-2 border-border bg-card p-2 shadow-sm sm:p-3",
          activeDirClass,
          "dir-field",
        )}
      >
        <span
          className={cn("absolute inset-x-0 top-0 h-1", activeDirClass, "dir-bar")}
          aria-hidden="true"
        />

        {/* V3.39: conmutador de dirección (EN→ES / ES→EN), coloreado por sentido. */}
        <div
          role="group"
          aria-label={t("dictionary.lookup.directionLabel")}
          className="grid grid-cols-2 gap-2"
        >
          {DIRECTION_OPTIONS.map((option) => {
            const isActive = direction === option.id;
            return (
              <button
                key={option.id}
                type="button"
                aria-pressed={isActive}
                onClick={() => changeDirection(option.id)}
                className={cn(
                  "inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border px-2 text-xs font-semibold transition-colors sm:min-h-9 sm:px-3 sm:text-sm",
                  isActive
                    ? cn(directionClass(option.id), "dir-chip")
                    : "border-transparent text-muted-foreground hover:bg-secondary hover:text-foreground",
                )}
              >
                <Languages className="size-4 shrink-0" aria-hidden="true" />
                <span className="min-w-0">{t(option.labelKey)}</span>
              </button>
            );
          })}
        </div>

        <div className="mt-2 flex flex-col gap-2 sm:mt-3 sm:flex-row sm:items-center">
          <div className="relative flex min-w-0 flex-1 items-center">
            <Search
              className={cn(
                "pointer-events-none absolute left-3.5 size-5",
                activeDirClass,
                "dir-ink",
              )}
              aria-hidden="true"
            />
            <label className="sr-only" htmlFor="dictionary-lookup-input">
              {t("dictionary.lookup.searchAria")}
            </label>
            <input
              id="dictionary-lookup-input"
              type="text"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              lang={direction === "es-en" ? "es" : "en"}
              value={query}
              maxLength={MAX_QUERY_LENGTH}
              disabled={!userId || loading}
              onChange={(e) => {
                setQuery(e.target.value);
                setInvalidError(false);
              }}
              placeholder={
                direction === "es-en"
                  ? t("dictionary.lookup.placeholder.es-en")
                  : t("dictionary.lookup.placeholder")
              }
              className="h-12 w-full min-w-0 rounded-xl border border-input bg-background/60 pr-11 pl-12 text-base font-medium text-foreground outline-none transition-colors placeholder:font-normal placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-60 sm:h-14 sm:text-lg"
            />
            {query.length > 0 && (
              <button
                type="button"
                aria-label={t("dictionary.lookup.clearAria")}
                onClick={clearQuery}
                className="absolute right-2 grid size-8 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            )}
          </div>
          <Button
            type="submit"
            size="lg"
            disabled={!userId || loading || query.trim().length === 0}
            className="h-12 shrink-0 gap-2 rounded-xl px-5 text-base sm:h-14"
          >
            <Search className="size-5" aria-hidden="true" />
            {t("dictionary.lookup.button")}
          </Button>
        </div>
      </form>

      {!userId && (
        <p className="text-sm text-muted-foreground">
          {t("dictionary.lookup.noProfile")}
        </p>
      )}

      {/* Sin consulta todavía: ejemplos para arrancar (como en los diccionarios
          de referencia). Los ejemplos son contenido, no interfaz. */}
      {showExamples && (
        <section
          className={cn(
            "flex flex-col items-center gap-4 rounded-2xl border border-dashed border-border px-5 py-8 text-center",
            activeDirClass,
          )}
        >
          <span
            className={cn(
              "grid size-14 place-items-center rounded-2xl",
              activeDirClass,
              "dir-wash",
            )}
          >
            <BookOpen
              className={cn("size-7", activeDirClass, "dir-ink")}
              aria-hidden="true"
            />
          </span>
          <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {t("dictionary.lookup.tryExamples")}
          </p>
          <ul className="flex flex-wrap justify-center gap-2">
            {DIRECTION_EXAMPLES[direction].map((word) => (
              <li key={word}>
                <button
                  type="button"
                  onClick={() => searchExample(word)}
                  lang={direction === "es-en" ? "es" : "en"}
                  className={cn(
                    "inline-flex min-h-10 items-center rounded-full border px-4 text-sm font-medium transition-transform active:scale-[0.98]",
                    activeDirClass,
                    "dir-chip",
                  )}
                >
                  {word}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {userId && loading && (
        <p
          className="flex items-center gap-2 text-sm text-muted-foreground"
          role="status"
        >
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          {t("common.loading")}
        </p>
      )}

      {invalidError && (
        <p className="text-sm text-destructive" role="alert">
          {t("dictionary.lookup.error.invalid")}
        </p>
      )}

      {networkError && (
        <div className="flex flex-col items-start gap-2" role="alert">
          <p className="text-sm text-destructive">
            {t("dictionary.lookup.error.network")}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void runLookup(lastQuery, lastDirection)}
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            {t("common.retry")}
          </Button>
        </div>
      )}

      {userId && !loading && !networkError && !invalidError && entry && (
        <div className="flex flex-col gap-5">
          <ResultCard
            entry={entry}
            userId={userId}
            onPractice={practiceTerm ? () => setPracticeWord(practiceTerm) : undefined}
            tracked={tracked}
            addOpen={addOpen}
            meanings={meanings}
            meaningIndex={activeMeaningIndex}
            onPickMeaning={(index) => {
              setMeaningIndex(index);
              // Cambiar de significado invalida la práctica anterior: era de
              // OTRO significado (p. ej. se practicaba «Lima» y ahora «file»).
              setPracticeWord(null);
            }}
            equivalent={equivalent}
            // V3.86.0: el alta ya NO se esconde por `tracked`; solo hace falta un
            // anverso con el que crear la ficha.
            onToggleAdd={cardFront ? toggleAddPanel : undefined}
            onOpenFlashcards={onOpenFlashcards}
            addPanel={
              addOpen && cardFront ? (
                <AddToFlashcardsPanel
                  term={cardFront}
                  back={cardBack}
                  manualBack={manualBack}
                  backDraft={addBack}
                  onBackDraft={setAddBack}
                  mnemonic={addMnemonic}
                  onMnemonic={setAddMnemonic}
                  tracked={tracked}
                  decks={decks}
                  deckError={deckError}
                  deckCreateError={deckCreateError}
                  selectedDecks={selectedDecks}
                  onToggleDeck={(id) => {
                    setSelectedDecks((current) =>
                      current.includes(id)
                        ? current.filter((x) => x !== id)
                        : [...current, id],
                    );
                    setDeckCreateError(null);
                  }}
                  onRetryDecks={() => void loadDecks()}
                  creatingDeck={creatingDeck}
                  onCreateDeck={(name) => void handleCreateDeck(name)}
                  savedDecks={savedDecks}
                  pendingDeck={pendingDeck}
                  adding={adding}
                  status={addStatus}
                  onConfirm={(payload) =>
                    void handleAddToFlashcards({
                      deckIds: selectedDecks,
                      mnemonic: payload.mnemonic,
                      back: payload.back,
                    })
                  }
                  onRetryDeck={() => void handleRetryDeckCard()}
                  onClose={closeAddPanel}
                  onOpenFlashcards={onOpenFlashcards}
                />
              ) : null
            }
          />

          {/* V3.32: escalera de drill oral de la palabra consultada. Practicar
              es una acción real (no es parte de la consulta, D3): solo el
              resultado de esta práctica escribe evidencia. V3.39: en ES→EN se
              practica el equivalente inglés. */}
          {practiceWord && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <Mic className="size-4 text-primary" aria-hidden="true" />
                <p className="text-xs text-muted-foreground">
                  {t("dictionary.lookup.practiceHint")}
                </p>
              </div>
              <WordDrill
                userId={userId}
                word={practiceWord}
                onProduced={() =>
                  void refreshEntry(practiceWord, entry.direction)
                }
                onClose={() => setPracticeWord(null)}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * V3.83.0: panel de alta del diccionario a Flashcards.
 * V3.84.0: el destino es un **mazo manual**, no una lista, y se puede crear el
 * mazo sin salir del panel.
 * V3.86.0: el mazo deja de ser UNA elección. Se marcan los que se quieran (o
 * ninguno) y una sola escritura crea la ficha en todos a la vez. Además caben el
 * **recordatorio** (mnemónico) y el **reverso escrito a mano** cuando la consulta
 * no encontró equivalente. Un fallo de red al cargar los mazos no cierra el
 * panel: se puede seguir añadiendo al léxico y se ofrece «Reintentar».
 */
function AddToFlashcardsPanel({
  term,
  back,
  manualBack,
  backDraft,
  onBackDraft,
  mnemonic,
  onMnemonic,
  tracked,
  decks,
  deckError,
  deckCreateError,
  selectedDecks,
  onToggleDeck,
  onRetryDecks,
  creatingDeck,
  onCreateDeck,
  savedDecks,
  pendingDeck,
  adding,
  status,
  onConfirm,
  onRetryDeck,
  onClose,
  onOpenFlashcards,
}: {
  term: string;
  /** Reverso resuelto (equivalente). Vacío = hay que escribirlo. */
  back: string;
  /** `true` cuando no hay equivalente y el reverso lo pone el alumno. */
  manualBack: boolean;
  backDraft: string;
  onBackDraft: (value: string) => void;
  mnemonic: string;
  onMnemonic: (value: string) => void;
  tracked: boolean;
  decks: FlashcardDeck[] | null;
  deckError: boolean;
  deckCreateError: DeckCreateError;
  selectedDecks: number[];
  onToggleDeck: (id: number) => void;
  onRetryDecks: () => void;
  creatingDeck: boolean;
  onCreateDeck: (name: string) => void;
  savedDecks: { id: number; name: string }[];
  pendingDeck: DeckCardTarget | null;
  adding: boolean;
  status: "idle" | "ok" | "partial" | "error";
  onConfirm: (payload: { mnemonic: string; back: string }) => void;
  onRetryDeck: () => void;
  onClose: () => void;
  onOpenFlashcards?: (deckId?: number) => void;
}) {
  const { t } = useI18n();
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  // V3.84.1: el alta entró en el aprendizaje, pero la tarjeta del mazo no. Se
  // declara el estado real (no un «error» genérico) y se ofrece reintentar SOLO
  // la tarjeta; el estudio sigue disponible porque la palabra ya está en el flujo.
  if (status === "partial") {
    return (
      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-start gap-2 rounded-xl border border-warning/40 bg-warning/10 p-3"
        role="alert"
      >
        <p className="flex items-center gap-2 text-sm font-medium text-warning">
          <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
          {t("dictionary.lookup.addPartial")
            .replace("{word}", term)
            .replace("{deck}", pendingDeck?.deckName ?? "")}
        </p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {t("dictionary.lookup.addPartialHint")}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            disabled={adding}
            onClick={onRetryDeck}
            className="gap-1.5"
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            {adding
              ? t("common.saving")
              : t("dictionary.lookup.addPartialRetry")}
          </Button>
          {onOpenFlashcards ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => onOpenFlashcards()}
              className="gap-1.5"
            >
              <Layers className="size-3.5" aria-hidden="true" />
              {t("dictionary.lookup.studyCta")}
            </Button>
          ) : null}
        </div>
      </motion.div>
    );
  }

  if (status === "ok") {
    return (
      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-start gap-2 rounded-xl border border-success/40 bg-success/10 p-3"
        role="status"
      >
        <p className="flex items-center gap-2 text-sm font-medium text-success">
          <Check className="size-4 shrink-0" aria-hidden="true" />
          {t("dictionary.lookup.addOk").replace("{word}", term)}
        </p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {t("dictionary.lookup.addLearning")}
        </p>
        {savedDecks.length > 0 ? (
          <p className="text-xs leading-relaxed text-success">
            {t("dictionary.lookup.addOkDeck").replace(
              "{deck}",
              savedDecks.map((d) => d.name).join(", "),
            )}
          </p>
        ) : null}
        {onOpenFlashcards ? (
          <Button
            type="button"
            size="sm"
            onClick={() => onOpenFlashcards(savedDecks[0]?.id)}
            className="gap-1.5"
          >
            <Layers className="size-3.5" aria-hidden="true" />
            {t("dictionary.lookup.studyCta")}
          </Button>
        ) : null}
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col gap-3 rounded-xl border border-border bg-background/60 p-3"
    >
      <p className="text-xs leading-relaxed text-muted-foreground">
        {tracked
          ? t("dictionary.lookup.addTrackedNote")
          : t("dictionary.lookup.addHint")}
      </p>

      {/* V3.86.0: el reverso escrito a mano solo aparece cuando la consulta no
          trajo equivalente: sin él la tarjeta no tendría nada que recordar. El
          aviso va FUERA del `label`: dentro, se sumaría al nombre accesible del
          campo y el lector de pantalla leería dos frases como etiqueta. */}
      {manualBack ? (
        <div className="flex flex-col gap-1">
          <label className="flex flex-col gap-1 text-[11px] font-medium text-muted-foreground">
            <span>{t("dictionary.lookup.addBackLabel")}</span>
            <input
              value={backDraft}
              onChange={(e) => onBackDraft(e.target.value)}
              maxLength={2000}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            />
          </label>
          <span className="text-[11px] text-muted-foreground">
            {t("dictionary.lookup.addBackHint")}
          </span>
        </div>
      ) : null}

      {deckError ? (
        <div className="flex flex-col items-start gap-1">
          <p className="text-[11px] text-muted-foreground">
            {t("dictionary.lookup.addDeckError")}
          </p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onRetryDecks}
            className="gap-1.5"
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            {t("dictionary.lookup.addRetryDecks")}
          </Button>
        </div>
      ) : (
        <fieldset className="flex flex-col gap-1.5">
          <legend className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
            <Layers className="size-3.5" aria-hidden="true" />
            {t("dictionary.lookup.addDecksLabel")}
          </legend>
          {(decks ?? []).length === 0 ? (
            <p className="text-[11px] text-muted-foreground">
              {t("dictionary.lookup.addNoDeck")}
            </p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {(decks ?? []).map((deck) => (
                <li key={deck.id}>
                  <label className="inline-flex min-h-8 items-center gap-1.5 rounded-md border border-border px-2.5 text-xs font-medium">
                    <input
                      type="checkbox"
                      checked={selectedDecks.includes(deck.id)}
                      onChange={() => onToggleDeck(deck.id)}
                    />
                    {deck.name}
                  </label>
                </li>
              ))}
            </ul>
          )}
          {selectedDecks.length === 0 ? (
            <p className="text-[11px] text-muted-foreground">
              {t("dictionary.lookup.addNoDeck")}
            </p>
          ) : null}
        </fieldset>
      )}

      {creating ? (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder={t("dictionary.lookup.addDeckNamePlaceholder")}
            aria-label={t("dictionary.lookup.addDeckNamePlaceholder")}
            maxLength={120}
            className="min-w-0 flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            onKeyDown={(e) => {
              if (e.key === "Enter" && newName.trim() && !creatingDeck) {
                e.preventDefault();
                onCreateDeck(newName.trim());
                setNewName("");
                setCreating(false);
              }
            }}
          />
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={creatingDeck || !newName.trim()}
            onClick={() => {
              onCreateDeck(newName.trim());
              setNewName("");
              setCreating(false);
            }}
          >
            {creatingDeck
              ? t("common.saving")
              : t("dictionary.lookup.addDeckCreate")}
          </Button>
        </div>
      ) : (
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="w-fit gap-1.5"
          onClick={() => setCreating(true)}
        >
          <Plus className="size-3.5" aria-hidden="true" />
          {t("dictionary.lookup.addDeckNewInline")}
        </Button>
      )}

      <label className="flex flex-col gap-1 text-[11px] font-medium text-muted-foreground">
        <span>{t("dictionary.lookup.addMnemonicLabel")}</span>
        <input
          value={mnemonic}
          onChange={(e) => onMnemonic(e.target.value)}
          placeholder={t("dictionary.lookup.addMnemonicPlaceholder")}
          maxLength={400}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
        />
      </label>

      {deckCreateError ? (
        <p className="text-[11px] text-destructive" role="alert">
          {deckCreateError === "duplicate"
            ? t("dictionary.lookup.addDeckDuplicate")
            : t("dictionary.lookup.addDeckCreateError")}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          disabled={adding || (manualBack && !backDraft.trim())}
          onClick={() => onConfirm({ mnemonic, back: manualBack ? backDraft : back })}
          className="gap-1.5"
        >
          <Plus className="size-3.5" aria-hidden="true" />
          {adding ? t("common.saving") : t("dictionary.lookup.addConfirm")}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={adding}
          onClick={onClose}
        >
          {t("common.cancel")}
        </Button>
      </div>

      {status === "error" ? (
        <p className="text-xs text-destructive" role="alert">
          {t("dictionary.lookup.addError")}
        </p>
      ) : null}
    </motion.div>
  );
}

/** Marca de uso de la forma exacta (con matriz de competencia completa). */
function SurfaceUsageBlock({ usage }: { usage: DictionarySurfaceUsage }) {
  const { t } = useI18n();
  return (
    <>
      <UsageStatusHeader
        status={usage.status}
        recall={usage.recall}
        nextReviewDays={usage.next_review_days}
      />
      <CountersLine
        produced={usage.production_count}
        exposed={usage.exposure_count}
      />
      {usage.competence && <CompetenceChips competence={usage.competence} />}
      {usage.last_activity_at && (
        <p className="text-[11px] text-muted-foreground">
          {t("dictionary.lookup.lastActivity").replace(
            "{date}",
            formatDay(usage.last_activity_at),
          )}
        </p>
      )}
    </>
  );
}

/** Marca de uso del agregado por unidad (buscar la unidad canónica sin fila de
 * la forma exacta: p. ej. "go" con filas de "going"). La matriz de competencia
 * completa no existe a este nivel; se muestran las banderas del agregado. */
function UnitUsageBlock({ usage }: { usage: DictionaryUnitUsage }) {
  const { t } = useI18n();
  const chips: Array<{ on: boolean; labelKey: string }> = [
    { on: usage.recognized, labelKey: "dictionary.competenceRecognized" },
    { on: usage.produced, labelKey: "dictionary.competenceProduced" },
    { on: usage.transfer, labelKey: "dictionary.competenceTransfer" },
  ];
  return (
    <>
      <p className="text-[11px] leading-relaxed text-muted-foreground">
        {t("dictionary.lookup.unitAggregate").replace("{unit}", usage.lexical_unit)}
      </p>
      <p className="text-[11px] text-muted-foreground">
        {t("dictionary.lookup.formsCount").replace(
          "{count}",
          String(usage.surface_count),
        )}
      </p>
      <UsageStatusHeader
        status={usage.status}
        recall={usage.recall}
        nextReviewDays={0}
      />
      <CountersLine produced={usage.production_count} exposed={usage.exposure_count} />
      <ul className="flex flex-wrap gap-1.5">
        {chips.map((chip) => (
          <li key={chip.labelKey}>
            <Badge
              variant={chip.on ? "secondary" : "outline"}
              className={cn(
                "text-[10px]",
                chip.on
                  ? "border-transparent bg-primary/10 text-primary"
                  : "text-muted-foreground",
              )}
            >
              {t(chip.labelKey)}
            </Badge>
          </li>
        ))}
      </ul>
    </>
  );
}

function UsageStatusHeader({
  status,
  recall,
  nextReviewDays,
}: {
  status: LexicalStatus | null;
  recall: number;
  nextReviewDays: number;
}) {
  const { t } = useI18n();
  if (!status) return null;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className={cn("w-fit", STATUS_TONE[status])}>
          {t(`dictionary.status.${status}`)}
        </Badge>
        {status !== "mastered" && nextReviewDays > 0 && (
          <span className="text-[11px] text-muted-foreground">
            {t("dictionary.nextReviewIn").replace("{days}", String(nextReviewDays))}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Progress
          value={Math.round(recall * 100)}
          className="h-1.5 flex-1"
          aria-label={`${t("dictionary.recall")} ${Math.round(recall * 100)}%`}
        />
        <span className="w-9 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
          {Math.round(recall * 100)}%
        </span>
      </div>
    </div>
  );
}

function CountersLine({
  produced,
  exposed,
}: {
  produced: number;
  exposed: number;
}) {
  const { t } = useI18n();
  return (
    <p className="text-[11px] text-muted-foreground">
      <span>
        {t("dictionary.lookup.producedCount").replace("{count}", String(produced))}
      </span>
      <span aria-hidden="true"> · </span>
      <span>
        {t("dictionary.lookup.exposedCount").replace("{count}", String(exposed))}
      </span>
    </p>
  );
}

/** Chips de la matriz de competencia por ítem (Reconocida/Producida/Transfer/
 * Retención): encendidos con color y apagados en neutro. */
function CompetenceChips({ competence }: { competence: LexicalCompetence }) {
  const { t } = useI18n();
  const chips: Array<{ on: boolean; labelKey: string }> = [
    { on: competence.recognition, labelKey: "dictionary.competenceRecognized" },
    { on: competence.production, labelKey: "dictionary.competenceProduced" },
    { on: competence.transfer, labelKey: "dictionary.competenceTransfer" },
    { on: competence.retention, labelKey: "dictionary.competenceRetention" },
  ];
  return (
    <ul className="flex flex-wrap gap-1.5">
      {chips.map((chip) => (
        <li key={chip.labelKey}>
          <Badge
            variant={chip.on ? "secondary" : "outline"}
            className={cn(
              "text-[10px]",
              chip.on
                ? "border-transparent bg-primary/10 text-primary"
                : "text-muted-foreground",
            )}
          >
            {t(chip.labelKey)}
          </Badge>
        </li>
      ))}
    </ul>
  );
}

function ResultCard({
  entry,
  userId,
  onPractice,
  tracked = false,
  addOpen = false,
  onToggleAdd,
  onOpenFlashcards,
  meanings = [],
  meaningIndex = 0,
  onPickMeaning,
  equivalent = "",
  addPanel,
}: {
  entry: DictionaryEntry;
  userId: string | null;
  onPractice?: () => void;
  /** V3.83.0/V3.86.0: la palabra ya está en el léxico. Ya NO esconde el alta:
   *  el panel declara que solo se guardan la tarjeta y sus mazos. */
  tracked?: boolean;
  /** V3.83.0: el panel de alta está abierto (cambia el rótulo del botón). */
  addOpen?: boolean;
  onToggleAdd?: () => void;
  /** V3.84.0: mazo con el que abrir el estudio (si se archivó en uno manual). */
  onOpenFlashcards?: (deckId?: number) => void;
  /** V3.86.0: significados elegibles de la unidad. */
  meanings?: DictionaryMeaning[];
  meaningIndex?: number;
  onPickMeaning?: (index: number) => void;
  /** V3.86.0: equivalente del significado elegido (si no hay, `translation`). */
  equivalent?: string;
  /** Panel de alta, ya construido por el contenedor (null si está cerrado). */
  addPanel?: ReactNode;
}) {
  const { t } = useI18n();
  const kindLabel = lexicalKindLabel(entry.kind, t);
  const pos = entry.pos ? entry.pos[0].toUpperCase() + entry.pos.slice(1) : "";
  const base =
    entry.usage.surface ??
    (entry.usage.unit as DictionarySurfaceUsage | DictionaryUnitUsage | null);
  // V3.39: en ES→EN la palabra de cabecera es el término español y el
  // equivalente inglés llega en `translation`; el audio, el drill y la marca de
  // uso son siempre del INGLÉS. V3.86.0: manda el significado ELEGIDO.
  const isReverse = entry.direction === "es-en";
  const shownEquivalent = equivalent || entry.translation || "";
  const audioText = isReverse ? shownEquivalent : entry.word;
  const alternatives = entry.alternatives ?? [];
  // Con significados elegibles, la lista de «alternativas» es la misma
  // información otra vez: se pinta el selector y se calla la lista.
  const showAlternatives = alternatives.length > 0 && meanings.length <= 1;
  const chosen = meanings.length > 0 ? meanings[meaningIndex] ?? null : null;

  // V3.75.8: la tarjeta se tiñe del color de SU dirección —barra superior, marca
  // de sentido y bloque del equivalente—, así que un resultado dice de un
  // vistazo en qué sentido se buscó (y no cambia al tocar el conmutador).
  const dirClass = directionClass(entry.direction);

  return (
    <>
      <Card className={cn("relative gap-4 overflow-hidden p-5 pt-6", dirClass)}>
        <span
          className={cn("absolute inset-x-0 top-0 h-1", dirClass, "dir-bar")}
          aria-hidden="true"
        />
        {/* Palabra + badges de contexto */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="mb-1.5 flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
                  dirClass,
                  "dir-chip",
                )}
              >
                <ArrowLeftRight className="size-3" aria-hidden="true" />
                {t(directionLabelKey(entry.direction))}
              </span>
              {entry.cefr && <LevelBadge level={entry.cefr} />}
              {pos && (
                <Badge
                  variant="secondary"
                  className="text-[10px] font-semibold uppercase"
                >
                  {pos}
                </Badge>
              )}
              {kindLabel && (
                <span className="text-xs font-normal text-muted-foreground">
                  {kindLabel}
                </span>
              )}
            </div>
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              <span lang={isReverse ? "es" : "en"}>{entry.word}</span>
            </h2>
          </div>
          {/* V3.84.0: con hasta 3 acciones + el audio, este cluster no cabía a
              320-390px y el `overflow-hidden` de la tarjeta lo recortaba en
              silencio. Envuelve (`flex-wrap`) y puede encoger (`min-w-0`). */}
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            {audioText && (
              /* V3.75.5: la palabra se puede oír en A o B (dos acentos). */
              <ItemReplayButton prompt={audioText} userId={userId} />
            )}
            {/* V3.83.0: alta a Flashcards. Si la palabra ya está en el léxico,
                el alta no cambiaría nada: se ofrece estudiar. El panel explica
                el vínculo con PERSONAL y el mazo automático. */}
            {onToggleAdd ? (
              <Button
                type="button"
                variant={addOpen ? "ghost" : "secondary"}
                size="sm"
                onClick={onToggleAdd}
                aria-expanded={addOpen}
                className="gap-1.5"
              >
                <Plus className="size-3.5" aria-hidden="true" />
                {addOpen
                  ? t("common.cancel")
                  : t("dictionary.lookup.addCta")}
              </Button>
            ) : null}
            {tracked && onOpenFlashcards ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => onOpenFlashcards()}
                className="gap-1.5"
              >
                <Layers className="size-3.5" aria-hidden="true" />
                {t("dictionary.lookup.studyCta")}
              </Button>
            ) : null}
            {/* V3.32: «Practicar esta palabra» — abre la escalera de drill oral
                (Recall → Sentence). Solo esta acción explícita escribe
                evidencia; el lookup no (D3). V3.39: sin equivalente inglés
                (ES→EN sin contenido) no hay nada que practicar. */}
            {onPractice && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onPractice}
                className="gap-1.5"
              >
                <Mic className="size-3.5" aria-hidden="true" />
                {t("dictionary.lookup.practiceCta")}
              </Button>
            )}
          </div>
        </div>

        {/* V3.83.0: el alta declara su vínculo («ya está en tu diccionario y en
            tu mazo») y el estado de éxito la navegación a estudiar. */}
        {tracked && !addOpen ? (
          <p className="text-xs text-muted-foreground">
            {t("dictionary.lookup.alreadyTracked")}
          </p>
        ) : null}

        {addPanel}

        {/* V3.86.0: SELECTOR DE SIGNIFICADO. Los nombres propios van marcados y
            nunca son el defecto: «lima» ofrece «file (herramienta)» antes que
            «Lima (capital del Perú)». Elegir uno manda sobre el término de
            práctica, el audio, el bloque del equivalente y el alta. */}
        {meanings.length > 0 ? (
          <fieldset className="flex flex-col gap-2">
            <legend className="flex flex-col gap-0.5">
              <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                <Languages className="size-3.5" aria-hidden="true" />
                {t("dictionary.lookup.meanings")}
              </span>
              <span className="text-[11px] font-normal text-muted-foreground">
                {t("dictionary.lookup.meaningPick")}
              </span>
            </legend>
            <ul className="flex flex-col gap-1.5">
              {meanings.map((meaning, index) => {
                const selected = index === meaningIndex;
                const label = `${meaning.term}${
                  meaning.pos ? ` · ${meaning.pos}` : ""
                }`;
                return (
                  <li key={`${meaning.term}-${meaning.pos}-${index}`}>
                    <label
                      className={cn(
                        "flex cursor-pointer items-start gap-2 rounded-xl border px-3 py-2 transition-colors",
                        selected
                          ? "border-primary/50 bg-primary/5"
                          : "border-border hover:border-primary/30",
                      )}
                    >
                      <input
                        type="radio"
                        name="dictionary-meaning"
                        className="mt-1"
                        checked={selected}
                        aria-label={`${t("dictionary.lookup.meaningAria")}: ${label}`}
                        onChange={() => onPickMeaning?.(index)}
                      />
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span className="flex flex-wrap items-center gap-1.5">
                          <span
                            className="text-sm font-semibold"
                            lang={isReverse ? "en" : "es"}
                          >
                            {meaning.term}
                          </span>
                          {meaning.pos ? (
                            <Badge
                              variant="secondary"
                              className="text-[10px] font-semibold uppercase"
                            >
                              {meaning.pos}
                            </Badge>
                          ) : null}
                          {meaning.domain ? (
                            <span className="text-[11px] text-muted-foreground">
                              {meaning.domain}
                            </span>
                          ) : null}
                          {meaning.proper_noun ? (
                            <Badge
                              variant="outline"
                              className="text-[10px] text-muted-foreground"
                            >
                              {t("dictionary.lookup.meaningProperNoun")}
                            </Badge>
                          ) : null}
                        </span>
                        {meaning.gloss ? (
                          <span className="text-[11px] leading-relaxed text-muted-foreground">
                            {meaning.gloss}
                          </span>
                        ) : null}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </fieldset>
        ) : null}

        {entry.definition_source === "llm" ? (
          <div className="flex flex-col gap-4">
            {entry.definition && (
              <div className="flex flex-col gap-1">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("dictionary.lookup.definitionLabel")}
                </span>
                <p className="text-base leading-relaxed" lang="en">
                  {entry.definition}
                </p>
              </div>
            )}
            {shownEquivalent ? (
              /* El equivalente es la respuesta de la consulta: se destaca en el
                 color de la dirección, con el rótulo también en esa tinta. */
              <div
                className={cn(
                  "flex flex-col gap-1 rounded-xl border px-4 py-3",
                  dirClass,
                  "dir-wash dir-line",
                )}
              >
                <span
                  className={cn(
                    "text-[11px] font-semibold uppercase tracking-wide",
                    dirClass,
                    "dir-ink",
                  )}
                >
                  {isReverse
                    ? t("dictionary.lookup.englishLabel")
                    : t("dictionary.lookup.translationLabel")}
                </span>
                <p
                  className="text-lg font-semibold leading-snug"
                  lang={isReverse ? "en" : "es"}
                >
                  {shownEquivalent}
                </p>
                {chosen?.gloss ? (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {chosen.gloss}
                  </p>
                ) : null}
              </div>
            ) : (
              /* V3.86.0: sin equivalente no se finge nada: se dice y el alta
                 ofrece escribir el reverso a mano. */
              <p className="text-xs leading-relaxed text-muted-foreground">
                {t("dictionary.lookup.addBackHint")}
              </p>
            )}
            {showAlternatives ? (
              <div className="flex flex-col gap-1">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("dictionary.lookup.alternativesLabel")}
                </span>
                <p className="text-sm leading-relaxed" lang="en">
                  {alternatives.join(" · ")}
                </p>
              </div>
            ) : null}
          </div>
        ) : (
          <p
            className="text-xs leading-relaxed text-muted-foreground"
            role="status"
          >
            {t("dictionary.lookup.contentUnavailable")}
          </p>
        )}

        {entry.example && (
          <div className="flex flex-col gap-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {t("dictionary.lookup.exampleTitle")}
            </span>
            <div className="flex items-stretch gap-3 overflow-hidden rounded-xl border border-border bg-background/60">
              <span
                className={cn("w-1 shrink-0", dirClass, "dir-bar")}
                aria-hidden="true"
              />
              <span
                className="min-w-0 flex-1 py-2.5 text-base font-medium break-words"
                lang="en"
              >
                {entry.example.phrase}
              </span>
              <span className="flex items-center pr-3">
                <ItemReplayButton prompt={entry.example.phrase} userId={userId} />
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground">
              {t("dictionary.lookup.exampleNote")}
            </p>
          </div>
        )}
      </Card>

      {/* Marca de uso/aprendizaje (solo lectura, D3) */}
      <Card className="gap-3 p-5" aria-label={t("dictionary.lookup.usageTitle")}>
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">
            {t("dictionary.lookup.usageTitle")}
          </h3>
        </div>
        {!entry.usage.tracked || !base ? (
          <div className="flex flex-col items-start gap-2">
            <Badge variant="outline" className="text-muted-foreground">
              {t("dictionary.lookup.notTrackedBadge")}
            </Badge>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {t("dictionary.lookup.usageNotTracked")}
            </p>
          </div>
        ) : entry.usage.surface ? (
          <SurfaceUsageBlock usage={entry.usage.surface} />
        ) : (
          <UnitUsageBlock usage={entry.usage.unit!} />
        )}
      </Card>
    </>
  );
}

function lexicalKindLabel(kind: string, t: (key: string) => string): string {
  const key = `dictionary.kind.${kind}`;
  const label = t(key);
  return label === key ? t("dictionary.kind.other") : label;
}

function formatDay(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString();
}
