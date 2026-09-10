import { useCallback, useEffect, useState } from "react";
import { ArrowRightLeft, Languages, Loader2, Trash2 } from "lucide-react";
import { translateText, type TranslateDirection } from "../../api/translate";
import type { VoiceLanguage } from "../../api/voz";
import { ListenButton } from "../../components/ListenButton";
import { MicButton } from "../../components/MicButton";
import { useI18n } from "../../hooks/useI18n";
import { cn } from "../../lib/utils";

/** Últimas frases traducidas que se recuerdan entre sesiones. */
export const HISTORY_STORAGE_KEY = "english-tutor.translator-history";
const HISTORY_LIMIT = 8;

interface HistoryItem {
  id: string;
  direction: TranslateDirection;
  source: string;
  target: string;
}

/** Idiomas de entrada y salida de cada dirección. */
function languagesFor(direction: TranslateDirection): {
  source: VoiceLanguage;
  target: VoiceLanguage;
} {
  return direction === "es-en"
    ? { source: "es", target: "en" }
    : { source: "en", target: "es" };
}

function isHistoryItem(value: unknown): value is HistoryItem {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.id === "string" &&
    (item.direction === "es-en" || item.direction === "en-es") &&
    typeof item.source === "string" &&
    typeof item.target === "string"
  );
}

function readHistory(): HistoryItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(HISTORY_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isHistoryItem).slice(0, HISTORY_LIMIT);
  } catch {
    return [];
  }
}

/**
 * Traductor de viaje (ruta `/traductor`, V3.39 Fase 2).
 *
 * Utilidad AUXILIAR bidireccional ES↔EN: se habla o escribe en el idioma de
 * origen y se lee/escucha la traducción en el destino. Por diseño es una ayuda
 * de apoyo: NO registra evidencia, no cuenta como intento y funciona sin
 * perfil (con perfil solo se aprovecha su voz del idioma si la tiene).
 *
 * El sentido vive en `direction` (`es-en` por defecto, el caso del viajero que
 * habla español) y el botón ⇄ intercambia sentido y textos. El historial
 * reciente se guarda en `localStorage` (últimas `HISTORY_LIMIT` frases) para
 * recuperar una consulta sin volver a dictarla.
 */
