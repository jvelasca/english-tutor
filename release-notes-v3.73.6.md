# Release notes — English Tutor v3.73.6

**Fecha:** 2026-09-17 · **Tipo:** release de **PARCHE** (corrige cifras declaradas de
la batería automática que **no eran reproducibles** en un clon limpio; **sin**
capacidad pedagógica nueva y **sin** cambios de producto) · **Versión de app:**
`3.73.5 → 3.73.6`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el banco y SIN tocar el currículum.** El backend
de producto, el frontend de producto y el launcher están **intactos**, y **el arnés de
validación, sus tests y el contrato de los 7 gates no se tocan**: el diff es
**documentación**. El contenido funcional de esta línea sigue siendo el de V3.73.1.

---

## Qué es esta release

Esta release nace de un **pre-vuelo del auditor**: clonar el repositorio **desde
GitHub** y ejecutar, uno por uno, los comandos que el punto de entrada
(`agentes/auditoria-total-externa-v373.md`) le manda ejecutar.

El pre-vuelo encontró **una cifra no reproducible** en ese documento:

> `pytest tests/ -q  # declarado: 2796 passed + 2 skipped (2798 casos) en el worktree limpio`

Medido en tres entornos reales:

| Entorno | passed | skipped | casos |
|---|---|---|---|
| **Clon limpio de GitHub** (sin `npm run build`) | **2795** | **3** | 2798 |
| Ese mismo clon tras `npm run build` | **2796** | **2** | 2798 |
| Árbol con `dist`, modelos Whisper y BD local | **2798** | **0** | 2798 |

El **total (2798 casos) sí era correcto y es invariante**; lo que fallaba era el
**reparto** y, sobre todo, su **explicación**: el documento atribuía los 2 saltos a
«condicionales del banco de escenario», y los saltos reales son de **artefactos no
versionados**:

```text
SKIPPED tests/test_serve_frontend_v372.py:173   -> frontend/dist no construido en este entorno
SKIPPED tests/test_stt_asr_integration.py:44    -> Modelo Whisper no descargado: integración ASR opt-in
SKIPPED tests/test_stt_asr_integration.py:55    -> Modelo Whisper no descargado: integración ASR opt-in
```

La cifra de 2796 se había medido en un worktree que **sí** tenía `dist` construido (de
ahí que allí no apareciera el salto del artefacto), y se presentó como si fuera la del
**checkout limpio**, que es la autoridad. Un auditor recién clonado ve **2795 + 3** y
habría abierto una incidencia que **no** es un defecto del producto. Eso es
exactamente lo que el pre-vuelo tenía que cazar antes de gastar una ronda del auditor.

**Lo que NO hace:** no toca producto (ni backend, ni frontend, ni launcher), no toca el
arnés `scripts/validation_gate.py` ni sus tests, no añade ni retira gates, y **no
cierra los 7 gates físicos**, que siguen `pending` por diseño (`status --strict` sigue
**rojo**).

---

## 1 · El invariante se declara, y el reparto también

El documento declara ahora el **invariante** (los **2798 casos**) y el **reparto por
entorno** con sus motivos exactos, medidos. Y añade el aviso que faltaba: «si acabas de
clonar y no has compilado, lo que verás es **2795 + 3**, y eso **no es un hallazgo**».

## 2 · Errata explícita, sin reescribir el histórico

La corrección se marca como **errata (V3.73.6)** dentro del propio documento, y las
notas de V3.73.4 y de V3.73.5 llevan una línea de errata que apunta a la medición
correcta. Las dos releases se dejan **como registro de lo que declararon**: lo que se
corrige es la cifra en circulación, no la historia.

## 3 · Los nombres de los 11 jobs, uno por línea

Los nombres de los jobs del CI iban partidos entre líneas (`Release⏎consistency`), de
modo que un `grep` literal fallaba. Ahora van **uno por línea**, para que el auditor
pueda comprobarlos con una búsqueda directa.

