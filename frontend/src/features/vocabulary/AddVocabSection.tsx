/**
 * Bloque «Añadir» del diccionario personal: palabra suelta, lista pegada y
 * packs temáticos. Solo materializa léxico + FSRS; no escribe mastery.
 */
import { useCallback, useEffect, useState } from "react";
import { ListPlus, Loader2, Package, Plus } from "lucide-react";
import {
  addVocabularyBulk,
  addVocabularyItem,
  enrollVocabCollection,
  listVocabCollections,
} from "../../api/vocabulary";
import type { VocabCollection } from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { cn } from "../../lib/utils";

interface AddVocabSectionProps {
  userId: string;
  onChanged?: () => void;
  /**
   * V3.78.0: «Mis listas» y los packs ya no repasan DENTRO del diccionario.
   * Calificar tarjetas tiene una sola superficie (Flashcards), así que estas
   * acciones navegan allí con la colección ya filtrada. El componente no sabe
   * cómo se hace ese salto: se lo dice el dueño de la navegación.
   */
  onStudy?: (opts: { collectionId: number; label: string }) => void;
}

/**
 * V3.88.0: qué acción está en vuelo. Antes las tres compartían un `busy` que
 * solo deshabilitaba botones: al añadir una palabra se apagaban también las
 * tarjetas de listas y packs, sin decir cuál estaba trabajando.
 */
type BusyAction =
  | { kind: "add" }
  | { kind: "bulk" }
  | { kind: "enroll"; id: number }
  | null;

/** Icono de espera para el botón que está trabajando (V3.88.0). */
function BusySpinner() {
  return <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />;
}

