# Release notes — English Tutor v3.73.4

**Fecha:** 2026-09-17 · **Tipo:** release de **PARCHE** (cierra la trazabilidad del
arnés de validación; **sin** capacidad pedagógica nueva y **sin** cambios de
producto) · **Versión de app:** `3.73.3 → 3.73.4`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el banco y SIN tocar el currículum.** El
backend de producto, el frontend de producto y el launcher están **intactos**: el
diff es el **arnés de validación**, sus **tests** y **documentación**. El contenido
funcional de esta línea sigue siendo el de V3.73.1.

---

## Qué es esta release

V3.73.3 entregó el kit y el guard de deriva, pero la evidencia que produce el
instrumento **no decía contra qué commit** se había probado cada gate. Eso dejaba
abierta la única grieta que importa en una certificación: siete gates verdes en
siete commits distintos se podían presentar como «los siete gates en verde».

Esta release sella la identidad del árbol en cada registro y añade la puerta fuerte
`status --strict --same-tree`.

**Lo que NO hace:** no toca producto (ni backend, ni frontend, ni launcher), no
abre arquitectura y **no cierra los 7 gates físicos**, que siguen `pending` por
diseño (`status --strict` sigue **rojo**).

---

## 1 · La evidencia sella el commit (y la run de CI)

`record` escribe ahora, junto al estado, las notas, la fecha UTC y la `VERSION` del
árbol, el **`head_sha`** del commit validado (`git rev-parse HEAD`), y acepta
`--ci-run` con el id numérico **o** la URL de la run de CI (se guarda el id, que es
lo que identifica el artefacto publicado):

```powershell
backend\.venv\Scripts\python.exe scripts\validation_gate.py record launcher-windows pass `
  --ci-run 35219576565 `
  --notes "Launcher en Windows 11: start, HTTPS :8000, navegador, microfono, TTS, STT, chat y persistencia tras reinicio OK"
```

La cadena de certificación queda **dentro** de
`docs/audit/validation-evidence.json`:

```
commit  →  run de CI  →  artefactos  →  gate record
```

Dos reglas nuevas, y las dos van en la dirección de rechazar:

- **Un `pass` sin commit se rechaza.** Si el árbol no tiene git, el registro no se
  escribe: un cierre que no dice de qué árbol es no es evidencia. Los siete gates
  de esta release son de acción humana justamente para que esto no dependa de una
  convención.
- **`fail`/`skip`/`pending` sí se registran sin SHA**, porque declaran un
  no-cierre, no una prueba. La honestidad de un `skip` no necesita commit; la de un
  `pass`, sí.

## 2 · La puerta fuerte: `status --strict --same-tree`

`status` imprime el commit de cada gate y marca la evidencia que viene de otro
árbol. `--strict` sigue significando exactamente lo de antes (**7/7**, y el CI no
cambia), y **`--same-tree`** añade la condición que faltaba:

| Puerta | Exige | Sale 0 cuando |
|---|---|---|
| `status --strict` | los 7 gates en `pass` | 7/7 |
| `status --strict --same-tree` | los 7 en `pass` **y** que los siete `head_sha` sean el commit actual | 7/7 contra un árbol congelado |

Es la forma de cierre que exige V4.0: si un gate se repite más tarde (porque se
corrigió algo), el `record` nuevo sella el commit nuevo y `--same-tree` vuelve a
distinguir «los siete gates de este árbol» de «siete gates de árboles distintos».

## 3 · `auto` vigila el formato de la evidencia

La comprobación 10 (`evidencia-integra`) falla ahora si un `pass` no trae
`head_sha`, o si el `head_sha` no es un commit (40 hex) o el `ci_run` no es un id
numérico. La evidencia escrita a mano tampoco puede cerrar un gate sin decir de qué
árbol es.

## 4 · Una sola cifra de gates humanos

`Gate.human` se declara **gate a gate**, sin valor por defecto, y vale `True` en
los **7**: el instrumento no ejecuta ningún flujo de la app, así que todos exigen
una persona delante. La expresión «7 gates (5 de ellos acción humana)» de las notas
históricas de V3.73.0 describía los **cinco bloques físicos que V3.72 declaró**
(corte de red, máquina limpia, Windows real, dispositivos y audio); el instrumento
los cubre y añade `journeys` y `pedagogia`. El runbook lo deja explicado: no quedan
dos cifras en circulación.

