/**
 * Peldaños PRESENTACIONALES de la escalera de micro-drill (V3.40, Fase 4).
 *
 * Extraídos de `wordDrill.tsx` (deuda de tamaño documentada) SIN cambiar el
 * contrato del drill: son componentes sin estado propio más allá de lo que el
 * padre controla. `WordDrill` sigue siendo el dueño del estado, de las llamadas
 * al servidor y de la puntuación (premisa 21); aquí solo vive el marcado de cada
 * peldaño, lo que permite añadir el paso Transfer y testear cada peldaño por
 * separado.
 *
 * El acierto de Recognition sigue siendo informativo (V3.13) y Recall sigue
 * siendo recuperación por texto (V3.34); Write (V3.39) y Transfer (V3.40) son
 * producción propia puntuada en servidor.
 */
import { Check, Loader2 } from "lucide-react";
import { motion } from "motion/react";

import { useI18n } from "../../hooks/useI18n";
import { cn } from "../../lib/utils";
import type {
  DrillRecallAttempt,
  DrillRecallPrompt,
  DrillRecognitionQuestion,
  DrillTransferContext,
} from "../../types/api";

/** Peldaño Recall (V3.34): recuperación por texto. Presentacional: el estado y
 * el scoring viven en `WordDrill` (el servidor puntúa, premisa 21). Sin
 * micrófono: el alumno escribe la palabra a partir del significado (cue). */
export interface RecallStepProps {
  prompt: DrillRecallPrompt | null;
  error: string | null;
  answer: string;
  onAnswerChange: (value: string) => void;
  outcome: DrillRecallAttempt | null;
  processing: boolean;
  onSubmit: () => void;
}

export function RecallStep({
  prompt,
  error,
  answer,
  onAnswerChange,
  outcome,
  processing,
  onSubmit,
}: RecallStepProps) {
  const { t } = useI18n();
  if (!prompt) {
    return error ? (
      <p className="text-xs text-destructive" role="alert">
        {error}
      </p>
    ) : (
      <Loader2
        className="size-4 animate-spin text-muted-foreground"
        aria-hidden="true"
      />
    );
  }
  if (!prompt.available) {
    return (
      <p className="text-xs text-muted-foreground">
        {t("dictionary.drill.recallUnavailable")}
      </p>
    );
  }
  const done = outcome !== null;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">
        {prompt.cue_kind
          ? t(`dictionary.drill.recallCue.${prompt.cue_kind}`)
          : t("dictionary.drill.recallPrompt")}
      </p>
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={answer}
          onChange={(e) => onAnswerChange(e.target.value)}
          disabled={processing || done}
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          lang="en"
          aria-label={t("dictionary.drill.recallInputLabel")}
          placeholder={t("dictionary.drill.recallPlaceholder")}
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground disabled:opacity-60"
        />
        <motion.button
          type="button"
          onClick={() => onSubmit()}
          disabled={!answer.trim() || processing || done}
          whileTap={processing ? undefined : { scale: 0.96 }}
          className="inline-flex shrink-0 items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          {processing ? (
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <Check className="size-4" aria-hidden="true" />
          )}
          {t("dictionary.drill.recallCheck")}
        </motion.button>
      </div>
    </div>
  );
}

/** Peldaño Recognition (V3.33): MCQ definición ↔ palabra. Informativo: el
 * acierto no acredita producción (V3.13), solo lo puntúa el servidor. */
export interface RecognitionStepProps {
  question: DrillRecognitionQuestion | null;
  error: string | null;
  selected: number | null;
  onSelect: (index: number) => void;
  disabled: boolean;
}

