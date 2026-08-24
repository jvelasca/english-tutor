# Subagente F8.4 — Frontend: CEFR + speaking (fluidez) + listening UI

## Rol
Programador frontend (React 19 + TypeScript + Vite + Vitest). Sin acceso a Git. NO toques el backend.

## Objetivo
Exponer en la UI los tres resultados de FASE 8 (ya implementados en el backend):
1. **CEFR multi-señal**: mostrar `cefr_bands` (bandas por destreza) y `cefr_descriptor` en `LearningProfile`.
2. **Speaking (fluidez)**: mostrar `fluency` (WPM) en `PronunciationPractice`.
3. **Listening**: nuevo componente `ListeningPractice` (escuchar con TTS + responder) y su cliente API.

## Contexto (autocontenido)
- El backend ya devuelve:
  - `GET /api/profile` → `LearningProfile` con `cefr_level`, **`cefr_bands`** (`{vocabulary, grammar, fluency, pronunciation}`, valores como "B1" o "—") y **`cefr_descriptor`** (string).
  - `POST /api/pronunciation` → `PronunciationResponse` con **`fluency`** (`{word_count, duration_seconds, wpm, level}`, `level` ∈ `"fluent"|"good"|"slow"|"—"`).
  - `GET /api/listening/question` → `ListeningQuestion` `{id, level, script, question, options}`.
  - `POST /api/listening/answer?user_id=…` body `{question_id, answer_index}` → `ListeningAnswerResponse` `{question_id, correct, correct_index, level}`.
  - `GET /api/listening/stats?user_id=…` → `ListeningStats` `{attempts, correct, accuracy}`.
- `frontend/src/api/voz.ts` ya exporta `speak(text: string): Promise<void>` (reproduce TTS vía `/api/tts`).
- Patrón API: `frontend/src/api/client.ts` exporta `getJson<T>(url)`, `postJson<T>(url, body)`.
- Patrón util puro + test: `utils/*.ts` + `utils/*.test.ts` (vitest). Estilo tests como `utils/cefr.test.ts`, `api/learning.test.ts`.
- `tsconfig.json` tiene `strict`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`. Evita variables/parámetros sin usar.
- Estilo visual: `index.css` usa design tokens (`var(--color-surface)`, `var(--color-border)`, `var(--color-accent)`, `var(--radius-md)`, `var(--space-*)`, `var(--text-*)`). Reutiliza las clases `.cefr-badge.basic/.intermediate/.advanced` como referencia de tonos.
- `App.tsx` ya renderiza `<ProgressDashboard>`, `<LearningProfile profile={profile} />` y, cuando `mode === "pronunciation"`, `<PronunciationPractice>`. `useChat` expone `currentUserId`, `refreshHistory`, `refreshEvents`.

## Verificación (desde `frontend/`)
```powershell
npm test
npm run build
```
`npm test` debe dar **74 tests** (65 previos + 9 nuevos). `npm run build` (tsc + vite build) debe compilar sin errores.

## Tarea detallada

### 1. `frontend/src/types/api.ts` — añadir/ampliar tipos

**(a)** En `PronunciationResponse`, añade el campo `fluency` y la interfaz `FluencyStats` justo antes:

```ts
export interface FluencyStats {
  word_count: number;
  duration_seconds: number | null;
  wpm: number | null;
  level: string;
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
  fluency: FluencyStats;
}
```

**(b)** Tras `export type CefrLevel = ...`, añade `CefrBands`:

```ts
export interface CefrBands {
  vocabulary: string;
  grammar: string;
  fluency: string;
  pronunciation: string;
}
```

**(c)** En `LearningProfile`, añade `cefr_bands` y `cefr_descriptor` justo después de `cefr_level`:

```ts
export interface LearningProfile {
  user_id: string;
  cefr_level: CefrLevel;
  cefr_bands: CefrBands;
  cefr_descriptor: string;
  vocabulary_size: number;
  // ... resto igual ...
}
```

**(d)** Al final del archivo (tras `ProgressHistory`), añade:

```ts
export interface ListeningQuestion {
  id: string;
  level: string;
  script: string;
  question: string;
  options: string[];
}

export interface ListeningAnswerResponse {
  question_id: string;
  correct: boolean;
  correct_index: number;
  level: string;
}

