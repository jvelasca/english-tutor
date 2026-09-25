# CIERRE GLOBAL V3.83.x — síntesis de la serie y readiness para la certificación

> **Naturaleza:** informe **interno** de cierre (no es un informe de auditoría externa).
> Por eso **no lleva letra**: el encargo externo de cierre reserva el prefijo **`AW`**
> (`agentes/auditoria-cierre-global-v383.md`) y su informe esperado es
> `docs/audit/AW-AUDITORIA-CIERRE-V383.md`. Este documento es la **síntesis de la casa**
> que ordena lo que el externo debe dictaminar: qué se ha verificado por comando, qué
> queda abierto y **si la serie está lista para empezar a certificar**.
> **Ancla:** tag anotado **`v3.83.1`** → commit
> **`4ee32e543e49c3a8d056d2ae36cc15c092825cf5`**.
> **Alcance:** la serie `v3.81.2..v3.83.1` como unidad de cierre, con foco en
> `v3.83.0..v3.83.1`. **Solo lectura de código:** no se ha tocado `backend/`,
> `frontend/src/` ni `launcher/`; los cambios de este cierre son **documentos**.
> **Autor:** el propio proyecto. **Fecha:** 2026-09-24.

---

## 0. Método

1. La fuente de verdad es el **código y las medidas reales**, nunca la documentación.
   Cada cifra de este informe se ha **re-ejecutado** sobre el árbol del tag.
2. Los **ocho gates** se leen del instrumento (`scripts/validation_gate.py`), no de la
   prosa: `GATES` es una tupla de **ocho** y `status --strict` exige 8/8.
3. El **inventario de deuda** se consolida desde `docs/audit/AU-AUDITORIA-TOTAL-V383.md`
   §5/§11/§12, `docs/audit/PARKED.md` (§V3.70, §V3.81.2, §V3.82.0, §V3.83.0) y
   `docs/audit/RE-GATES-DERIVA.md`.
4. Los identificadores de la serie se **resuelven con git**, no se fijan a mano
   (regla desde V3.73.5).

---

## 1. Ancla y estado de la serie

### 1.1 El árbol auditado es el del tag, congelado

```text
git rev-parse HEAD          → 4ee32e543e49c3a8d056d2ae36cc15c092825cf5  (= v3.83.1)
git diff --stat v3.83.1..HEAD                                        → VACÍO
```

El `HEAD` del árbol de trabajo **es** el commit del tag: la serie está congelada y es
reproducible.

| Tag | Commit |
|---|---|
| `v3.81.0` (ancla documental de la campaña) | `6724d8be7d563348e6626810beeb3cf0da7f5812` |
| `v3.81.2` (cierre de G0, privacidad) | `dd435144cfdde070789d97f9d3087c947565abba` |
| `v3.82.0` (contrato de sesión + migración) | `3f686a031d194974f284e590dc39746633aef6f0` |
| `v3.83.0` (producto: Diccionario → Flashcards) | `e05b3dd6a6ef531c993c3340aa921417d8cbca5d` |
| **`v3.83.1` (instrumento y honestidad)** | **`4ee32e543e49c3a8d056d2ae36cc15c092825cf5`** |

### 1.2 Qué es y qué no es `v3.83.1`

**Es un patch de instrumento y honestidad, no de producto.** Verificado por comando:

```text
git diff --stat v3.83.0..v3.83.1 -- backend frontend/src launcher scripts
  backend/config.py | 2 +-          ← la línea VERSION, y nada más
git diff --shortstat v3.83.0..v3.83.1
  20 files changed, 2990 insertions(+), 16 deletions(-)
```

El resto del diff son **pruebas visuales**, **el arnés** (`playwright.config.ts`),
**la versión** (`package.json`/`lock`) y **documentación**. Sin DDL, sin rutas nuevas,
sin bumps de `GENERATOR_VERSION` / `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION`
sigue `1.3.1`) / `LISTENING_BANK_VERSION`.

**El rango `v3.83.0..v3.83.1` tiene nueve commits**, de los cuales **ocho ya estaban en
`main`** (6 `docs(audit)` + 2 `test(visual)`) y el noveno es el release. Esa absorción
**resuelve H4** (el cambio de arnés posterior al tag **ya dentro del tag**).

### 1.3 Estado de publicación y CI

```text
gh run list --commit 4ee32e543e49c3a8d056d2ae36cc15c092825cf5
  → 36042834375  CI  push  main  conclusion=success
gh run list --commit 3f686a031d194974f284e590dc39746633aef6f0   (v3.82.0)
  → (ninguna)
```

