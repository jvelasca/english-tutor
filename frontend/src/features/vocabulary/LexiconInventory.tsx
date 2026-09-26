import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { motion, type Variants } from "motion/react";
import { BookOpen, RefreshCw, Search } from "lucide-react";
import { getDrillCandidates, getLexicon } from "../../api/vocabulary";
import { normalizeDrillCandidates, normalizeLexicon } from "../../api/normalize";
import type { LexicalItem, LexicalStatus, Lexicon } from "../../types/api";
import { cefrBarValue, sortLexicalItems } from "./dictionary";
import { SpeakingDrillSection } from "./wordDrill";
import { AddVocabSection } from "./AddVocabSection";
import { useI18n } from "../../hooks/useI18n";
import { LevelBadge } from "../../components/LevelBadge";
import { SkillBar } from "../../components/SkillBar";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Progress } from "../../components/ui/progress";
import { cn } from "../../lib/utils";

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
};

const STATUS_TONE: Record<LexicalStatus, string> = {
  mastered: "border-transparent bg-success/15 text-success",
  known: "border-transparent bg-primary/15 text-primary",
  learning: "border-transparent bg-warning/15 text-warning",
  weak: "border-transparent bg-destructive/10 text-destructive",
};

interface LexiconInventoryProps {
  userId: string | null;
  /**
   * V3.77.2: dueño del layout. `DictionaryScreen` ya pinta el `h1`, el subtítulo
   * y el ancho de página (igual que hace con `DictionaryLookup`), así que la
   * vista incrustada no debe repetirlos: con `showHeader={false}` no emite su
   * propio `h1` ni el contenedor `max-w-3xl/px-4/py-8` (antes había dos `h1` en
   * la misma página y el ancho quedaba reducido dos veces). El diccionario
   * incrustado en la práctica de rutas sí lo deja por defecto.
   */
  showHeader?: boolean;
  /**
   * V3.85.0: «Mis listas» y los packs ya no repasan DENTRO del inventario.
   * Calificar tarjetas tiene una sola superficie (la sesión de Flashcards), así
   * que estas acciones saltan allí con la colección ya filtrada. El componente
   * no sabe cómo se hace ese salto: se lo dice el dueño de la navegación.
   */
  onStudyCollection?: (opts: { collectionId: number; label: string }) => void;
}

/** Estados del léxico, en el orden en que se ofrecen como filtro. */
const STATUS_FILTERS: LexicalStatus[] = [
  "mastered",
  "known",
  "learning",
  "weak",
];

/** Procedencias posibles de una palabra (`vocabulary.source`). */
const SOURCE_FILTERS: { id: string; labelKey: string }[] = [
  { id: "curriculum", labelKey: "dictionary.inventory.sourceCurriculum" },
  { id: "user", labelKey: "dictionary.inventory.sourceUser" },
  { id: "imported", labelKey: "dictionary.inventory.sourceImported" },
];

/**
 * Inventario del léxico (antes «Diccionario personal», V3.85.0).
 *
 * V3.78.0 convirtió esta vista en 「posesión」: buscador, filtro por estado y
 * procedencia, fuerza de memoria por fila y una única entrada al estudio.
 *
 * V3.85.0 la separa del ESTUDIO: el repaso (cola FSRS + drill de competencia) y
 * la sesión de tarjetas viven en la pestaña Flashcards, y aquí solo queda lo que
 * es inventario —mirar, buscar, acotar, añadir— más la cola de competencia del
 * drill oral, que es superficie de PRODUCCIÓN. El componente ya no pide la cola
 * de repaso ni pinta un resumen de estudio: eso era lo que llenaba la vista de
 * una lista larga que no se podía trabajar.
 */