export function AddVocabSection({
  userId,
  onChanged,
  onStudy,
}: AddVocabSectionProps) {
  const { t, lang } = useI18n();
  const [word, setWord] = useState("");
  const [translation, setTranslation] = useState("");
  const [listTitle, setListTitle] = useState("");
  const [listText, setListText] = useState("");
  const [packs, setPacks] = useState<VocabCollection[]>([]);
  const [busyAction, setBusyAction] = useState<BusyAction>(null);
  const busy = busyAction !== null;
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState(false);

  const refreshPacks = useCallback(async () => {
    try {
      const data = await listVocabCollections(userId);
      // V3.77: el estado se queda SIEMPRE con un array. Fiarse de la forma de la
      // respuesta (y hacer `packs.filter` con `undefined` si el campo no viene)
      // no rompe esta tarjeta: **tira la pantalla entera**, porque el fallo
      // ocurre al pintar. Lo encontró la suite visual, que mockea `/api/**` con
      // respuestas vacías; el mismo camino es el de un servidor que cambie el
      // contrato. Falla la lista, no la pantalla.
      setPacks(Array.isArray(data?.collections) ? data.collections : []);
      setError(false);
    } catch {
      setError(true);
    }
  }, [userId]);

  useEffect(() => {
    void refreshPacks();
  }, [refreshPacks]);

  async function handleAddWord(e: React.FormEvent) {
    e.preventDefault();
    if (!word.trim() || busy) return;
    setBusyAction({ kind: "add" });
    setMessage(null);
    try {
      const out = await addVocabularyItem(userId, word.trim(), {
        translation: translation.trim(),
      });
      setWord("");
      setTranslation("");
      setMessage(
        t("dictionary.add.wordOk").replace("{word}", out.added?.[0] ?? word),
      );
      onChanged?.();
      void refreshPacks();
    } catch {
      setMessage(t("dictionary.add.error"));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleBulk(e: React.FormEvent) {
    e.preventDefault();
    if (!listText.trim() || busy) return;
    setBusyAction({ kind: "bulk" });
    setMessage(null);
    try {
      const out = await addVocabularyBulk(userId, listText, {
        title: listTitle.trim() || t("dictionary.add.defaultList"),
      });
      setListText("");
      setListTitle("");
      setMessage(
        t("dictionary.add.bulkOk").replace("{n}", String(out.count ?? 0)),
      );
      onChanged?.();
      void refreshPacks();
    } catch {
      setMessage(t("dictionary.add.error"));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleEnroll(pack: VocabCollection) {
    if (busy) return;
    setBusyAction({ kind: "enroll", id: pack.id });
    setMessage(null);
    try {
      const out = await enrollVocabCollection(userId, pack.id);
      setMessage(
        t("dictionary.add.enrollOk")
          .replace("{n}", String(out.count ?? 0))
          .replace("{title}", lang === "es" && pack.title_es ? pack.title_es : pack.title),
      );
      onChanged?.();
      void refreshPacks();
    } catch {
      setMessage(t("dictionary.add.error"));
    } finally {
      setBusyAction(null);
    }
  }

  const themes = packs.filter((c) => c.kind === "theme_pack");
  const lists = packs.filter((c) => c.kind === "user_list");

  return (
    <div className="flex flex-col gap-4">
      <Card className="gap-3 p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Plus className="size-4 text-primary" aria-hidden="true" />
          {t("dictionary.add.wordTitle")}
        </h2>
        <form onSubmit={(e) => void handleAddWord(e)} className="flex flex-col gap-2 sm:flex-row">
          <input
            value={word}
            onChange={(e) => setWord(e.target.value)}
            placeholder={t("dictionary.add.wordPlaceholder")}
            maxLength={80}
            className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
            lang="en"
          />
          <input
            value={translation}
            onChange={(e) => setTranslation(e.target.value)}
            placeholder={t("dictionary.add.translationPlaceholder")}
            maxLength={200}
            className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
            lang="es"
          />
          <Button type="submit" size="sm" disabled={busy || !word.trim()}>
            {busyAction?.kind === "add" ? <BusySpinner /> : null}
            {busyAction?.kind === "add"
              ? t("common.saving")
              : t("dictionary.add.wordCta")}
          </Button>
        </form>
      </Card>

      <Card className="gap-3 p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <ListPlus className="size-4 text-primary" aria-hidden="true" />
          {t("dictionary.add.listTitle")}
        </h2>
        <p className="text-[11px] text-muted-foreground">
          {t("dictionary.add.listHint")}
        </p>
        <form onSubmit={(e) => void handleBulk(e)} className="flex flex-col gap-2">
          <input
            value={listTitle}
            onChange={(e) => setListTitle(e.target.value)}
            placeholder={t("dictionary.add.listNamePlaceholder")}
            maxLength={120}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
          />
          <textarea
            value={listText}
            onChange={(e) => setListText(e.target.value)}
            placeholder={t("dictionary.add.listPlaceholder")}
            rows={5}
            className="min-h-24 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            lang="en"
          />
          <Button
            type="submit"
            size="sm"
            className="w-fit"
            disabled={busy || !listText.trim()}
          >
            {busyAction?.kind === "bulk" ? <BusySpinner /> : null}
            {busyAction?.kind === "bulk"
              ? t("common.saving")
              : t("dictionary.add.listCta")}
          </Button>
        </form>
      </Card>

      <Card className="gap-3 p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Package className="size-4 text-primary" aria-hidden="true" />
          {t("dictionary.add.packsTitle")}
        </h2>
        <p className="text-[11px] text-muted-foreground">
          {t("dictionary.add.packsHint")}
        </p>
        {error ? (
          <p className="text-sm text-muted-foreground">{t("dictionary.loadError")}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {themes.map((pack) => {
              const title =
                lang === "es" && pack.title_es ? pack.title_es : pack.title;
              return (
                <li
                  key={pack.id}
                  className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 rounded-md border border-border/60 px-3 py-2"
                >
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <span className="truncate text-sm font-medium">{title}</span>
                    <span className="text-[11px] text-muted-foreground">
                      {pack.item_count} · {pack.cefr_hint || "—"}
                    </span>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {pack.enrolled ? (
                      <Badge
                        variant="secondary"
                        className={cn("border-transparent bg-success/15 text-success")}
                      >
                        {t("dictionary.add.enrolled")}
                      </Badge>
                    ) : (
                      <Button
                        type="button"
                        size="sm"
                        disabled={busy}
                        onClick={() => void handleEnroll(pack)}
                      >
                        {busyAction?.kind === "enroll" &&
                        busyAction.id === pack.id ? (
                          <BusySpinner />
                        ) : null}
                        {busyAction?.kind === "enroll" &&
                        busyAction.id === pack.id
                          ? t("common.saving")
                          : t("dictionary.add.enroll")}
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        {lists.length > 0 ? (
          <div className="mt-2 flex flex-col gap-1">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {t("dictionary.add.myLists")}
            </span>
            {/* V3.77.2: filas con recuento y acción. Antes eran insignias
                `title (n)` sin ninguna forma de trabajar la lista. */}
            <ul className="flex flex-col gap-2">
              {lists.map((list) => (
                <li
                  key={list.id}
                  className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 rounded-md border border-border/60 px-3 py-2"
                >
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <span className="truncate text-sm font-medium">
                      {list.title}
                    </span>
                    <span className="text-[11px] text-muted-foreground">
                      {list.item_count} {t("dictionary.total")}
                    </span>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={busy || list.item_count === 0 || !onStudy}
                    onClick={() =>
                      onStudy?.({
                        collectionId: list.id,
                        label: list.title,
                      })
                    }
                  >
                    {t("dictionary.add.reviewList")}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </Card>

      {message ? (
        <p className="text-sm text-muted-foreground" role="status">
          {message}
        </p>
      ) : null}
    </div>
  );
}
