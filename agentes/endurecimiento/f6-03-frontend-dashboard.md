# Subagente F6.3 — Frontend: dashboard de progreso real

## Rol
Programador frontend React + TypeScript (Vite + Vitest). Sin acceso a Git ni al backend.

## Objetivo
Sustituir el panel de "counts" `ProgressSummary` por un **`ProgressDashboard`** que muestre el
progreso pedagógico **real** devuelto por `GET /api/progress/history` (ya implementado en el
backend, F6.2) y la línea de tiempo `GET /api/learning/events` (F4/F6.1). El dashboard debe ser
**responsive total** (móvil y tablet, además de escritorio — premisa 14) y respetar el sistema
de diseño por tokens y tema claro/oscuro existente.

## Contexto (autocontenido)
- Arquitectura frontend: `api/` (única capa que hace fetch) → `hooks/` (estado, llaman a `api/`)
  → `components/` (render puro, reciben props, NO hacen fetch) → `App.tsx` (composición).
- Backend ya expone (NO lo modifiques):
  - `GET /api/progress/history?user_id=<id>&bucket=day|week|month` → `ProgressHistory`:
    `{ user_id, bucket, series: [{bucket, messages, exercises, corrections, pronunciation}],
    streak: {current_days, best_days, last_active_date}, mastery: {active: GrammarRecurringError[],
    resolved: GrammarRecurringError[]}, milestones: [{id, label, achieved}] }`.
  - `GET /api/learning/events?user_id=<id>` → `LearningEvent[]`: `{id, user_id, type, detail,
    created_at}` con `type` en `"message"|"exercise"|"correction"|"pronunciation"|"conversation"`.
- `frontend/src/types/api.ts`: define los tipos espejo. `GrammarRecurringError` ya existe.
- `frontend/src/api/client.ts`: `getJson<T>(url)` (con `fetch`, manejo de errores). Úsala.
- `frontend/src/hooks/useChat.ts` (LEERLO entero antes de editar): hoy tiene `progress`/
  `refreshProgress` (que se van a **reemplazar**) y `profile`/`refreshProfile` (se mantienen).
  `sendText` ya llama `analyzeText(...).then(refreshProfile)` tras cada envío.
- `frontend/src/App.tsx` (LEERLO): renderiza `<ProgressSummary progress={progress} />` y
  `<PronunciationPractice ... onAttempt={refreshProgress} />`.
- `frontend/src/components/ProgressSummary.tsx`: se **elimina** (reemplazado).
- `frontend/src/index.css`: tokens en `:root` (`--color-*`, `--space-*`, `--radius-*`,
  `--shadow-*`, `--text-*`); tema claro en `:root[data-theme="light"]`; breakpoint móvil
  `@media (max-width: 768px)` ya existe (al final del archivo). La clase `.progress-empty` es
  **compartida** (también la usa `LearningProfile.tsx`): NO la elimines.
- Tests: vitest con `describe/it/expect` y `vi.stubGlobal("fetch", ...)` para mockear fetch
  (ver `frontend/src/api/chat.test.ts` y `api/learning.test.ts`).
- Verificación (desde `frontend/`):
  ```powershell
  npm test
  npx tsc --noEmit
  npm run build
  ```
- `tsconfig.json` tiene `strict`, `noUnusedLocals` y `noUnusedParameters`: NO dejes imports ni
  variables sin usar.

## Tarea detallada

### 1. `frontend/src/types/api.ts` — añadir tipos (al final)
```typescript
export type Bucket = "day" | "week" | "month";

export type LearningEventType =
  | "message"
  | "exercise"
  | "correction"
  | "pronunciation"
  | "conversation";

export interface LearningEvent {
  id: number;
  user_id: string;
  type: LearningEventType;
  detail: string;
  created_at: string;
}

export interface SeriesPoint {
  bucket: string;
  messages: number;
  exercises: number;
  corrections: number;
  pronunciation: number;
}

export interface Streak {
  current_days: number;
  best_days: number;
  last_active_date: string | null;
}

export interface ErrorMastery {
  active: GrammarRecurringError[];
  resolved: GrammarRecurringError[];
}

export interface Milestone {
  id: string;
  label: string;
  achieved: boolean;
}

export interface ProgressHistory {
  user_id: string;
  bucket: Bucket;
  series: SeriesPoint[];
  streak: Streak;
  mastery: ErrorMastery;
  milestones: Milestone[];
}
```