export function LexiconInventory({
  userId,
  showHeader = true,
  onStudyCollection,
}: LexiconInventoryProps) {
  const { t } = useI18n();
  const [lexicon, setLexicon] = useState<Lexicon | null>(null);
  const [candidates, setCandidates] = useState<string[]>([]);
  const [drillWord, setDrillWord] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<LexicalStatus | "all">("all");
  const [sourceFilter, setSourceFilter] = useState<string>("all");

  const refresh = useCallback(async () => {
    if (!userId) return;
    try {
      const [data, drill] = await Promise.all([
        getLexicon(userId),
        getDrillCandidates(userId),
      ]);
      // V3.77.2: el ESTADO nunca guarda una forma sin comprobar. La frontera de
      // API ya normaliza, pero se aplica también aquí para que el componente sea
      // seguro aunque se monte con un cliente sustituido. Antes `setLexicon({})`
      // + `setCandidates(undefined)` dejaban `items`/`summary` sin forma y el
      // `.map` al pintar tumbaba (sin ErrorBoundary) la app entera.
      setLexicon(normalizeLexicon(data));
      setCandidates(normalizeDrillCandidates(drill).words);
      setLoadError(false);
    } catch {
      /* backend no disponible */
      setLoadError(true);
    }
  }, [userId]);

  useEffect(() => {
    if (!userId) return;
    void refresh();
  }, [userId, refresh]);

  const sorted = useMemo(
    () => (lexicon ? sortLexicalItems(lexicon.items) : []),
    [lexicon],
  );

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return sorted.filter((lex) => {
      if (statusFilter !== "all" && lex.status !== statusFilter) return false;
      if (sourceFilter !== "all" && lex.source !== sourceFilter) return false;
      if (!needle) return true;
      return (
        lex.word.toLowerCase().includes(needle) ||
        lex.lemma.toLowerCase().includes(needle)
      );
    });
  }, [sorted, search, statusFilter, sourceFilter]);

  const hasFilters =
    search.trim() !== "" || statusFilter !== "all" || sourceFilter !== "all";

  if (!lexicon) {
    return (
      <div
        className={
          showHeader ? "mx-auto w-full max-w-3xl px-4 py-8 sm:px-6" : "w-full"
        }
      >
        {showHeader && <DictionaryHeader />}
        {!userId ? (
          /* V3.77.2: sin perfil no hay léxico que pedir. Antes `refresh` salía
             temprano y `lexicon` se quedaba en `null` para siempre: la vista
             mostraba «Cargando…» de forma indefinida. */
          <p className="mt-4 text-sm text-muted-foreground">
            {t("dictionary.noProfile")}
          </p>
        ) : loadError ? (
          <p className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
            {t("dictionary.loadError")}
            <button
              type="button"
              onClick={() => void refresh()}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium hover:border-primary/50"
            >
              <RefreshCw className="size-3.5" aria-hidden="true" />
              {t("common.retry")}
            </button>
          </p>
        ) : (
          <p className="mt-4 text-sm text-muted-foreground">{t("common.loading")}</p>
        )}
      </div>
    );
  }

  const { summary } = lexicon;
  const maxCefr = Math.max(1, ...summary.by_cefr.map((b) => b.count));

  return (
    <div
      className={
        showHeader ? "mx-auto w-full max-w-3xl px-4 py-8 sm:px-6" : "w-full"
      }
    >
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-5"
      >
        {showHeader && <DictionaryHeader total={summary.total} />}

        {/* V3.85.0: aquí solo queda la cola de competencia del drill oral, que
            es PRODUCCIÓN y no calificación de tarjetas. Estudio y repaso se
            mudan a Flashcards. La sección se omite si no hay nada que practicar:
            una cabecera sin contenido era parte del ruido. */}
        {userId && (candidates.length > 0 || drillWord !== null) && (
          <motion.section
            variants={item}
            aria-label={t("dictionary.speakingPractice")}
            className="flex flex-col gap-3"
          >
            <h2 className="text-sm font-semibold tracking-tight">
              {t("dictionary.speakingPractice")}
            </h2>
            <SpeakingDrillSection
              userId={userId}
              words={candidates}
              drillWord={drillWord}
              onDrillChange={setDrillWord}
              onProduced={(word) => {
                setCandidates((prev) => prev.filter((w) => w !== word));
                void refresh();
              }}
            />
          </motion.section>
        )}

        {/* Añadir palabras / listas / temas. */}
        {userId && (
          <motion.section
            variants={item}
            aria-label={t("dictionary.add.section")}
            className="flex flex-col gap-3"
          >
            <h2 className="text-sm font-semibold tracking-tight">
              {t("dictionary.add.section")}
            </h2>
            <AddVocabSection
              userId={userId}
              onChanged={() => void refresh()}
              onStudy={onStudyCollection}
            />
          </motion.section>
        )}

        <motion.section variants={item} aria-label={t("dictionary.title")}>
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold tracking-tight">
              {t("dictionary.myLexicon")}
            </h2>
            {/* Incrustado no hay cabecera que muestre el total, así que el
                contador viaja aquí para no perder la información. */}
            {!showHeader && (
              <Badge variant="secondary" className="shrink-0">
                {summary.total} {t("dictionary.total")}
              </Badge>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile
              label={t("dictionary.known")}
              value={summary.known}
              tone="text-primary"
            />
            <StatTile
              label={t("dictionary.learning")}
              value={summary.learning}
              tone="text-warning"
            />
            <StatTile
              label={t("dictionary.weak")}
              value={summary.weak}
              tone="text-destructive"
            />
            <StatTile
              label={t("dictionary.mastered")}
              value={summary.mastered}
              tone="text-success"
            />
          </div>
        </motion.section>

        {/* V3.21 (V20-16) / V3.22: stats de la matriz de competencia del léxico
            (Retention separada de Transfer; production_gap y transfer_gap). */}
        <motion.section variants={item} aria-label={t("dictionary.competenceTitle")}>
          <Card className="gap-3 p-5">
            <div className="flex flex-col gap-1">
              <h2 className="text-sm font-semibold">{t("dictionary.competenceTitle")}</h2>
              <p className="text-[11px] leading-relaxed text-muted-foreground">
                {t("dictionary.competenceHint")}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <StatTile
                label={t("dictionary.competenceRecognized")}
                value={summary.recognized}
                tone="text-primary"
              />
              <StatTile
                label={t("dictionary.competenceProduced")}
                value={summary.produced}
                tone="text-success"
              />
              <StatTile
                label={t("dictionary.competenceTransfer")}
                value={summary.transfer}
                tone="text-success"
              />
              <StatTile
                label={t("dictionary.competenceRetention")}
                value={summary.retention}
                tone="text-primary"
              />
              <StatTile
                label={t("dictionary.competenceProductionGap")}
                value={summary.production_gap}
                tone="text-destructive"
              />
              <StatTile
                label={t("dictionary.competenceGap")}
                value={summary.transfer_gap}
                tone="text-destructive"
              />
            </div>
          </Card>
        </motion.section>

        {summary.by_cefr.length > 0 && (
          <motion.section variants={item} aria-label={t("dictionary.byCefr")}>
            <Card className="gap-3 p-5">
              <h2 className="text-sm font-semibold">{t("dictionary.byCefr")}</h2>
              <ul className="flex flex-col gap-2.5">
                {summary.by_cefr.map((bucket) => (
                  <li key={bucket.cefr} className="flex items-center gap-3">
                    <LevelBadge level={bucket.cefr} className="w-12 justify-center" />
                    <SkillBar
                      value={cefrBarValue(bucket.count, maxCefr)}
                      hint={String(bucket.count)}
                      className="flex-1"
                    />
                  </li>
                ))}
              </ul>
            </Card>
          </motion.section>
        )}

        <motion.section variants={item} aria-label={t("dictionary.items")}>
          <Card className="gap-0 overflow-hidden p-0">
            {/* V3.78.0: inventario = hay que poder BUSCAR y ACOTAR. Antes solo
                se podía desplazar la lista entera; con el léxico de toda la app
                eso deja de ser un listado y pasa a ser un archivo. */}
            <div className="flex flex-col gap-2.5 border-b border-border/60 p-3 sm:p-4">
              <div className="relative">
                <Search
                  className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground"
                  aria-hidden="true"
                />
                <input
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder={t("dictionary.inventory.searchPlaceholder")}
                  aria-label={t("dictionary.inventory.search")}
                  className="h-9 w-full rounded-md border border-border bg-background pr-2.5 pl-8 text-sm outline-none focus-visible:border-primary/60"
                />
              </div>
              <div
                className="flex flex-wrap items-center gap-1.5"
                role="group"
                aria-label={t("dictionary.inventory.filterStatus")}
              >
                <FilterChip
                  active={statusFilter === "all"}
                  onClick={() => setStatusFilter("all")}
                >
                  {t("dictionary.inventory.sourceAll")}
                </FilterChip>
                {STATUS_FILTERS.map((status) => (
                  <FilterChip
                    key={status}
                    active={statusFilter === status}
                    onClick={() => setStatusFilter(status)}
                  >
                    {t(`dictionary.status.${status}`)}
                  </FilterChip>
                ))}
              </div>
              <div
                className="flex flex-wrap items-center gap-1.5"
                role="group"
                aria-label={t("dictionary.inventory.filterSource")}
              >
                <FilterChip
                  active={sourceFilter === "all"}
                  onClick={() => setSourceFilter("all")}
                >
                  {t("dictionary.inventory.sourceAll")}
                </FilterChip>
                {SOURCE_FILTERS.map((source) => (
                  <FilterChip
                    key={source.id}
                    active={sourceFilter === source.id}
                    onClick={() => setSourceFilter(source.id)}
                  >
                    {t(source.labelKey)}
                  </FilterChip>
                ))}
              </div>
            </div>
            {sorted.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-5 py-10 text-center">
                <BookOpen
                  className="size-8 text-muted-foreground/60"
                  aria-hidden="true"
                />
                <p className="text-sm text-muted-foreground">{t("dictionary.empty")}</p>
              </div>
            ) : visible.length === 0 ? (
              /* Con filtros, una lista vacía NO es «no tienes palabras»: es que
                 no hay coincidencias. Distinguirlo evita el «no tengo nada»
                 mentiroso cuando en realidad el filtro es el que no encuentra. */
              <div className="flex flex-col items-center gap-2 px-5 py-10 text-center">
                <Search
                  className="size-8 text-muted-foreground/60"
                  aria-hidden="true"
                />
                <p className="text-sm text-muted-foreground">
                  {t("dictionary.inventory.noMatches")}
                </p>
                {hasFilters && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setSearch("");
                      setStatusFilter("all");
                      setSourceFilter("all");
                    }}
                  >
                    {t("dictionary.inventory.clear")}
                  </Button>
                )}
              </div>
            ) : (
              <>
                <ul className="divide-y divide-border/60">
                  {visible.map((lex) => (
                    <LexicalRow key={lex.word} lexical={lex} />
                  ))}
                </ul>
                {/* El contador solo aparece cuando hay recorte: si se ven todas,
                    repetir el total sería ruido. */}
                {visible.length !== sorted.length && (
                  <p className="border-t border-border/60 px-4 py-2 text-[11px] text-muted-foreground">
                    {t("dictionary.inventory.showing")
                      .replace("{n}", String(visible.length))
                      .replace("{total}", String(sorted.length))}
                  </p>
                )}
              </>
            )}
          </Card>
        </motion.section>
      </motion.div>
    </div>
  );
}