export function RecognitionStep({
  question,
  error,
  selected,
  onSelect,
  disabled,
}: RecognitionStepProps) {
  const { t } = useI18n();
  if (!question) {
    return error ? (
      <p className="text-xs text-destructive" role="alert">
        {error}
      </p>
    ) : (
      <Loader2
        className="size-4 animate-spin text-muted-foreground"
        aria-hidden="true"
      />
    );
  }
  if (!question.available) {
    return (
      <p className="text-xs text-muted-foreground">
        {t("dictionary.drill.recognitionUnavailable")}
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">
        {t("dictionary.drill.recognitionPrompt")}
      </p>
      <ul
        role="group"
        aria-label={t("dictionary.drill.recognitionPrompt")}
        className="flex flex-col gap-1.5"
      >
        {question.options.map((option, i) => (
          <li key={`${i}-${option}`}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onSelect(i)}
              aria-pressed={selected === i}
              className={cn(
                "w-full rounded-md border px-3 py-2 text-left text-sm transition-colors disabled:opacity-60",
                selected === i
                  ? "border-transparent bg-primary text-primary-foreground"
                  : "border-border bg-secondary text-secondary-foreground hover:border-primary/50 hover:text-foreground",
              )}
            >
              {option}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Escritura de una frase PROPIA (pasos Write de V3.39 y Transfer de V3.40).
 * La consigna la aporta el padre; aquí solo el área de texto y su nota de
 * longitud mínima. */
export interface ProductionTextareaProps {
  prompt: string;
  value: string;
  onValueChange: (value: string) => void;
  disabled: boolean;
  inputLabel: string;
  placeholder: string;
  minWordsNote: string;
  rows?: number;
}

export function ProductionTextarea({
  prompt,
  value,
  onValueChange,
  disabled,
  inputLabel,
  placeholder,
  minWordsNote,
  rows = 2,
}: ProductionTextareaProps) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">{prompt}</p>
      <textarea
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        disabled={disabled}
        rows={rows}
        autoComplete="off"
        spellCheck={false}
        lang="en"
        aria-label={inputLabel}
        placeholder={placeholder}
        className="w-full resize-none rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground disabled:opacity-60"
      />
      <p className="text-[11px] text-muted-foreground">{minWordsNote}</p>
    </div>
  );
}

/** Peldaño Transfer (V3.40): producción en un CONTEXTO NUEVO. A diferencia de
 * Write (frase libre), la consigna da un escenario servido por el backend; el
 * estado del intento lo controla `WordDrill`. */
export interface TransferStepProps {
  context: DrillTransferContext | null;
  error: string | null;
  answer: string;
  onAnswerChange: (value: string) => void;
  disabled: boolean;
  minWordsNote: string;
  inputLabel: string;
  placeholder: string;
}

// V3.46 (P1-03): etiqueta legible de la CONDICIÓN de recuperación servida. El
// servidor decide cuánta ayuda da la tarea (nombra la palabra, la insinúa o no
// la exige); la UI solo la explica.
const CONDITION_LABEL_KEYS: Record<string, string> = {
  prompted: "dictionary.drill.transferConditionPrompted",
  cued_context: "dictionary.drill.transferConditionCued",
  open_context: "dictionary.drill.transferConditionOpen",
  free_choice: "dictionary.drill.transferConditionFree",
  naturally_emergent: "dictionary.drill.transferConditionNatural",
};

export function TransferStep({
  context,
  error,
  answer,
  onAnswerChange,
  disabled,
  minWordsNote,
  inputLabel,
  placeholder,
}: TransferStepProps) {
  const { t } = useI18n();
  if (!context) {
    return error ? (
      <p className="text-xs text-destructive" role="alert">
        {error}
      </p>
    ) : (
      <Loader2
        className="size-4 animate-spin text-muted-foreground"
        aria-hidden="true"
      />
    );
  }
  if (!context.available) {
    return (
      <p className="text-xs text-muted-foreground">
        {t("dictionary.drill.transferUnavailable")}
      </p>
    );
  }
  const conditionKey = CONDITION_LABEL_KEYS[context.condition ?? ""];
  return (
    <div className="flex flex-col gap-2">
      {conditionKey && (
        <p className="text-[11px] text-muted-foreground">
          {t("dictionary.drill.transferConditionLabel")}: {t(conditionKey)}
        </p>
      )}
      <ProductionTextarea
        prompt={context.prompt}
        value={answer}
        onValueChange={onAnswerChange}
        disabled={disabled}
        inputLabel={inputLabel}
        placeholder={placeholder}
        minWordsNote={minWordsNote}
        rows={3}
      />
    </div>
  );
}
