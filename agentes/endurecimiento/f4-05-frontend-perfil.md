# Subagente F4.5 — Frontend Learning Profile (tipos + api + panel + integración)

## Rol
Programador frontend (Vite + React + TypeScript, modo estricto). Sin acceso a Git ni al backend.

## Objetivo
Consumir el perfil de aprendizaje del backend (Fase 4) y mostrarlo: badge de nivel **CEFR**,
**vocabulario**, **errores recurrentes**, **pronunciación media** y **recomendaciones**. Además,
alimentar el backend analizando el texto que escribe el alumno tras cada envío.

## Contexto (autocontenido)
- Backend ya expone (F4.1–F4.4), con `user_id` por query param y 404 si el usuario no existe:
  - `GET /api/profile` → `LearningProfile` (ver forma abajo).
  - `POST /api/vocabulary/analyze` `{ text }` y `POST /api/grammar/analyze` `{ text }`.
- `frontend/src/api/client.ts`: `getJson<T>(url)`, `postJson<T>(url, body)` (hacen fetch y lanzan
  Error si no es 2xx).
- `frontend/src/types/api.ts` (LEERLO): tipos espejo de los schemas del backend.
- `frontend/src/api/progress.ts` y `frontend/src/components/ProgressSummary.tsx`: patrón a seguir
  (api + panel colapsable/estado vacío + utilidades de formato).
- `frontend/src/hooks/useChat.ts` (LEERLO): tiene `progress`/`refreshProgress` con aislamiento al
  cambiar de usuario; hay que replicar ese patrón para `profile`. `sendText` envía el texto y
  persiste la conversación.
- `frontend/src/utils/progress.ts`: `formatAverage(value: number | null): string`.
- `frontend/src/index.css`: tokens (`--color-*`, `--space-*`, `--radius-*`, `--text-*`,
  `--color-accent`, `--color-success`, `--color-warning`), tema claro/oscuro vía variables.
- Tests: `frontend/src/api/conversations.test.ts` (patrón `vi.stubGlobal("fetch", ...)`);
  `frontend/src/utils/progress.test.ts` (patrón de utilidades).
- Verificación (desde `frontend/`):
  ```powershell
  npm test            # vitest run
  npx tsc --noEmit    # tipos
  npm run build       # tsc + vite build
  ```

### Forma de `LearningProfile` (backend)
```json
{
  "user_id": "…",
  "cefr_level": "A2",
  "vocabulary_size": 12,
  "top_words": ["apple", "cat"],
  "recurring_errors": [
    { "rule": "he_she_it_s", "message": "Falta la -s.", "count": 5,
      "last_example": "He go", "last_seen": "…" }
  ],
  "pronunciation_average": 82.5,
  "recommendations": ["…"]
}
```

## Tarea detallada

### 1. `frontend/src/types/api.ts` — añadir tipos
```ts
export type CefrLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export interface GrammarRecurringError {
  rule: string;
  message: string;
  count: number;
  last_example: string;
  last_seen: string;
}

export interface LearningProfile {
  user_id: string;
  cefr_level: CefrLevel;
  vocabulary_size: number;
  top_words: string[];
  recurring_errors: GrammarRecurringError[];
  pronunciation_average: number | null;
  recommendations: string[];
}
```

### 2. `frontend/src/api/learning.ts` (nuevo)
```ts
import { getJson, postJson } from "./client";
import type { LearningProfile } from "../types/api";

export function getProfile(userId: string): Promise<LearningProfile> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<LearningProfile>(`/api/profile?${query}`);
}

export async function analyzeText(text: string, userId: string): Promise<void> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  await Promise.all([
    postJson<unknown>(`/api/vocabulary/analyze?${query}`, { text }),
    postJson<unknown>(`/api/grammar/analyze?${query}`, { text }),
  ]);
}
```

