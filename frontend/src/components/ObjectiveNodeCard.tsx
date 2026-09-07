import { useEffect, useState } from "react";
import { Loader2, RotateCcw } from "lucide-react";
import { getEvidenceGraphNode } from "../api/academy";
import type { EvidenceGraphNode } from "../types/api";
import { useI18n } from "../hooks/useI18n";
import { dimensionLabel } from "../utils/learningLabels";
import { Card } from "./ui/card";
import { cn } from "@/lib/utils";

interface ObjectiveNodeCardProps {
  userId: string;
  objectiveId: string;
  levelId?: string;
}

function pct(score: number): string {
  return `${Math.round(score * 100)}%`;
}

type LoadState = "loading" | "error" | "empty" | "done";

/**
 * Detalle de nodo por can-do (V3.17, D2): "¿por qué está así este can-do?".
 *
 * Consume `GET /api/academy/evidence-graph/objective/{id}` (vía
 * `getEvidenceGraphNode`), el endpoint de nodo por objetivo, y lo pinta de
 * forma reutilizable: can-do, nivel y dominio, dimensiones con el factor
 * limitante resaltado y el foco recomendado. Se monta en el curso (por
 * objetivo de unidad, bajo demanda) y en el panel de Habilidades (perfil).
 *
 * V3.18 (D7.1, auditoría v3.17): distingue TRES salidas — `empty` cuando el
 * backend responde 404 / nodo no construible (copia tranquila de "sin datos"),
 * `error` cuando la petición falla de verdad (red/5xx; copia de error con
 * reintento) y el nodo propiamente. Nunca declara dominio: solo refleja lo que
 * el servidor puntúa. V3.18 (D5): las dimensiones se pintan con
 * `dimensionLabel` (inglés de inmersión), no con el id en crudo.
 */
export function ObjectiveNodeCard({
  userId,
  objectiveId,
  levelId,
}: ObjectiveNodeCardProps) {
  const { t } = useI18n();
  const [node, setNode] = useState<EvidenceGraphNode | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    setNode(null);
    void (async () => {
      try {
        const data = await getEvidenceGraphNode(userId, objectiveId, levelId);
        if (cancelled) return;
        setNode(data);
        setState(data ? "done" : "empty");
      } catch {
        if (!cancelled) setState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, objectiveId, levelId, attempt]);

  if (state === "loading") {
    return (
      <div
        role="status"
        aria-busy="true"
        aria-live="polite"
        className="flex items-center gap-2 p-4 text-sm text-muted-foreground"
      >
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        {t("common.loading")}
      </div>
    );
  }

  if (state === "empty") {
    return (
      <p className="rounded-lg border border-border/60 bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
        {t("evidenceGraph.empty")}
      </p>
    );
  }

  if (state === "error") {
    return (
      <div
        role="alert"
        className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-foreground"
      >
        <span>{t("evidenceGraph.error")}</span>
        <button
          type="button"
          onClick={() => setAttempt((n) => n + 1)}
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1 text-xs font-medium text-foreground"
        >
          <RotateCcw className="size-3" aria-hidden="true" />
          {t("common.retry")}
        </button>
      </div>
    );
  }

  // Guard de tipos: `state === "done"` garantiza nodo (se fija junto en la
  // petición), pero TypeScript no relaciona ambos estados.
  if (!node) return null;

  return (
    <Card className="space-y-3 p-4">
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          {t("evidenceGraph.canDo")}
        </p>
        <p className="font-medium">{node.can_do}</p>
        <p className="text-xs text-muted-foreground">
          {node.level} · {t("evidenceGraph.mastery")}: {pct(node.mastery)}
        </p>
      </div>

      <ul className="space-y-1.5">
        {node.dimensions.map((dim) => {
          const isLimit = node.limiting_factor?.id === dim.id;
          return (
            <li
              key={dim.id}
              className={cn(
                "flex items-center justify-between text-sm",
                isLimit && "font-semibold text-amber-700 dark:text-amber-400",
              )}
            >
              <span>
                {dimensionLabel(dim.id)}
                {dim.missing ? ` · ${t("evidenceGraph.missing")}` : ""}
                {isLimit ? ` · ${t("evidenceGraph.limiting")}` : ""}
              </span>
              <span>{pct(dim.score)}</span>
            </li>
          );
        })}
      </ul>

      {node.recommended_focus.dimension && (
        <p className="text-sm text-muted-foreground">
          {t("evidenceGraph.focus")}:{" "}
          <span className="font-medium text-foreground">
            {dimensionLabel(node.recommended_focus.dimension)} →{" "}
            {node.recommended_focus.phase}
          </span>
        </p>
      )}
    </Card>
  );
}
