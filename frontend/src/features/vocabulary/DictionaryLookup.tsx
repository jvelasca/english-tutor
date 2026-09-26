import { useState, type FormEvent, type ReactNode } from "react";
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
  createFlashcard,
  createFlashcardDeck,
  listFlashcardDecks,
  lookupDictionaryWord,
} from "../../api/vocabulary";
import type {
  DictionaryDirection,
  DictionaryEntry,
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

/** Valor centinela del selector de mazo: «crear uno nuevo» (V3.84.0). */
const NEW_DECK_OPTION = "__new__";

/** Destino de la tarjeta manual del alta (V3.84.1): lo que queda por guardar si
 *  la SEGUNDA escritura falla, para poder reintentarla sin repetir el alta. */
interface DeckCardTarget {
  id: number;
  name: string;
  front: string;
  back: string;
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
  // el panel, para no pagar una consulta en cada búsqueda). `selectedDeck` es el
  // id del mazo donde guardar la tarjeta ADEMÁS de dejarla en aprendizaje;
  // vacío = solo aprendizaje.
  const [addOpen, setAddOpen] = useState(false);
  const [decks, setDecks] = useState<FlashcardDeck[] | null>(null);
  const [deckError, setDeckError] = useState(false);
  const [selectedDeck, setSelectedDeck] = useState("");
  // Nombre del mazo donde se guardó de verdad (para declararlo y para abrirlo).
  const [savedDeck, setSavedDeck] = useState<{ id: number; name: string } | null>(
    null,
  );
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
    setAddStatus("idle");
    setAddOpen(false);
    setSelectedDeck("");
    setSavedDeck(null);
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
   *  destino; y los packs temáticos tampoco, porque son contenido curado. */
  async function openAddPanel() {
    setAddOpen(true);
    setAddStatus("idle");
    if (!userId || decks !== null || deckError) return;
    try {
      const data = await listFlashcardDecks(userId);
      const all = Array.isArray(data?.decks) ? data.decks : [];
      setDecks(all.filter((d) => !d.is_auto));
    } catch {
      setDeckError(true);
      setDecks([]);
    }
  }

  function closeAddPanel() {
    setAddOpen(false);
    setAddStatus("idle");
    setSelectedDeck("");
    setSavedDeck(null);
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
      setSelectedDeck(String(created.id));
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : "";
      setDeckCreateError(detail === "DECK_NAME_TAKEN" ? "duplicate" : "generic");
    } finally {
      setCreatingDeck(false);
    }
  }

  /** V3.84.1: SEGUNDA escritura del alta, aislada para poder reintentarla sola.
   *  Devuelve si la tarjeta entró de verdad; nunca lanza. */
  async function saveDeckCard(target: DeckCardTarget): Promise<boolean> {
    if (!userId) return false;
    try {
      await createFlashcard(userId, target.id, {
        front: target.front,
        back: target.back,
      });
      setSavedDeck({ id: target.id, name: target.name });
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
    setSelectedDeck("");
  }

  async function handleAddToFlashcards() {
    if (!userId || !practiceTerm || adding) return;
    setAdding(true);
    setAddStatus("idle");
    setSavedDeck(null);
    setPendingDeck(null);
    const translation =
      entry?.direction === "en-es" ? entry.translation ?? "" : entry?.word ?? "";
    const term = practiceTerm;
    // 1) El alta que ya existía: léxico + carta FSRS + estado `learning`.
    //    Si ESTA falla, no se escribió nada: error simple, sin estado parcial.
    try {
      await addVocabularyItem(userId, term, { translation });
    } catch {
      setAddStatus("error");
      setAdding(false);
      return;
    }
    // El alta ya deja la palabra en el léxico (estado `learning`): se refresca
    // en silencio para que la marca de uso lo refleje sin desmontar la tarjeta.
    void refreshEntry(lastQuery, lastDirection);
    // 2) V3.84.0: además, si el alumno eligió un mazo manual, se guarda la
    //    tarjeta con anverso/reverso. Son DOS escrituras y así se declara.
    //    V3.84.1: si esta segunda falla, el aprendizaje YA está hecho; se
    //    declara el estado PARCIAL y se ofrece reintentar solo la tarjeta, en
    //    vez de pintar un «error» que miente sobre lo que sí se guardó.
    if (selectedDeck) {
      const deckId = Number(selectedDeck);
      const deckName = decks?.find((d) => d.id === deckId)?.name ?? term;
      const target: DeckCardTarget = {
        id: deckId,
        name: deckName,
        front: term,
        back: translation,
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
    setSelectedDeck("");
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
    setSelectedDeck("");
    setSavedDeck(null);
    setPendingDeck(null);
    setDeckCreateError(null);
  }

  const practiceTerm = entry
    ? entry.direction === "es-en"
      ? entry.translation
      : entry.word
    : null;
  // V3.83.0: `tracked` significa que la palabra YA está en el léxico del alumno
  // (y por tanto en PERSONAL y en el mazo automático). En ese caso no se ofrece
  // un alta que no cambiaría nada: se ofrece estudiar.
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
    setInvalidError(false);
    setNetworkError(false);
    setAddStatus("idle");
    setAddOpen(false);
    setSelectedDeck("");
    setSavedDeck(null);
    setPendingDeck(null);
    setDeckCreateError(null);
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
            onToggleAdd={practiceTerm && !tracked ? toggleAddPanel : undefined}
            onOpenFlashcards={onOpenFlashcards}
            addPanel={
              addOpen && practiceTerm ? (
                <AddToFlashcardsPanel
                  term={practiceTerm}
                  decks={decks}
                  deckError={deckError}
                  deckCreateError={deckCreateError}
                  selectedDeck={selectedDeck}
                  onSelectDeck={(id) => {
                    setSelectedDeck(id);
                    setDeckCreateError(null);
                  }}
                  creatingDeck={creatingDeck}
                  onCreateDeck={(name) => void handleCreateDeck(name)}
                  savedDeck={savedDeck}
                  pendingDeck={pendingDeck}
                  adding={adding}
                  status={addStatus}
                  onConfirm={() => void handleAddToFlashcards()}
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
 *
 * Declara **qué** significa añadir (la palabra entra en el proceso de estudio
 * con estado `learning` y su carta FSRS, así que aparecerá en PERSONAL y en el
 * mazo automático «Mi diccionario») y, además, permite guardarla como tarjeta
 * en un mazo manual. Son dos destinos distintos y el panel los declara: la
 * palabra SIEMPRE queda en aprendizaje, y SOLO si se elige mazo se crea además
 * una tarjeta allí. El éxito deja la salida natural: estudiar en Flashcards.
 */
function AddToFlashcardsPanel({
  term,
  decks,
  deckError,
  deckCreateError,
  selectedDeck,
  onSelectDeck,
  creatingDeck,
  onCreateDeck,
  savedDeck,
  pendingDeck,
  adding,
  status,
  onConfirm,
  onRetryDeck,
  onClose,
  onOpenFlashcards,
}: {
  term: string;
  decks: FlashcardDeck[] | null;
  deckError: boolean;
  deckCreateError: DeckCreateError;
  selectedDeck: string;
  onSelectDeck: (id: string) => void;
  creatingDeck: boolean;
  onCreateDeck: (name: string) => void;
  savedDeck: { id: number; name: string } | null;
  pendingDeck: DeckCardTarget | null;
  adding: boolean;
  status: "idle" | "ok" | "partial" | "error";
  onConfirm: () => void;
  onRetryDeck: () => void;
  onClose: () => void;
  onOpenFlashcards?: (deckId?: number) => void;
}) {
  const { t } = useI18n();
  const [newName, setNewName] = useState("");
  const creating = selectedDeck === NEW_DECK_OPTION;

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
            .replace("{deck}", pendingDeck?.name ?? "")}
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
        {savedDeck ? (
          <p className="text-xs leading-relaxed text-success">
            {t("dictionary.lookup.addOkDeck").replace(
              "{deck}",
              savedDeck.name,
            )}
          </p>
        ) : null}
        {onOpenFlashcards ? (
          <Button
            type="button"
            size="sm"
            onClick={() => onOpenFlashcards(savedDeck?.id)}
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
        {t("dictionary.lookup.addHint")}
      </p>

      {deckError ? (
        <p className="text-[11px] text-muted-foreground">
          {t("dictionary.lookup.addDeckError")}
        </p>
      ) : (
        <label className="flex flex-col gap-1 text-[11px] font-medium text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Layers className="size-3.5" aria-hidden="true" />
            {t("dictionary.lookup.addDeckLabel")}
          </span>
          <select
            value={selectedDeck}
            onChange={(e) => onSelectDeck(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="">{t("dictionary.lookup.addDeckNone")}</option>
            {(decks ?? []).map((deck) => (
              <option key={deck.id} value={deck.id}>
                {deck.name}
              </option>
            ))}
            <option value={NEW_DECK_OPTION}>
              {t("dictionary.lookup.addDeckNew")}
            </option>
          </select>
        </label>
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
            }}
          >
            {creatingDeck
              ? t("common.saving")
              : t("dictionary.lookup.addDeckCreate")}
          </Button>
        </div>
      ) : null}

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
          disabled={adding || creating}
          onClick={onConfirm}
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
  addPanel,
}: {
  entry: DictionaryEntry;
  userId: string | null;
  onPractice?: () => void;
  /** La palabra ya está en el léxico: no se ofrece alta, se ofrece estudiar. */
  tracked?: boolean;
  /** V3.83.0: el panel de alta está abierto (cambia el rótulo del botón). */
  addOpen?: boolean;
  onToggleAdd?: () => void;
  /** V3.84.0: mazo con el que abrir el estudio (si se archivó en uno manual). */
  onOpenFlashcards?: (deckId?: number) => void;
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
  // uso son siempre del INGLÉS.
  const isReverse = entry.direction === "es-en";
  const audioText = isReverse ? entry.translation ?? "" : entry.word;
  const alternatives = entry.alternatives ?? [];

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
            {entry.translation && (
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
                  {entry.translation}
                </p>
              </div>
            )}
            {alternatives.length > 0 && (
              <div className="flex flex-col gap-1">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("dictionary.lookup.alternativesLabel")}
                </span>
                <p className="text-sm leading-relaxed" lang="en">
                  {alternatives.join(" · ")}
                </p>
              </div>
            )}
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