- **El CI no dispara en tags** (`.github/workflows/ci.yml` escucha `push: branches:
  [main]` y `pull_request`). La run que certifica el commit del tag `v3.83.1` es la del
  **push a `main`**: **`36042834375`, verde**.
- **Contraste con `v3.82.0`:** su commit de tag **no tiene ninguna run** —la Release se
  publicó 67 s después del commit y la primera run que llegó cubrió a su hijo—. Ese
  hallazgo (`AV` §1.1-9 / §1.4) **no lo resuelve este parche**: lo deja a la vista.

### 1.4 Estado verificado por comando (medidas reales)

| Comprobación | Comando | Resultado |
|---|---|---|
| Instrumento automático | `validation_gate.py auto --require-dist` | **10 pass · 0 fail · 0 skip** |
| Gates | `validation_gate.py status` | **8 gates, los 8 en `pending`** |
| Evidencia física | `Test-Path docs/audit/validation-evidence.json` | **NO EXISTE** |
| Consistencia de versión | `check_release_consistency.py` | **OK en los 6 orígenes** (`3.83.1`) |
| i18n `--strict` | `check_i18n_coverage.py --strict` | **1772** definidas · **0** sin uso · **0** sin definir · **0** duplicadas · **0** vacías |
| Candado de 8 gates | `test_docs_drift_v373.py:183` | `assert len(GATES) == 8` |
| H1 vivo | `retention.py` ~185 | `return not owner or owner == user_id` |
| `without_password` (BD de uso) | consulta `mode=ro` | **2** (`J.A`, `Paz`) |
| `frontend/dist` | fecha de `assets/` | **24/09 13:53**, anterior a `3.83.1` (desfase declarado) |
| Backend | `ruff check .` + `pytest tests/ -q` | **ruff limpio** · **3122 passed** |
| Lanzador | `ruff check .` + `pytest tests/ -q` | **ruff limpio** · **269 passed** |
| Frontend (unitarios) | `npm run test` (vitest) | **1033 passed** (109 ficheros) |
| Frontend (visual) | `npx playwright test` (barrido **completo**) | **86 passed · 28 skipped** |
| H2 muerde | `reducedMotionAndZoom.spec.ts` | `page.emulateMedia` + guarda `matchMedia(...).matches === true` |

---

## 2. Los ocho gates — tabla de readiness

Puerta real de V4.0: `validation_gate.py status --strict` debe salir **0** (8/8 en
`pass`); la puerta fuerte `--strict --same-tree` exige además que la evidencia sea del
**mismo commit**. Hoy **no hay ningún `record`**.

| Gate | Qué exige | Precondición que falta | Tipo de bloqueo | Estado |
|---|---|---|---|---|
| **G0** `identidad-cuentas` | E2E de cuentas verde sobre copia + ninguna cuenta pendiente de activación sin invitación entregada | Ejecutar `backend/scripts/migrate_legacy_accounts.py` sobre la BD de uso (**2** pendientes) | **Acción de uso** (no código) | `pending` |
| **G1** `offline-fisico` | Los 12 flujos con Wi-Fi **y** Ethernet desconectados | Corte de red **físico** | Hardware/red | `pending` |
| **G2** `maquina-limpia` | Instalación desde cero en clon/VM | Una máquina o VM **físicamente limpia** | Hardware | `pending` |
| **G3** `launcher-windows` | Launcher en Windows real: HTTPS, navegador, micro, TTS, STT, chat, persistencia | Windows real + micrófono + altavoces | Hardware | `pending` |
| **G4** `dispositivos` | Matriz de móvil/tablet sobre la LAN | Dispositivos reales + certificado aceptado | Hardware | `pending` |
| **G5** `audio-stt-tts` | Grabación/transcripción y reproducción reales + aviso de voz degradada | Micro y altavoces reales | Hardware | `pending` |
| **G6** `journeys` | Los 12 recorridos de la UI de principio a fin | Un perfil con datos + una persona | Persona | `pending` |
| **G7** `pedagogia` | Auditoría final del contenido (9 instrumentos ya generados) | Lectura humana de la matriz de G7 | Persona (lectura) | `pending` |

**Lectura de la tabla.**

- **Los ocho son de acción humana** (`Gate.human = True` en los ocho): el instrumento
  **no ejecuta** ningún flujo de la app. Ninguno es simulable con honestidad en CI.
