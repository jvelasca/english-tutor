/**
 * Sesión de estudio de tarjetas: voltear + 4 grados FSRS.
 *
 * Camino etiquetado (D5/E3): solo reprograma `fsrs_cards` (lexicon o flashcard
 * según la tarjeta) y escribe eventos informativos. No abre el drill ni escribe
 * mastery.
 *
 * V3.78.0 — de `RetentionSession` a `StudySession`. Dos cambios de fondo:
 *
 * 1. **Recibe los ítems**, no los pide. Antes la sesión pedía su propia cola y
 *    por eso solo podía existir UNA sesión: la del léxico entero. Ahora el
 *    contenedor decide qué se estudia (el mazo automático, un mazo manual, una
 *    lista concreta) y aquí solo se pinta. Es lo que permite que haya una sola
 *    superficie de estudio sin duplicar el motor de tarjetas.
 * 2. **Los grados los aplica el contenedor** (`onGrade`), porque el endpoint
 *    depende del mazo. Aquí se garantiza lo que V3.77.2 arregló: la calificación
 *    no cierra la sesión recargando la cola, así que el resumen final («N
 *    tarjetas repasadas») es alcanzable y el contador no se pierde.
 *
 * V3.80.0 — la cara B deja de ser un callejón sin salida. Al voltear, si el
 * reverso viene vacío, la sesión lo pide al diccionario que YA existe
 * (`lookupDictionaryWord`: caché global + generación del modelo local, con su
 * tope de espera) y lo pinta. Además, un lápiz sobre el reverso revelado abre un
 * campo para escribir o corregir la traducción propia, que se guarda con
 * `PATCH /api/vocabulary/items` y **pasa a mandar** sobre el pack y la caché.
 * Dos honestidades deliberadas: «Generando…» mientras se espera al modelo (no un
 * vacío que parezca un error) y, si el modelo no responde, decirlo sin bloquear
 * la calificación — la sesión nunca se cuelga por un reverso que falta.
 *
 * El resumen y el arranque los controla el contenedor con la `key`: una sesión
 * nueva remonta el componente, así que no hay que «resetear» estado por efecto.
 */
import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import {
  Frown,
  Layers,
  Lightbulb,
  Pencil,
  RefreshCw,
  RotateCcw,
  Smile,
  Sparkles,
  Zap,
} from "lucide-react";
import type { FlashcardStudyItem, StudyConfig } from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import {
  lookupDictionaryWord,
  setVocabularyTranslation,
} from "../../api/vocabulary";
import { ItemReplayButton } from "../../components/ItemReplayButton";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Progress } from "../../components/ui/progress";
import { cn } from "../../lib/utils";
import { mnemonicSlice } from "./hintReveal";

/**
 * Los cuatro grados FSRS con su identidad visual (V3.83.0): icono, color
 * semántico y atajo de teclado. El color no es decorativo —cada grado tiene el
 * suyo en toda la app (rojo/ámbar/primario/verde)— y el atajo (1–4) convierte
 * calificar en un gesto de juego, sin quitar el botón: sigue siendo pulsable y
 * accesible.
 */
const GRADES = [
  {
    grade: 1,
    key: "fsrs.grade.again",
    Icon: RotateCcw,
    tone: "border-destructive/40 bg-destructive/10 text-destructive hover:bg-destructive/20 hover:text-destructive",
  },
  {
    grade: 2,
    key: "fsrs.grade.hard",
    Icon: Frown,
    tone: "border-warning/40 bg-warning/10 text-warning hover:bg-warning/20 hover:text-warning",
  },
  {
    grade: 3,
    key: "fsrs.grade.good",
    Icon: Smile,
    tone: "border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 hover:text-primary",
  },
  {
    grade: 4,
    key: "fsrs.grade.easy",
    Icon: Zap,
    tone: "border-success/40 bg-success/10 text-success hover:bg-success/20 hover:text-success",
  },
] as const;

