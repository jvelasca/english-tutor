# Subagente F9.3 — Panel de calidad del tutor (frontend)

## Rol
Programador frontend React + TypeScript. Sin acceso a Git (no hagas commit) ni al backend.

## Objetivo
Añadir un **panel de calidad del tutor** que evalúa, de forma determinista y en local
(sin LLM-juez, premisa 12), las respuestas del tutor en la conversación actual. Es el
espejo frontend del evaluador `backend/services/evaluation.py` (señales libres de contexto:
`english`, `conciseness`, `engagement`, `total`). **No requiere backend nuevo**: se calcula
en el cliente sobre los mensajes `assistant`. Todo responsive móvil/tablet (premisa 14).

## Contexto (autocontenido)
- Stack: Vite + React + TypeScript (modo estricto). Tests con vitest (colocados junto a los
  archivos, `*.test.ts`). Estilos en `frontend/src/index.css` con tokens de diseño en `:root`
  (`--color-*`, `--text-*`, `--space-*`, `--radius-*`, `--shadow-*`) y tema claro/oscuro.
- Verificación (desde `frontend/`):
  ```powershell
  npm test -- --run
  npx tsc --noEmit
  npm run build
  ```
- El tipo `Message` vive en `frontend/src/types/api.ts` (`{ id?, role: "user"|"assistant",
  content, mode? }`). `App.tsx` recibe `messages` desde `useChat()` y ya monta
  `LearningProfile`, `ProgressDashboard` y `ListeningPractice`. Los componentes son
  presentacionales: reciben props, no hacen fetch.

## Tarea

### 1. `frontend/src/utils/tutorEvaluation.ts` (nuevo, puro)

```ts
// Evaluación objetiva y determinista del tutor (espejo de services/evaluation.py).
// Puntúa señales libres de contexto: inglés, concisión y engagement (0..100).

const SPANISH_WORDS = new Set<string>([
  "porque", "cuando", "donde", "usted", "nosotros", "ellos", "ellas",
  "también", "tiene", "tienen", "hace", "hacer", "puede", "pueden", "pero",
  "muy", "bien", "hay", "ser", "estar", "tener", "más", "está", "están",
  "sí", "cómo", "qué", "cuál", "quién", "dónde", "cuándo", "después",
  "antes", "ahora", "aquí", "allí", "gracias", "hola", "adiós", "buenos",
  "buenas", "días", "noches", "mañana", "noche", "día", "año", "años",
]);

const FRIENDLY_MARKERS = [
  "great", "good", "nice", "well done", "excellent", "perfect", "correct",
  "almost", "try again", "let's", "keep going", "awesome", "fantastic",
];

export interface TutorReplyEvaluation {
  english: number;
  conciseness: number;
  engagement: number;
  total: number;
}

export interface TutorEvaluationAverage {
  english: number | null;
  conciseness: number | null;
  engagement: number | null;
  total: number | null;
}

export function normalize(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9áéíóúñü ]/g, " ");
}

export function words(text: string): string[] {
  return text.toLowerCase().match(/[a-záéíóúñü]+/g) ?? [];
}

export function spanishWordRatio(text: string): number {
  const ws = words(text);
  if (ws.length === 0) return 0;
  const spanish = ws.filter((w) => SPANISH_WORDS.has(w)).length;
  return Math.round((spanish / ws.length) * 100) / 100;
}

export function englishWordRatio(text: string): number {
  return Math.round((1 - spanishWordRatio(text)) * 100) / 100;
}

export function concisenessScore(wordCount: number): number {
  if (wordCount <= 0) return 0;
  if (wordCount < 10) return 50;
  if (wordCount <= 180) return 100;
  if (wordCount <= 400) return 70;
  return 40;
}

export function engagementScore(reply: string): number {
  if (reply.includes("?")) return 100;
  const n = normalize(reply);
  if (FRIENDLY_MARKERS.some((m) => n.includes(m))) return 70;
  return 0;
}

export function evaluateTutorReply(reply: string): TutorReplyEvaluation {
  const english = Math.round(englishWordRatio(reply) * 100);
  const conciseness = concisenessScore(words(reply).length);
  const engagement = engagementScore(reply);
  const total = Math.round(
    0.5 * english + 0.25 * conciseness + 0.25 * engagement,
  );
  return { english, conciseness, engagement, total };
}

export function averageEvaluations(
  evals: TutorReplyEvaluation[],
): TutorEvaluationAverage {
  if (evals.length === 0) {
    return { english: null, conciseness: null, engagement: null, total: null };
  }
  const avg = (key: keyof TutorReplyEvaluation): number =>
    Math.round(evals.reduce((acc, e) => acc + e[key], 0) / evals.length);
  return {
    english: avg("english"),
    conciseness: avg("conciseness"),
    engagement: avg("engagement"),
    total: avg("total"),
  };
}
```

