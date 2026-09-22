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
import { useState } from "react";
import { Layers, Pencil, RefreshCw } from "lucide-react";
import type { FlashcardStudyItem } from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import {
  lookupDictionaryWord,
  setVocabularyTranslation,
} from "../../api/vocabulary";
import { ItemReplayButton } from "../../components/ItemReplayButton";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { cn } from "../../lib/utils";

const GRADES = [
  { grade: 1, key: "fsrs.grade.again", tone: "text-destructive" },
  { grade: 2, key: "fsrs.grade.hard", tone: "text-warning" },
  { grade: 3, key: "fsrs.grade.good", tone: "text-primary" },
  { grade: 4, key: "fsrs.grade.easy", tone: "text-success" },
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
}: StudySessionProps) {
  const { t } = useI18n();
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [done, setDone] = useState(0);

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

  const current = items[index] ?? null;
  const key = current ? cardKey(current) : "";
  const face = key ? faces[key] : undefined;
  const back = face ? face.back : (current?.back ?? "");
  const definition = face ? face.definition : (current?.definition ?? "");
  const generating = key !== "" && generatingKey === key;
  const lookupState = key ? lookupStates[key] : undefined;
  // El lápiz solo se ofrece en tarjetas del léxico: son las únicas cuya
  // traducción propia tiene fila que corregir. El reverso de una tarjeta
  // manual se edita en la pestaña Tarjetas, que es su sitio.
  const canEdit = current?.card_type === "lexicon";

  /**
   * Pide el reverso al diccionario cuando la tarjeta viene sin él.
   *
   * No hidrata si ya hay reverso: la cara que sirvió el backend (pack, tu
   * traducción o caché) es la verdad y no se sustituye por otra generación.
   * Tampoco reintenta una tarjeta ya resuelta o ya fallida: insistir con el
   * modelo caído solo añadiría esperas a la sesión.
   */
  async function hydrate(item: FlashcardStudyItem, itemKey: string) {
    if (item.back || item.card_type !== "lexicon") return;
    if (faces[itemKey] || lookupStates[itemKey] || generatingKey === itemKey) {
      return;
    }
    setGeneratingKey(itemKey);
    try {
      const entry = await lookupDictionaryWord(userId, item.front);
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
      setLookupStates((m) => ({ ...m, [itemKey]: "failed" }));
    } finally {
      setGeneratingKey("");
    }
  }

  function reveal() {
    if (!current) return;
    setFlipped(true);
    void hydrate(current, key);
  }

  async function grade(g: number) {
    if (!current || busy) return;
    setBusy(true);
    try {
      await onGrade(current, g);
      setDone((n) => n + 1);
      setFlipped(false);
      // Al cambiar de tarjeta se cierra cualquier edición abierta: el campo es
      // de la tarjeta anterior y dejarlo abierto guardaría en la equivocada.
      setEditing(false);
      setSaveError(false);
      setDraft("");
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

  async function saveOwnBack() {
    if (!current || saving || !key) return;
    setSaving(true);
    setSaveError(false);
    const translation = draft.trim();
    try {
      await setVocabularyTranslation(userId, current.front, translation);
      // Lo escrito manda: la cara de esta sesión pasa a ser la del alumno, y la
      // definición del modelo (si la había) se conserva como apoyo.
      setFaces((m) => ({ ...m, [key]: { back: translation, definition } }));
      setOwnBacks((m) => ({ ...m, [key]: true }));
      setLookupStates((m) => {
        const next = { ...m };
        delete next[key];
        return next;
      });
      setEditing(false);
    } catch {
      setSaveError(true);
    } finally {
      setSaving(false);
    }
  }

  if (!current) {
    return (
      <Card className="gap-3 p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Layers className="size-4 text-primary" aria-hidden="true" />
          {deckName}
        </h2>
        <p className="text-sm font-medium">
          {t("flashcards.study.finished").replace("{n}", String(done))}
        </p>
        <div className="flex flex-wrap items-center gap-2">
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

  const hasFace = Boolean(back || definition);

  return (
    <Card className="gap-4 p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{deckName}</h2>
        <div className="flex items-center gap-2">
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

      <button
        type="button"
        onClick={() => (flipped ? setFlipped(false) : reveal())}
        className={cn(
          "flex min-h-36 w-full flex-col items-center justify-center gap-3 rounded-xl border border-border bg-secondary/40 px-4 py-6 text-center transition-colors hover:border-primary/40",
        )}
        aria-label={t("flashcards.study.flip")}
      >
        <span className="text-2xl font-bold tracking-tight" lang="en">
          {current.front}
        </span>
        {flipped ? (
          <div className="flex flex-col gap-1">
            {generating ? (
              <span className="flex items-center gap-2 text-sm text-muted-foreground">
                <RefreshCw className="size-3.5 animate-spin" aria-hidden="true" />
                {t("flashcards.study.generating")}
              </span>
            ) : null}
            {!generating && back ? (
              <span className="text-lg font-semibold" lang="es">
                {back}
              </span>
            ) : null}
            {!generating && definition ? (
              <span className="text-sm text-muted-foreground" lang="en">
                {definition}
              </span>
            ) : null}
            {!generating && !hasFace ? (
              <span className="text-sm text-muted-foreground">
                {lookupState === "failed"
                  ? t("flashcards.study.lookupFailed")
                  : t("flashcards.study.noFace")}
              </span>
            ) : null}
          </div>
        ) : (
          <span className="text-xs text-muted-foreground">
            {t("flashcards.study.tapReveal")}
          </span>
        )}
      </button>

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

      {flipped ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {GRADES.map((g) => (
            <Button
              key={g.grade}
              type="button"
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => void grade(g.grade)}
              className={cn("font-semibold", g.tone)}
            >
              {t(g.key)}
            </Button>
          ))}
        </div>
      ) : (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="w-fit self-center"
          onClick={reveal}
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
