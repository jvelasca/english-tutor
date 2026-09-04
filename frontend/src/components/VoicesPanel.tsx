import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { getVoices } from "../api/voices";
import { saveSettings } from "../api/settings";
import { useI18n } from "../hooks/useI18n";
import type { VoicesResponse } from "../types/api";
import { cn } from "../lib/utils";

/**
 * Configuración → Voces: catálogo de voces Piper instaladas y selección por
 * usuario (`tts_voice`). Solo se ofrecen voces ya presentes en
 * `models/piper/` (no hay descarga desde la UI); el texto de ayuda explica cómo
 * añadir más. Al cambiar de voz, los audios de listening sin audio humano se
 * regeneran bajo demanda con la nueva voz (y quedan en caché).
 */
export function VoicesPanel({ userId }: { userId: string | null }) {
  const { t } = useI18n();
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [data, setData] = useState<VoicesResponse | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [saveError, setSaveError] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    void (async () => {
      try {
        const res = await getVoices(userId);
        if (cancelled) return;
        setData(res);
        setState("done");
      } catch {
        if (!cancelled) setState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, tick]);

  async function select(voiceId: string) {
    if (!userId || savingId) return;
    setSavingId(voiceId);
    setSaveError(false);
    try {
      await saveSettings(userId, { tts_voice: voiceId });
      // Devuelve el catálogo con la nueva selección resuelta por el backend.
      setData(await getVoices(userId));
    } catch {
      setSaveError(true);
    } finally {
      setSavingId(null);
    }
  }

  const nameOf = (id: string) =>
    data?.voices.find((v) => v.id === id)?.name ?? id;

  return (
    <div className="field">
      <span className="field-label">{t("settings.voices")}</span>

      {state === "loading" && (
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          {t("common.loading")}
        </p>
      )}

      {state === "error" && (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted-foreground">{t("home.unavailable")}</p>
          <button
            type="button"
            className="dialog-secondary self-start"
            onClick={() => setTick((n) => n + 1)}
          >
            {t("home.retry")}
          </button>
        </div>
      )}

      {state === "done" && data && data.voices.length > 0 && (
        <ul className="flex list-none flex-col gap-2 p-0" role="radiogroup" aria-label={t("settings.voices")}>
          {data.voices.map((v) => {
            const active = v.id === data.selected;
            const saving = savingId === v.id;
            return (
              <li key={v.id} className="flex">
                <button
                  type="button"
                  role="radio"
                  aria-checked={active}
                  disabled={!userId || savingId !== null}
                  onClick={() => void select(v.id)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors",
                    active
                      ? "border-primary/60 bg-primary/10"
                      : "border-border bg-card hover:border-primary/40",
                    "disabled:cursor-not-allowed disabled:opacity-70",
                  )}
                >
                  <span
                    className={cn(
                      "grid size-4 shrink-0 place-items-center rounded-full border",
                      active ? "border-primary" : "border-border",
                    )}
                    aria-hidden="true"
                  >
                    {active && (
                      <span className="size-2 rounded-full bg-primary" />
                    )}
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="flex flex-wrap items-center gap-2 text-sm font-semibold text-foreground">
                      {v.name}
                      {v.id === data.default && (
                        <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                          {t("voices.defaultBadge")}
                        </span>
                      )}
                    </span>
                    <span className="font-mono text-[11px] text-muted-foreground">
                      {v.id}
                    </span>
                  </span>
                  {saving && (
                    <Loader2 className="size-4 shrink-0 animate-spin text-muted-foreground" aria-hidden="true" />
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {state === "done" && data && data.voices.length === 0 && (
        <div className="flex flex-col gap-1.5">
          <p className="text-sm font-medium text-foreground">
            {t("voices.empty.title")}
          </p>
          <p className="whitespace-pre-line text-xs leading-relaxed text-muted-foreground">
            {t("voices.empty.hint")}
          </p>
        </div>
      )}

      {!userId && (
        <p className="mt-2 text-xs text-warning">{t("voices.selectProfile")}</p>
      )}

      {saveError && (
        <p className="mt-2 text-xs text-destructive">{t("voices.saveError")}</p>
      )}

      {data && (
        <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
          {t("voices.note").replace("{voice}", nameOf(data.selected))}
        </p>
      )}
    </div>
  );
}
