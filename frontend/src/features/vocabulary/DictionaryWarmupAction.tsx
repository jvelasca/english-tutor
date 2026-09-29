import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { LoadingNotice } from "../../components/LoadingNotice";
import { useI18n } from "../../hooks/useI18n";
import {
  getDictionaryWarmupJob,
  startDictionaryWarmup,
} from "../../api/vocabulary";
import type { DictionaryWarmupJob } from "../../types/api";

/**
 * Cada cuánto se pregunta por el trabajo. El trabajo avanza de palabra en
 * palabra (cada una puede tardar decenas de segundos con el modelo local en
 * CPU), así que este intervalo solo decide con qué frecuencia se refresca la
 * cifra; no es una llamada al modelo.
 */
const POLL_MS = 1500;

type WarmupState = "idle" | "running" | "done" | "error";

/**
 * Precalentado del diccionario del alumno (V3.88.0).
 *
 * La PRIMERA consulta de una palabra sin caché paga la generación del modelo
 * local. Este bloque convierte ese coste en algo que el alumno puede adelantar
 * cuando le conviene: arranca el trabajo de fondo del backend, muestra el
 * progreso con `LoadingNotice` (spinner → reloj si se alarga) y declara el
 * resultado real (`prepared`/`skipped`), sin prometer que todo se pudo preparar.
 *
 * No es contenido nuevo: el backend reutiliza el camino de la consulta
 * (single-flight + cuotas), así que precalentar no genera nada que una búsqueda
 * no generaría, solo antes.
 */
export function DictionaryWarmupAction({ userId }: { userId: string | null }) {
  const { t } = useI18n();
  const [state, setState] = useState<WarmupState>("idle");
  const [job, setJob] = useState<DictionaryWarmupJob | null>(null);
  const timer = useRef<number | null>(null);
  const alive = useRef(true);

  const stopPolling = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    return () => {
      // El trabajo sigue en el backend (y su resultado es la caché global); lo
      // que se detiene es el polling de esta pestaña, que ya no existe.
      alive.current = false;
      stopPolling();
    };
  }, [stopPolling]);

  const poll = useCallback(
    (jobId: string) => {
      stopPolling();
      timer.current = window.setTimeout(() => {
        void (async () => {
          try {
            const next = await getDictionaryWarmupJob(userId ?? "", jobId);
            if (!alive.current) return;
            setJob(next);
            if (next.status === "running") {
              poll(jobId);
            } else {
              setState(next.status === "error" ? "error" : "done");
            }
          } catch {
            if (!alive.current) return;
            setState("error");
          }
        })();
      }, POLL_MS);
    },
    [stopPolling, userId],
  );

  const start = useCallback(async () => {
    if (!userId || state === "running") return;
    stopPolling();
    setState("running");
    setJob(null);
    try {
      const started = await startDictionaryWarmup(userId);
      if (!alive.current) return;
      setJob(started);
      if (started.status === "running") {
        poll(started.id);
      } else {
        // Sin nada que preparar el backend ya lo declara terminado.
        setState("done");
      }
    } catch {
      if (!alive.current) return;
      setState("error");
    }
  }, [poll, state, stopPolling, userId]);

  if (!userId) return null;

  const prepared = job?.prepared ?? 0;
  const skipped = job?.skipped ?? 0;
  const total = job?.total ?? 0;

  return (
    <Card className="gap-2 p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {t("dictionary.warmup.title")}
      </h2>
      <p className="text-[11px] leading-relaxed text-muted-foreground">
        {t("dictionary.warmup.hint")}
      </p>

      {state === "running" ? (
        <>
          <LoadingNotice label={t("dictionary.warmup.running")} />
          {total > 0 ? (
            <p className="text-[11px] tabular-nums text-muted-foreground">
              {t("dictionary.warmup.progress")
                .replace("{done}", String(prepared + skipped))
                .replace("{total}", String(total))}
            </p>
          ) : null}
        </>
      ) : null}

      {state === "done" ? (
        <p
          role="status"
          aria-live="polite"
          className="text-[11px] leading-relaxed text-muted-foreground"
        >
          {total === 0
            ? t("dictionary.warmup.nothing")
            : t("dictionary.warmup.done")
                .replace("{prepared}", String(prepared))
                .replace("{skipped}", String(skipped))}
        </p>
      ) : null}

      {state === "error" ? (
        <p role="alert" className="text-[11px] text-destructive">
          {t("dictionary.warmup.error")}
        </p>
      ) : null}

      <Button
        type="button"
        size="sm"
        variant="outline"
        className="w-fit"
        disabled={state === "running"}
        onClick={() => void start()}
      >
        {t("dictionary.warmup.cta")}
      </Button>
    </Card>
  );
}