### 2. `frontend/src/api/progress.ts` — añadir `getProgressHistory`
Mantén `getProgress` y añade:
```typescript
export function getProgressHistory(
  userId: string,
  bucket: Bucket,
): Promise<ProgressHistory> {
  const query = new URLSearchParams({ user_id: userId, bucket }).toString();
  return getJson<ProgressHistory>(`/api/progress/history?${query}`);
}
```
Actualiza el import de tipos para incluir `Bucket` y `ProgressHistory`.

### 3. `frontend/src/api/learning.ts` — añadir `getEvents`
Mantén lo existente y añade:
```typescript
export function getEvents(userId: string): Promise<LearningEvent[]> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<LearningEvent[]>(`/api/learning/events?${query}`);
}
```
Actualiza el import de tipos para incluir `LearningEvent`.

### 4. `frontend/src/utils/progress.ts` — añadir helpers puros
Mantén lo existente y añade:
```typescript
export function bucketLabel(bucket: Bucket): string {
  switch (bucket) {
    case "day":
      return "Día";
    case "week":
      return "Semana";
    case "month":
      return "Mes";
  }
}

export function eventLabel(type: LearningEventType): string {
  switch (type) {
    case "message":
      return "Mensaje";
    case "exercise":
      return "Ejercicio";
    case "correction":
      return "Corrección";
    case "pronunciation":
      return "Pronunciación";
    case "conversation":
      return "Conversación";
  }
}
```
Actualiza el import de tipos para incluir `Bucket` y `LearningEventType`.

### 5. `frontend/src/components/ProgressDashboard.tsx` (nuevo; reemplaza a ProgressSummary)
Crea el componente con estas props: `{ history: ProgressHistory | null; events: LearningEvent[];
bucket: Bucket; onBucketChange: (b: Bucket) => void }`. Estructura:

