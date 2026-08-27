import { Check, Circle, CircleDot } from "lucide-react";
import type { CurriculumObjective } from "../types/api";
import { useI18n } from "../hooks/useI18n";
import { cn } from "@/lib/utils";

/**
 * Hito de un objetivo dentro de un nivel CEFR. Representa visualmente el estado
 * `mastered` (✓), `available`/`review` (●) y `locked` (○) con iconos de
 * lucide-react en lugar de caracteres.
 */
export function Milestone({ objective }: { objective: CurriculumObjective }) {
  const { t } = useI18n();
  const isMastered = objective.status === "mastered";
  const isInProgress =
    objective.status === "available" || objective.status === "review";
  const Icon = isMastered ? Check : isInProgress ? CircleDot : Circle;

  const label = isMastered
    ? t("course.completed")
    : isInProgress
      ? t("course.inProgress")
      : t("course.locked");

  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-lg border border-border/60 px-3 py-2.5",
        objective.status === "locked" && "opacity-60",
      )}
    >
      <span
        className={cn(
          "grid size-6 shrink-0 place-items-center",
          isMastered
            ? "text-success"
            : isInProgress
              ? "text-primary"
              : "text-muted-foreground",
        )}
      >
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <div className="flex min-w-0 flex-1 items-center justify-between gap-3">
        <span
          className={cn(
            "min-w-0 truncate text-sm",
            isMastered
              ? "text-muted-foreground line-through"
              : "text-foreground",
          )}
        >
          {objective.can_do}
        </span>
        <span
          className={cn(
            "shrink-0 text-xs font-medium",
            isMastered
              ? "text-success"
              : isInProgress
                ? "text-primary"
                : "text-muted-foreground",
          )}
        >
          {label}
        </span>
      </div>
    </div>
  );
}
