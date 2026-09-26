# Release notes — English Tutor v3.85.1

> ## ⚠️ ERRATA — esta versión NUNCA se publicó como tag
>
> **`v3.85.1` no existe como etiqueta en el repositorio y no se recrea.** Cuando se
> redactaron estas notas, el trabajo quedó **en el árbol de trabajo sin commitear** y la
> versión nunca llegó a etiquetarse: en el `HEAD` de entonces seguía `v3.85.0`.
>
> **Todo lo que describe este documento va DENTRO de `v3.86.0`** (el tag `v3.86.0` incluye
> íntegramente el delta aquí narrado, más el delta propio de `v3.86.0`). Es decir: aquí no
> hay una release que auditar por separado, y **cualquier afirmación de este texto sobre un
> tag `v3.85.1` es falsa**.
>
> El documento se **conserva sin reescribir** porque (a) es el registro de lo que se hizo y
> por qué, y (b) varias partes de `v3.86.0` lo citan. **La versión auditables es `v3.86.0`**;
> su punto de entrada externo declara esta fusión en su §6.
>
> *Declarado el 2026-09-26, antes de publicar `v3.86.0`, para que un auditor externo no
> persiga un tag inexistente.*

**Fecha:** 2026-09-26 · **Tipo:** release **DE PRODUCTO** (patch) · **Versión de app:**
`3.85.0 → 3.85.1`

**SOLO FRONTEND, SIN migración de BD, SIN endpoints nuevos y SIN cambio de contrato de API.**
**SIN bump** de `GENERATOR_VERSION` / `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue
`1.3.1`) / `LISTENING_BANK_VERSION` ni de las evaluaciones. **No se añade ni se retira gate**
—siguen los **ocho**, todos en `pending`— y `docs/audit/validation-evidence.json` **sigue sin
existir**.

**En una frase.** Cierra la auditoría externa `AY` sobre el arco `v3.84.0..v3.85.0`: la sesión
encadenada de «Repasar hoy» deja de atascarse cuando el planner sirve un peldaño reconductivo,
el panel APRENDER → Vocabulario recupera el acceso al repaso y el artefacto de contraste vuelve
a identificar la release que lo genera.

---

## 1. El P0: la sesión se quedaba clavada (hallazgo C1)

`ReviewSession` gobernaba el avance con **`produced`**, que solo se pone a `true` cuando
`WordDrill` dispara **`onProduced`**. Y `onProduced` se dispara **solo** en los peldaños que
acreditan producción:

| Peldaño | ¿Disparaba `onProduced`? | Consecuencia en la sesión |
|---|---|---|
| `recognition` | **no** (señal, no producción) | **clavada** |
| `recall` | **no** (señal léxica) | **clavada** |
| `sentence` | sí, si pasa | avanzaba |
| `write` | sí, si pasa | avanzaba |
| `transfer` | sí, si pasa | avanzaba |

Como el planner sirve el peldaño recomendado por hueco de competencia (`initialStep = item.activity`),
bastaba con que la cola recomendara `recognition` o `recall` como actividad inicial para que
**«Siguiente palabra» no apareciera nunca**: el alumno quedaba encerrado en ese ítem y la única
salida era cerrar el drill, que **aborta la sesión entera**. El E2E de `v3.85.0` no lo descubría
porque servía **todos** los ítems como `activity: "write"` —una elección honesta para poder
correr sin micrófono, y exactamente lo que tapaba el agujero—.

**El arreglo no es que Recognition y Recall mientan.** Se separan dos señales que estaban
confundidas en una:

- **`stepCompleted`** (`onStepCompleted`, **nuevo**): el peldaño ha dado **veredicto** —apruebe
  o falle—. Es la puerta del **avance** de la sesión encadenada.
- **`produced`** (`onProduced`, **sin cambios**): el intento **pasó** el peldaño y acredita
  **evidencia productiva**. Sigue reservado a `sentence` / `write` / `transfer`.

Así, un acierto de Recognition o Recall **deja avanzar** sin fabricar evidencia productiva: la
semejanza «completar el peldaño» y «producir» deja de ser la misma cosa. El veredicto se declara
**una sola vez por palabra** (idempotente por montaje) para que reintentar el mismo peldaño no
lo anuncie dos veces.

```
ReviewSession
   ↓ veredicto del peldaño (apruebe o falle)
onStepCompleted  →  «Siguiente palabra» / «Terminar»
   ↓ solo sentence/write/transfer aprobados
