# Release notes — English Tutor v3.73.2

**Fecha:** 2026-09-17 · **Tipo:** release de **PARCHE correctiva** (corrige la CI de
V3.73.1; **sin** capacidad pedagógica nueva y **sin** cambios de producto) ·
**Versión de app:** `3.73.1 → 3.73.2`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el banco y SIN tocar el currículum.** El
backend de producto, el frontend de producto y el launcher están **intactos**: el
diff es **tests e instrumento de auditoría del backend** más bookkeeping
documental. El contenido funcional de esta línea sigue siendo el de V3.73.1.

---

## Qué es esta release

V3.73.1 se publicó —commit `59e731d`, tag `v3.73.1`— con **la CI en rojo**: 10 de
sus 11 jobs verdes y **`Backend (ruff + pytest)` fallando** (`1 failed, 2775
passed`). V3.73.2 la pone verde **reapuntando el invariante que la propia §6 de
V3.73.1 rompió**, y deja escrito el fallo de proceso que lo permitió.

**Lo que NO hace:** no toca producto (ni backend, ni frontend, ni launcher), no
abre arquitectura, no cierra la matriz de visual regression y **no cierra los 7
gates físicos**, que siguen `pending` por diseño (`status --strict` sigue **rojo**).

---

## 1 · El fallo (y por qué la verificación local no lo vio)

`backend/tests/test_ped_coverage_v370.py::test_reading_has_no_dedicated_scorer`
cierra la asimetría declarada de `reading` —contenido y **UI sí**, scorer propio y
corpus no— y lo hacía con:

```python
assert (FRONTEND_FEATURES_DIR / "reading").is_dir()
```

La §6 de V3.73.1 ordenó borrar `frontend/src/features/reading/ReadingPractice.tsx`.
Ese borrado dejó el **directorio vacío**… y **git no versiona directorios vacíos**.
La consecuencia es exactamente la peor posible para una verificación:

| Dónde | ¿Existe `frontend/src/features/reading/`? | Resultado |
|---|---|---|
| Disco del autor (donde se corrió la suite) | **Sí** (vacío, invisible a git) | **2779 passed** |
| Checkout limpio (CI, `actions/checkout`) | **No** | **1 failed, 2775 passed** |

La comprobación local **no era insuficiente por falta de tests: era
estructuralmente incapaz de verlo**. Ninguna repetición de la suite en ese disco
habría cambiado el resultado, y por eso el fallo lo encontró la CI y no yo. La
autoridad para un invariante que depende de **rutas del árbol** es un **checkout
limpio**, no el árbol de trabajo.

## 2 · El reapunte (no un debilitamiento)

Desde la Opción A de V3.73.1, la UI de `reading` **ya no es un directorio de
feature**: es el **chat con destreza** `/chat/lectura`. El invariante que importa
(«reading declara objetivos, checks y UI, sin scorer propio ni corpus») se
mantiene; lo que cambia es **dónde se comprueba**:

- **`backend/scripts/audit_dossier.py`.** `MODALITY_ARTIFACTS["reading"]["ui"]`
  pasa a **`chat:lectura`** y la existencia se resuelve con la tabla explícita
  **`UI_ARTIFACT_PATHS`** (tipo + ruta) en vez de asumir que todo artefacto de UI
  es un directorio de `frontend/src/features`. Los **otros 8 artefactos** de UI
  conservan **exactamente** el `is_dir()` de antes: el cambio es un *override*
  declarado, no un aflojamiento del chequeo general.
- **`backend/tests/test_ped_coverage_v370.py`.** En vez de mirar la existencia de
  un directorio, comprueba el **cableado real** —`frontend/src/router/chat.ts`
  declara `reading: "lectura"` (tolerante a formato con `re.search`)— y que el
  **dossier generado siga viendo esa UI** (`ui_exists true`), manteniendo
  `scorer_exists false` y `corpus 0`. Es más específico que antes: si alguien
  quita `reading` del router de chat, el test falla; un directorio vacío ya no
  puede satisfacerlo.

## 3 · Dossier

`docs/audit/generated/skill-coverage.{json,md}` **regenerados**:

```diff
-   "ui_feature": "reading",
+   "ui_feature": "chat:lectura",
    "ui_exists": true,
```

Solo cambia la **procedencia** de la UI. `ui_exists` sigue `true` y **no** aparece
el gap espurio `reading → «sin feature de UI»` que habría salido sin reapuntar el
instrumento (o sea: sin el reapunte, el dossier habría empezado a declarar un
hueco **falso**). `docs/audit/AB-PED-COBERTURA.md` actualiza la evidencia del
hallazgo 4 con la ubicación nueva.

---

## Verificación (lo que se ejecutó)

```powershell
# Backend, en un CHECKOUT LIMPIO de verdad (git worktree, sin el directorio vacío)
# y en el commit del reapunte (el commit de release solo añade bookkeeping)
git worktree add <tmp> aa5c705
cd <tmp>\backend
..\..\...\.venv\Scripts\python.exe -m pytest tests/ -q      # 2776 passed, 3 skipped (2779 casos)
..\..\...\.venv\Scripts\python.exe -m scripts.audit_dossier skill-coverage
git status --short                                           # vacío: el dossier es estable

# Frontend (sin cambios de producto: se corre igualmente por higiene)
cd frontend
npx tsc --noEmit                                             # limpio
npx vitest run                                               # 712 passed (85 ficheros)
npm run audit:contrast                                       # 0 fallos bloqueantes + 2 guardas
npm run build                                                # OK

# Gates del repo (raíz)
backend\.venv\Scripts\python.exe -m ruff check .              # limpio (backend)
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py       # 6 orígenes (3.73.2)
backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py --strict    # 0/0/0
backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist  # 10/10
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict      # exit 1 (correcto)
```

**Nota de proceso:** la verificación de esta release se hace sobre un **checkout
limpio** precisamente porque el fallo que corrige era invisible en el árbol de
trabajo. Repetir la suite en el disco del autor no habría demostrado nada.

---

## Honestidad

- **El error fue mío y de método, no de los tests.** La suite local dijo
  `2779 passed` sobre un árbol que ya no era el que se iba a publicar. Un
  invariante que depende de la **existencia de rutas** solo se puede verificar en
  un checkout limpio; dar por bueno el árbol de trabajo fue el fallo.
- **V3.73.1 queda en el historial con su CI roja.** No se reescribe el tag
  publicado `v3.73.1`: se corrige hacia delante con V3.73.2, y las notas de
  V3.73.1 llevan su corrección anotada.
- **Esto no reabre V3.73.1.** El contenido funcional del cierre GUI sigue siendo
  el de V3.73.1; lo que cambia es **dónde se mide** un invariante de cobertura.
- **Los 7 gates siguen en `pending`.** `status --strict` sigue saliendo **1** y
  esa sigue siendo la puerta real de V4.0. El código sigue **congelado**.

## Criterio de V4.0 (sin cambios)

V4.0 se declara cuando `validation_gate.py status --strict` salga **0**: los 7
gates en `pass`. El siguiente hito sigue donde siempre estuvo: **ejecutar
físicamente G1–G7**.