export function TranslatorScreen({ userId }: { userId: string | null }) {
  const { t } = useI18n();
  const [direction, setDirection] = useState<TranslateDirection>("es-en");
  const [sourceText, setSourceText] = useState("");
  const [targetText, setTargetText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>(readHistory);

  const { source: sourceLang, target: targetLang } = languagesFor(direction);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(
        HISTORY_STORAGE_KEY,
        JSON.stringify(history),
      );
    } catch {
      /* almacenamiento no disponible: el historial es best-effort */
    }
  }, [history]);

  const runTranslate = useCallback(
    async (rawText: string, dir: TranslateDirection) => {
      const text = rawText.trim();
      if (!text) return;
      setBusy(true);
      setError(null);
      try {
        const translation = await translateText(text, dir);
        setTargetText(translation);
        setHistory((prev) =>
          [
            {
              id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
              direction: dir,
              source: text,
              target: translation,
            },
            ...prev.filter(
              (item) => !(item.source === text && item.direction === dir),
            ),
          ].slice(0, HISTORY_LIMIT),
        );
      } catch (e) {
        setTargetText("");
        setError(`${t("translator.error")}${(e as Error).message}`);
      } finally {
        setBusy(false);
      }
    },
    [t],
  );

  function changeDirection(next: TranslateDirection) {
    if (next === direction) return;
    setDirection(next);
    setTargetText("");
    setError(null);
  }

  function swap() {
    const next: TranslateDirection = direction === "es-en" ? "en-es" : "es-en";
    setDirection(next);
    setSourceText(targetText);
    setTargetText(sourceText);
    setError(null);
  }

  function reuse(item: HistoryItem) {
    setDirection(item.direction);
    setSourceText(item.source);
    setTargetText(item.target);
    setError(null);
  }

  const DIRECTION_KEYS: Record<TranslateDirection, string> = {
    "es-en": "translator.direction.es-en",
    "en-es": "translator.direction.en-es",
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-6 sm:px-6">
        <header className="mb-4 flex flex-col gap-1.5">
          <h1 className="flex items-center gap-2 text-lg font-bold tracking-tight">
            <Languages className="size-5 text-primary" aria-hidden="true" />
            {t("translator.title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("translator.subtitle")}
          </p>
        </header>

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div
            role="group"
            aria-label={t("translator.directionLabel")}
            className="bg-secondary flex w-fit items-center gap-1 rounded-md p-1"
          >
            {(["es-en", "en-es"] as const).map((dir) => {
              const isActive = direction === dir;
              return (
                <button
                  key={dir}
                  type="button"
                  aria-pressed={isActive}
                  onClick={() => changeDirection(dir)}
                  className={cn(
                    "inline-flex min-h-9 items-center rounded px-3 text-xs font-semibold transition-colors",
                    isActive
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t(DIRECTION_KEYS[dir])}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            onClick={swap}
            aria-label={t("translator.swap")}
            title={t("translator.swap")}
            className="grid size-9 shrink-0 place-items-center rounded-full border border-border bg-secondary text-secondary-foreground transition-colors hover:border-primary/50 hover:text-foreground"
          >
            <ArrowRightLeft className="size-4" aria-hidden="true" />
          </button>
        </div>

        <section className="mb-4 flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              {t("translator.sourceLabel")}
            </h2>
            <div className="flex items-center gap-2">
              <ListenButton
                text={sourceText}
                label={t("translator.listenSource")}
                language={sourceLang}
                userId={userId}
              />
              <MicButton
                language={sourceLang}
                disabled={busy}
                onTranscribed={(text) => {
                  setSourceText(text);
                  void runTranslate(text, direction);
                }}
              />
            </div>
          </div>
          <textarea
            value={sourceText}
            onChange={(e) => setSourceText(e.target.value)}
            lang={sourceLang}
            rows={3}
            aria-label={t("translator.inputAria")}
            placeholder={t(`translator.placeholder.${direction}`)}
            className="w-full resize-none rounded-lg border border-border bg-card px-3 py-2 text-sm shadow-sm outline-none focus:border-primary/60"
          />
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => void runTranslate(sourceText, direction)}
              disabled={busy || sourceText.trim().length === 0}
              className="bg-primary text-primary-foreground inline-flex min-h-9 items-center gap-2 rounded-full px-4 text-sm font-semibold transition-opacity disabled:opacity-50"
            >
              {busy && (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              )}
              {busy ? t("translator.button.busy") : t("translator.button")}
            </button>
          </div>
        </section>

        <section
          data-testid="translator-output"
          className="border-border bg-card/60 flex min-h-28 flex-col gap-2 rounded-xl border p-3"
          aria-live="polite"
        >
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              {t("translator.targetLabel")}
            </h2>
            <ListenButton
              text={targetText}
              label={t("translator.listenTarget")}
              language={targetLang}
              userId={userId}
            />
          </div>
          {error ? (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          ) : targetText ? (
            <p lang={targetLang} className="text-base leading-relaxed">
              {targetText}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t("translator.empty")}
            </p>
          )}
        </section>

        <p className="mt-3 text-xs text-muted-foreground">
          <span className="border-border mr-1.5 rounded border px-1.5 py-0.5 font-semibold">
            {t("translator.notTracked")}
          </span>
          {t("translator.notTrackedHint")}
        </p>

        <section className="mt-6 flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              {t("translator.history.title")}
            </h2>
            {history.length > 0 && (
              <button
                type="button"
                onClick={() => setHistory([])}
                aria-label={t("translator.history.clear")}
                className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs font-semibold"
              >
                <Trash2 className="size-3.5" aria-hidden="true" />
                {t("translator.history.clear")}
              </button>
            )}
          </div>
          {history.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("translator.history.empty")}
            </p>
          ) : (
            <ul data-testid="translator-history" className="flex flex-col gap-1.5">
              {history.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => reuse(item)}
                    aria-label={t("translator.history.reuse").replace(
                      "{text}",
                      item.source,
                    )}
                    className="border-border bg-card hover:border-primary/40 flex w-full flex-col items-start gap-0.5 rounded-lg border px-3 py-2 text-left transition-colors"
                  >
                    <span
                      lang={languagesFor(item.direction).source}
                      className="text-xs text-muted-foreground"
                    >
                      {item.source}
                    </span>
                    <span
                      lang={languagesFor(item.direction).target}
                      className="text-sm"
                    >
                      {item.target}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