onProduced       →  evidencia productiva (sin cambios)
```

## 2. Accesibilidad de la sesión (auditoría AY)

- El contador `1 of 2` pasa a ser **región viva** (`role="status"`, `aria-live="polite"`,
  `aria-atomic="true"`): el progreso se **anuncia**, no solo se ve.
- Al aparecer «Siguiente palabra»/«Terminar», el **foco viaja al CTA**: el usuario de teclado
  ya no tiene que tabular por todo el drill para avanzar.

## 3. D4 — el panel APRENDER → Vocabulario recupera el repaso

`v3.85.0` retiró `<ReviewQueueSection>` del inventario y el panel incrustado
(`VocabularyRoutesPractice` → `QuizRoutePage`) se quedó **sin ninguna vía al repaso**. La
regresión se cierra **sin duplicar la sesión**: un **único CTA** («Repasar hoy» → `vocRoutes.reviewCta`)
proyecta la vista persistida (`"flashcards"`) y navega a la superficie central
(`#/diccionario` → Flashcards → Estudiar), que es donde vive `ReviewToday`. Un solo destino, un
solo origen de verdad para la sesión.

## 4. G3 — el artefacto de contraste vuelve a identificar la release

`docs/audit/generated/contrast-report.json` declaraba `audit: "V3.75.8-rampa-niveles-direccion"`
en `v3.85.0`: no era un informe de la release auditada y por eso la cifra «480 pares + 6 guardas
/ 0 bloqueantes» **no se pudo dar por demostrada** para los textos nuevos. `contrast_audit.mjs`
deriva ahora el sello (`audit` y `version`) de `frontend/package.json`, y el informe se
**regenera** para esta release.

## 5. Semántica fijada: qué es «Repasar hoy» (hallazgo C2)

Completar un peldaño **no** equivale a calificar/reprogramar la carta FSRS, así que el contador
puede **volver a aparecer** tras una sesión completa. No es un bucle técnico: es una decisión de
producto, y queda **fijada**:

> **«Repasar hoy» TRABAJA COMPETENCIA; NO consume vencimiento FSRS.**
> La sesión no «paga» la deuda del día: ejercita el hueco de competencia que el planner declara.
> Por eso una palabra puede seguir vencida y volver a ofrecerse —y eso es correcto mientras el
> rótulo no prometa lo contrario—.

La cifra del botón sigue siendo honesta: `due_count = len(served_items)` (el backend devuelve la
longitud de lo que sirve, no un total teórico).

## 6. Decisión de UX declarada: el límite 20 → 50 (hallazgo D3)

`v3.85.0` pasó de 20 a 50 sin decirlo (ver la errata `E2` en `release-notes-v3.85.0.md`). Se
declara ahora y se dictamina:

- **Qué cambia:** `REVIEW_LIMIT = 50` (= `REVIEW_QUEUE_MAX_LIMIT`), frente a
  `REVIEW_QUEUE_DEFAULT_LIMIT = 20` que aplicaba `ReviewQueueSection`.
- **Por qué:** una sesión encadenada que cubra el día entero de una tirada.
- **El coste, que no se esconde:** hasta **50 ítems con un clic obligatorio por ítem** y **sin
  estado persistido** (salir la pierde entera). El techo de 50 es hoy el **máximo del endpoint**,
  no una medida de carga razonable por sesión.
- **Deuda declarada:** segmentar la sesión (lotes, reanudación, o un techo de sesión menor que el
  techo del endpoint) queda **aparcado** en `docs/audit/PARKED.md §V3.85.1`.

## 7. Errata documental (hallazgo D2)

Las notas de `v3.85.0` §3 nombraban un `ReviewTodayCard` **inexistente**: el resumen se renderiza
**en línea dentro de `StudyTab`** y su estado vive en el hook `useReviewToday`. Declarado como
errata `E1` en `release-notes-v3.85.0.md` (el tag no se recrea).

## 8. Pruebas

**Unit (Vitest):**

| Fichero | Qué fija |
|---|---|
| `wordDrill.test.tsx` | el veredicto de Recognition/Recall declarado **sin** `onProduced`; Write fallido da veredicto sin acreditar producción |
| `ReviewToday.test.tsx` | un ítem servido como `recognition` avanza y **encadena**; `recall` avanza; el contador es región viva y el foco cae en el CTA |

**E2E (Playwright):**

- `reviewSession.spec.ts`: **nuevo caso de los cinco peldaños** —Recognition, Recall, Sentence
  (con micrófono falso), Write y Transfer—, cada uno exigiendo que la sesión avance; más una
  **sonda de teclado/foco** de la sesión. El caso original se conserva.
