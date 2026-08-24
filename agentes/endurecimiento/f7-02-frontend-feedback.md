# Subagente F7.2 — Frontend: feedback fonético en PronunciationPractice

## Rol
Programador frontend React + TypeScript (Vite + Vitest). Sin acceso a Git ni al backend.

## Objetivo
Mostrar en `PronunciationPractice.tsx` el **feedback fonético** que el backend ya devuelve
(implementado en F7.1): precisión por palabra, similitud fonética (Soundex) y el desglose por
palabra (correctas / omitidas / sustituidas / de más). Se añade una capa pura y testeada de
formateo (`utils/pronunciationFeedback.ts`) y se amplía el contrato en `types/api.ts`.

## Contexto (autocontenido)
- El backend ahora devuelve en `POST /api/pronunciation` un `PronunciationResponse` ampliado:
  `{ expected, heard, score, level, ok, word_accuracy, phonetic_score, breakdown }` con
  `breakdown = { correct: string[], missing: string[], extra: string[],
  substituted: {expected, heard}[], total: number }`.
- `frontend/src/types/api.ts`: `PronunciationLevel` y `PronunciationResponse` ya existen
  (LEERLO). Hay que ampliar `PronunciationResponse` y añadir `WordSubstitution` +
  `PronunciationBreakdown`.
- `frontend/src/api/pronunciation.ts` (LEERLO): `checkPronunciation(blob, expected, userId)` hace
  fetch y devuelve `PronunciationResponse`. NO necesita cambios.
- `frontend/src/components/PronunciationPractice.tsx` (LEERLO entero): hoy muestra, cuando hay
  `result`, un bloque `.pronunciation-result` con `score`, `expected`, `heard` y `nivel`.
- `frontend/src/utils/progress.ts`: ya existe `pronunciationLevelLabel` (NO lo toques).
- Tests: vitest con `describe/it/expect` (ver `frontend/src/utils/progress.test.ts`). No hay
  infra de tests de componentes (solo `api/` y `utils/`), así que los tests de F7.2 cubren la
  capa pura `utils/pronunciationFeedback.ts`.
- `frontend/src/index.css`: tokens en `:root` (`--color-*`, `--space-*`, `--text-*`,
  `--radius-*`); tema claro en `:root[data-theme="light"]`; breakpoint móvil
  `@media (max-width: 768px)` al final (`.pronunciation { padding: var(--space-4); }` ya está).
- `tsconfig.json` tiene `strict`, `noUnusedLocals`, `noUnusedParameters`: no dejes imports ni
  variables sin usar.
- Verificación (desde `frontend/`):
  ```powershell
  npm test
  npx tsc --noEmit
  npm run build
  ```

## Tarea detallada

### 1. `frontend/src/types/api.ts` — ampliar el contrato
Sustituye el bloque actual de `PronunciationResponse`:

```typescript
export interface WordSubstitution {
  expected: string;
  heard: string;
}

export interface PronunciationBreakdown {
  correct: string[];
  missing: string[];
  extra: string[];
  substituted: WordSubstitution[];
  total: number;
}

export interface PronunciationResponse {
  expected: string;
  heard: string;
  score: number;
  level: PronunciationLevel;
  ok: boolean;
  word_accuracy: number;
  phonetic_score: number;
  breakdown: PronunciationBreakdown;
}
```

### 2. `frontend/src/utils/pronunciationFeedback.ts` (nuevo, puro)

```typescript
import type { PronunciationBreakdown } from "../types/api";

/** Une palabras en español: "a", "a y b", "a, b y c". */
export function joinWords(words: string[]): string {
  if (words.length === 0) return "";
  if (words.length === 1) return words[0];
  return `${words.slice(0, -1).join(", ")} y ${words[words.length - 1]}`;
}

/** Avisos de pronunciación: una frase por categoría con errores (sin errores → []). */
export function feedbackHints(breakdown: PronunciationBreakdown): string[] {
  const hints: string[] = [];
  if (breakdown.missing.length > 0) {
    hints.push(`Te faltó: ${joinWords(breakdown.missing)}`);
  }
  if (breakdown.substituted.length > 0) {
    const subs = breakdown.substituted.map((s) => `${s.expected} → ${s.heard}`);
    hints.push(`Sustituiste: ${subs.join(", ")}`);
  }
  if (breakdown.extra.length > 0) {
    hints.push(`Añadiste de más: ${joinWords(breakdown.extra)}`);
  }
  return hints;
}

/** Resumen de aciertos: "4 de 5 palabras correctas". */
export function wordsCorrectLabel(breakdown: PronunciationBreakdown): string {
  return `${breakdown.correct.length} de ${breakdown.total} palabras correctas`;
}
```

### 3. `frontend/src/components/PronunciationPractice.tsx` — mostrar el feedback
- Añade al import: `import { feedbackHints, wordsCorrectLabel } from "../utils/pronunciationFeedback";`
- Dentro del componente, tras los `useState`, añade el cálculo (si `result` existe):