```tsx
import type { Bucket, LearningEvent, ProgressHistory } from "../types/api";
import { bucketLabel, eventLabel } from "../utils/progress";

const BUCKETS: Bucket[] = ["day", "week", "month"];

interface ProgressDashboardProps {
  history: ProgressHistory | null;
  events: LearningEvent[];
  bucket: Bucket;
  onBucketChange: (bucket: Bucket) => void;
}

export function ProgressDashboard({
  history,
  events,
  bucket,
  onBucketChange,
}: ProgressDashboardProps) {
  if (history === null) {
    return (
      <section className="progress-dashboard">
        <header className="pd-header">
          <h2 className="pd-title">Tu progreso</h2>
          <BucketToggle value={bucket} onChange={onBucketChange} />
        </header>
        <p className="progress-empty">
          Aún no hay progreso. Empieza a conversar o a practicar pronunciación y
          aquí verás tu evolución, racha e hitos.
        </p>
      </section>
    );
  }

  const maxMessages = Math.max(1, ...history.series.map((p) => p.messages));
  const maxPron = Math.max(1, ...history.series.map((p) => p.pronunciation));

  return (
    <section className="progress-dashboard">
      <header className="pd-header">
        <h2 className="pd-title">Tu progreso</h2>
        <BucketToggle value={bucket} onChange={onBucketChange} />
      </header>

      <div className="pd-grid">
        <div className="pd-card">
          <h3>Racha</h3>
          <p className="pd-big">
            {history.streak.current_days}
            <span className="pd-unit"> días</span>
          </p>
          <p className="pd-sub">Mejor racha: {history.streak.best_days} días</p>
          {history.streak.last_active_date && (
            <p className="pd-sub pd-faint">
              Última actividad: {history.streak.last_active_date}
            </p>
          )}
        </div>

        <div className="pd-card">
          <h3>Actividad</h3>
          {history.series.length === 0 ? (
            <p className="progress-empty">Sin actividad registrada.</p>
          ) : (
            <div className="pd-chart" role="img" aria-label="Actividad por período">
              {history.series.map((p) => (
                <div key={p.bucket} className="pd-col" title={p.bucket}>
                  <div className="pd-bars">
                    <span
                      className="pd-bar pd-bar-messages"
                      style={{
                        height:
                          p.messages === 0
                            ? "0%"
                            : `${Math.max(10, (p.messages / maxMessages) * 100)}%`,
                      }}
                    />
                    <span
                      className="pd-bar pd-bar-pron"
                      style={{
                        height:
                          p.pronunciation === 0
                            ? "0%"
                            : `${Math.max(10, (p.pronunciation / maxPron) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="pd-axis">{p.bucket}</span>
                </div>
              ))}
            </div>
          )}
          <div className="pd-legend">
            <span>
              <span className="pd-dot pd-dot-messages" aria-hidden="true" /> Mensajes
            </span>
            <span>
              <span className="pd-dot pd-dot-pron" aria-hidden="true" /> Pronunciación
            </span>
          </div>
        </div>
      </div>

      <div className="pd-card">
        <h3>Dominio de errores</h3>
        <div className="pd-mastery">
          <div>
            <h4 className="pd-subhead">Activos ({history.mastery.active.length})</h4>
            {history.mastery.active.length === 0 ? (
              <p className="progress-empty">Sin errores recurrentes activos.</p>
            ) : (
              <ul className="pd-errors">
                {history.mastery.active.map((e) => (
                  <li key={e.rule} className="pd-error">
                    <span className="pd-error-count">{e.count}×</span>
                    <span>{e.message}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h4 className="pd-subhead">Resueltos ({history.mastery.resolved.length})</h4>
            {history.mastery.resolved.length === 0 ? (
              <p className="progress-empty">Aún no hay errores resueltos.</p>
            ) : (
              <ul className="pd-errors">
                {history.mastery.resolved.map((e) => (
                  <li key={e.rule} className="pd-error pd-error-resolved">
                    <span className="pd-error-count">{e.count}×</span>
                    <span>{e.message}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      <div className="pd-card">
        <h3>Hitos</h3>
        <ul className="pd-milestones">
          {history.milestones.map((m) => (
            <li
              key={m.id}
              className={`pd-milestone${m.achieved ? " achieved" : ""}`}
            >
              {m.label}
            </li>
          ))}
        </ul>
      </div>

      <div className="pd-card">
        <h3>Actividad reciente</h3>
        {events.length === 0 ? (
          <p className="progress-empty">Sin actividad reciente.</p>
        ) : (
          <ul className="pd-timeline">
            {events.slice(0, 8).map((e) => (
              <li key={e.id} className="pd-event">
                <span className={`pd-event-type ${e.type}`}>{eventLabel(e.type)}</span>
                <span className="pd-event-detail">{e.detail || "—"}</span>
                <span className="pd-event-date">{e.created_at.slice(0, 10)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function BucketToggle({
  value,
  onChange,
}: {
  value: Bucket;
  onChange: (b: Bucket) => void;
}) {
  return (
    <div className="bucket-toggle" role="group" aria-label="Período de agrupación">
      {BUCKETS.map((b) => (
        <button
          key={b}
          type="button"
          className={b === value ? "active" : ""}
          onClick={() => onChange(b)}
          aria-pressed={b === value}
        >
          {bucketLabel(b)}
        </button>
      ))}
    </div>
  );
}
```

### 6. `frontend/src/hooks/useChat.ts` — reemplazar progress por history/events
Haz estos cambios (lee el archivo primero; conserva el resto intacto):
- Import: sustituye `import { getProgress } from "../api/progress";` por
  `import { getProgressHistory } from "../api/progress";`.
- Import: `import { analyzeText, getProfile } from "../api/learning";` →
  `import { analyzeText, getEvents, getProfile } from "../api/learning";`.
- En el import de tipos, sustituye `ProgressSummary` por `Bucket, LearningEvent, ProgressHistory`
  (conserva los demás tipos, y quita el `ProgressSummary` que quedaría sin uso).
- Estado: sustituye `const [progress, setProgress] = useState<ProgressSummary | null>(null);`
  por:
  ```ts
  const [history, setHistory] = useState<ProgressHistory | null>(null);
  const [events, setEvents] = useState<LearningEvent[]>([]);
  const [bucket, setBucket] = useState<Bucket>("week");
  ```
- Sustituye el callback `refreshProgress` por:
  ```ts
  const refreshHistory = useCallback(async () => {
    if (!currentUserId) return;
    try {
      setHistory(await getProgressHistory(currentUserId, bucket));
    } catch {
      /* backend no disponible */
    }
  }, [currentUserId, bucket]);

  const refreshEvents = useCallback(async () => {
    if (!currentUserId) return;
    try {
      setEvents(await getEvents(currentUserId));
    } catch {
      /* backend no disponible */
    }
  }, [currentUserId]);
  ```
- Sustituye el efecto `useEffect(() => { setProgress(null); void refreshProgress(); }, [refreshProgress]);`
  por estos dos (para no parpadear al cambiar de bucket):
  ```ts
  useEffect(() => {
    setHistory(null);
    setEvents([]);
  }, [currentUserId]);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  useEffect(() => {
    void refreshEvents();
  }, [refreshEvents]);
  ```
  (Conserva el efecto de `refreshProfile` existente.)
- En `sendText`, sustituye `void analyzeText(trimmed, currentUserId).then(refreshProfile).catch(() => {});`
  por:
  ```ts
  void analyzeText(trimmed, currentUserId)
    .then(() => {
      refreshProfile();
      refreshEvents();
      refreshHistory();
    })
    .catch(() => {});
  ```
- En el `return`, sustituye `progress, refreshProgress,` por
  `history, events, bucket, setBucket, refreshHistory, refreshEvents,` (conserva `profile` y
  `refreshProfile`).

### 7. `frontend/src/App.tsx` — conectar el dashboard
- Sustituye `import { ProgressSummary } from "./components/ProgressSummary";` por
  `import { ProgressDashboard } from "./components/ProgressDashboard";`.
- En la desestructuración de `useChat()`, sustituye `progress, refreshProgress,` por
  `history, events, bucket, setBucket, refreshHistory, refreshEvents,`.
- Sustituye `<ProgressSummary progress={progress} />` por
  `<ProgressDashboard history={history} events={events} bucket={bucket} onBucketChange={setBucket} />`.
- Sustituye `onAttempt={refreshProgress}` (en `<PronunciationPractice ... />`) por
  `onAttempt={() => { refreshHistory(); refreshEvents(); }}`.

### 8. Eliminar `frontend/src/components/ProgressSummary.tsx`
Borra el archivo (ya no se usa). No borres `utils/progress.ts` (sus helpers se reutilizan).

### 9. `frontend/src/index.css` — estilos + responsive
Añade al final (antes del bloque `@media (max-width: 768px)` existente, o justo después del
bloque de `.learning-profile`) los estilos del dashboard usando tokens. Incluye:
- `.progress-dashboard` (contenedor tarjeta, fondo `--color-surface`, borde
  `--color-border`, radio `--radius-lg`, padding `--space-5`).
- `.pd-header` (flex, `justify-content: space-between`, `align-items: center`, gap).
- `.pd-title` (tamaño `--text-lg`).
- `.bucket-toggle` (segmented control: fondo `--color-bg-soft`, radio `--radius-pill`, botones
  con `--color-text-dim`, estado `.active` con `--color-accent` y `--color-on-accent`).
- `.pd-grid` (grid 2 columnas con gap `--space-4`).
- `.pd-card` (tarjeta interior: fondo `--color-bg-soft`, borde `--color-border`, radio
  `--radius-md`, padding `--space-4`); `.pd-card h3` (tamaño `--text-base`, color
  `--color-text-dim`, margin ajustado).
- `.pd-big` (número grande `--text-2xl`, `font-weight: 700`); `.pd-unit` (tamaño `--text-sm`,
  color `--color-text-dim`); `.pd-sub` (tamaño `--text-sm`, color `--color-text-dim`);
  `.pd-faint` (color `--color-text-faint`).
- `.pd-chart` (flex, `align-items: flex-end`, `gap: var(--space-2)`, altura fija ~110px);
  `.pd-col` (flex column, `flex: 1`, `justify-content: flex-end`, `align-items: center`,
  `gap: var(--space-1)`); `.pd-bars` (flex, `align-items: flex-end`, `gap: 2px`, altura 100%);
  `.pd-bar` (ancho ~8px, radio `--radius-sm`); `.pd-bar-messages` (fondo `--color-accent`);
  `.pd-bar-pron` (fondo `--color-success`); `.pd-axis` (tamaño `--text-xs`, color
  `--color-text-faint`, `overflow: hidden`, `text-overflow: ellipsis`, `max-width: 100%`,
  `white-space: nowrap`).
- `.pd-legend` (flex, gap `--space-4`, tamaño `--text-xs`, color `--color-text-dim`);
  `.pd-dot` (círculo 8px inline-block, radio pill); `.pd-dot-messages` (fondo `--color-accent`);
  `.pd-dot-pron` (fondo `--color-success`).
- `.pd-mastery` (grid 2 columnas, gap `--space-4`); `.pd-subhead` (tamaño `--text-sm`,
  color `--color-text-dim`, margin ajustado).
- `.pd-errors` (lista sin viñetas); `.pd-error` (flex, gap `--space-2`, tamaño `--text-sm`);
  `.pd-error-count` (badge `--color-error-soft`/`--color-error`); `.pd-error-resolved`
  (color `--color-success`).
- `.pd-milestones` (grid con `repeat(auto-fill, minmax(150px, 1fr))`, gap `--space-2`);
  `.pd-milestone` (chip con borde `--color-border`, color `--color-text-faint`, radio
  `--radius-pill`, padding `--space-1 --space-3`, tamaño `--text-sm`);
  `.pd-milestone.achieved` (borde/fondo `--color-accent` con `--color-accent-ring` o texto
  `--color-text`, y un indicador de éxito `--color-success`).
- `.pd-timeline` (lista sin viñetas, gap); `.pd-event` (flex, gap `--space-3`, `align-items:
  baseline`, borde inferior `--color-border`, padding `--space-2` 0); `.pd-event-type` (badge
  pequeño con color por tipo, radio `--radius-pill`, tamaño `--text-xs`); `.pd-event-detail`
  (flex 1, `overflow: hidden`, `text-overflow: ellipsis`, `white-space: nowrap`, tamaño
  `--text-sm`); `.pd-event-date` (tamaño `--text-xs`, color `--color-text-faint`).
- Responsive **tablet** (nuevo, `@media (max-width: 1024px)`): `.pd-grid` y `.pd-mastery` a
  `1fr` (una columna).
- Responsive **móvil**: dentro del `@media (max-width: 768px)` existente, añade
  `.pd-header { flex-direction: column; align-items: flex-start; }` y `.pd-chart { height: 80px; }`
  (o lo que asegure que no desborda).

Usa los tokens existentes (no inventes nombres). Mantén coherencia con `.learning-profile` y
`.progress`. Aplica micro-interacciones (transición con `var(--duration-fast)`/`var(--ease-out)`
en hover de botones y chips) y respeta `prefers-reduced-motion`.

### 10. Tests
- **`frontend/src/utils/progress.test.ts`**: añade import de `bucketLabel` y `eventLabel`, y dos
  bloques `describe` nuevos: `bucketLabel` (1 `it` con los 3 buckets) y `eventLabel` (1 `it` con
  los 5 tipos). Conserva los tests existentes.
- **`frontend/src/api/progress.test.ts`** (nuevo): mockea fetch (patrón de `api/learning.test.ts`)
  y cubre: `getProgressHistory` llama a `/api/progress/history?user_id=u1&bucket=week` (1 `it`);
  `getProgress` llama a `/api/progress?user_id=u1` (1 `it`).
- **`frontend/src/api/learning.test.ts`**: añade import de `getEvents` y 1 `it` que verifica que
  `getEvents("u1")` llama a `/api/learning/events?user_id=u1`.

## Criterios de aceptación
- `npm test` **verde: 56 tests** (51 previos + 5 nuevos).
- `npx tsc --noEmit` **sin errores** (ojo con `strict`, `noUnusedLocals`, `noUnusedParameters`).
- `npm run build` **OK**.
- No queda ninguna referencia a `ProgressSummary` (archivo borrado, imports actualizados).

## Restricciones
- NO tocar el backend.
- NO cambiar `api/client.ts`, `utils/sse.ts`, `hooks/useHandsFree.ts`, `hooks/useTheme.ts`, ni
  otros componentes salvo `App.tsx`, `PronunciationPractice.tsx` (solo si es necesario el
  `onAttempt`; NO cambies su lógica) y la creación de `ProgressDashboard.tsx`.
- `components/` NO hace fetch: todo el estado y las llamadas viven en `useChat`.
- Mantener el estilo: español en textos de UI, tokens de diseño, a11y (`role`, `aria-label`,
  `aria-pressed`), estados vacíos.

## Salida
Lista de archivos creados/modificados/eliminados (resumen por archivo), la salida de
`npm test`, de `npx tsc --noEmit`, de `npm run build`, y cualquier desviación.