- **Siete exigen hardware o una sesión de campo larga** (G1–G7).
- **G0 es el único que no exige hardware**: exige una **decisión de uso** —ejecutar la
  migración heredada y entregar credenciales—. Su `pending` es **operativo**, no
  técnico: entrar sin contraseña está cerrado **por construcción**
  (`403 ACCOUNT_NOT_ACTIVATED`).
- **Ningún gate puede declararse `pass` sin `record`**, y un `pass` sin `head_sha`
  **no se registra**. `--same-tree` **no puede** cerrarse hoy: no hay evidencia que
  comparar.

---

## 3. Inventario consolidado de deuda (P1/P2/P3)

Reúne lo que hoy está disperso, con su origen, su evidencia y su destino.

### 3.1 Deuda de la serie V3.83.x

| ID | Sev | Qué es | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| **H1** | **P2** | El guardia de colecciones acepta un **pack global** como destino de ingestión: `return not owner or owner == user_id`; un cliente no-UI podría inyectar palabra/traducción en el catálogo compartido | `backend/domain/retention.py` ~185; `AU §5-H1` y §12 | Para **ingestión**: `return bool(owner) and owner == user_id`, o predicado con modo `read`/`enroll` vs `ingest`, más un caso en el candado de superficie pública | **Vivo**, aparcado en `AU §12` |
| **H5** | **P2** | `add_item` **no atómico**: `seed_study_items` (léxico, ya comprometido) y después membresía/FSRS; si un paso falla, la UI dice «No se pudo añadir» cuando la palabra **ya está** en el léxico | `backend/domain/retention.py::add_item`; `AU §5-H5` | Envolver en una transacción, o degradar el mensaje a «se añadió al diccionario; la lista no se pudo actualizar» | Abierto |
| **H3** | **P3** | El cierre de sesión muestra **siempre** `Sparkles` junto a «0 % …» si todas fueron «Again» | `AU §5-H3` | Condicionar el icono a `good > 0` | Abierto, cosmético |
| ~~**H4**~~ | ~~P2~~ | Cambio de arnés (`fd086e8`) posterior al tag **sin tag propio** | `AU §5-H4` | — | **Resuelto de facto**: `v3.83.1` **absorbe** ese commit dentro del tag (§1.2) |
| **H2** | P2→**cerrado** | El gate `reduced-motion` **emulaba en vacío** (`test.use({ reducedMotion })` no es opción válida en Playwright 1.62) | `AU §5-H2`; `reducedMotionAndZoom.spec.ts` | Corregido con `page.emulateMedia` + guarda `matchMedia` | **Cerrado en `main` y etiquetado en `v3.83.1`** |

### 3.2 Deuda de auditoría de la serie

| ID | Sev | Qué es | Evidencia | Nota |
|---|---|---|---|---|
| **D1** | **P1** | El arco `v3.81.2..v3.82.0` —el que **cambia el contrato de `POST /api/session` y migra la BD**— tiene **encargo (`AV`) pero no informe** | `agentes/auditoria-total-externa-v382.md`; `docs/audit/AV-AUDITORIA-TOTAL-V382.md` **no existe** | Es la mayor deuda de auditoría de la serie |
| **D2** | **P2** | El commit de tag de `v3.82.0` **no tiene ninguna run de CI** | `AV` §1.1-9 / §1.4 | `v3.83.1` sí la tiene (contraste) |

### 3.3 Deuda heredada (mantenimiento y pedagogía)

| ID | Sev | Qué es | Evidencia | Destino |
|---|---|---|---|---|
| **E6/H6** | **P2** | **12 PRs de Dependabot** abiertos (`#7`–`#18`). `#10` (`react`/`react-dom` desparejados) y `#13` (`vite` 8 no instalable por peer de `@vitejs/plugin-react` 4.x) **siguen rojos**; los **diez** restantes **sin dictaminar** | `gh pr checks 10` / `13`; `AU §11` | Mantenimiento: agrupar `#10`/`#13` y dictaminar los demás |
| **Pedagogía V3.70** | **P1–P2** | La cola de `PARKED.md §V3.70` (1 P0 · **15 P1** · **12 P2** · 5 P3). El **P0** se cerró en `V3.75.1`; varios P1/P2 se cerraron después | `docs/audit/PARKED.md §V3.70` | Reconciliar contra el árbol actual antes de cerrar **G7** |
| **Cola V3.71 (RE)** | **P2/P3** | `RE-06` (deuda aceptada): `BETA_GATES.md` sigue fechado `2026-08-31` · `2.0.0` — es histórico con anotaciones | `docs/audit/RE-GATES-DERIVA.md` | Aceptado |

