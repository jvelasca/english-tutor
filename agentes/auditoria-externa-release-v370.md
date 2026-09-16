# Auditoría EXTERNA de RELEASE de V3.70 — punto de entrada (listo para lanzar)

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **`v3.70.0` ya
> publicada**, no un plan. La revisión es **de solo lectura**: no se cambia código,
> datos, configuración ni etiquetas publicadas.
>
> **Por qué una auditoría de RELEASE y no de diseño.** A diferencia de V3.69,
> **V3.70 no tuvo auditoría de diseño externa**: su briefing maestro
> (`agentes/v370-auditoria-pedagogica.md`) la declaró **entrega interna** por
> decisión de alcance (regla dura: *V3.70 es una auditoría, no una release de
> capacidad; solo medición*). Este documento cubre el hueco: audita **lo
> entregado**, es decir la diferencia entre «la medición es correcta» y «lo
> publicado demuestra lo que dice demostrar».
>
> **Estado:** entregado 2026-09-16. **Informe esperado:**
> `docs/audit/AG-AUDITORIA-RELEASE-V370.md` (los prefijos `AA`–`AF` los ocupan los
> seis dossiers de la propia V3.70; `AG` evita colisión y mantiene la trazabilidad
> del mismo incremento).

## Punto de entrada

- Repositorio: `jvelasca/english-tutor` (**público**), rama `main`.
- **Release auditada:** commit **`9ba9c49`** (`release(v3.70.0): auditoria
  pedagogica + CEFR`) con el **tag anotado `v3.70.0`** (objeto `219038f…`, apunta
  a `9ba9c49`).
- **Cierre documental posterior** (no toca código): `2db93ba` (`docs(v3.70.0):
  cuantificar la deriva de formato…`) y `f93499d` (`docs(v3.70.0): registrar el
  cierre…`). El **HEAD documental** puede ser posterior; **el objeto de esta
  auditoría es el tag `v3.70.0`**.
- **Base de comparación:** `v3.69.0` → release `9a4e70a`, tag `v3.69.0`, cierre
  documental `8b41d7d`/`bded470`/`1e1f9b0`.