### 3. `frontend/src/utils/cefr.ts` (nuevo) + test
```ts
export type CefrTone = "basic" | "intermediate" | "advanced";

export function cefrTone(level: string): CefrTone {
  if (level === "C1" || level === "C2") return "advanced";
  if (level === "B1" || level === "B2") return "intermediate";
  return "basic";
}

export function cefrLabel(level: string): string {
  switch (level) {
    case "A1": return "Principiante";
    case "A2": return "Básico";
    case "B1": return "Intermedio";
    case "B2": return "Intermedio alto";
    case "C1": return "Avanzado";
    case "C2": return "Maestría";
    default: return level;
  }
}
```
Test `frontend/src/utils/cefr.test.ts`: tono por nivel (A1→basic, B2→intermediate, C1→advanced,
desconocido→basic) y etiqueta por nivel (incl. desconocido→el propio valor).

### 4. `frontend/src/components/LearningProfile.tsx` (nuevo)
Panel de presentación pura (recibe `profile: LearningProfile | null`, no hace fetch). Muestra:
- Cabecera con badge CEFR (`cefrTone`/`cefrLabel`).
- Vocabulario: nº de palabras + chips con `top_words`.
- Pronunciación media (`formatAverage`, `—` si null).
- Errores recurrentes: lista `count×` + `message` (estado vacío si no hay).
- Recomendaciones: lista de `recommendations`.
- Estado vacío cuando `profile === null`.

```tsx
import { cefrLabel, cefrTone } from "../utils/cefr";
import { formatAverage } from "../utils/progress";
import type { LearningProfile as ProfileData } from "../types/api";

interface LearningProfileProps {
  profile: ProfileData | null;
}

export function LearningProfile({ profile }: LearningProfileProps) {
  if (profile === null) {
    return (
      <section className="learning-profile">
        <p className="progress-empty">
          Aún no hay perfil de aprendizaje. Escribe en inglés y aquí verás tu nivel,
          vocabulario y recomendaciones.
        </p>
      </section>
    );
  }
  const tone = cefrTone(profile.cefr_level);
  return (
    <section className="learning-profile">
      <header className="learning-header">
        <span className="learning-title">Tu perfil</span>
        <span className={`cefr-badge ${tone}`}>
          {profile.cefr_level} · {cefrLabel(profile.cefr_level)}
        </span>
      </header>

      <div className="learning-grid">
        <div className="learning-block">
          <h3>Vocabulario</h3>
          <p className="learning-big">{profile.vocabulary_size}</p>
          {profile.top_words.length > 0 ? (
            <ul className="learning-chips">
              {profile.top_words.map((w) => (
                <li key={w} className="learning-chip">{w}</li>
              ))}
            </ul>
          ) : (
            <p className="progress-empty">Sin palabras registradas.</p>
          )}
        </div>

        <div className="learning-block">
          <h3>Pronunciación media</h3>
          <p className="learning-big">
            {profile.pronunciation_average === null
              ? "—"
              : formatAverage(profile.pronunciation_average)}
          </p>
        </div>
      </div>

      <div className="learning-block">
        <h3>Errores recurrentes</h3>
        {profile.recurring_errors.length === 0 ? (
          <p className="progress-empty">Sin errores recurrentes detectados.</p>
        ) : (
          <ul className="learning-errors">
            {profile.recurring_errors.map((e) => (
              <li key={e.rule} className="learning-error">
                <span className="learning-error-count">{e.count}×</span>
                <span>{e.message}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="learning-block">
        <h3>Recomendaciones</h3>
        <ul className="learning-recs">
          {profile.recommendations.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
```

### 5. `frontend/src/hooks/useChat.ts` — estado `profile`
Replica el patrón de `progress`:
- Estado `const [profile, setProfile] = useState<LearningProfile | null>(null);`.
- `refreshProfile` con guard `if (!currentUserId) return;` y try/catch.
- Efecto `useEffect(() => { setProfile(null); void refreshProfile(); }, [refreshProfile]);`
  (aislamiento al cambiar de usuario).