### 3.4 Discrepancias verificadas y resueltas

- **`without_password`: 3 vs 2.** `PARKED.md §V3.81.2` dice **3** (`J.A` ×2 y `Paz`);
  `V3.82.0` dice **2**. La consulta **en vivo** da **2** (`J.A`, `Paz`): la cifra **3**
  era correcta **para su fecha** (existía una fila duplicada/posteriormente consolidada)
  y **no es una deriva viva**. La cifra vigente es **2**.
- **`frontend/dist` desfasado.** `PARKED.md §V3.83.0` declara que no se reconstruyó en
  esa release; los `assets/` en disco son del **24/09 13:53**, anteriores a `3.83.1`.
  `check_dist_artifact` solo comprueba que el `index.html` sea servible, así que
  `--require-dist` **pasa** sin decir de qué versión es el artefacto. **Deuda `P3`
  declarada.**

---

## 4. Dictamen de readiness

### 4.1 Lo que **BLOQUEA** empezar la certificación

1. **La campaña física no se ha ejecutado.** Los **ocho** gates siguen `pending` y
   `validation-evidence.json` **no existe**: no hay un solo `record`. Es el bloqueo
   principal y es **por definición**: la certificación de V4.0 exige **8/8** en `pass`
   contra el mismo commit.
2. **El ancla de certificación está desfasada.** El árbol congelado de la campaña sigue
   siendo **`v3.81.0`**, pero desde entonces se publicó **producto que cambia el
   contrato de sesión y migra la BD** (`V3.82.0`) y **producto de UI** (`V3.83.0`).
   Antes de la primera sesión hay que **re-anclar** (§5) y re-derivar lo que proceda.
3. **Falta el informe `AV`.** El único arco que **retira** una ruta de registro,
   **despublica** un listado, **elimina** la entrada sin contraseña y **cambia** la
   forma de `POST /api/session` sigue **sin dictamen externo**.

### 4.2 Lo que **NO** bloquea (deuda aceptada)

- **H1** (`P2`): heredado (`V3.77.1`), **no alcanzable desde la UI** (el selector filtra
  a `user_list` y está fijado por E2E), con corrección de una línea recomendada y viva.
- **H5** (`P2`): el modo de fallo es del **lado seguro** para la promesa (nunca hay
  «archivada que no se estudia»); es un problema de **mensaje**, no de estado.
- **H3** (`P3`): cosmético.
- **H4**: **resuelto**.
- **Dependabot** (`P2`): PRs **abiertos**, no ramas mergeadas; no alcanzan a la app
  publicada.
- **Cola pedagógica V3.70** (`P1–P2`): se cierra **dentro** de G7, no antes; el gate ya
  cubre la revisión del contenido.

### 4.3 Veredicto

> **La serie V3.83.x está lista para EMPEZAR la certificación, no para declararla.**
>
> La instrumentación queda **congelada y honesta**: `v3.83.1` corrige el gate vacuo
> (H2), cierra la contradicción documental (E5/i), aparca H1 con su severidad y
> **etiqueta por fin un árbol reproducible**. El producto de la serie está dictaminado
> en `AU` y el arco crítico tiene **encargo**.
>
> Lo que falta **no es código ni producto**: es **ejecutar** los ocho gates sobre un
> árbol **re-anclado**, y **obtener el informe `AV`**. Recomendación: **congelar la rama
> de instrumentación** (no abrir `3.83.2`/`3.83.3` por cuestiones menores), **re-anclar
> la campaña a `v3.83.1`** y arrancar la primera sesión de campo.

---

## 5. Re-anclaje de certificación

**El árbol que se certifica pasa a ser el de `v3.83.1`**, no `v3.81.0`.

**Por qué.** La campaña tiene **0 `record`**, así que **no hay nada que invalidar**
(`--same-tree` no puede marcar evidencia «de otro árbol» porque no hay evidencia). Y el
ancla **debe** incluir **toda la instrumentación**: el arreglo de H2 (el gate
`reduced-motion` que ahora **muerde**) y las tres sondas visuales nuevas viven **dentro**
del tag `v3.83.1`, no en `v3.81.0`. Certificar sobre el árbol viejo probaría un arnés
que ya se sabe **vacuo**.

**Qué hay que leer antes de la primera sesión.**