export interface ListeningStats {
  attempts: number;
  correct: number;
  accuracy: number | null;
}
```

### 2. `frontend/src/utils/cefr.ts` — añadir `bandLabel`
Añade al final:

```ts
export function bandLabel(skill: string): string {
  switch (skill) {
    case "vocabulary":
      return "Vocabulario";
    case "grammar":
      return "Gramática";
    case "fluency":
      return "Fluidez";
    case "pronunciation":
      return "Pronunciación";
    default:
      return skill;
  }
}
```

### 3. `frontend/src/utils/cefr.test.ts` — añadir tests de `bandLabel`
Actualiza el import a `import { bandLabel, cefrLabel, cefrTone } from "./cefr";` y añade:

```ts
describe("bandLabel", () => {
  it("mapea cada destreza a su etiqueta", () => {
    expect(bandLabel("vocabulary")).toBe("Vocabulario");
    expect(bandLabel("grammar")).toBe("Gramática");
    expect(bandLabel("fluency")).toBe("Fluidez");
    expect(bandLabel("pronunciation")).toBe("Pronunciación");
  });

  it("devuelve el valor crudo para destrezas desconocidas", () => {
    expect(bandLabel("writing")).toBe("writing");
  });
});
```

### 4. `frontend/src/utils/fluency.ts` (nuevo)

```ts
export function wpmLabel(wpm: number | null): string {
  return wpm === null ? "—" : `${Math.round(wpm)} palabras/min`;
}

export function fluencyLevelLabel(level: string): string {
  switch (level) {
    case "fluent":
      return "Fluido";
    case "good":
      return "Buen ritmo";
    case "slow":
      return "Lento";
    default:
      return "—";
  }
}
```

### 5. `frontend/src/utils/fluency.test.ts` (nuevo, 4 tests)

```ts
import { describe, expect, it } from "vitest";
import { fluencyLevelLabel, wpmLabel } from "./fluency";

describe("wpmLabel", () => {
  it("formatea las palabras por minuto", () => {
    expect(wpmLabel(60)).toBe("60 palabras/min");
    expect(wpmLabel(120.4)).toBe("120 palabras/min");
  });

  it("devuelve guion para null", () => {
    expect(wpmLabel(null)).toBe("—");
  });
});

describe("fluencyLevelLabel", () => {
  it("mapea cada nivel a su etiqueta", () => {
    expect(fluencyLevelLabel("fluent")).toBe("Fluido");
    expect(fluencyLevelLabel("good")).toBe("Buen ritmo");
    expect(fluencyLevelLabel("slow")).toBe("Lento");
  });

  it("devuelve guion para niveles desconocidos", () => {
    expect(fluencyLevelLabel("—")).toBe("—");
  });
});
```

### 6. `frontend/src/api/listening.ts` (nuevo)

```ts
import { getJson, postJson } from "./client";
import type {
  ListeningAnswerResponse,
  ListeningQuestion,
  ListeningStats,
} from "../types/api";

export function getListeningQuestion(userId: string): Promise<ListeningQuestion> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<ListeningQuestion>(`/api/listening/question?${query}`);
}

export function submitListeningAnswer(
  userId: string,
  questionId: string,
  answerIndex: number,
): Promise<ListeningAnswerResponse> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return postJson<ListeningAnswerResponse>(`/api/listening/answer?${query}`, {
    question_id: questionId,
    answer_index: answerIndex,
  });
}

export function getListeningStats(userId: string): Promise<ListeningStats> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<ListeningStats>(`/api/listening/stats?${query}`);
}
```

### 7. `frontend/src/api/listening.test.ts` (nuevo, 3 tests)

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getListeningQuestion,
  getListeningStats,
  submitListeningAnswer,
} from "./listening";

function mockFetch(ok: boolean, data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("listening api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getListeningQuestion llama con user_id en la query", async () => {
    const fn = mockFetch(true, {
      id: "l1",
      script: "Hi",
      question: "Q",
      options: ["a", "b"],
    });
    await getListeningQuestion("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/question?user_id=u1");
  });

  it("submitListeningAnswer envía question_id y answer_index", async () => {
    const fn = mockFetch(true, {
      question_id: "l1",
      correct: true,
      correct_index: 1,
      level: "A1",
    });
    await submitListeningAnswer("u1", "l1", 1);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/answer?user_id=u1");
    expect(JSON.parse(init.body as string)).toEqual({
      question_id: "l1",
      answer_index: 1,
    });
  });

  it("getListeningStats llama con user_id en la query", async () => {
    const fn = mockFetch(true, { attempts: 1, correct: 1, accuracy: 100 });
    await getListeningStats("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/stats?user_id=u1");
  });
});
```