- En `sendText`, tras persistir, alimentar el backend y refrescar (fire-and-forget):
  ```ts
  void analyzeText(trimmed, currentUserId).then(refreshProfile).catch(() => {});
  ```
  (añade `refreshProfile` a las deps de `sendText`).
- Exportar `profile` y `refreshProfile` en el objeto de retorno.

### 6. `frontend/src/App.tsx`
Importa `LearningProfile`, desestructura `profile` de `useChat()` y renderiza
`<LearningProfile profile={profile} />` justo después de `<ProgressSummary progress={progress} />`.

### 7. `frontend/src/index.css` — estilos
Añade una sección `.learning-profile` consistente con `.progress` (mismos tokens, tema
claro/oscuro vía variables). Incluye: `.learning-header`, `.learning-title`, `.cefr-badge` con
tonos `.basic` (warning), `.intermediate` (accent), `.advanced` (success), `.learning-grid`
(2 columnas, 1 en móvil), `.learning-block`, `.learning-big`, `.learning-chips`/`.learning-chip`,
`.learning-errors`/`.learning-error`/`.learning-error-count`, `.learning-recs`.

```css
.learning-profile {
  margin: var(--space-2) 0;
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.learning-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.learning-title {
  font-size: var(--text-sm);
  font-weight: 600;
}

.cefr-badge {
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-pill);
  font-size: var(--text-xs);
  font-weight: 700;
  line-height: 1;
}

.cefr-badge.basic { color: var(--color-warning); background: color-mix(in srgb, var(--color-warning) 15%, transparent); }
.cefr-badge.intermediate { color: var(--color-accent); background: var(--color-accent-ring); }
.cefr-badge.advanced { color: var(--color-success); background: color-mix(in srgb, var(--color-success) 15%, transparent); }

.learning-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.learning-block { margin-bottom: var(--space-3); }
.learning-block:last-child { margin-bottom: 0; }

.learning-block h3 {
  margin: 0 0 var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-text-dim);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.learning-big {
  margin: 0;
  font-size: var(--text-xl);
  font-weight: 700;
  line-height: 1;
}

.learning-chips {
  margin: var(--space-2) 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.learning-chip {
  padding: var(--space-1) var(--space-2);
  background: var(--color-bg-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  font-size: var(--text-xs);
}

.learning-errors {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.learning-error {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  font-size: var(--text-sm);
}

.learning-error-count {
  color: var(--color-error);
  font-weight: 700;
}

.learning-recs {
  margin: 0;
  padding-left: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--color-text-dim);
}

@media (max-width: 768px) {
  .learning-grid { grid-template-columns: 1fr; }
}
```

### 8. Tests
- `frontend/src/utils/cefr.test.ts` (nuevo).
- `frontend/src/api/learning.test.ts` (nuevo): mock de `fetch`; verifica `getProfile` llama a
  `/api/profile?user_id=u1` y `analyzeText` llama a `/api/vocabulary/analyze?user_id=u1` y
  `/api/grammar/analyze?user_id=u1` con body `{"text":"hi"}`.

## Criterios de aceptación
- `npm test` **verde** (40 previos + nuevos de cefr + learning).
- `npx tsc --noEmit` **sin errores** (modo estricto, sin unused locals/params).
- `npm run build` **OK**.

## Restricciones
- NO tocar el backend.
- NO tocar `components/ProgressSummary.tsx` ni `utils/progress.ts` (solo reutilizarlos).
- Tipado estricto; reutilizar tokens de `index.css` (no inventar colores hardcode).
- Estilo: componentes de presentación puros (props, sin fetch); `api/` es la única capa que
  hace fetch.

## Salida
Lista de archivos creados/modificados, salida de `npm test`, de `npx tsc --noEmit`, de
`npm run build`, y cualquier desviación.