interface StudySessionProps {
  userId: string;
  /** Ítems de la sesión, ya resueltos por el contenedor. */
  items: FlashcardStudyItem[];
  /** Nombre del mazo, solo para la cabecera. */
  deckName: string;
  /** Califica una tarjeta. El contenedor decide el endpoint y el mazo. */
  onGrade: (item: FlashcardStudyItem, grade: number) => Promise<void>;
  /** Vuelve al panel de entrada. El contenedor recarga la cola al hacerlo. */
  onExit: () => void;
  /**
   * V3.87.0: cómo se construyó la cola (dirección, modo, ayudas). Opcional: sin
   * ella la sesión se comporta EXACTAMENTE como V3.86.1 (EN→ES, volteo).
   */
  studyConfig?: StudyConfig | null;
  /**
   * V3.78.0: volver a empezar con la cola RECARGADA. Es la «acción de
   * actualizar» que pidió V3.77.2: si la sesión acaba de terminar, lo útil no
   * es volver a mirar el mismo panel, es ver si queda algo y seguir. Si el
   * contenedor no la ofrece, el botón no se pinta (no se promete nada).
   */
  onRestart?: () => void;
}

/** Clave estable de una tarjeta en la sesión (el `id` solo no basta: va el tipo). */
function cardKey(item: FlashcardStudyItem): string {
  return `${item.card_type}:${item.card_id}`;
}