### 8. `frontend/src/components/LearningProfile.tsx` — bandas + descriptor
- Cambia el import de `cefr` por:
  ```ts
  import { bandLabel, cefrLabel, cefrTone } from "../utils/cefr";
  ```
- Justo después del cierre `</header>` e inmediatamente ANTES de `<div className="learning-grid">`, inserta:

```tsx
      {profile.cefr_descriptor && (
        <p className="cefr-descriptor">{profile.cefr_descriptor}</p>
      )}

      <div className="cefr-bands">
        {(["vocabulary", "grammar", "fluency", "pronunciation"] as const).map(
          (skill) => (
            <span
              key={skill}
              className={`cefr-band ${cefrTone(profile.cefr_bands[skill])}`}
            >
              <span className="cefr-band-label">{bandLabel(skill)}</span>
              <span className="cefr-band-value">
                {profile.cefr_bands[skill]}
              </span>
            </span>
          ),
        )}
      </div>
```

### 9. `frontend/src/components/PronunciationPractice.tsx` — fluidez
- Añade el import:
  ```ts
  import { fluencyLevelLabel, wpmLabel } from "../utils/fluency";
  ```
- Dentro del `<div className="lines">`, justo después del `<div>` de "Similitud fonética" y ANTES del cierre `</div>` de `.lines`, añade:

```tsx
            <div>
              <span className="label">Fluidez:</span>{" "}
              {fluencyLevelLabel(result.fluency.level)} ·{" "}
              {wpmLabel(result.fluency.wpm)}
            </div>
```

### 10. `frontend/src/components/ListeningPractice.tsx` (nuevo)

```tsx
import { useEffect, useState } from "react";
import {
  getListeningQuestion,
  getListeningStats,
  submitListeningAnswer,
} from "../api/listening";
import { speak } from "../api/voz";
import type {
  ListeningAnswerResponse,
  ListeningQuestion,
  ListeningStats,
} from "../types/api";

interface ListeningPracticeProps {
  userId: string | null;
  onAttempt: () => void;
}

export function ListeningPractice({
  userId,
  onAttempt,
}: ListeningPracticeProps) {
  const [question, setQuestion] = useState<ListeningQuestion | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<ListeningAnswerResponse | null>(null);
  const [stats, setStats] = useState<ListeningStats | null>(null);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!userId) return;
    setError(null);
    setResult(null);
    setSelected(null);
    try {
      setQuestion(await getListeningQuestion(userId));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function refreshStats() {
    if (!userId) return;
    try {
      setStats(await getListeningStats(userId));
    } catch {
      /* backend no disponible */
    }
  }

  useEffect(() => {
    void load();
    void refreshStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  async function play() {
    if (!question || playing) return;
    setPlaying(true);
    try {
      await speak(question.script);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPlaying(false);
    }
  }

  async function choose(index: number) {
    if (!userId || !question || result) return;
    setSelected(index);
    try {
      setResult(await submitListeningAnswer(userId, question.id, index));
      onAttempt();
      void refreshStats();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="listening">
      <h3>Comprensión auditiva</h3>
      {error && <p className="listening-error">{error}</p>}
      {!question ? (
        <p className="progress-empty">Cargando ejercicio…</p>
      ) : (
        <>
          <button
            type="button"
            className="listen-button"
            onClick={play}
            disabled={playing || !userId}
          >
            {playing ? "Reproduciendo…" : "Escuchar audio"}
          </button>
          <p className="listening-question">{question.question}</p>
          <div className="listening-options">
            {question.options.map((opt, i) => {
              let cls = "listening-option";
              if (result && i === result.correct_index) cls += " correct";
              if (result && i === selected && !result.correct) cls += " wrong";
              return (
                <button
                  key={opt}
                  type="button"
                  className={cls}
                  onClick={() => choose(i)}
                  disabled={!!result}
                >
                  {opt}
                </button>
              );
            })}
          </div>
          {result && (
            <div className={`listening-result ${result.correct ? "ok" : "ko"}`}>
              {result.correct ? "¡Correcto!" : "Incorrecto."}{" "}
              <span className="listening-script">{question.script}</span>
            </div>
          )}
          {stats && (
            <p className="listening-stats">
              Aciertos: {stats.correct} de {stats.attempts}
              {stats.accuracy !== null ? ` (${stats.accuracy}%)` : ""}
            </p>
          )}
          <button
            type="button"
            className="listening-next"
            onClick={load}
            disabled={!userId}
          >
            Siguiente
          </button>
        </>
      )}
    </section>
  );
}
```

