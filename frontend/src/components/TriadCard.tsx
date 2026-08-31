import { useEffect, useState } from "react";
import { getDashboard } from "../api/academy";
import type { Dashboard } from "../types/api";
import { useI18n } from "../hooks/useI18n";
import { Card } from "./ui/card";

interface TriadCardProps {
  userId: string | null;
  refreshKey?: number;
}

/**
 * Tríada Progress / Mastery / Readiness (V2.2).
 *
 * Fuente única (`GET /api/academy/dashboard`) reutilizada por Home/Progress/Course
 * para que las tres métricas sean consistentes en toda la aplicación.
 */
export function TriadCard({ userId, refreshKey = 0 }: TriadCardProps) {
  const { t } = useI18n();
  const [data, setData] = useState<Dashboard | null>(null);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    void (async () => {
      try {
        const d = await getDashboard(userId);
        if (!cancelled) setData(d);
      } catch {
        /* backend no disponible */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey]);

  if (!data) return null;
  const band = data.readiness.band;

  return (
    <Card className="gap-0 p-0">
      <div className="grid grid-cols-3 divide-x divide-border">
        <TriadStat
          label={t("triad.progress")}
          value={`${Math.round(data.progress)}%`}
          hint={t("triad.progressHint")}
        />
        <TriadStat
          label={t("triad.mastery")}
          value={`${Math.round(data.mastery)}%`}
          hint={t("triad.masteryHint")}
        />
        <TriadStat
          label={t("triad.readiness")}
          value={`${Math.round(data.readiness.overall)}%`}
          hint={t(`readiness.${band}`)}
        />
      </div>
    </Card>
  );
}

function TriadStat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="flex flex-col items-center gap-1 px-3 py-4">
      <span className="text-2xl font-bold tabular-nums">{value}</span>
      <span className="text-xs font-medium">{label}</span>
      <span className="text-[11px] text-muted-foreground">{hint}</span>
    </div>
  );
}