---

## Verificación (lo que se ejecutó)

```powershell
# Backend
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q      # 2796 passed, 2 skipped (2798 casos) en el worktree limpio
                                                    # 2798 passed (0 skipped, mismos 2798 casos) en el árbol de trabajo
.venv\Scripts\python.exe -m ruff check .           # limpio

# Frontend (esta release NO toca producto: se comprueba que no ha derivado)
cd ..\frontend
npx tsc --noEmit                                   # limpio
npx vitest run                                     # 712 passed
npm run build                                      # OK

# Launcher
cd ..\launcher
..\backend\.venv\Scripts\python.exe -m pytest tests/ -q   # 113 passed
..\backend\.venv\Scripts\python.exe -m ruff check .       # limpio

# Gates del repo (raíz)
cd ..
backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist  # 10/10
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict      # exit 1 (correcto)
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict --same-tree  # exit 1 (correcto)
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py            # 6 orígenes (3.73.4)
backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py --strict         # 0/0/0
```

La cifra del **checkout limpio** (la autoridad, como en V3.73.2/V3.73.3) es **2796
passed · 2 skipped** (2798 casos), medida en el `git worktree` sobre el tag en el
**pre-vuelo**; los 2 saltos son condicionales del banco de escenario, que en el
worktree no tiene la BD local (no versionada). En el árbol de trabajo la misma suite
da **2798 passed** (0 skipped): mismos 2798 casos, sin BD que los condicione.
Además, en ese worktree el **manifiesto offline** y la **identidad del árbol** se
comprobaron con valores reales:

| Dato | Valor |
|---|---|
| `VERSION` | `3.73.4` |
| `HEAD` (SHA) | `5007c3a59127701932a0c1c21525da6936f9f7fa` |
| Run de CI del commit | `35251738073` (11/11, `success`) |
| `git status --short` del worktree | limpio tras el pre-vuelo |
| `auto --require-dist` en el worktree | **10/10**, y el informe regenerado **idéntico** al commiteado (0 diff) |
| `scripts.audit_dossier runtime-audit` | **Ausentes: 0** |
| `download_models.py --check` | falta solo la **BD** (se crea sola al arrancar); Ollama `llama3.1:8b` presente en `ollama list` |
| Entorno del worktree (no versionado) | `.venv` y `models/` **enlazados** de la instalación local (no se descargan: eso es G2, que no se ejecuta hoy) |

**Tests nuevos:** `backend/tests/test_validation_gate_v373.py` **29 → 43**
(+14 casos): el SHA sellado en el `record`, el `pass` sin git rechazado, el
no-cierre registrable sin SHA, la normalización y el rechazo de `--ci-run`, la
puerta `--same-tree` (evidencia propia, ajena y árbol sin git), que `--strict`
sigue siendo «7/7» sin `--same-tree`, y el formato de `head_sha`/`ci_run` en la
evidencia escrita a mano.

---

## Honestidad

- **Los 7 gates siguen en `pending`.** Esta release **no** ha cortado la red, no
  ha instalado en una máquina limpia, no ha probado un móvil real ni un micrófono
  real. Endurece el instrumento; **la ejecución sigue siendo humana**.
- **`status --strict` sigue saliendo 1** y eso sigue siendo lo correcto: es la
  puerta de V4.0, no un fallo.
- **El cierre fuerte es `--strict --same-tree`**, pero solo tiene sentido cuando
  los siete gates existan: hoy no hay ningún gate en `pass`, así que la puerta
  nueva está **sin estrenar** por diseño.
- **El `head_sha` no sustituye al artefacto.** Dice contra qué commit se probó; los
  artefactos (informe de `auto`, evidencia, capturas) siguen siendo la prueba de lo
  que se observó.
- **Sigue abierto** `RA-02` (endpoint de Ollama sin declarar en `config.py`), y
  `RA-07`/`RD-05` como deuda aceptada.

## Criterio de V4.0 (sin cambios)

V4.0 se declara cuando `validation_gate.py status --strict` salga **0** y, con el
árbol congelado, `status --strict --same-tree` salga **0** también: los 7 gates en
`pass` **contra el mismo commit**. El siguiente hito sigue siendo el que estaba:
**ejecutar físicamente G1–G7**.
