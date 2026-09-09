import { useState, type FormEvent } from "react";
import { Loader2, RefreshCw, Search } from "lucide-react";
import { lookupDictionaryWord } from "../../api/vocabulary";
import type {
  DictionaryEntry,
  DictionarySurfaceUsage,
  DictionaryUnitUsage,
  LexicalCompetence,
  LexicalStatus,
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { LevelBadge } from "../../components/LevelBadge";
import { ListenButton } from "../../components/ListenButton";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Progress } from "../../components/ui/progress";
import { cn } from "../../lib/utils";

/** Colores de estado: misma taxonomía y paleta que `PersonalDictionary`. */
const STATUS_TONE: Record<LexicalStatus, string> = {
  mastered: "border-transparent bg-success/15 text-success",
  known: "border-transparent bg-primary/15 text-primary",
  learning: "border-transparent bg-warning/15 text-warning",
  weak: "border-transparent bg-destructive/10 text-destructive",
};

const MAX_QUERY_LENGTH = 80;

interface DictionaryLookupProps {
  userId: string | null;
}

/** Diccionario de consulta (V3.30, D2/D3): busca CUALQUIER palabra (esté o no
 * en el léxico del alumno) y muestra definición/traducción cacheadas del modelo
 * local (o degradación a `definition_source="none"`), una frase de ejemplo
 * determinista del banco y la marca de uso/aprendizaje. La consulta es solo
 * lectura: nunca registra evidencia. */
export function DictionaryLookup({ userId }: DictionaryLookupProps) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [networkError, setNetworkError] = useState(false);
  const [invalidError, setInvalidError] = useState(false);
  const [entry, setEntry] = useState<DictionaryEntry | null>(null);
  // Palabra de la consulta actual (para el retry tras un error de red).
  const [lastQuery, setLastQuery] = useState("");

  async function runLookup(raw: string) {
    if (!userId) return;
    const word = raw.trim();
    // Validación local espejo del backend (422): vacía tras recortar, solo
    // puntuación o demasiado larga. Así el error de «palabra inválida» es
    // determinista y nunca depende de la lengua del detalle del servidor.
    if (!word || word.length > MAX_QUERY_LENGTH || !/[\p{L}\p{N}]/u.test(word)) {
      setInvalidError(true);
      setNetworkError(false);
      setEntry(null);
      return;
    }
    setInvalidError(false);
    setNetworkError(false);
    setLoading(true);
    setLastQuery(word);
    try {
      const data = await lookupDictionaryWord(userId, word);
      setEntry(data);
    } catch {
      setEntry(null);
      setNetworkError(true);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void runLookup(query);
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
      <header className="mb-5">
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight sm:text-3xl">
          <Search className="size-6 text-primary" aria-hidden="true" />
          {t("dictionary.lookup.title")}
        </h1>
        <p className="mt-1 text-muted-foreground">
          {t("dictionary.lookup.subtitle")}
        </p>
      </header>

      <form role="search" onSubmit={onSubmit} className="flex flex-col gap-2 sm:flex-row">
        <label className="sr-only" htmlFor="dictionary-lookup-input">
          {t("dictionary.lookup.searchAria")}
        </label>
        <input
          id="dictionary-lookup-input"
          type="text"
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          lang="en"
          value={query}
          maxLength={MAX_QUERY_LENGTH}
          disabled={!userId || loading}
          onChange={(e) => {
            setQuery(e.target.value);
            setInvalidError(false);
          }}
          placeholder={t("dictionary.lookup.placeholder")}
          className="h-10 min-w-0 flex-1 rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/70 focus-visible:border-primary/60 focus-visible:ring-2 focus-visible:ring-ring/50 disabled:opacity-60"
        />
        <Button
          type="submit"
          disabled={!userId || loading || query.trim().length === 0}
          className="shrink-0 gap-1.5"
        >
          <Search className="size-4" aria-hidden="true" />
          {t("dictionary.lookup.button")}
        </Button>
      </form>

      {!userId && (
        <p className="mt-4 text-sm text-muted-foreground">
          {t("dictionary.lookup.noProfile")}
        </p>
      )}

      {userId && loading && (
        <p
          className="mt-6 flex items-center gap-2 text-sm text-muted-foreground"
          role="status"
        >
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          {t("common.loading")}
        </p>
      )}

      {invalidError && (
        <p className="mt-6 text-sm text-destructive" role="alert">
          {t("dictionary.lookup.error.invalid")}
        </p>
      )}

      {networkError && (
        <div className="mt-6 flex flex-col items-start gap-2" role="alert">
          <p className="text-sm text-destructive">
            {t("dictionary.lookup.error.network")}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void runLookup(lastQuery)}
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            {t("common.retry")}
          </Button>
        </div>
      )}

      {userId && !loading && !networkError && !invalidError && entry && (
        <ResultCard entry={entry} />
      )}
    </div>
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

function ResultCard({ entry }: { entry: DictionaryEntry }) {
  const { t } = useI18n();
  const kindLabel = lexicalKindLabel(entry.kind, t);
  const pos = entry.pos ? entry.pos[0].toUpperCase() + entry.pos.slice(1) : "";
  const base =
    entry.usage.surface ??
    (entry.usage.unit as DictionarySurfaceUsage | DictionaryUnitUsage | null);

  return (
    <div className="mt-6 flex flex-col gap-5">
      <Card className="gap-3 p-5">
        {/* Palabra + badges de contexto */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="flex flex-wrap items-center gap-2 text-xl font-bold tracking-tight">
              <span lang="en">{entry.word}</span>
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
            </h2>
          </div>
          <ListenButton
            text={entry.word}
            label={t("dictionary.lookup.listenWord")}
          />
        </div>

        {entry.definition_source === "llm" ? (
          <div className="flex flex-col gap-3">
            {entry.definition && (
              <div className="flex flex-col gap-1">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("dictionary.lookup.definitionLabel")}
                </span>
                <p className="text-sm leading-relaxed" lang="en">
                  {entry.definition}
                </p>
              </div>
            )}
            {entry.translation && (
              <div className="flex flex-col gap-1">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("dictionary.lookup.translationLabel")}
                </span>
                <p className="text-sm leading-relaxed" lang="es">
                  {entry.translation}
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
            <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-background/60 px-3 py-2">
              <span className="text-sm font-medium" lang="en">
                {entry.example.phrase}
              </span>
              <ListenButton
                text={entry.example.phrase}
                label={t("dictionary.lookup.listenExample")}
              />
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
    </div>
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