### 11. `frontend/src/App.tsx` — montar ListeningPractice
- Añade el import (orden alfabético, entre `LearningProfile` y `ModeSelect`):
  ```ts
  import { ListeningPractice } from "./components/ListeningPractice";
  ```
- Inserta, justo después de `<LearningProfile profile={profile} />` y antes de `<main className="chat">`:

```tsx
        <ListeningPractice
          userId={currentUserId}
          onAttempt={() => {
            refreshHistory();
            refreshEvents();
          }}
        />
```

### 12. `frontend/src/index.css` — estilos
Añade **al final del archivo** (después del bloque `@media (prefers-reduced-motion)`):

```css
/* CEFR: descriptor y bandas por destreza */
.cefr-descriptor {
  margin: 0 0 var(--space-3);
  font-size: var(--text-sm);
  color: var(--color-text-dim);
}

.cefr-bands {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.cefr-band {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-pill);
  font-size: var(--text-xs);
  line-height: 1;
}

.cefr-band-label {
  color: var(--color-text-dim);
  font-weight: 500;
}

.cefr-band-value {
  font-weight: 700;
}

.cefr-band.basic {
  color: var(--color-warning);
  background: color-mix(in srgb, var(--color-warning) 15%, transparent);
}

.cefr-band.intermediate {
  color: var(--color-accent);
  background: var(--color-accent-ring);
}

.cefr-band.advanced {
  color: var(--color-success);
  background: color-mix(in srgb, var(--color-success) 15%, transparent);
}

/* Listening */
.listening {
  margin: var(--space-2) 0;
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.listening h3 {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--color-text-dim);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.listen-button {
  align-self: flex-start;
  background: linear-gradient(135deg, var(--color-accent), var(--color-accent-2));
  color: var(--color-on-accent);
  border: none;
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-5);
  font-weight: 600;
  cursor: pointer;
}

.listen-button:hover:not(:disabled) {
  filter: brightness(1.08);
}

.listen-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.listening-question {
  margin: 0;
  font-size: var(--text-base);
  font-weight: 600;
}

.listening-options {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-2);
}

.listening-option {
  text-align: left;
  background: var(--color-bg-soft);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  cursor: pointer;
}

.listening-option:hover:not(:disabled) {
  border-color: var(--color-accent);
}

.listening-option:disabled {
  cursor: default;
}

.listening-option.correct {
  border-color: var(--color-success);
  background: color-mix(in srgb, var(--color-success) 15%, transparent);
}

.listening-option.wrong {
  border-color: var(--color-error);
  background: var(--color-error-soft);
}

.listening-result {
  border-radius: var(--radius-md);
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  font-size: var(--text-sm);
}

.listening-result.ok {
  border-color: var(--color-success);
  color: var(--color-success);
}

.listening-result.ko {
  border-color: var(--color-error);
  color: var(--color-error);
}

.listening-script {
  color: var(--color-text);
}

.listening-stats {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--color-text-dim);
}

.listening-next {
  align-self: flex-start;
  background: var(--color-surface-2);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
  cursor: pointer;
}

.listening-next:hover:not(:disabled) {
  border-color: var(--color-accent);
}

.listening-next:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.listening-error {
  margin: 0;
  color: var(--color-error);
  font-size: var(--text-sm);
}

@media (max-width: 768px) {
  .listening-options {
    grid-template-columns: 1fr;
  }
}
```

## Criterios de aceptación
- `npm test` → **74 tests** (65 previos + 9 nuevos: 4 fluency + 2 bandLabel + 3 listening).
- `npm run build` → `tsc` y `vite build` sin errores.
- Ningún test existente se rompe.

## Restricciones
- NO tocar el backend ni `config.py`.
- NO tocar `utils/modes.ts` ni el sistema de modos (listening se muestra como sección independiente, no como modo).
- No añadir variables/parámetros sin usar (tsconfig `noUnusedLocals`/`noUnusedParameters`).
- Estilo: `import type` para tipos, comillas dobles, nombres en español para textos visibles.

## Salida
Lista de archivos creados/modificados (resumen), salida de `npm test` (línea de resumen) y de `npm run build`, y cualquier desviación.