- `vocabularyRoutesReview.spec.ts`: caso nuevo que fija el CTA del panel APRENDER → Vocabulario
  y su destino (Flashcards → Estudiar).

**Rango:** el caso de los cinco peldaños **falla** si la sesión se vuelve a atar a `onProduced`.
Es la guardia del P0.

## 9. Verificación

| Comprobación | Resultado |
|---|---|
| `npx tsc --noEmit` | limpio |
| `npm run test` (vitest) | **1048/1048** (109 ficheros) |
| `python -m pytest -q` (backend) | **3141/3141** |
| `python -m ruff check backend launcher` (alcance del proyecto) | limpio |
| `python scripts/check_i18n_coverage.py --strict` | **1776** cadenas, 0 huérfanas / 0 sin definir / 0 duplicadas |
| `node scripts/contrast_audit.mjs --strict` | **480 pares + 6 guardas / 0 bloqueantes** (`audit: V3.85.1-contraste-wcag`) |
| `npm run build` | correcto |
| `python scripts/validation_gate.py auto --require-dist` | **10/10** (8 gates) |
| `npx playwright test` (barrido completo, 26 ficheros) | **106 passed · 0 failed** (32 no ejecutados por los `test.skip` de proyecto, de 138 en total) |
| `python scripts/check_release_consistency.py` | OK en los 6 orígenes (`3.85.1`) |

---

## 10. Honestidad

1. **No hay motor de sesión nuevo**, igual que en `v3.85.0`: la sesión sigue reutilizando
   `WordDrill` ítem a ítem y el mismo `GET /api/learning/review`.
2. **El avance ya no exige producir, pero tampoco certifica nada.** Completar un peldaño
   reconductivo avanza la sesión y **no** deja evidencia productiva: la medición sigue siendo del
   servidor y de los peldaños que producen.
3. **El contador puede reaparecer tras una sesión completa.** Es la semántica declarada (§5), no
   un defecto: «Repasar hoy» trabaja competencia.
4. **El techo de 50 sigue sin resolverse**: la sesión larga con un clic por ítem y sin
   reanudación queda aparcada, no arreglada.
5. **El panel incrustado tiene CTA, no sesión.** El estudio sigue viviendo en Flashcards; el
   panel solo transporta.
6. **El `contrast-report.json` regenerado mide los pares existentes**: los rótulos nuevos reutilizan
   pares ya medidos. No se añaden pares nuevos por esta release.
7. **`python -m ruff check .` desde la RAÍZ del repositorio sigue reportando 1 hallazgo
   preexistente**, ajeno a esta release: `scripts/purge_virtual_testers.py:198` (`DTZ005`,
   `datetime.now()` sin zona horaria). El fichero es **idéntico al del tag `v3.85.0`** (`git diff
   v3.85.0 HEAD -- scripts/purge_virtual_testers.py` vacío), así que **no lo introduce este
   arco**; el alcance de ruff que declara el proyecto es por paquete (**`backend`** y
   **`launcher`**, cada uno con su `pyproject.toml`), y ese alcance pasa limpio. Se declara en
   vez de arreglarse en silencio: no pertenece al alcance quirúrgico de esta release.
8. **Los 8 gates humanos siguen `pending`** y `validation-evidence.json` **no existe**.

---

## Para auditar esta release

- **Ancla:** el tag **`v3.85.1`**.
- **Alcance:** `frontend/src/features/vocabulary/wordDrill.tsx`, `ReviewToday.{tsx,test.tsx}`,
  `wordDrill.test.tsx`, `frontend/src/features/routes/QuizRoutePage.tsx`,
  `frontend/src/features/vocabulary/VocabularyRoutesPractice.tsx`, `frontend/src/utils/i18n.ts`,
  `frontend/scripts/contrast_audit.mjs`, `frontend/tests/visual/reviewSession.spec.ts`,
  `frontend/tests/visual/vocabularyRoutesReview.spec.ts`, los artefactos generados y la
  documentación de release.
- **Lo que NO toca:** esquema de BD, contrato de API, endpoints, `GENERATOR_VERSION`,
  `DECISION_POLICY_VERSION`, `CURRICULUM_VERSION`, `LISTENING_BANK_VERSION`, las evaluaciones y el
  número o la definición de los gates. **No hay una sola línea de lógica de backend**
  (`backend/config.py` solo cambia `VERSION`).
- **Punto de entrada al detalle:** `docs/audit/PARKED.md §V3.85.1`, `release-notes-v3.85.0.md`
  (errata) y `docs/audit/AY-AUDITORIA-TOTAL-V385.md` (informe de la auditoría que la origina).