export function StudySession({
  userId,
  items,
  deckName,
  onGrade,
  onExit,
  onRestart,
  studyConfig,
}: StudySessionProps) {
  const { t } = useI18n();
  const [index, setIndex] = useState(0);
  const [hintStep, setHintStep] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [done, setDone] = useState(0);
  // V3.83.0: aciertos de la sesión (grados ≥ 3). Es lo único que se puede decir
  // con honestidad al terminar: un % de esta sesión, no una nota de dominio.
  const [good, setGood] = useState(0);
  // Con «reducir movimiento» activo, el volteo 3D y la celebración se apagan:
  // la información sigue igual, el movimiento es lo que desaparece.
  const reduceMotion = useReducedMotion();

  // V3.80.0: caras B resueltas durante esta sesión (generadas o escritas a
  // mano). Se indexan por tarjeta para que volver atrás no vuelva a pedirlas.
  const [faces, setFaces] = useState<
    Record<string, { back: string; definition: string }>
  >({});
  const [generatingKey, setGeneratingKey] = useState("");
  // Por qué no hay reverso cuando la hidratación ya terminó: `empty` es «el
  // modelo respondió y no había nada» y `failed` es «el modelo no respondió».
  // Decir lo mismo en los dos casos sería mentir en uno de los dos.
  const [lookupStates, setLookupStates] = useState<
    Record<string, "empty" | "failed">
  >({});
  const [ownBacks, setOwnBacks] = useState<Record<string, true>>({});
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  // V3.87.0: producción (modo `production`). El alumno escribe la respuesta
  // antes de voltear; al comprobar se muestra la correcta y se autocalifica el
  // grado FSRS (acierto → Good, fallo → Again) sin dejar de enseñar la cara.
  const [typed, setTyped] = useState("");
  const [checked, setChecked] = useState(false);
  const [matched, setMatched] = useState(false);

  /**
   * V3.80.1: candado contra la carrera generación ↔ edición.
   *
   * `hydrate()` es una promesa que puede tardar (modelo local) y el lápiz se
   * puede usar mientras está en vuelo. Sin esto, la respuesta tardía del modelo
   * podía pisar la traducción que el alumno acababa de guardar, dejando en
   * pantalla un valor que contradecía la fuente de verdad que él mismo había
   * editado.
   *
   * - `hydrationEpoch`: sube al guardar una traducción propia (y al borrarla) e
   *   invalida cualquier hidratación pendiente de ESA tarjeta.
   * - `ownBacksRef`: espejo síncrono de `ownBacks`, porque dentro del closure
   *   async el estado de React puede estar desfasado.
   */
  const hydrationEpoch = useRef<Record<string, number>>({});
  const ownBacksRef = useRef<Record<string, true>>({});

  /** Marca (o desmarca) la traducción propia de una tarjeta, estado y ref a la vez. */
  function markOwnBack(itemKey: string, own: boolean) {
    if (own) {
      ownBacksRef.current[itemKey] = true;
      setOwnBacks((m) => ({ ...m, [itemKey]: true }));
      return;
    }
    delete ownBacksRef.current[itemKey];
    setOwnBacks((m) => {
      const next = { ...m };
      delete next[itemKey];
      return next;
    });
  }

  /** Olvida el resultado (o el fallo) de la hidratación de una tarjeta. */
  function clearLookupState(itemKey: string) {
    setLookupStates((m) => {
      const next = { ...m };
      delete next[itemKey];
      return next;
    });
  }

  const current = items[index] ?? null;
  const key = current ? cardKey(current) : "";
  const face = key ? faces[key] : undefined;
  const back = face ? face.back : (current?.back ?? "");
  const definition = face ? face.definition : (current?.definition ?? "");
  // V3.86.0: recordatorio de la ficha manual. Vive en la FICHA, así que el mazo
  // automático (vista del léxico) nunca lo trae. Se pinta en el reverso, sin
  // tocar la máquina de estudio.
  const mnemonic = current?.mnemonic ?? "";
  const generating = key !== "" && generatingKey === key;
  const lookupState = key ? lookupStates[key] : undefined;
  // El lápiz solo se ofrece en tarjetas del léxico: son las únicas cuya
  // traducción propia tiene fila que corregir. El reverso de una tarjeta
  // manual se edita en la pestaña Tarjetas, que es su sitio.
  //
  // V3.80.1: de ahí sale también el `lang`. Una tarjeta de léxico es EN→ES por
  // construcción; una manual puede contener cualquier idioma, así que declarar
  // `lang` en ella sería mentir. Se omite cuando no se conoce.
  const isLexicon = current?.card_type === "lexicon";
  const canEdit = isLexicon;

  // V3.87.0 — configuración de estudio. La dirección es PRESENTACIÓN: `front`/
  // `back` siguen siendo la identidad de la ficha (y el lápiz sigue editando la
  // traducción), pero se pregunta `prompt` y se responde `answer`.
  const dirEsEn = studyConfig?.direction === "es-en";
  const promptText = current?.prompt || current?.front || "";
  // La ayuda solo se enseña si la config la pide y la tarjeta la trae.
  const hint =
    studyConfig && studyConfig.hints !== "off" ? (current?.hint ?? "") : "";
  const hintPiece = mnemonicSlice(mnemonic, hintStep);
  const definitionHint =
    hint && mnemonic && hint.includes(mnemonic.trim())
      ? ""
      : hint;
  const production = studyConfig?.mode === "production";
  // El `answer` del backend solo manda en ES→EN; en EN→ES la cara B puede
  // hidratarse en vivo (léxico), así que la verdad es `back`/`face`.
  const answerText = dirEsEn ? current?.answer || current?.front || "" : back;
  // Sin respuesta no hay nada que comprobar: la producción degrada a volteo.
  const productionActive = production && Boolean(answerText.trim());
  const promptLang = isLexicon ? (dirEsEn ? "es" : "en") : undefined;
  const answerLang = isLexicon ? (dirEsEn ? "en" : "es") : undefined;

  /** Compara la respuesta escrita con la esperada (tolerante: caja y espacios). */
  function sameAnswer(a: string, b: string): boolean {
    const clean = (value: string) =>
      value.trim().toLowerCase().replace(/\s+/g, " ");
    return clean(a) === clean(b) && clean(a) !== "";
  }

  /**
   * Pide el reverso al diccionario cuando la tarjeta viene sin él.
   *
   * No hidrata si ya hay reverso: la cara que sirvió el backend (pack, tu
   * traducción o caché) es la verdad y no se sustituye por otra generación.
   * Tampoco reintenta una tarjeta ya resuelta o ya fallida: insistir con el
   * modelo caído solo añadiría esperas a la sesión.
   *
   * `force` (V3.80.1) se usa tras borrar la traducción propia: la tarjeta vuelve
   * a quedar sin reverso y hay que reintentar la caché aunque una hidratación
   * anterior hubiera marcado la tarjeta como resuelta.
   */
  async function hydrate(
    item: FlashcardStudyItem,
    itemKey: string,
    force = false,
  ) {
    if (item.back || item.card_type !== "lexicon") return;
    if (
      !force &&
      (faces[itemKey] || lookupStates[itemKey] || generatingKey === itemKey)
    ) {
      return;
    }
    // V3.80.1: foto del turno de hidratación. Si al volver ha cambiado (el
    // alumno guardó o borró su traducción), esta respuesta ya no vale.
    const epoch = hydrationEpoch.current[itemKey] ?? 0;
    const stale = () =>
      (hydrationEpoch.current[itemKey] ?? 0) !== epoch ||
      Boolean(ownBacksRef.current[itemKey]);
    setGeneratingKey(itemKey);
    try {
      const entry = await lookupDictionaryWord(userId, item.front);
      if (stale()) return;
      const translation = (entry.translation ?? "").trim();
      const definition = (entry.definition ?? "").trim();
      if (translation || definition) {
        setFaces((m) => ({
          ...m,
          [itemKey]: { back: translation, definition },
        }));
      } else {
        // El modelo respondió y no había nada que dar: es un «no consta», no un
        // fallo. Se dice que no hay reverso, sin culpar a nadie.
        setLookupStates((m) => ({ ...m, [itemKey]: "empty" }));
      }
    } catch {
      if (!stale()) {
        setLookupStates((m) => ({ ...m, [itemKey]: "failed" }));
      }
    } finally {
      setGeneratingKey((k) => (k === itemKey ? "" : k));
    }
  }

  function reveal() {
    if (!current) return;
    setFlipped(true);
    void hydrate(current, key);
  }

  /** V3.87.0: comprueba la respuesta escrita y revela (modo producción). */
  function check() {
    if (!current || busy) return;
    setMatched(sameAnswer(typed, answerText));
    setChecked(true);
    setFlipped(true);
    void hydrate(current, key);
  }

  /** Autocalificación FSRS de producción: acierto → Good, fallo → Again. */
  function continueProduction() {
    void grade(matched ? 3 : 1);
  }

  async function grade(g: number) {
    if (!current || busy) return;
    setBusy(true);
    try {
      await onGrade(current, g);
      setDone((n) => n + 1);
      if (g >= 3) setGood((n) => n + 1);
      setFlipped(false);
      setHintStep(0);
      // Al cambiar de tarjeta se cierra cualquier edición abierta: el campo es
      // de la tarjeta anterior y dejarlo abierto guardaría en la equivocada.
      setEditing(false);
      setSaveError(false);
      setDraft("");
      // La producción es de ESTA tarjeta: al avanzar se limpia su intento.
      setTyped("");
      setChecked(false);
      setMatched(false);
      // V3.77.2: la sesión NO se cierra recargando la cola. Se avanza el índice
      // para que `current` sea null y el resumen se pinte con el contador
      // intacto; si se recargara aquí, el contador se borraría y el alumno
      // nunca vería cuánto había hecho.
      setIndex((i) => i + 1);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  // V3.83.0: atajos 1–4 para calificar cuando la tarjeta ya está revelada. Se
  // ignora mientras se escribe el reverso propio (el campo captura el número) y
  // mientras hay una calificación en vuelo, para no disparar dos grados de la
  // misma tarjeta.
  useEffect(() => {
    if (!flipped || busy || editing || productionActive) return;
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      const value = Number(event.key);
      if (!Number.isInteger(value) || value < 1 || value > 4) return;
      event.preventDefault();
      void grade(value);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // `grade` se recrea en cada render: el efecto se re-suscribe, que es
    // barato y evita cerrar sobre un `current`/`busy` desfasado.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flipped, busy, editing, current, key, productionActive]);

  async function saveOwnBack() {
    if (!current || saving || !key) return;
    setSaving(true);
    setSaveError(false);
    const translation = draft.trim();
    // Foto de la tarjeta: el guardado es asíncrono y la sesión puede avanzar
    // (o no) mientras está en vuelo; esto escribe siempre en la correcta.
    const item = current;
    const itemKey = key;
    try {
      await setVocabularyTranslation(userId, item.front, translation);
      // V3.80.1 (P1): guardar o borrar invalida cualquier hidratación en vuelo
      // de esta tarjeta. Su respuesta tardía ya no puede pisar esta decisión.
      hydrationEpoch.current[itemKey] =
        (hydrationEpoch.current[itemKey] ?? 0) + 1;
      clearLookupState(itemKey);
      // El turno de generación ya no manda: se retira el «Generando…» para que
      // la cara del alumno (o la del pack, al borrar) se vea de inmediato.
      setGeneratingKey((k) => (k === itemKey ? "" : k));
      if (translation) {
        // Lo escrito manda: la cara de esta sesión pasa a ser la del alumno, y
        // la definición del modelo (si la había) se conserva como apoyo.
        setFaces((m) => ({
          ...m,
          [itemKey]: { back: translation, definition },
        }));
        markOwnBack(itemKey, true);
      } else {
        // V3.80.1 (P2): borrar la traducción propia NO la deja marcada como
        // propia —eso diría «Tu versión» sobre un texto que ya no existe—: la
        // precedencia vuelve al pack o a la caché, así que se recupera la cara
        // efectiva que sirvió el backend y se reintenta la caché si no la había.
        markOwnBack(itemKey, false);
        if (item.back) {
          setFaces((m) => ({
            ...m,
            [itemKey]: { back: item.back, definition },
          }));
        } else {
          setFaces((m) => {
            const next = { ...m };
            delete next[itemKey];
            return next;
          });
          void hydrate(item, itemKey, true);
        }
      }
      setEditing(false);
    } catch {
      setSaveError(true);
    } finally {
      setSaving(false);
    }
  }

  if (!current) {
    // V3.83.0: el cierre de sesión es el momento de celebrar. Se dice lo que de
    // verdad se puede afirmar —cuántas tarjetas y el acierto de ESTA sesión—,
    // sin convertirlo en una nota de dominio (D5/E3).
    const accuracy = done > 0 ? Math.round((good / done) * 100) : 0;
    return (
      <Card className="gap-4 p-6 text-center">
        <motion.div
          initial={reduceMotion ? false : { scale: 0.5, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 260, damping: 18 }}
          className="mx-auto grid size-16 place-items-center rounded-full bg-success/15 text-success"
          aria-hidden="true"
        >
          <Sparkles className="size-8" />
        </motion.div>
        <div className="flex flex-col items-center gap-1">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Layers className="size-4 text-primary" aria-hidden="true" />
            {deckName}
          </h2>
          <p className="text-sm font-medium">
            {t("flashcards.study.finished").replace("{n}", String(done))}
          </p>
          {done > 0 ? (
            <p className="text-xs text-muted-foreground">
              {t("flashcards.study.sessionAccuracy").replace(
                "{pct}",
                String(accuracy),
              )}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button type="button" size="sm" variant="outline" onClick={onExit}>
            {t("flashcards.study.back")}
          </Button>
          {onRestart ? (
            <Button type="button" size="sm" variant="ghost" onClick={onRestart}>
              <RefreshCw className="size-3.5" aria-hidden="true" />
              {t("flashcards.study.refresh")}
            </Button>
          ) : null}
        </div>
      </Card>
    );
  }

  const hasFace = Boolean(answerText || definition);
  const progressPct =
    items.length > 0 ? Math.round(((index + 1) / items.length) * 100) : 0;

  return (
    <Card className="gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{deckName}</h2>
        <div className="flex flex-wrap items-center gap-2">
          {ownBacks[key] ? (
            <Badge variant="outline">{t("flashcards.study.ownBack")}</Badge>
          ) : null}
          <Badge variant={current.is_new ? "default" : "secondary"}>
            {current.is_new
              ? t("flashcards.study.newCard")
              : t("flashcards.study.reviewCard")}
          </Badge>
          <Badge variant="secondary">
            {t("flashcards.study.progress")
              .replace("{i}", String(index + 1))
              .replace("{n}", String(items.length))}
          </Badge>
        </div>
      </div>

      {/* V3.83.0: barra de progreso de la sesión, para que el avance sea un
          gesto visible y no solo un número. */}
      <Progress
        value={progressPct}
        className="h-1.5"
        aria-label={t("flashcards.study.progressBar")
          .replace("{i}", String(index + 1))
          .replace("{n}", String(items.length))}
      />

      {/* Volteo 3D: las dos caras viven en la misma escena y solo una mira al
          frente. El botón sigue siendo el control («Flip card») y las caras son
          spans no interactivos, así que la accesibilidad y los tests no cambian.
          Con «reducir movimiento» la rotación se apaga y el cambio de cara es
          instantáneo. */}
      <button
        type="button"
        onClick={() => {
          // V3.87.0: en producción el volteo lo controla la comprobación; ver la
          // respuesta sin haber escrito no es la actividad.
          if (productionActive) return;
          if (flipped) setFlipped(false);
          else reveal();
        }}
        aria-disabled={productionActive}
        className="relative block w-full [perspective:1200px]"
        aria-label={t("flashcards.study.flip")}
      >
        <motion.span
          className="relative block min-h-52 w-full [transform-style:preserve-3d]"
          animate={reduceMotion ? undefined : { rotateY: flipped ? 180 : 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <span className="absolute inset-0 flex flex-col items-center justify-center gap-3 rounded-xl border border-border bg-secondary/40 px-4 py-6 text-center [backface-visibility:hidden]">
            <span
              className="text-3xl font-bold tracking-tight break-words sm:text-4xl"
              lang={promptLang}
            >
              {promptText}
            </span>
            {!flipped ? (
              <span className="text-xs text-muted-foreground">
                {productionActive
                  ? t("flashcards.study.productionPrompt")
                  : t("flashcards.study.tapReveal")}
              </span>
            ) : null}
            {!flipped && definitionHint ? (
              <span className="text-xs text-muted-foreground break-words">
                {definitionHint}
              </span>
            ) : null}
          </span>
          <span
            className="absolute inset-0 flex flex-col items-center justify-center gap-2 rounded-xl border border-primary/30 bg-primary/5 px-4 py-6 text-center [backface-visibility:hidden] [transform:rotateY(180deg)]"
            aria-hidden={!flipped}
          >
            {generating ? (
              <span className="flex items-center gap-2 text-sm text-muted-foreground">
                <RefreshCw className="size-3.5 animate-spin" aria-hidden="true" />
                {t("flashcards.study.generating")}
              </span>
            ) : null}
            {!generating && answerText ? (
              <span
                className="text-lg font-semibold break-words"
                lang={answerLang}
              >
                {answerText}
              </span>
            ) : null}
            {!generating && definition ? (
              <span
                className="text-sm text-muted-foreground break-words"
                lang={isLexicon ? "en" : undefined}
              >
                {definition}
              </span>
            ) : null}
            {/* V3.86.0: el recordatorio, en pequeño y separado: es una ayuda
                para recordar, no la respuesta de la tarjeta. */}
            {!generating && mnemonic ? (
              <span
                className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground"
                aria-label={t("flashcards.cards.mnemonic")}
              >
                <Lightbulb className="size-3 shrink-0" aria-hidden="true" />
                <span className="break-words">{mnemonic}</span>
              </span>
            ) : null}
            {!generating && !hasFace ? (
              <span className="text-sm text-muted-foreground">
                {lookupState === "failed"
                  ? t("flashcards.study.lookupFailed")
                  : t("flashcards.study.noFace")}
              </span>
            ) : null}
          </span>
        </motion.span>
      </button>

      {!flipped && mnemonic.trim() && !productionActive ? (
        <div className="flex flex-col items-center gap-2">
          <Button
            type="button"
            variant="outline"
            className="min-h-12 gap-1.5"
            onClick={() => setHintStep((step) => Math.min(step + 1, 3))}
            disabled={hintStep >= 3}
          >
            <Lightbulb className="size-4" aria-hidden="true" />
            {t("flashcards.study.hintLabel")}
          </Button>
          {hintPiece ? (
            <p
              className="max-w-sm text-center text-sm text-muted-foreground break-words"
              aria-live="polite"
            >
              {hintPiece}
            </p>
          ) : null}
        </div>
      ) : null}

      {canEdit && flipped ? (
        <div className="flex flex-col gap-2">
          {editing ? (
            <div className="flex flex-col gap-2">
              <input
                type="text"
                value={draft}
                autoFocus
                maxLength={500}
                placeholder={t("flashcards.study.backPlaceholder")}
                aria-label={t("flashcards.study.backPlaceholder")}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void saveOwnBack();
                  if (e.key === "Escape") setEditing(false);
                }}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:border-primary/50 focus:outline-none"
              />
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  disabled={saving}
                  onClick={() => void saveOwnBack()}
                >
                  {saving ? t("common.saving") : t("common.save")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={saving}
                  onClick={() => setEditing(false)}
                >
                  {t("common.cancel")}
                </Button>
              </div>
            </div>
          ) : (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="w-fit self-center"
              onClick={() => {
                setDraft(back);
                setSaveError(false);
                setEditing(true);
              }}
            >
              <Pencil className="size-3.5" aria-hidden="true" />
              {back
                ? t("flashcards.study.fixBack")
                : t("flashcards.study.writeBack")}
            </Button>
          )}
          {saveError ? (
            <p className="text-sm text-destructive">
              {t("flashcards.study.editError")}
            </p>
          ) : null}
        </div>
      ) : null}

      {current.card_type === "lexicon" ? (
        <div className="flex items-center justify-center gap-2">
          <ItemReplayButton prompt={current.front} userId={userId} />
        </div>
      ) : null}

      {error ? (
        <p className="flex items-center gap-2 text-sm text-destructive">
          {t("dictionary.loadError")}
          <button
            type="button"
            onClick={() => setError(false)}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium hover:border-primary/50"
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            {t("common.retry")}
          </button>
        </p>
      ) : null}

      {productionActive && !flipped ? (
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
            {t("flashcards.study.productionLabel")}
            <input
              type="text"
              value={typed}
              autoFocus
              maxLength={500}
              onChange={(e) => setTyped(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") check();
              }}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:border-primary/50 focus:outline-none"
            />
          </label>
          <Button
            type="button"
            size="sm"
            className="w-fit self-center"
            disabled={busy}
            onClick={check}
          >
            {t("flashcards.study.check")}
          </Button>
        </div>
      ) : productionActive && checked ? (
        <div className="flex flex-col items-center gap-2">
          {/* Se enseña la cara correcta (arriba, ya volteada) junto al veredicto:
              la autocalificación no debe ocultar qué era lo que había que decir. */}
          <p
            className={cn(
              "text-sm font-medium",
              matched ? "text-success" : "text-destructive",
            )}
          >
            {matched
              ? t("flashcards.study.productionCorrect")
              : t("flashcards.study.productionWrong")}
          </p>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={busy}
            onClick={continueProduction}
          >
            {t("flashcards.study.continue")}
          </Button>
        </div>
      ) : flipped ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {GRADES.map((g) => {
            const Icon = g.Icon;
            return (
              <Button
                key={g.grade}
                type="button"
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => void grade(g.grade)}
                aria-keyshortcuts={String(g.grade)}
                className={cn(
                  "min-h-12 flex-col gap-0.5 py-2.5 font-semibold sm:flex-row sm:gap-1.5",
                  g.tone,
                )}
              >
                <Icon className="size-4" aria-hidden="true" />
                <kbd className="rounded border border-border/60 bg-background/60 px-1 text-[10px] font-bold text-muted-foreground">
                  {g.grade}
                </kbd>
                {/* El texto de la nota va en su propio nodo: el nombre
                    accesible y los tests siguen leyendo «Good», no «3Good». */}
                <span>{t(g.key)}</span>
              </Button>
            );
          })}
        </div>
      ) : (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={reveal}
          className="min-h-12 w-full self-center sm:w-fit"
        >
          {t("flashcards.study.reveal")}
        </Button>
      )}

      <button
        type="button"
        className="text-xs text-muted-foreground underline-offset-2 hover:underline"
        onClick={onExit}
      >
        {t("flashcards.study.exit")}
      </button>
    </Card>
  );
}
