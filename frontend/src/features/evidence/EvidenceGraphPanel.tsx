import { useCallback, useEffect, useState } from "react";
import { getEvidenceGraph } from "../../api/academy";
import type { EvidenceGraph, EvidenceGraphNode } from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { Card } from "../../components/ui/card";
import { cn } from "../../lib/utils";

interface EvidenceGraphPanelProps {
  userId: string | null;
  levelId?: string;
}

function pct(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/**
 * Evidence Graph (V2.12): can-do → dimensiones → limiting factor.
 */
export function EvidenceGraphPanel({
  userId,
  levelId,
}: EvidenceGraphPanelProps) {
  const { t } = useI18n();
  const [graph, setGraph] = useState<EvidenceGraph | null>(null);
  const [selected, setSelected] = useState<EvidenceGraphNode | null>(null);

  const refresh = useCallback(async () => {
    if (!userId) return;
    try {
      const data = await getEvidenceGraph(userId, levelId);
      setGraph(data);
      setSelected(data.nodes[0] ?? null);
    } catch {
      /* backend no disponible */
    }
  }, [userId, levelId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!userId) return null;

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-base font-semibold">{t("evidenceGraph.title")}</h3>
        <p className="text-sm text-muted-foreground">
          {t("evidenceGraph.subtitle")}
        </p>
      </div>

      {graph && (
        <Card className="space-y-2 p-3 text-sm">
          <p>
            <span className="text-muted-foreground">
              {t("evidenceGraph.level")}:{" "}
            </span>
            {graph.level} · {t("evidenceGraph.avgMastery")}{" "}
            {pct(graph.average_mastery)}
          </p>
          <p>
            <span className="text-muted-foreground">
              {t("evidenceGraph.open")}:{" "}
            </span>
            {graph.open_count} · {t("evidenceGraph.mastered")}:{" "}
            {graph.mastered_count}
          </p>
          {graph.top_limiting_factor && (
            <p>
              <span className="text-muted-foreground">
                {t("evidenceGraph.topLimiting")}:{" "}
              </span>
              {graph.top_limiting_factor.id} (×{graph.top_limiting_factor.count})
            </p>
          )}
        </Card>
      )}

      {graph && graph.nodes.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {graph.nodes.slice(0, 12).map((node) => (
            <button
              key={node.objective_id}
              type="button"
              className={cn(
                "rounded-md border px-2 py-1 text-xs",
                selected?.objective_id === node.objective_id
                  ? "border-primary bg-primary/10"
                  : "border-border text-muted-foreground",
              )}
              onClick={() => setSelected(node)}
            >
              {node.title}
            </button>
          ))}
        </div>
      )}

      {selected && (
        <Card className="space-y-3 p-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {t("evidenceGraph.canDo")}
            </p>
            <p className="font-medium">{selected.can_do}</p>
            <p className="text-xs text-muted-foreground">
              {t("evidenceGraph.mastery")}: {pct(selected.mastery)}
            </p>
          </div>

          <ul className="space-y-1.5">
            {selected.dimensions.map((dim) => {
              const isLimit = selected.limiting_factor?.id === dim.id;
              return (
                <li
                  key={dim.id}
                  className={cn(
                    "flex items-center justify-between text-sm",
                    isLimit && "font-semibold text-amber-700 dark:text-amber-400",
                  )}
                >
                  <span>
                    {dim.id}
                    {dim.missing ? ` · ${t("evidenceGraph.missing")}` : ""}
                    {isLimit ? ` · ${t("evidenceGraph.limiting")}` : ""}
                  </span>
                  <span>{pct(dim.score)}</span>
                </li>
              );
            })}
          </ul>

          {selected.recommended_focus.dimension && (
            <p className="text-sm text-muted-foreground">
              {t("evidenceGraph.focus")}:{" "}
              <span className="font-medium text-foreground">
                {selected.recommended_focus.dimension} →{" "}
                {selected.recommended_focus.phase}
              </span>
            </p>
          )}
        </Card>
      )}

      {!graph && (
        <p className="text-sm text-muted-foreground">{t("evidenceGraph.empty")}</p>
      )}
    </div>
  );
}