- **El contrato de la API cambió** respecto a `v3.81.0`: `POST /api/session` exige
  `{email, password}` (401 genérico / 403 `ACCOUNT_NOT_ACTIVATED`), `PUT
  /api/session/pin` **se retiró** y existe el ciclo de activación/recuperación.
- **`G0` depende de una acción de uso:** reducir `without_password` a **0** ejecutando
  la migración heredada, no de código.
- **La evidencia se sella con el `HEAD` real** en el momento de grabar, no con una fila
  fija: `head_sha` + `--ci-run` dentro de `validation-evidence.json`.
- **Se re-derivan** los dossiers de G7 si el diff de producto los mueve (los instrumentos
  del dossier no leen cuentas ni UI, pero la comprobación se hace, no se argumenta).

---

## 6. Declaraciones de honestidad

- **`v3.83.1` no arregla el producto:** etiqueta el árbol y cierra la letra; el único
  cambio en `backend/` es `VERSION` y `frontend/src`/`launcher/` están intactos.
- **El diff del tag incluye los ocho commits que ya estaban en `main`** (6 `docs(audit)`
  + 2 `test(visual)`), no solo el commit de release.
- **H1 sigue vivo en el código.** Esta serie lo **sitúa** fuera de un patch de
  instrumento; **no** lo rebaja ni lo cierra.
- **Los ocho gates siguen `pending`** y `validation-evidence.json` **no existe**: no hay
  ninguna aprobación física que la serie pueda estar blanqueando.
- **El CI no dispara en tags:** la run que certifica el commit del tag es la del push a
  `main` (`36042834375`, `success`); `v3.82.0` **no tiene ninguna**.
- **El ancla de certificación está desfasada** (`v3.81.0`) y eso **no lo arregla** un
  parche de instrumento: es una decisión de cierre (§5).
- **Lo que NO he hecho:** no he cerrado gates, no he recreado tags, no he tocado
  `backend/` ni `frontend/src/` ni la base de datos, y **no he corregido H1** aunque la
  corrección sea de una línea: este cierre es de **lectura y documentación**.

---

## 7. Reproducir / verificar

```powershell
# ancla y candado
git rev-parse 'v3.83.1^{commit}'
git log --oneline v3.83.0..v3.83.1
git diff --stat v3.83.1..HEAD -- backend frontend/src launcher scripts   # VACÍO
git diff --stat v3.83.0..v3.83.1 -- backend frontend/src launcher scripts # solo config.py

# instrumentos
backend\.venv\Scripts\python.exe scripts\validation_gate.py status
backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict
python scripts\check_release_consistency.py
python scripts\check_i18n_coverage.py --strict
Test-Path docs\audit\validation-evidence.json            # False

# estado por gate (lo que falta registrar)
Select-String -Path backend\tests\test_docs_drift_v373.py -Pattern 'len\(GATES\) == 8'

# la prueba de que H1 es real (lectura, no ejecución)
python -c "print('retention.py:185 -> return not owner or owner == user_id')"

# CI del commit del tag (la del push a main, no del tag)
gh run list --commit 4ee32e543e49c3a8d056d2ae36cc15c092825cf5
```

---

## 8. Tests y candados que respaldan

- `backend/tests/test_docs_drift_v373.py:183` — **ocho** gates (`len(GATES) == 8`).
- `backend/tests/test_validation_gate_v373.py` — el instrumento: `pass` sin `head_sha`
  se rechaza; estados y gates desconocidos se detectan.
- `frontend/tests/visual/reducedMotionAndZoom.spec.ts` — H2: `page.emulateMedia` +
  guarda `matchMedia(...).matches === true` (el gate **muerde**).
- `frontend/tests/visual/dictionaryFlashcardsBridge.spec.ts`,
  `studySessionKeyboard.spec.ts`, `studySessionVisual.spec.ts` — evidencia nueva de `AU`
  §6, etiquetada en `v3.83.1`.
- `backend/tests/test_public_surface.py` — la superficie sin sesión **pinada** (candado
  del arco `v3.82.0`).

---

## Anexo — Encargo externo de cierre

- **Entrada:** `agentes/auditoria-cierre-global-v383.md` (prefijo **`AW`**).
- **Informe esperado:** `docs/audit/AW-AUDITORIA-CIERRE-V383.md`.
- **Prefijos reservados:** `AP`, `AQ`, `AR`, `AS`, `AT`, `AU` (dictaminado), `AV`
  (pendiente), **`AW`** (este).
