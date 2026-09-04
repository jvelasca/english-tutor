import { useEffect, useState } from "react";
import { Check, Download, Loader2 } from "lucide-react";
import { downloadVoice, getVoices } from "../api/voices";
import { saveSettings } from "../api/settings";
import { useI18n } from "../hooks/useI18n";
import type { VoicesResponse } from "../types/api";
import { cn } from "../lib/utils";

/**
 * Configuración → Voces: catálogo de voces Piper instaladas, selección por
 * usuario (`tts_voice`) y descarga de voces del catálogo curado desde la propia
 * UI (servidas por `backend/services/voice_downloads.py`). Al cambiar de voz,
 * los audios de listening sin audio humano se regeneran bajo demanda con la
 * nueva voz (y quedan en caché).
 */
export function VoicesPanel({ userId }: { userId: string | null }) {
  const { t } = useI18n();
  const [state, setState] = useState<"loading" | "error" | "done">("loading");
  const [data, setData] = useState<VoicesResponse | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [saveError, setSaveError] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  async function refresh(): Promise<VoicesResponse> {
    const res = await getVoices(userId);
    setData(res);
    return res;
  }

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

  async function download(voiceId: string) {
    if (downloadingId) return;
    setDownloadingId(voiceId);
    setDownloadError(null);
    try {
      await downloadVoice(voiceId);
      await refresh();
    } catch (e) {
      setDownloadError((e as Error).message);
    } finally {
      setDownloadingId(null);
    }
  }

  const nameOf = (id: string) =>
    data?.voices.find((v) => v.id === id)?.name ?? id;
  const installed = data?.voices ?? [];

  return (
    <div className="flex flex-col gap-5">
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

        {state === "done" && data && installed.length === 0 && (
          <div className="flex flex-col gap-1.5">
            <p className="text-sm font-medium text-foreground">
              {t("voices.empty.title")}
            </p>
            <p className="whitespace-pre-line text-xs leading-relaxed text-muted-foreground">
              {t("voices.empty.hint")}
            </p>
          </div>
        )}

        {state === "done" && data && installed.length > 0 && (
          <ul className="flex list-none flex-col gap-2 p-0" role="radiogroup" aria-label={t("settings.voices")}>
            {installed.map((v) => {
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
                      {active && <span className="size-2 rounded-full bg-primary" />}
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

      {/* Descarga de voces del catálogo curado (configuradas por el backend). */}
      {state === "done" && data && (
        <div className="field border-t border-border pt-4">
          <span className="field-label">{t("voices.download.title")}</span>
          <p className="mb-3 text-[11px] leading-relaxed text-muted-foreground">
            {t("voices.download.hint")}
          </p>

          {data.downloadable.length === 0 ? (
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Check className="size-3.5 text-success" aria-hidden="true" />
              {t("voices.download.allInstalled")}
            </p>
          ) : (
            <ul className="flex list-none flex-col gap-2 p-0">
              {data.downloadable.map((v) => {
                const busy = downloadingId === v.id;
                return (
                  <li
                    key={v.id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2.5"
                  >
                    <span className="flex min-w-0 flex-col">
                      <span className="text-sm font-semibold text-foreground">
                        {v.name}
                      </span>
                      <span className="font-mono text-[11px] text-muted-foreground">
                        {v.id} · {t("voices.download.size").replace("{mb}", String(v.size_mb))}
                      </span>
                    </span>
                    <button
                      type="button"
                      disabled={!!downloadingId}
                      onClick={() => void download(v.id)}
                      className="dialog-secondary flex shrink-0 items-center gap-1.5 px-3 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {busy ? (
                        <>
                          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                          {t("voices.download.loading")}
                        </>
                      ) : (
                        <>
                          <Download className="size-3.5" aria-hidden="true" />
                          {t("voices.download.button")}
                        </>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          {downloadError && (
            <p className="mt-2 text-xs text-destructive">{downloadError}</p>
          )}
        </div>
      )}
    </div>
  );
}
