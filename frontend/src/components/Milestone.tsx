import { useState } from "react";
import { Check, ChevronDown, Circle, CircleDot } from "lucide-react";
import type { CurriculumObjective } from "../types/api";
import { useI18n } from "../hooks/useI18n";
import { cn } from "@/lib/utils";
import { ObjectiveNodeCard } from "./ObjectiveNodeCard";

interface MilestoneProps {
  objective: CurriculumObjective;
  /** Con userId el hito abre el detalle de can-do (V3.17, D2) bajo demanda. */
  userId?: string;
  levelId?: string;
}

/**
 * Hito de un objetivo dentro de un nivel CEFR. Representa visualmente el estado
 * `mastered` (✓), `available`/`review` (●) y `locked` (○) con iconos de
 * lucide-react en lugar de caracteres.

 * En el curso (userId presente) la fila es expansible: al desplegarla consume
 * `getEvidenceGraphNode` vía `ObjectiveNodeCard` para mostrar el detalle del
 * can-do con su nodo del Evidence Graph (D2).
 */
export function Milestone({ objective, userId, levelId }: MilestoneProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const isMastered = objective.status === "mastered";
  const isInProgress =
    objective.status === "available" || objective.status === "review";
  const Icon = isMastered ? Check : isInProgress ? CircleDot : Circle;

  const label = isMastered
    ? t("course.completed")
    : isInProgress
      ? t("course.inProgress")
      : t("course.locked");

  const expandable = Boolean(userId);
  const row = (
    <>
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
      {expandable && (
        <ChevronDown
          className={cn(
            "size-4 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
          aria-hidden="true"
        />
      )}
    </>
  );

  return (
    <div className="overflow-hidden rounded-lg border border-border/60">
      {expandable ? (
        <button
          type="button"
          aria-expanded={open}
          aria-controls={`objective-node-${objective.id}`}
          onClick={() => setOpen((cur) => !cur)}
          className={cn(
            "flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-accent/40",
            objective.status === "locked" && "opacity-60",
          )}
        >
          {row}
        </button>
      ) : (
        <div
          className={cn(
            "flex items-center gap-3 px-3 py-2.5",
            objective.status === "locked" && "opacity-60",
          )}
        >
          {row}
        </div>
      )}
      {open && userId && (
        <div
          id={`objective-node-${objective.id}`}
          className="border-t border-dashed border-border bg-muted/20 p-2"
        >
          <ObjectiveNodeCard
            userId={userId}
            objectiveId={objective.id}
            levelId={levelId}
          />
        </div>
      )}
    </div>
  );
}