- **CI:** el push llevó juntos el commit de release y su documentación, así que
  **no hay run separado de `9ba9c49`**; el run que lo contiene es el del HEAD
  `2db93ba`, **6/6 verde** en
  [run 35062382562](https://github.com/jvelasca/english-tutor/actions/runs/35062382562)
  — `Content validation` `104685242134` · `Frontend (tsc + vitest + build)`
  `104685242332` · `Playwright E2E` `104685242381` · `Beta V3.0 gate`
  `104685242384` · `Release consistency` `104685242411` · `Backend (ruff +
  pytest)` `104685242419`. El commit de cierre documental `f93499d` salió 6/6 en
  [run 35062997777](https://github.com/jvelasca/english-tutor/actions/runs/35062997777).
  **El auditor debe comprobar los números en la API de GitHub y distinguir lo que
  es resultado del run de lo que sigue siendo declaración del release.**
- **Los números de línea citados** corresponden al árbol publicado en `v3.70.0`
  (los commits posteriores son solo documentales).

**Artefactos nuevos de la release (objeto de la auditoría):**

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `backend/scripts/audit_dossier.py` (**+1033 líneas**) | **Cinco subcomandos NUEVOS de SOLO LECTURA** (`cefr-adequacy`, `skill-coverage`, `feedback-coverage`, `mastery-claims`, `assessment-instruments`) | Que la pedagogía del contenido y de los instrumentos está **medida de forma determinista y regenerable**, sin tocar `data/` ni `curriculum/` |
| `backend/tests/test_ped_*_v370.py` (**5 ficheros, 48 tests**) | `content_cefr` (8), `coverage` (10), `feedback` (10), `mastery` (10), `instruments` (10) | Que cada hallazgo está **pinneado**: quien cierre un hueco **rompe el test** y obliga a re-auditar el eje |
| `docs/audit/AA-PED-CONTENIDO-CEFR.md` … `AE-PED-INSTRUMENTOS.md` | Cinco dossiers de eje, con el formato de `docs/audit/TEMPLATE.md` | Cada hallazgo con severidad, evidencia `archivo:línea` y comando de reproducción |
| `docs/audit/AF-SINTESIS-PEDAGOGICA-V370.md` | Síntesis | **1 P0 · 15 P1 · 12 P2 · 5 P3** (33 hallazgos) y **4 propiedades positivas** |
| `docs/audit/generated/*.{md,json}` (**10 pares**) | Salida regenerable de los 10 subcomandos (5 viejos + 5 nuevos) | Determinismo byte a byte y **corrección de la deriva** de `curriculum-stats` (C1 = 20, C2 = 20) |
| `release-notes-v3.70.0.md` | Nota de release | Alcance, tabla de 33 hallazgos con severidad/fase y §«Honestidad» |
| `docs/RELEVO.md` (nota de cabecera + «0. START HERE»), `CHANGELOG.md` `[3.70.0]`, `PLAN.md` | Relevo y coherencia | Estado, verificación, **CIERRE** con el run id |

## Alcance y enfoque

1. **Falsar el alcance del diff.** La release afirma **cero líneas de LÓGICA de
   producto**: el único diff fuera de tests/documentación son los **bumps de
   versión** y los **cinco subcomandos de medición**. Comprobarlo; cualquier línea
   de lógica de producto (motor, scorer, currículum, banco, política, UI) es
   **hallazgo P1**.
2. **Validar los instrumentos como MEDICIÓN, no como ruta de producto.**
   `audit_dossier.py` escribe **solo** en `docs/audit/generated/`; ¿es cierto que
   **nunca** escribe en `data/` ni en `curriculum/`? ¿El instrumento **duplica**
   constantes del motor (p. ej. `REFERENCE_BANDS`) que podrían derivar de las del
   producto, invalidando la medición sin que nadie lo note?
3. **Validar los 48 tests como DEMOSTRACIÓN, no como inventario.** ¿Cada test
   fallaría si el hallazgo no se cumpliera? ¿Hay alguno **tautológico**: que afirme
   sobre un valor que el propio test calcula con la misma función que se audita, o
   que compare una constante consigo misma? La regla declarada es que **un test
   falla al cerrar el hueco** (p. ej. corregir el sesgo posicional rompe
   `test_mc_position_bias_of_curriculum_checks_is_declared`): fijar al menos **un
   caso** y dictaminar si es real o decorativo.
4. **Auditar la honestidad del P0 y de las 4 propiedades positivas.** El P0
   (329/368 checks con la correcta en la **posición 0**) es una afirmación
   fuerte; ¿está bien clasificada como **contenido** y no como defecto del motor?
   ¿Las 4 propiedades declaradas «limpias» resisten, o son cherry-picking?
5. **Verificar la corrección de la deriva documental.** ¿`curriculum-stats`
   declara hoy C1 = 20 y C2 = 20 objetivos reales, y son ciertos?
6. **Comprobar que no se toca política, contenido ni motor**:
   `DECISION_POLICY_VERSION`, los tres `GENERATOR_VERSION`, la carpeta
   `backend/curriculum/` y `backend/repositories/db.py`.
7. **Comprobar la coherencia con las auditorías `X`/`Y`**: que V3.70 **no
   contradiga** sus veredictos ni convierta en «cerrado» ningún P2/P3 sin
   evidencia, y que **no cierre ningún P** de la auditoría de V3.69 (los 6 P2
   siguen abiertos por decisión de alcance).
8. **Comprobar la coherencia documental y de cierre**: tag, commit, CI, nota de
   `docs/RELEVO.md`, `CHANGELOG.md`, `release-notes-v3.70.0.md`.

**No se audita:** el diseño del motor adaptativo (ya auditado en `Y`) ni el plan
de V3.70 (no tuvo auditoría de diseño). No se pide re-implementar nada: el
resultado esperado es un **dictamen**, no un rediseño.

## Afirmaciones a falsar

Cada punto trae **cómo comprobarlo** y **qué resultado lo falsaría**.

1. **Cero lógica de producto.**
   `git diff v3.69.0 v3.70.0 --stat -- backend frontend ':!backend/tests' ':!frontend/tests'`
   → **4 ficheros**: `backend/config.py` (1 línea, `VERSION`),
   `backend/scripts/audit_dossier.py` (**+1033**, los cinco subcomandos de
   medición), `frontend/package.json` y `frontend/package-lock.json` (bumps).
   *Falsado por*: cualquier otra línea de producto.
2. **SIN migración.** `git diff v3.69.0 v3.70.0 -- backend/repositories/db.py`
   **vacío** y **ningún** `CREATE TABLE`/`ALTER TABLE` nuevo respecto a V3.69.
3. **Contenido y política intactos.**
   `git diff v3.69.0 v3.70.0 -- backend/curriculum` **vacío**;
   `git diff v3.69.0 v3.70.0 -- backend/services backend/routers backend/domain
   backend/repositories` **vacío**; `DECISION_POLICY_VERSION = "v3.68.0"`
   (`backend/repositories/decision_records.py:61`) y los tres `GENERATOR_VERSION`
   (`services/dictionary_content.py:74` = `"1.4.0"`,
   `services/listening_generate.py:35` = `"1.0.0"`,
   `services/speaking_generate.py:30` = `"2.0.0"`) **sin diff**.
4. **Los cinco subcomandos son de SOLO LECTURA.** El único escritor del script es
   `_write_generated` (`backend/scripts/audit_dossier.py:279-285`), que escribe en
   `GENERATED_DIR = REPO_DIR/"docs"/"audit"/"generated"` (línea 42). *Falsado por*:
   cualquier `open(..., "w")`, `write_text`, `mkdir`, `unlink`, `shutil` o similar
   con destino en `data/` o `curriculum/`, o cualquier escritura fuera de
   `docs/audit/generated/`.
5. **Determinismo byte a byte.** Re-ejecutar los **10 subcomandos** deja
   `docs/audit/generated/` **sin cambios** (`git status --porcelain
   docs/audit/generated` vacío). *Falsado por*: un solo byte distinto (reloj,
   `hash()` aleatorio, orden no determinista).
6. **Los 48 tests existen y son 48.** `Select-String "^def test_"` por fichero →
   8 + 10 + 10 + 10 + 10. *Falsado por*: conteo distinto. Y **cada uno fija un
   hallazgo medido**, no una intención.
7. **El P0 del sesgo posicional es real y reproducible.**
   `python -m scripts.audit_dossier mc-bias` y `cefr-adequacy` → **329/368 checks
   del currículum con la correcta en la posición 0** (~89,4 %), frente a un corpus
   de listening equilibrado (~25 % por posición). *Falsado por*: una cifra
   distinta o un cálculo que mida otra cosa.
8. **La deriva de `docs/audit/generated/` quedó corregida.**
   `curriculum-stats` declara hoy **C1 = 20** y **C2 = 20** objetivos, no 14 y 14.
9. **Ningún test depende de red ni de modelos externos.** La batería completa
   corre sin Ollama, Whisper ni Piper (`docs/PREMISAS.md` premisa 12). *Falsado por*:
   una llamada de red o un modelo descargado en un test de los 48.
10. **Los números del CI salen del run, no del propio incremento:** Backend →
    `2598 passed, 2 skipped, 1 warning` (job `104685242419`; los 2 `skipped` son
    `test_stt_asr_integration.py`, opt-in de Whisper no descargado en el runner);
    Frontend → **76 ficheros / 659 tests** + `build` (job `104685242332`);
    Playwright → **25 passed + 26 skipped** (job `104685242381`); ruff
    `All checks passed!`; Release consistency **3.70.0**. En local el mismo árbol
    da **2600 passed** (2598 + los 2 skipped).
11. **Coherencia documental:** `python scripts/check_release_consistency.py` →
    `OK: Release consistency (3.70.0) en todos los orígenes`; `docs/RELEVO.md`
    lleva la nota de V3.70 con su bloque **CIERRE (2026-09-16)**; `CHANGELOG.md`
    la entrada `[3.70.0]`; `release-notes-v3.70.0.md` la tabla de 33 hallazgos.
12. **V3.70 no cierra ningún P.** Los **6 P2 de la auditoría de V3.69** siguen
    abiertos (declarado en la release note y en `docs/audit/PARKED.md`), y los 33
    hallazgos de V3.70 quedan **asignados a fase**, no corregidos.

## Cómo reproducir (comandos exactos)

```powershell
# Instrumentos de medición (regeneran docs/audit/generated/; comparar con git)
cd backend
python -m scripts.audit_dossier corpus-stats
python -m scripts.audit_dossier curriculum-stats
python -m scripts.audit_dossier speaking-stats
python -m scripts.audit_dossier mc-bias
python -m scripts.audit_dossier cefr-adequacy
python -m scripts.audit_dossier skill-coverage
python -m scripts.audit_dossier feedback-coverage
python -m scripts.audit_dossier mastery-claims
python -m scripts.audit_dossier assessment-instruments
# (el subcomando `sample` requiere --bank/--level)

# Puerta de lint del CI + batería nueva + suite completa + gate de transferencia
python -m ruff check .                                  # All checks passed
python -m pytest tests/test_ped_content_cefr_v370.py tests/test_ped_coverage_v370.py `
  tests/test_ped_feedback_v370.py tests/test_ped_mastery_v370.py tests/test_ped_instruments_v370.py -q
python -m pytest tests/ -q                              # 2600 passed (local)
python -m scripts.transfer_validation                    # OK=True

# Frontend
cd ..\frontend
npx tsc --noEmit                                        # OK
npm test                                                # 76 ficheros / 659 tests
npm run build                                           # OK

# Gates de script
cd ..
python scripts/check_release_consistency.py              # OK (3.70.0)
python scripts/check_beta_v3.py                          # OK
cd backend; python scripts/content_validation.py         # OK=True quality=True

# Alcance del diff (deben salir SOLO los bumps + audit_dossier.py)
cd ..
git diff --stat v3.69.0 v3.70.0 -- backend frontend ':!backend/tests' ':!frontend/tests'
```

**Aviso que el proyecto declara en vez de esconder** (§«Honestidad sobre la
verificación» y §«Deriva de formato» de `release-notes-v3.70.0.md`, y aquí se
ofrece al auditor como material de dictamen):

- **Deriva de formato, medida (no estimada):** `ruff format --check .` sobre
  `backend/` reporta **317 de 377 ficheros (84,1 %) que se reformatearían** y solo
  **60 ya formateados**. `ruff format --check` **no es un gate del CI** (`ci.yml`
  corre solo `ruff check .`), la deriva es **preexistente** y **V3.70 declara que
  no la introduce ni la agrava** (sus 5 ficheros de test y sus 5 subcomandos nacen
  de `ruff check` limpio) y que **no reformatea el árbol** para no hacer el diff
  inauditable. ¿Es una decisión legítima o una forma de no limpiar? Dictaminar.
- **Intermitencias del entorno local, declaradas:** (i) un *access violation* del
  intérprete (`0xC0000005`) en la primera ejecución de la suite tras reiniciar la
  máquina, **no reproducible** (las ejecuciones siguientes dieron 2560 y 2600
  passed); (ii) `resize.spec.ts`, que V3.69 registró como intermitente en local y
  **verde en el CI**, y que V3.70 re-midió **3/3 verde en aislamiento**. ¿Son
  hallazgos del release o ruido de entorno?

## Preguntas de alto valor

1. **El P0**: ¿es un defecto de **contenido** (autoría del banco) o de **motor**
   (el scorer o el gate podrían compensarlo)? ¿La clasificación declarada
   («→ V4.0.x») es correcta o debería tocar el motor?
2. **Los 48 tests**: ¿cuántos **demuestran** (fallarían al cerrar el hueco) y
   cuántos solo **describen** (afirman sobre constantes o valores que el propio
   test calcula)? Enumera cualquier caso tautológico con `archivo:línea`.
3. **`_write_generated`**: ¿es el **único** escritor del script? ¿Hay algún camino
   (import, efecto colateral al importar `services.*`, caché de diccionario,
   `init_db`) por el que ejecutar un subcomando **modifique** `data/`?
4. **Constantes duplicadas**: `REFERENCE_BANDS` vive en `audit_dossier.py:120`
   mientras el producto tiene sus propios umbrales de banda en
   `services/cefr.py`/`services/adaptive.py`/`services/academy.py`. ¿La medición
   mide **contra el criterio interno declarado** (correcto) o introduce una
   **segunda fuente de verdad** que puede derivar sin que nadie lo note?
5. **La cota del placement** (`SE ≥ 0,7071`): ¿la derivación analítica es
   correcta y es realmente la **mejor** cota con los 8 ítems declarados, o un
   artefacto del modelo 1PL asumido?
6. **Las 4 propiedades positivas**: ¿son propiedades reales y no
   cherry-picking? ¿Resisten a un contraejemplo buscado a propósito?
7. **Coherencia con `X`/`Y`**: ¿V3.70 contradice algún veredicto previo? ¿Marca
   como «corregida» la deriva documental (AA-08) sin que la corrección sea
   completa (¿hay otras cifras desincronizadas)?
8. **El alcance**: ¿`audit_dossier.py` es de verdad **herramienta de medición y no
   ruta de producto**, o al crecer (+1033 líneas) se ha convertido en una
   **segunda implementación** de la lógica de negocio que podría divergir?
9. **Honestidad del «no corrige nada»**: ¿queda algún hallazgo **arreglado de
   tapadillo** (un umbral, una constante, un golden) que contradiga la regla
   dura?
10. **Los 6 P2 de V3.69**: ¿siguen **realmente** abiertos, o alguno quedó
    resuelto de facto por V3.70 sin declararlo?

## Formato del informe

Sigue `docs/audit/TEMPLATE.md` y el patrón de las auditorías `W` (V3.63), `X`
(V3.67), `Y` (V3.68) y `Z2` (V3.69, si está disponible): `Alcance` · `Método` ·
`Evidencia` · `Hallazgos`
(`| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |`) ·
`Veredicto` · `Regenerar / Verificar`.

**Requisitos adicionales:**

1. **Dictamen por eje** (AA–AF): *correcto* / *correcto con matiz* / *incorrecto*,
   con una línea de motivo.
2. **Dictamen de los 48 tests**: cuántos demuestran / cuántos describen, con la
   lista de los tautológicos (`archivo:línea`).
3. **Dictamen del alcance del diff**: confirmado «cero lógica de producto» o
   corregido con `archivo:línea`.
4. **Dictamen del P0 y de las 4 propiedades positivas**, uno a uno.
5. **Dictamen de la deriva de formato (317/377)**: ¿hallazgo del release o deuda
   preexistente correctamente acotada?
6. **Veredicto de una línea** apto para publicar: *¿se acepta `v3.70.0` como base
   para V3.71 (runtime/offline/instalación), con o sin condiciones?*
7. Severidades `P0`/`P1`/`P2`/`P3` con `alta`/`media`/`baja`/`documental` y
   evidencia `archivo:línea`. Distinguir **«el test no demuestra»** de **«la
   medición no es correcta»**: son hallazgos distintos y con destinatarios
   distintos.

## Checklist de cierre del auditor

- [ ] El diff de producto contra `v3.69.0` es **solo** bumps de versión +
      `backend/scripts/audit_dossier.py` (medición).
- [ ] `backend/curriculum/`, `backend/services`, `backend/routers`,
      `backend/domain` y `backend/repositories/db.py` **sin diff**.
- [ ] `audit_dossier.py` **solo** escribe en `docs/audit/generated/`.
- [ ] Los 10 subcomandos se reproducen sin cambiar un byte de
      `docs/audit/generated/`.
- [ ] Los 48 tests se cuentan y se dictaminan (demuestran vs describen).
- [ ] El P0 (329/368 en posición 0) se reproduce.
- [ ] CI comprobado en la API de GitHub (6/6, job ids y conteos).
- [ ] Los 6 P2 de V3.69 siguen abiertos y ninguno de los 33 hallazgos se declara
      «cerrado».
- [ ] El veredicto distingue **medición** de **corrección**: V3.70 no añade
      capacidad ni corrige nada.