function DictionaryHeader({ total }: { total?: number }) {
  const { t } = useI18n();
  return (
    <motion.header variants={item} className="flex items-center justify-between gap-3">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight sm:text-3xl">
          <BookOpen className="size-6 text-primary" aria-hidden="true" />
          {t("dictionary.title")}
        </h1>
        <p className="mt-1 text-muted-foreground">{t("dictionary.subtitle")}</p>
      </div>
      {total != null && (
        <Badge variant="secondary" className="shrink-0">
          {total} {t("dictionary.total")}
        </Badge>
      )}
    </motion.header>
  );
}

function StatTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 text-left shadow-sm">
      <span className={cn("text-2xl font-bold tabular-nums", tone)}>{value}</span>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

function lexicalKindLabel(kind: string, t: (key: string) => string): string {
  // P1 (§3.2): taxonomía ampliada de Lexical Unit. Fallback genérico para
  // cualquier valor desconocido (nunca se etiqueta por defecto como "word").
  const key = `dictionary.kind.${kind}`;
  const label = t(key);
  return label === key ? t("dictionary.kind.other") : label;
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
        active
          ? "border-primary/60 bg-primary/10 text-foreground"
          : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function LexicalRow({ lexical }: { lexical: LexicalItem }) {
  const { t } = useI18n();
  const kindLabel = lexicalKindLabel(lexical.kind, t);
  const statusLabel = t(`dictionary.status.${lexical.status}`);
  /* V3.78.0: procedencia. `vocabulary.source` se guardaba desde siempre pero no
     se mostraba; sin ella, el inventario no distingue lo que trajo el currículo
     de lo que añadió el alumno. Se etiqueta con fallback al valor crudo para no
     perder información si el backend añade una procedencia nueva. */
  const sourceKey = `dictionary.inventory.source${lexical.source
    .charAt(0)
    .toUpperCase()}${lexical.source.slice(1)}`;
  const sourceLabel = t(sourceKey) === sourceKey ? lexical.source : t(sourceKey);
  /* Fuerza de memoria: estado del scheduler. Si no hay carta se dice que no
     consta y se cae al texto antiguo de `next_review_days` (proyección de la
     evidencia), que sigue siendo la única señal disponible en ese caso. */
  const memory = lexical.memory ?? null;
  const memoryText = memory
    ? memory.state === "new" || memory.reps === 0
      ? t("dictionary.inventory.memoryNew")
      : memory.due
        ? t("dictionary.inventory.memoryDue")
        : t("dictionary.inventory.memoryNext").replace(
            "{n}",
            String(Math.max(1, Math.round(memory.next_in_days))),
          )
    : null;
  const memoryTitle = memory
    ? t("dictionary.inventory.memoryTitle")
        .replace("{state}", memory.state)
        .replace("{due}", memory.due_at ? memory.due_at.slice(0, 10) : "—")
        .replace("{stability}", memory.stability.toFixed(1))
        .replace("{retrievability}", String(Math.round(memory.retrievability * 100)))
    : undefined;

  return (
    <li className="flex items-center gap-3 p-3 sm:p-4">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="truncate text-sm font-semibold text-foreground">
            {lexical.word}
          </span>
          {lexical.cefr && <LevelBadge level={lexical.cefr} className="shrink-0" />}
          <span className="shrink-0 text-xs text-muted-foreground">{kindLabel}</span>
          <span className="shrink-0 text-[11px] text-muted-foreground/80">
            {sourceLabel}
          </span>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <Progress
            value={Math.round(lexical.recall * 100)}
            className="h-1.5 flex-1"
            aria-label={`${t("dictionary.recall")} ${Math.round(lexical.recall * 100)}%`}
          />
          <span className="w-9 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
            {Math.round(lexical.recall * 100)}%
          </span>
        </div>
        {/* V3.80.0: tu reverso, en solo lectura. Está aquí para que el
            inventario diga qué palabras ya tienen cara B propia; se corrige en
            la sesión de estudio (el título lo declara para no prometer un
            campo editable que no existe en este sitio). */}
        {lexical.translation ? (
          <p
            className="mt-1.5 truncate text-xs text-muted-foreground"
            lang="es"
            title={t("dictionary.inventory.ownTranslationTitle")}
          >
            {t("dictionary.inventory.ownTranslation").replace(
              "{text}",
              lexical.translation,
            )}
          </p>
        ) : null}
      </div>
      <div className="flex min-w-0 max-w-[45%] shrink-0 flex-col items-end gap-1">
        <Badge className={cn(STATUS_TONE[lexical.status])}>{statusLabel}</Badge>
        {memoryText ? (
          <span
            className={cn(
              "text-right text-[11px] tabular-nums break-words",
              memory?.due ? "text-warning" : "text-muted-foreground",
            )}
            title={memoryTitle}
          >
            {memoryText}
          </span>
        ) : (
          lexical.status !== "mastered" && (
            <span className="text-[11px] text-muted-foreground">
              {lexical.status === "weak"
                ? t("mastery.reviewNow")
                : t("dictionary.nextReviewIn").replace(
                    "{days}",
                    String(lexical.next_review_days),
                  )}
            </span>
          )
        )}
      </div>
    </li>
  );
}