```tsx
  const hints = result ? feedbackHints(result.breakdown) : [];
```

- Sustituye el bloque `{result && (...)}` actual por el siguiente (mantén la lógica de
  `recording`/`processing`/`toggle` intacta; solo cambia el bloque de render del resultado):

```tsx
      {result && (
        <div className={`pronunciation-result ${result.level}`}>
          <div className="score">{result.score}/100</div>
          <div className="lines">
            <div>
              <span className="label">Esperado:</span> {result.expected}
            </div>
            <div>
              <span className="label">Oído:</span> {result.heard}
            </div>
            <div>
              <span className="label">Nivel:</span>{" "}
              {result.level === "good"
                ? "Muy bien"
                : result.level === "fair"
                  ? "Aceptable"
                  : "Sigue practicando"}
            </div>
            <div>
              <span className="label">Precisión por palabra:</span>{" "}
              {result.word_accuracy}%
            </div>
            <div>
              <span className="label">Similitud fonética:</span>{" "}
              {result.phonetic_score}%
            </div>
          </div>
          <p className="pronunciation-words-label">
            {wordsCorrectLabel(result.breakdown)}
          </p>
          {hints.length > 0 && (
            <ul className="pronunciation-hints">
              {hints.map((hint) => (
                <li key={hint}>{hint}</li>
              ))}
            </ul>
          )}
        </div>
      )}
```

### 4. `frontend/src/index.css` — estilos (tokens + responsive)
Añade junto a los estilos de `.pronunciation` (busca `.pronunciation-result` y añade después):

```css
.pronunciation-words-label {
  margin: var(--space-2) 0 0;
  font-size: var(--text-sm);
  color: var(--color-text-dim);
}

.pronunciation-hints {
  margin: var(--space-2) 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.pronunciation-hints li {
  font-size: var(--text-sm);
  color: var(--color-text);
}
```

Usa los tokens existentes; no inventes nombres. No rompas el responsive: estos estilos son
fluidos y funcionan en móvil/tablet sin media queries adicionales.

### 5. Test `frontend/src/utils/pronunciationFeedback.test.ts` (nuevo, 9 tests)

```typescript
import { describe, expect, it } from "vitest";
import {
  feedbackHints,
  joinWords,
  wordsCorrectLabel,
} from "./pronunciationFeedback";
import type { PronunciationBreakdown } from "../types/api";

function breakdown(partial: Partial<PronunciationBreakdown>): PronunciationBreakdown {
  return {
    correct: [],
    missing: [],
    extra: [],
    substituted: [],
    total: 0,
    ...partial,
  };
}

describe("joinWords", () => {
  it("une en español", () => {
    expect(joinWords([])).toBe("");
    expect(joinWords(["world"])).toBe("world");
    expect(joinWords(["a", "b"])).toBe("a y b");
    expect(joinWords(["a", "b", "c"])).toBe("a, b y c");
  });
});

describe("feedbackHints", () => {
  it("detecta palabras omitidas", () => {
    expect(feedbackHints(breakdown({ missing: ["world"] }))).toEqual([
      "Te faltó: world",
    ]);
  });

  it("detecta sustituciones", () => {
    expect(
      feedbackHints(breakdown({ substituted: [{ expected: "have", heard: "am" }] })),
    ).toEqual(["Sustituiste: have → am"]);
  });

  it("detecta palabras de más", () => {
    expect(feedbackHints(breakdown({ extra: ["world"] }))).toEqual([
      "Añadiste de más: world",
    ]);
  });

  it("sin errores devuelve vacío", () => {
    expect(feedbackHints(breakdown({}))).toEqual([]);
  });
});

describe("wordsCorrectLabel", () => {
  it("resume aciertos", () => {
    expect(
      wordsCorrectLabel(breakdown({ correct: ["a", "b", "c", "d"], total: 5 })),
    ).toBe("4 de 5 palabras correctas");
  });
});
```

## Criterios de aceptación
- `npm test` **verde: 65 tests** (56 previos + 9 nuevos).
- `npx tsc --noEmit` **sin errores** (ojo con `strict`, `noUnusedLocals`, `noUnusedParameters`).
- `npm run build` **OK**.

## Restricciones
- NO tocar el backend.
- NO tocar `api/pronunciation.ts`, `utils/progress.ts`, `hooks/` ni otros componentes salvo
  `PronunciationPractice.tsx` (solo el bloque de render del resultado) y la creación de
  `utils/pronunciationFeedback.ts`.
- `components/` NO hace fetch (todo sigue igual: `checkPronunciation` ya está en `api/`).
- Mantener el estilo: español en textos de UI, tokens de diseño, a11y, estados vacíos.

## Salida
Lista de archivos creados/modificados (resumen por archivo), la salida de `npm test`, de
`npx tsc --noEmit`, de `npm run build`, y cualquier desviación.
