import { useCallback, useEffect, useState } from "react";
import { motion, type Variants } from "motion/react";
import { BookOpen, RefreshCw } from "lucide-react";
import { getDrillCandidates, getLexicon } from "../../api/vocabulary";
import { normalizeDrillCandidates, normalizeLexicon } from "../../api/normalize";
import type { LexicalItem, LexicalStatus, Lexicon } from "../../types/api";
import { cefrBarValue, sortLexicalItems } from "./dictionary";
import { ReviewQueueSection } from "./ReviewQueueSection";
import { SpeakingDrillSection } from "./wordDrill";
import { RetentionSession } from "./RetentionSession";
import { AddVocabSection } from "./AddVocabSection";
import { useI18n } from "../../hooks/useI18n";
import { LevelBadge } from "../../components/LevelBadge";
import { SkillBar } from "../../components/SkillBar";
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

interface PersonalDictionaryProps {
  userId: string | null;
  /**
   * V3.77.2: dueño del layout. `DictionaryScreen` ya pinta el `h1`, el subtítulo
   * y el ancho de página (igual que hace con `DictionaryLookup`), así que la
   * vista incrustada no debe repetirlos: con `showHeader={false}` no emite su
   * propio `h1` ni el contenedor `max-w-3xl/px-4/py-8` (antes había dos `h1` en
   * la misma página y el ancho quedaba reducido dos veces).
   */
  showHeader?: boolean;
}

/** Diccionario personal (V2.3): evidencia por ítem léxico con estado y recall.
 * V3.19: la sección de candidatas al speaking micro-drill se nutre de la señal
 * determinista del servidor (`getDrillCandidates`) y cada palabra gana una
 * acción de micro-práctica oral dentro del panel. V3.32: la escalera de drill
 * (Recall → Sentence) vive en `./wordDrill` y se comparte con el diccionario
 * de consulta («Practicar esta palabra»). */
export function PersonalDictionary({
  userId,
  showHeader = true,
}: PersonalDictionaryProps) {
  const { t } = useI18n();
  const [lexicon, setLexicon] = useState<Lexicon | null>(null);
  const [candidates, setCandidates] = useState<string[]>([]);
  const [drillWord, setDrillWord] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);

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

  const { summary, items } = lexicon;
  const sorted = sortLexicalItems(items);

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

        {/* Practicar hoy: retención (Anki-lite) + cola de competencia (drill). */}
        {userId && (
          <motion.section
            variants={item}
            aria-label={t("dictionary.practiceToday")}
            className="flex flex-col gap-4"
          >
            <h2 className="text-sm font-semibold tracking-tight">
              {t("dictionary.practiceToday")}
            </h2>
            <RetentionSession userId={userId} onFinished={() => void refresh()} />
            <ReviewQueueSection userId={userId} />
            {(candidates.length > 0 || drillWord !== null) && (
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
            )}
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
            <AddVocabSection userId={userId} onChanged={() => void refresh()} />
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
            {sorted.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-5 py-10 text-center">
                <BookOpen
                  className="size-8 text-muted-foreground/60"
                  aria-hidden="true"
                />
                <p className="text-sm text-muted-foreground">{t("dictionary.empty")}</p>
              </div>
            ) : (
              <ul className="divide-y divide-border/60">
                {sorted.map((lex) => (
                  <LexicalRow key={lex.word} lexical={lex} />
                ))}
              </ul>
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

function LexicalRow({ lexical }: { lexical: LexicalItem }) {
  const { t } = useI18n();
  const kindLabel = lexicalKindLabel(lexical.kind, t);
  const statusLabel = t(`dictionary.status.${lexical.status}`);

  return (
    <li className="flex items-center gap-3 p-3 sm:p-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-semibold text-foreground">
            {lexical.word}
          </span>
          {lexical.cefr && <LevelBadge level={lexical.cefr} className="shrink-0" />}
          <span className="shrink-0 text-xs text-muted-foreground">{kindLabel}</span>
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
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        <Badge className={cn(STATUS_TONE[lexical.status])}>{statusLabel}</Badge>
        {lexical.status !== "mastered" && (
          <span className="text-[11px] text-muted-foreground">
            {lexical.status === "weak"
              ? t("mastery.reviewNow")
              : t("dictionary.nextReviewIn").replace(
                  "{days}",
                  String(lexical.next_review_days),
                )}
          </span>
        )}
      </div>
    </li>
  );
}
