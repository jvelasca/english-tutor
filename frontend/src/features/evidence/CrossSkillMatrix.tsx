import { useEffect, useState } from "react";
import { Check, Loader2, Minus, Table2, X } from "lucide-react";
import { getCrossSkillMatrix } from "../../api/crossSkill";
import type {
  CrossSkillChannelKey,
  CrossSkillChannel,
  CrossSkillMatrix as CrossSkillMatrixData,
  CrossSkillStructure,
} from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { Badge } from "../../components/ui/badge";
import { cn } from "../../lib/utils";

const CHANNEL_ORDER: CrossSkillChannelKey[] = [
  "recognition",
  "production",
  "listening",
  "speaking",
  "transfer",
];

function CellSymbol({ cell }: { cell: CrossSkillChannel }) {
  const { t } = useI18n();
  if (cell.evidence > 0) {
    return (
      <span
        className="inline-flex items-center gap-1 text-success"
        aria-label={t("crossSkill.evidenceCount").replace(
          "{n}",
          String(cell.evidence),
        )}
        title={t("crossSkill.evidenceCount").replace(
          "{n}",
          String(cell.evidence),
        )}
      >
        <Check className="size-3.5" aria-hidden="true" />
        <span className="tabular-nums">{cell.evidence}</span>
      </span>
    );
  }
  if (cell.offered) {
    return (
      <X
        className="mx-auto size-3.5 text-muted-foreground/70"
        aria-label="✗"
      />
    );
  }
  return (
    <Minus className="mx-auto size-3.5 text-muted-foreground/30" aria-hidden="true" />
  );
}

function StructureRow({ structure }: { structure: CrossSkillStructure }) {
  const { t } = useI18n();
  return (
    <tr className="border-t border-border">
      <th
        scope="row"
        className="max-w-[220px] px-2 py-2 align-top text-left text-[11px] font-medium leading-snug text-foreground"
      >
        <span lang="en">{structure.name}</span>
        {structure.can_do && (
          <span
            className="mt-0.5 block text-[10px] font-normal leading-snug text-muted-foreground"
            lang="en"
          >
            {structure.can_do}
          </span>
        )}
      </th>
      {CHANNEL_ORDER.map((key) => {
        const label = t(`crossSkill.channel.${key}`);
        const cell = structure.channels[key];
        return (
          <td
            key={key}
            className="px-2 py-2 text-center"
            aria-label={`${label}: ${
              cell.evidence > 0 ? "✓" : cell.offered ? "✗" : "–"
            }`}
          >
            <CellSymbol cell={cell} />
          </td>
        );
      })}
    </tr>
  );
}

/**
 * Matriz cross-skill por estructura (V3.13, P1.2, solo lectura).
 *
 * Por cada estructura gramatical de B1 muestra qué instrumentos ofrece el
 * currículo por destreza y qué evidencia correcta acumula el usuario:
 *   ✓ n → evidencia correcta; ✗ → instrumento ofrecido, aún sin evidencia;
 *   –   → el currículo no expone la estructura a esa destreza.
 */
export function CrossSkillMatrix({
  userId,
  level,
}: {
  userId: string | null;
  level: string;
}) {
  const { t } = useI18n();
  const [data, setData] = useState<CrossSkillMatrixData | null>(null);
  const [error, setError] = useState(false);

  const levelId = level.toLowerCase();

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setData(null);
    setError(false);
    const uid = userId;
    void (async () => {
      try {
        const matrix = await getCrossSkillMatrix(uid, levelId);
        if (!cancelled) setData(matrix);
      } catch {
        if (!cancelled) setError(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, levelId]);

  return (
    <section className="flex flex-col gap-2 rounded-lg border border-border bg-card px-3 py-3">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
          <Table2 className="size-3.5 text-muted-foreground" aria-hidden="true" />
          {t("crossSkill.title")}
        </p>
        <Badge variant="outline" className="text-[10px]">
          {level.toUpperCase()}
        </Badge>
      </header>

      {error ? (
        <p className="text-xs text-muted-foreground">{t("crossSkill.error")}</p>
      ) : !data ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          {t("crossSkill.loading")}
        </div>
      ) : data.structures.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t("crossSkill.empty")}</p>
      ) : (
        <>
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {t("crossSkill.note")}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-xs">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  <th scope="col" className="px-2 py-1 text-left">
                    {t("crossSkill.structure")}
                  </th>
                  {CHANNEL_ORDER.map((key) => (
                    <th
                      key={key}
                      scope="col"
                      className={cn("px-2 py-1 text-center")}
                      title={t(`crossSkill.channel.${key}`)}
                    >
                      <span className="inline-flex items-center gap-1">
                        <span aria-hidden="true">
                          {key === "recognition"
                            ? "Rec"
                            : key === "production"
                              ? "Prod"
                              : key === "listening"
                                ? "Lis"
                                : key === "speaking"
                                  ? "Spe"
                                  : "Trf"}
                        </span>
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.structures.map((structure) => (
                  <StructureRow key={structure.structure_id} structure={structure} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {t("crossSkill.protoNote")}
          </p>
        </>
      )}
    </section>
  );
}
