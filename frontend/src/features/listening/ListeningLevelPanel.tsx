import { useEffect, useState } from "react";
import { ChevronDown, Loader2, Plus } from "lucide-react";
import { getListeningLevelItems } from "../../api/listening";
import type {
  ListeningExtrasJob,
  ListeningItem,
  ListeningItemState,
  ListeningLevelItems,
  ListeningRouteRetention,
  ListeningRouteState,
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { ListenButton } from "../../components/ListenButton";
import {
  PhraseTranslateButton,
  usePhraseTranslation,
} from "../../components/PhraseTranslate";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { cn } from "../../lib/utils";

const GROUPS: ListeningItemState[] = ["failed", "mastered", "unseen"];
// Cantidades de práctica extra que se pueden añadir a una ruta (V3.6).
const EXTRAS_AMOUNTS = [10, 25, 50];

// Umbrales de la retención retardada que decide DEMONSTRATED (Constitución §2.1
// y P1/H5): re-exposiciones ≥ 7 días con ratio ≥ 90% de la precisión inmediata.
const DEMO_MIN_RATIO_PCT = 90;
const DEMO_MIN_DAYS = 7;

function groupKey(state: ListeningItemState): string {
  return `listening.levelStates.${state}`;
}

interface ListeningLevelPanelProps {
  userId: string | null;
  level: string;
  /** Estado pedagógico de la ruta (functional ≠ demonstrated), si el backend lo expone. */
  routeState?: ListeningRouteState;
  routeRetention?: ListeningRouteRetention | null;
  /** Sesión de práctica activa: no se pueden iniciar más sesiones. */
  disabled?: boolean;
  onPracticeLevel: (level: string, total: number) => void;
  onDrillFailed: (level: string, failedIds: string[]) => void;
  /** Repasar lo aprendido: rotación solo por las frases ya dominadas (V3.6). */
  onReviewLearned: (level: string, total: number) => void;
  /** Añadir práctica extra generada a la ruta (V3.6). */
  onAddExtras: (level: string, count: number) => void;
  /** Estado del trabajo de generación de la ruta (para mostrar progreso/error). */
  extrasJob?: ListeningExtrasJob | null;
  /** Contador que fuerza a recargar el panel (tras terminar una generación). */
  refreshNonce?: number;
}

/**
 * Historial por frase de un nivel (control del alumno). Al desplegar el donut de
 * un nivel muestra sus frases agrupadas en falladas / dominadas / sin ver, cada
 * una con su altavoz TTS, y ofrece repetir las falladas hasta dominarlas,
 * repasar lo aprendido (solo dominadas) o practicar/repasar el nivel completo.
 * Cuando el banco oficial de la ruta está dominado ofrece añadir práctica extra
 * generada (IA local) para consolidar sin tocar la certificación. Solo lectura
 * + acciones: la práctica en sí la hace `ListeningPractice`.
 */
export function ListeningLevelPanel({
  userId,
  level,
  routeState,
  routeRetention,
  disabled,
  onPracticeLevel,
  onDrillFailed,
  onReviewLearned,
  onAddExtras,
  extrasJob,
  refreshNonce,
}: ListeningLevelPanelProps) {
  const { t } = useI18n();
  const [data, setData] = useState<ListeningLevelItems | null>(null);
  const [open, setOpen] = useState<ListeningItemState>("failed");
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setData(null);
    setError(false);
    const uid = userId;
    void (async () => {
      try {
        const items = await getListeningLevelItems(uid, level);
        if (!cancelled) setData(items);
      } catch {
        if (!cancelled) setError(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, level, refreshNonce]);

  if (error) {
    return (
      <p className="text-xs text-muted-foreground">
        {t("listening.levelItemsError")}
      </p>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
        {t("listening.loading")}
      </div>
    );
  }

  const groups = GROUPS.map((state) => ({
    state,
    label: t(groupKey(state)).replace(
      "{count}",
      String(
        state === "failed"
          ? data.failed
          : state === "mastered"
            ? data.mastered
            : data.unseen,
      ),
    ),
    items: data.items.filter((i) => i.state === state),
  }));

  const failedIds = data.items
    .filter((i) => i.state === "failed")
    .map((i) => i.question_id);

  const gate = data.gate;
  const showGate =
    !!gate && !gate.passed && gate.total > 0 && gate.mastered > 0;
  // Banco curado oficial: puerta y `completed` se calculan solo sobre él, así
  // que los ítems extra (source "generated") no alteran estos contadores.
  const baseTotal = gate?.total ?? data.total;
  const extras = gate && gate.total > 0 ? Math.max(0, data.total - gate.total) : 0;
  // La ruta está "cubierta" (banco oficial dominado) aunque la puerta siga
  // bloqueada por precisión/variedad/checkpoint: es el momento de la práctica
  // extra ilimitada.
  const baseCovered =
    !!gate && gate.total > 0 && gate.mastered >= gate.total;
  const pendingCert =
    gate && gate.total > 0
      ? !gate.passed && gate.mastered >= gate.total
      : data.mastered === data.total && data.total > 0;
  const jobRunning = extrasJob?.status === "running";
  const jobDone = extrasJob?.status === "done";
  const jobError = extrasJob?.status === "error" ? extrasJob.error : "";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <Badge variant="outline" className="gap-1">
            {data.total} {t("listening.levelItemsPhrases")}
          </Badge>
          <span className="text-muted-foreground">
            {t("listening.levelItemsSummary")
              .replace("{mastered}", String(data.mastered))
              .replace("{failed}", String(data.failed))
              .replace("{unseen}", String(data.unseen))}
          </span>
        </div>
        {data.completed ? (
          <Badge className="gap-1">{t("listening.completedShort")}</Badge>
        ) : (
          pendingCert && (
            <Badge
              variant="outline"
              className="border-warning/40 text-warning"
            >
              {t("listening.routePendingCert")}
            </Badge>
          )
        )}
      </div>

      {data.completed && routeState === "functional" && (
        <div className="rounded-lg border border-warning/30 bg-warning/5 px-3 py-2.5 text-xs">
          <p className="font-medium text-warning">
            {t("listening.demoNotYet").replace("{level}", level)}
          </p>
          <p className="mt-1 leading-relaxed text-muted-foreground">
            {t("listening.demoRequires")
              .replace("{level}", level)
              .replace("{ratio}", String(DEMO_MIN_RATIO_PCT))
              .replace("{days}", String(DEMO_MIN_DAYS))}
          </p>
          {routeRetention && (
            <p className="mt-1 leading-relaxed text-muted-foreground">
              {t("listening.demoRetentionStatus")
                .replace(
                  "{rate}",
                  routeRetention.retention_rate !== null
                    ? `${Math.round(routeRetention.retention_rate * 100)}%`
                    : "—",
                )
                .replace(
                  "{exposures}",
                  String(routeRetention.long_delayed_exposures),
                )
                .replace("{ratio}", String(DEMO_MIN_RATIO_PCT))}
            </p>
          )}
        </div>
      )}
      {routeState === "demonstrated" && (
        <div className="rounded-lg border border-success/30 bg-success/5 px-3 py-2.5 text-xs">
          <p className="font-medium text-success">
            {t("listening.demoTitle").replace("{level}", level)}
          </p>
          <p className="mt-1 leading-relaxed text-muted-foreground">
            {t("listening.demoMet").replace("{days}", String(DEMO_MIN_DAYS))}
          </p>
        </div>
      )}

      {showGate && (
        <div className="rounded-lg border border-warning/30 bg-warning/5 px-3 py-2.5 text-xs">
          <p className="font-medium text-warning">
            {t("listening.routeGateIntro").replace("{level}", level)}
          </p>
          <p className="mt-1 leading-relaxed text-muted-foreground">
            {t("listening.routeGateLine")
              .replace("{coverage}", String(Math.round(gate.coverage_pct)))
              .replace(
                "{coverageRequired}",
                String(Math.round(gate.coverage_required_pct)),
              )
              .replace(
                "{accuracyRequired}",
                String(Math.round(gate.accuracy_required)),
              )
              .replace(
                "{accuracy}",
                gate.accuracy !== null ? `${Math.round(gate.accuracy)}%` : "—",
              )
              .replace("{topics}", String(gate.topics))
              .replace("{topicsRequired}", String(gate.topics_required))
              .replace("{checkpoint}", String(gate.checkpoint))
              .replace(
                "{checkpointRequired}",
                String(gate.checkpoint_required),
              )}
          </p>
        </div>
      )}

      {baseCovered && (
        <div className="rounded-lg border border-border bg-muted/30 px-3 py-2.5 text-xs">
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold text-foreground">
                {t("listening.extraAddTitle").replace("{level}", level)}
              </p>
              {extras > 0 && (
                <span className="tabular-nums text-muted-foreground">
                  {t("listening.extraBreakdown")
                    .replace("{base}", String(baseTotal))
                    .replace("{extras}", String(extras))}
                </span>
              )}
            </div>
            <p className="leading-relaxed text-muted-foreground">
              {t("listening.extraHonestNote")}
            </p>
            {jobRunning ? (
              <p
                role="status"
                aria-live="polite"
                className="flex items-center gap-2 text-warning"
              >
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                {t("listening.extraGenerating")}
              </p>
            ) : jobDone ? (
              <p className="text-success">
                {t("listening.extraDone")
                  .replace("{added}", String(extrasJob.added.length))
                  .replace("{level}", level)}
              </p>
            ) : jobError ? (
              <p className="text-destructive">
                {t("listening.extraError").replace("{error}", jobError)}
              </p>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">
                  {t("listening.extraAddLabel")}
                </span>
                {EXTRAS_AMOUNTS.map((amount) => (
                  <Button
                    key={amount}
                    type="button"
                    variant="outline"
                    className="min-h-8 gap-1 px-2.5 text-xs"
                    onClick={() => onAddExtras(level, amount)}
                    disabled={disabled}
                  >
                    <Plus className="size-3.5" aria-hidden="true" />
                    {t("listening.extraAddCta").replace(
                      "{count}",
                      String(amount),
                    )}
                  </Button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {groups.map((group) => {
        const isOpen = open === group.state;
        return (
          <div
            key={group.state}
            className="overflow-hidden rounded-lg border border-border"
          >
            <button
              type="button"
              onClick={() => setOpen(isOpen ? "failed" : group.state)}
              aria-expanded={isOpen}
              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs font-semibold text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              <span>{group.label}</span>
              <ChevronDown
                className={cn(
                  "size-3.5 shrink-0 text-muted-foreground transition-transform",
                  isOpen && "rotate-180",
                )}
                aria-hidden="true"
              />
            </button>
            {isOpen && (
              <ul
                className="flex max-h-64 flex-col gap-1 overflow-y-auto border-t border-border px-2 py-1.5"
                aria-label={group.label}
              >
                {group.items.length === 0 ? (
                  <li className="px-2 py-1 text-xs text-muted-foreground">
                    {t("listening.levelItemsEmpty")}
                  </li>
                ) : (
                  group.items.map((item) => (
                    <ListeningItemRow key={item.question_id} item={item} />
                  ))
                )}
              </ul>
            )}
          </div>
        );
      })}

      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <Button
          type="button"
          className="min-h-9"
          onClick={() => onDrillFailed(level, failedIds)}
          disabled={disabled || data.failed === 0}
        >
          {t("listening.repeatFailed").replace(
            "{count}",
            String(data.failed),
          )}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="min-h-9"
          onClick={() => onReviewLearned(level, data.mastered)}
          disabled={disabled || data.mastered === 0}
        >
          {t("listening.reviewLearned").replace(
            "{count}",
            String(data.mastered),
          )}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="min-h-9"
          onClick={() => onPracticeLevel(level, data.total)}
          disabled={disabled}
        >
          {data.completed
            ? t("listening.reviewLevel").replace("{level}", level)
            : t("listening.practiceLevel").replace("{level}", level)}
        </Button>
      </div>
    </div>
  );
}

function ListeningItemRow({ item }: { item: ListeningItem }) {
  const { t } = useI18n();
  const phrase = usePhraseTranslation(item.script);
  return (
    <li className="flex items-start justify-between gap-3 rounded-md px-2 py-1.5 hover:bg-accent/60">
      <div className="min-w-0 flex-1">
        <p
          className="text-xs leading-relaxed text-foreground"
          lang={phrase.isSpanish ? "es" : "en"}
        >
          {phrase.display}
        </p>
        <p className="mt-0.5 flex flex-wrap gap-x-2 text-[10px] uppercase tracking-wide text-muted-foreground">
          {item.source === "generated" && (
            <span className="font-semibold normal-case tracking-normal text-warning">
              {t("listening.generatedTag")}
            </span>
          )}
          {item.topic && <span>{item.topic.replace(/_/g, " ")}</span>}
          {item.difficulty > 0 && (
            <span>
              {t("listening.levelItemsDifficulty")}: {item.difficulty}
            </span>
          )}
          {item.attempts > 0 && (
            <span>
              {t("listening.levelItemsAttempts")}: {item.attempts}
            </span>
          )}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <PhraseTranslateButton state={phrase} />
        <ListenButton text={item.script} label={t("speak.phrase")} />
      </div>
    </li>
  );
}
