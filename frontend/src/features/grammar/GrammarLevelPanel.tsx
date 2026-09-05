import { useEffect, useState } from "react";
import { Award, ChevronDown, GraduationCap, Loader2 } from "lucide-react";
import { getGrammarLevelItems } from "../../api/grammarRoutes";
import type {
  GrammarItem,
  GrammarItemState,
  GrammarLevelItems,
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { cn } from "../../lib/utils";

const GROUPS: GrammarItemState[] = ["failed", "mastered", "unseen"];

function groupKey(state: GrammarItemState): string {
  return `gramRoutes.levelStates.${state}`;
}

interface GrammarLevelPanelProps {
  userId: string | null;
  level: string;
  /** Sesión de práctica activa: no se pueden iniciar más sesiones. */
  disabled?: boolean;
  /** Contador que fuerza a recargar el panel (tras un intento). */
  refreshNonce?: number;
  onPracticeLevel: (level: string, total: number) => void;
  onDrillFailed: (level: string, failedIds: string[]) => void;
  /** Repasar lo aprendido: rotación solo por los checks ya acertados. */
  onReviewLearned: (level: string, total: number) => void;
  /** Abre el instrumento formal ("demostrar el nivel" con examen/escalera). */
  onDemonstrate: (level: string) => void;
}

/**
 * Historial por check de un nivel (control del alumno). Al desplegar el donut de
 * un nivel muestra sus preguntas agrupadas en falladas / dominadas / sin ver,
 * cada una con su enunciado, y ofrece repetir las falladas hasta acertarlas,
 * repasar lo aprendido (solo dominadas) o practicar/repasar el nivel completo.
 * La ruta es práctica: demostrar el nivel exige los exámenes y la escalera de
 * evaluaciones formales del curso, nunca esta ruta.
 */
export function GrammarLevelPanel({
  userId,
  level,
  disabled,
  refreshNonce,
  onPracticeLevel,
  onDrillFailed,
  onReviewLearned,
  onDemonstrate,
}: GrammarLevelPanelProps) {
  const { t } = useI18n();
  const [data, setData] = useState<GrammarLevelItems | null>(null);
  const [open, setOpen] = useState<GrammarItemState>("failed");
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setData(null);
    setError(false);
    const uid = userId;
    void (async () => {
      try {
        const items = await getGrammarLevelItems(uid, level);
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
        {t("gramRoutes.levelItemsError")}
      </p>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
        {t("gramRoutes.loading")}
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
    .map((i) => i.check_id);

  const gate = data.gate;
  const shortBank = !!gate?.short_bank;
  const showGate =
    !!gate && !gate.passed && gate.total > 0 && gate.mastered > 0;
  const pendingCert =
    gate && gate.total > 0
      ? !gate.passed && gate.mastered >= gate.total
      : data.mastered === data.total && data.total > 0;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <Badge variant="outline" className="gap-1">
            {data.total} {t("gramRoutes.levelItemsChecks")}
          </Badge>
          {shortBank && (
            <Badge variant="outline" className="border-warning/40 text-warning">
              {t("gramRoutes.shortBank")}
            </Badge>
          )}
          <span className="text-muted-foreground">
            {t("gramRoutes.levelItemsSummary")
              .replace("{mastered}", String(data.mastered))
              .replace("{failed}", String(data.failed))
              .replace("{unseen}", String(data.unseen))}
          </span>
        </div>
        {data.completed ? (
          <Badge className="gap-1">{t("gramRoutes.completedShort")}</Badge>
        ) : (
          pendingCert && (
            <Badge variant="outline" className="border-warning/40 text-warning">
              {t("gramRoutes.routePendingCert")}
            </Badge>
          )
        )}
      </div>

      {shortBank && (
        <div className="rounded-lg border border-warning/30 bg-warning/5 px-3 py-2.5 text-xs">
          <p className="font-medium text-warning">
            {t("gramRoutes.shortBankTitle").replace("{level}", level)}
          </p>
          <p className="mt-1 leading-relaxed text-muted-foreground">
            {t("gramRoutes.shortBankNote").replace("{total}", String(data.total))}
          </p>
        </div>
      )}

      {showGate && (
        <div className="rounded-lg border border-warning/30 bg-warning/5 px-3 py-2.5 text-xs">
          <p className="font-medium text-warning">
            {t("gramRoutes.routeGateIntro").replace("{level}", level)}
          </p>
          <p className="mt-1 leading-relaxed text-muted-foreground">
            {t("gramRoutes.routeGateLine")
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
                    {t("gramRoutes.levelItemsEmpty")}
                  </li>
                ) : (
                  group.items.map((item) => (
                    <GrammarItemRow key={item.check_id} item={item} />
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
          {t("gramRoutes.repeatFailed").replace("{count}", String(data.failed))}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="min-h-9"
          onClick={() => onReviewLearned(level, data.mastered)}
          disabled={disabled || data.mastered === 0}
        >
          {t("gramRoutes.reviewLearned").replace(
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
            ? t("gramRoutes.reviewLevel").replace("{level}", level)
            : t("gramRoutes.practiceLevel").replace("{level}", level)}
        </Button>
      </div>

      {/* Demostrar el nivel: la ruta es práctica; el examen certifica. */}
      <div className="flex flex-col gap-2 rounded-lg border border-primary/25 bg-primary/5 px-3 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-semibold text-foreground">
            {t("gramRoutes.demonstrateTitle").replace("{level}", level)}
          </p>
          <GraduationCap className="size-4 text-primary" aria-hidden="true" />
        </div>
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("gramRoutes.demonstrateNote").replace("{level}", level)}
        </p>
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t("gramRoutes.demonstrateFormal").replace("{level}", level)}
        </p>
        <div>
          <Button
            type="button"
            variant="outline"
            className="min-h-9 gap-2"
            onClick={() => onDemonstrate(level)}
            disabled={disabled}
          >
            <Award className="size-4" aria-hidden="true" />
            {t("gramRoutes.demonstrateCta")}
          </Button>
        </div>
      </div>
    </div>
  );
}

function GrammarItemRow({ item }: { item: GrammarItem }) {
  const { t } = useI18n();
  return (
    <li className="flex items-start justify-between gap-3 rounded-md px-2 py-1.5 hover:bg-accent/60">
      <div className="min-w-0 flex-1">
        <p className="text-xs leading-relaxed text-foreground" lang="en">
          {item.prompt}
        </p>
        <p className="mt-0.5 flex flex-wrap gap-x-2 text-[10px] uppercase tracking-wide text-muted-foreground">
          {item.topic && <span>{item.topic.replace(/_/g, " ")}</span>}
          {item.attempts > 0 && (
            <span>
              {t("gramRoutes.levelItemsAttempts")}: {item.attempts}
            </span>
          )}
        </p>
      </div>
    </li>
  );
}