---

## Verificación (lo que se ejecutó)

```powershell
# Pre-vuelo del auditor: clon NUEVO desde GitHub (no desde el arbol local)
git clone https://github.com/jvelasca/english-tutor et-audit
cd et-audit; git fetch --tags
git log --oneline -3 main                       # e10b24d arriba
git rev-parse v3.73.5^{commit}                  # e10b24d...
git diff --stat v3.73.5..main -- backend frontend launcher scripts   # VACIO
gh run list --commit <sha>                      # success, 11/11

# Bateria en el clon limpio (medido, no supuesto)
cd backend; pytest tests/ -q -rs                # 2795 passed, 3 skipped
cd ..\launcher; pytest tests/ -q                # 113 passed
python scripts/check_release_consistency.py     # 6 origenes
python scripts/validation_gate.py status --strict        # exit 1 (correcto)

# Recuentos declarados, comprobados uno a uno
pytest tests/test_validation_gate_v373.py --collect-only -q   # 43
pytest tests/test_serve_frontend_v373.py --collect-only -q    # 19
pytest tests/test_net_interfaces_v373.py --collect-only -q    # 23
pytest tests/test_docs_drift_v373.py --collect-only -q        # 19   (suma 104)
launcher: test_lan_ip_v373.py 13 + test_preflight_v373.py 7   # suma 20

# Arbol de trabajo (esta release)
cd backend; pytest tests/ -q                    # 2798 passed
ruff check .                                    # limpio
cd ..\frontend; npx tsc --noEmit                # limpio
npx vitest run                                  # 712 passed (85 ficheros)
cd ..\launcher; pytest tests/ -q                # 113 passed
cd ..; check_release_consistency.py             # 6 origenes (3.73.6)
check_i18n_coverage.py --strict                 # 0/0/0
validation_gate.py auto --require-dist          # 10/10
```

| Dato | Valor |
|---|---|
| `VERSION` | `3.73.6` |
| Cambios de código (producto y arnés) | **ninguno**: el diff frente a `v3.73.5` es solo documentación |
| Orígenes de versión consistentes | **6/6** |
| Recuentos declarados verificados en el clon | 43 / 19 / 23 / 19 (104) · launcher 113 y 13+7=20 |
| Gates | **7 en `pending`** (no se mueve ninguno) |

---

## Honestidad

- **Los 7 gates siguen en `pending`.** Esta release **no** ha cortado la red, no ha
  instalado en una máquina limpia, no ha probado un móvil ni un micrófono reales. Es
  una release de **precisión documental**; la validación física sigue siendo el único
  hito pendiente para V4.0.
- **`status --strict` sigue saliendo 1** y eso sigue siendo lo correcto: es la puerta
  de V4.0, no un fallo.
- **La cifra errónea se propagó desde V3.73.4 y desde aquí se corrige sin borrar el
  rastro.** También aparecía repetida en la nota de V3.73.5 de `docs/RELEVO.md`,
  copiada sin medirla: la errata cubre también ese caso, porque el error real no fue
  escribir un número, sino **declarar como reproducido lo que solo se había medido en
  otro entorno**.
- **El pre-vuelo no sustituye al auditor.** Verifica que sus comandos no dan falsos
  positivos y que las cifras declaradas son reproducibles; **no** juzga el producto.
- **Sigue sin haber `npm run build` en la receta del auditor**: el documento declara
  los dos repartos (con y sin `dist`) en lugar de exigir un paso extra, para que
  ninguno de los dos sea una sorpresa.

## Criterio de V4.0 (sin cambios)

V4.0 se declara cuando `validation_gate.py status --strict` salga **0** y, con el
árbol congelado, `status --strict --same-tree` salga **0** también: los 7 gates en
`pass` **contra el mismo commit**. El siguiente hito sigue siendo el que estaba:
**ejecutar físicamente G1–G7**.
