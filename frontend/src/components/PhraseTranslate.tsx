import { useEffect, useRef, useState } from "react";
import { Languages, Loader2 } from "lucide-react";
import { translateText } from "../api/translate";
import { useI18n } from "../hooks/useI18n";
import { cn } from "../lib/utils";

export interface PhraseTranslate {
  /** Texto original en inglés de la frase. */
  text: string;
  /** Texto a mostrar: la traducción si está activa, el original si no. */
  display: string;
  /** `true` cuando la frase se muestra traducida al español. */
  isSpanish: boolean;
  loading: boolean;
  /** La última traducción falló (modelo local no disponible); se autoclear. */
  failed: boolean;
  /** Alterna ES ⇄ EN. Al cargar una frase nueva siempre se vuelve al inglés. */
  toggle: () => void;
}

/**
 * Traducción de apoyo EN→ES a demanda (listening). No registra evidencia ni
 * cuenta como intento: es una consulta puntual que hace el alumno solo cuando
 * duda. Estado por frase: cuando cambia el texto o el `resetKey` (p. ej. el id
 * de la pregunta) se resetea y se vuelve a mostrar el inglés.
 */
export function usePhraseTranslation(
  text: string,
  resetKey?: string,
): PhraseTranslate {
  const [showEs, setShowEs] = useState(false);
  const [translation, setTranslation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  // Generación de la frase: descarta respuestas del LLM obsoletas si el texto
  // cambia (nueva pregunta) mientras una traducción estaba en curso.
  const generation = useRef(0);
  const failTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const token = resetKey ?? text;

  // Nueva frase o ítem → siempre se empieza mostrando el inglés.
  useEffect(() => {
    generation.current += 1;
    setShowEs(false);
    setTranslation(null);
    setLoading(false);
    setFailed(false);
    if (failTimer.current) {
      clearTimeout(failTimer.current);
      failTimer.current = null;
    }
  }, [token]);

  useEffect(
    () => () => {
      if (failTimer.current) clearTimeout(failTimer.current);
    },
    [],
  );

  async function toggle() {
    const source = text.trim();
    if (!source || loading) return;
    if (showEs) {
      setShowEs(false);
      return;
    }
    if (translation) {
      setShowEs(true);
      return;
    }

    const gen = generation.current;
    setLoading(true);
    setFailed(false);
    try {
      const es = await translateText(source);
      if (gen !== generation.current) return;
      setTranslation(es);
      setShowEs(true);
    } catch {
      if (gen !== generation.current) return;
      setFailed(true);
      failTimer.current = setTimeout(() => {
        setFailed(false);
        failTimer.current = null;
      }, 5000);
    } finally {
      if (gen === generation.current) setLoading(false);
    }
  }

  return {
    text,
    display: showEs && translation ? translation : text,
    isSpanish: showEs && translation !== null,
    loading,
    failed,
    toggle,
  };
}

interface PhraseTranslateButtonProps {
  state: PhraseTranslate;
  className?: string;
}

/**
 * Botón "ES" circular junto al altavoz de un texto: alterna entre mostrar la
 * frase en inglés y su traducción al español. Si el modelo local no está
 * disponible, muestra un aviso transitorio y nunca rompe el flujo.
 */
export function PhraseTranslateButton({
  state,
  className,
}: PhraseTranslateButtonProps) {
  const { t } = useI18n();
  const title = state.isSpanish
    ? t("translate.showEn")
    : state.failed
      ? t("translate.unavailable")
      : t("translate.showEs");

  return (
    <span className="relative inline-flex flex-col items-center">
      <button
        type="button"
        onClick={state.toggle}
        disabled={!state.text.trim() || state.loading}
        aria-label={title}
        aria-pressed={state.isSpanish}
        title={title}
        className={cn(
          "grid size-8 shrink-0 place-items-center rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-60",
          state.isSpanish
            ? "border-transparent bg-primary text-primary-foreground hover:bg-primary/90"
            : "border-border bg-secondary text-secondary-foreground hover:border-primary/50 hover:text-foreground",
          className,
        )}
      >
        {state.loading ? (
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        ) : (
          <Languages className="size-4" aria-hidden="true" />
        )}
      </button>
      {state.failed && (
        <span
          role="status"
          className="mt-1 max-w-36 text-center text-[10px] leading-tight text-warning"
        >
          {t("translate.unavailable")}
        </span>
      )}
    </span>
  );
}