### 2. `frontend/src/utils/tutorEvaluation.test.ts` (nuevo, 14 tests)

Cubre al menos:
1. `normalize` baja a minúsculas y quita puntuación (`"Hello, World!"` → contiene `"hello"` y
   `"world"`).
2. `words` extrae palabras (`"I have twenty years"` → `["i","have","twenty","years"]`).
3. `spanishWordRatio` detecta español (`"Está muy bien, gracias."` > 0.5).
4. `englishWordRatio` todo inglés → `1`.
5. `concisenessScore(50)` → `100`.
6. `concisenessScore(5)` → `50`.
7. `concisenessScore(500)` → `40`.
8. `engagementScore("Good! How old are you?")` → `100`.
9. `engagementScore("Great work, keep going.")` → `70`.
10. `engagementScore("Just a statement.")` → `0`.
11. `evaluateTutorReply` sobre una respuesta en inglés con pregunta → `english === 100` y
    `total >= 80`.
12. `evaluateTutorReply` sobre respuesta en español → `english < 50`.
13. `averageEvaluations` promedia dos evaluaciones.
14. `averageEvaluations([])` → todos los campos `null`.

### 3. `frontend/src/components/TutorQualityPanel.tsx` (nuevo)

- Props: `{ messages: Message[] }`.
- Filtra los mensajes `role === "assistant"` con `content` no vacío, evalúa cada uno con
  `evaluateTutorReply`, y calcula medias con `averageEvaluations`.
- Si no hay turnos del tutor, devuelve `null` (no renderiza nada).
- Renderiza una `<section className="tutor-quality" aria-label="Calidad del tutor">` con:
  - Cabecera "Calidad del tutor".
  - 4 chips de estadística: `Total`, `Inglés`, `Concisión`, `Engagement` (valores `—` si son
    `null`). Usa `role="status"` o `aria-live="polite"`.
  - Una lista breve de los **últimos 3 turnos** (más reciente primero) con su `total` y un
    resumen tipo "Inglés 100 · Concisión 100 · Engagement 100".
- Presentacional: solo props, sin fetch ni estado global. Usa tokens de `index.css`.

### 4. `frontend/src/App.tsx` — integrar

- Importa `TutorQualityPanel` y monta `<TutorQualityPanel messages={messages} />` justo
  después de `<LearningProfile profile={profile} />` (dentro de `<div className="main">`).
- Sin otros cambios.

### 5. `frontend/src/index.css` — estilos

- Añade una sección `.tutor-quality` (y sub-elementos: cabecera, chips `.tutor-quality-stats`,
  `.stat-chip`, lista `.tutor-turns`, items) usando tokens de diseño y tema claro/oscuro
  (igual que `.learning-profile` / `.listening` ya existentes). **Responsive**: al menos
  `@media (max-width: 768px)` (móvil) apilando los chips en una fila que envuelve o en
  columna, y `@media (max-width: 1024px)` (tablet) si aporta.

## Criterios de aceptación
- `npm test -- --run` **verde: 88 tests** (74 previos + 14 nuevos).
- `npx tsc --noEmit` sin errores.
- `npm run build` OK.
- Ningún test existente se rompe.

## Restricciones
- NO tocar el backend.
- NO tocar otros componentes/utils/api/types salvo lo indicado.
- En `types/api.ts` NO añadir nada (los tipos de evaluación viven en el util).
- NO hagas commit ni toques documentación.

## Salida
Lista de archivos creados/modificados, salida de `npm test -- --run`, `npx tsc --noEmit` y
`npm run build`, y cualquier desviación.
