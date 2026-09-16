# RE — Gates, CI y deriva documental (V3.71)

> **Tipo:** dossier de evidencia **interno** (no es un informe de auditoría
> externa). Por eso **no lleva letra**: `Z` y `Z2` siguen reservadas a los
> informes externos pendientes de V3.69
> (`docs/audit/Z-AUDITORIA-DISENO-V369.md`,
> `docs/audit/Z2-AUDITORIA-RELEASE-V369.md`, ver
> `agentes/auditoria-externa-v369-seguimiento.md`).
> **Eje auditado:** **RE** («gates/CI/deriva documental») del briefing
> `agentes/v371-runtime-offline-instalacion.md`.
> **Punto de partida:** release `v3.70.0` → commit
> `9ba9c4956a9f1d3c9c2bd3b0e5b1a1b1b5c5b5b5` (ver `docs/RELEVO.md`).
> **Autor:** el propio proyecto.
> **Fecha:** 2026-09-16.

## Alcance

- **Se audita:**
  1. que los **75 tests del launcher** dejen de ejecutarse **solo en local** y
     pasen a ser un **gate de CI**;
  2. que la documentación **no contradiga al código** («fuente de verdad») en las
     cuatro derivas declaradas por el briefing de V3.71.
- **No se audita:** el runtime de producto (**RA**), el offline real (**RB**), la
  instalación limpia (**RC**), el bootstrap de Ollama (**RF**) ni el «modelo por
  defecto» como **decisión** (solo su **coherencia documental**). Es decir, este
  dossier **no implementa ni verifica** el runtime: cierra el eje más barato y de
  efecto inmediato del incremento.
- **Relación con `docs/BETA_V3.md` §4.4:** la matriz de dispositivos sigue
  siendo una acción **humana** pendiente; aquí solo se corrige que la
  documentación la declarase cerrada.

## Método

1. **Fuente de verdad = código y medidas reales**, nunca la documentación:
   - modelo por defecto → `backend/config.py::DEFAULT_MODEL` / `UNUSABLE_MODELS`;
   - cobertura de CI → `.github/workflows/ci.yml` (parseado con `yaml`);
   - ficheros del launcher → listado real de `launcher/`;
   - estado de la matriz → tabla real de `docs/DEVICE_MATRIX.md`.
2. **Fijación por test.** Cada deriva queda **pinchada** por un test que falla si
   vuelve, de modo que el CI avisa en lugar de dejar que la documentación se
   separe otra vez. Los tests viven en
   `backend/tests/test_docs_drift_v371.py` (job **Backend** del CI, que ya
   ejecutaba `pytest tests/`).
3. **Sin cambios de producto:** el diff de este eje es **CI + documentación +
   tests**. Cero líneas de lógica de aplicación.

## Evidencia

### E1 — El launcher entra en CI (nuevo job `launcher`)

| Elemento | Antes | Después |
|---|---|---|
| Jobs de `ci.yml` | 6 (`backend`, `frontend`, `release-consistency`, `beta-v3-gate`, `content-validation`, `playwright`) | **7** (+ `launcher`) |
| Tests del launcher | 75 en local, **0** en CI | 75 en local **y** en CI |
| Lint del launcher | `launcher/pyproject.toml` (ruff) solo manual | `ruff check .` en CI |
| Runner | — | `ubuntu-latest`, Python `3.13` (igual que backend/beta-v3-gate) |
| Dependencias | — | `pytest==8.4.2` y `ruff==0.16.3` **pineados igual que `backend/requirements-dev.txt`** |

Medidas locales (equivalen a los dos pasos del job):

```powershell
cd launcher
python -m ruff check .        # All checks passed!
python -m pytest tests/ -q    # 75 passed in 21.35s
```

**Por qué es viable en Ubuntu** (el launcher es GUI Windows): los 75 tests
**no importan `tkinter`** en su lógica (la frontera es `ui.py`, que es puro) y no
usan ninguna API de Windows. Hay `0` `parametrize` en `launcher/tests/`, así que
«1 `def test_` = 1 test» y el recuento documentado es verificable.

### E2 — Las cuatro derivas documentales

| # | Deriva | Antes | Después |
|---|---|---|---|
| D1 | Árbol del launcher incompleto | `docs/ARQUITECTURA.md:281-291` omitía `browser_cookies.py`, `state_store.py` y `allow-firewall.ps1`; la lista de tests omitía `test_state_store` | `docs/ARQUITECTURA.md:284-298` lista los **10** fuentes (`.py`/`.ps1`) y los **6** módulos de test; `docs/ARQUITECTURA.md:312-316` da la responsabilidad de `browser_cookies.py`, `state_store.py` y `*.ps1` |
| D2 | Modelo por defecto contradictorio | `docs/PREMISAS.md:20` y `README.md:267-270` presentaban `qwen3.5:9b` como por defecto; el código fija `llama3.1:8b` y lo **veta** | `docs/PREMISAS.md:20` y `README.md:268-270` nombran `llama3.1:8b` como `DEFAULT_MODEL` y declaran `qwen3.5:9b` **vetado** (`UNUSABLE_MODELS`) |
| D3 | ✅ falsos en los gates | `docs/BETA_GATES.md:24,26` daban ✅ a «Launcher de escritorio» y «CI completa» **sin** que el launcher estuviera en CI | `docs/BETA_GATES.md:35-37` documenta el job `launcher` y el recuento de tests; la ✅ pasa a ser **verificable** (E1) |
| D4 | Matriz de dispositivos declarada verde | `docs/BETA_GATES.md:98` daba ✅ a «Matriz de dispositivos» mientras `docs/DEVICE_MATRIX.md:30-42` estaba **10/10 en ⬜** | `docs/BETA_GATES.md:109` pasa a **⬜ pendiente** («G5 no cerrado»), `docs/BETA_GATES.md:111` ajusta el score y `docs/BETA_GATES.md:115-121` corrige el veredicto |

Además, `docs/BETA_GATES.md:14-23` gana una **nota de corrección (V3.71)** que
registra las tres afirmaciones desactualizadas **sin reescribir el histórico**
(fecha `2026-08-31`, versión `2.0.0`: son las de la evaluación original, no las
del árbol actual). El histórico no se falsea; se **anota**.

### E3 — Estado del árbol tras el eje

| Comprobación | Comando | Resultado |
|---|---|---|
| Consistencia de versión | `python scripts/check_release_consistency.py` | `OK: Release consistency (3.70.0) en todos los orígenes` |
| `ci.yml` es YAML válido y tiene 7 jobs | `python -c "import yaml;print(list(yaml.safe_load(open('.github/workflows/ci.yml'))['jobs']))"` | `['backend','frontend','release-consistency','beta-v3-gate','content-validation','playwright','launcher']` |
| Lint del backend | `python -m ruff check .` (en `backend/`) | `All checks passed!` |
| Tests nuevos | `python -m pytest tests/test_docs_drift_v371.py -q` | `8 passed` |

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| RE-01 | **P2** | Los **75 tests del launcher no se ejecutaban en CI**: el launcher era el único subsistema sin gate, y `BETA_GATES.md` declaraba «CI completa» igualmente | E1; `docs/BETA_GATES.md:26` (antes) | Job `launcher` (ruff + pytest) con los **mismos pins** que `backend` | **cerrado** (E1) |
| RE-02 | **P2** | `docs/PREMISAS.md` y `README.md` presentaban como modelo por defecto uno **vetado en el código**: la documentación de premisas contradecía a la fuente de verdad | E2/D2; `backend/config.py:10,18` | Corregir la documentación a favor del código y **declararlo** (decisión C del gerente) | **cerrado** (E2/D2) |
| RE-03 | **P3** | `docs/BETA_GATES.md` daba ✅ a «Matriz de dispositivos» con `docs/DEVICE_MATRIX.md` **10/10 en ⬜** ⇒ G5 se declaraba cerrado sin evidencia | E2/D4; `docs/audit/G-DEVICES.md:77` (`abierto (acción humana)`) | Marcar G5 como **no cerrado** y anotar el histórico | **cerrado** (E2/D4) |
| RE-04 | **P3** | Árbol del launcher en `docs/ARQUITECTURA.md` desactualizado (3 ficheros y 1 módulo de test ausentes) | E2/D1 | Completar el árbol y el mapa de responsabilidades | **cerrado** (E2/D1) |
| RE-05 | **P3** | Nada impedía que las derivas **volvieran**: eran correcciones de texto sin test que las fijase | `backend/tests/test_docs_drift_v371.py` (nuevo) | 8 tests que comparan la documentación **contra el código y las medidas reales** | **cerrado** |
| RE-06 | **P3 (deuda)** | `docs/BETA_GATES.md` sigue fechado `2026-08-31` · `2.0.0`: es un documento **histórico** con anotaciones, no un estado vivo del árbol | `docs/BETA_GATES.md:6` + nota V3.71 | Se **declara** la naturaleza histórica en la propia nota; la foto viva del estado es `docs/RELEVO.md` | **aceptado** |

## Veredicto

**Aprobado.** El launcher deja de ser el subsistema sin gate (7/7 jobs) y las
cuatro derivas documentales quedan **corregidas y fijadas por test**, de modo que
una reincidencia **rompe el CI** en lugar de pasar desapercibida.

Matiz honesto: esto **no** cierra ninguno de los ejes caros de V3.71. **RA**
(runtime de producto), **RB** (offline real), **RC** (instalación limpia) y
**RF** (bootstrap de Ollama) siguen **abiertos**, y **G5 (matriz de dispositivos)
sigue abierto** por acción humana pendiente.

| Área | Valoración |
|---|---|
| Cobertura de CI | 9,5/10 (el launcher entra; Playwright sigue solo con Chromium) |
| Coherencia documentación↔código | 9,5/10 (4 derivas cerradas, 1 deuda declarada) |
| Verificabilidad de los gates | 9,5/10 (cada gate con evidencia o con ⬜ explícito) |
| Runtime de producto / offline / instalación | **sin evaluar en este eje** |

**Hallazgos: P0 = 0 · P1 = 0 · P2 = 2 · P3 = 4 (1 deuda aceptada).**

## Regenerar / Verificar

```powershell
# 1. Las cuatro derivas, fijadas por test (job Backend del CI)
cd backend
.venv\Scripts\python.exe -m pytest tests/test_docs_drift_v371.py -q   # 8 passed
.venv\Scripts\python.exe -m ruff check .

# 2. El job del launcher (lo que ejecuta el CI, en Ubuntu)
cd ..\launcher
python -m ruff check .            # All checks passed!
python -m pytest tests/ -q        # 75 passed

# 3. Coherencia de release y forma del workflow
cd ..
python scripts/check_release_consistency.py
python -c "import yaml; print(list(yaml.safe_load(open('.github/workflows/ci.yml'))['jobs']))"

# 4. Falsar a mano cada deriva (deben salir vacíos / coherentes)
Select-String -Path docs\PREMISAS.md,README.md -Pattern 'por defecto' |
  Select-String -Pattern 'qwen3.5:9b'          # no debe devolver nada
Select-String -Path docs\BETA_GATES.md -Pattern 'Matriz de dispositivos'  # ⬜, no ✅
```

## Tests que respaldan

- `backend/tests/test_docs_drift_v371.py` (**8 tests**, nuevos en V3.71):
  - `test_docs_declaran_el_modelo_por_defecto_real` — D2 (las docs nombran
    `config.DEFAULT_MODEL`).
  - `test_docs_no_presentan_un_modelo_vetado_como_por_defecto` — D2 (ninguna
    línea con «por defecto» presenta un modelo de `UNUSABLE_MODELS` sin
    declararlo vetado).
  - `test_arquitectura_documenta_los_ficheros_del_launcher` — D1 (los 10
    fuentes `.py`/`.ps1` del launcher aparecen en `ARQUITECTURA.md`).
  - `test_arquitectura_documenta_los_tests_del_launcher` — D1 (los 6 módulos de
    test **y** el recuento real de tests).
  - `test_ci_ejecuta_los_tests_y_el_lint_del_launcher` — RE-01 (existe el job,
    con `working-directory: launcher`, y corre pytest y ruff).
  - `test_el_job_del_launcher_pinea_las_mismas_versiones_que_el_backend` —
    RE-01 (la promesa «mismos pins» es verificable contra
    `backend/requirements-dev.txt`).
  - `test_beta_gates_declara_el_job_del_launcher_y_su_correccion` — D3 + nota de
    corrección.
  - `test_beta_gates_no_declara_verde_una_matriz_de_dispositivos_pendiente` —
    D4 (bicondicional: «verde» ⇔ hay filas completadas en la matriz).
- `launcher/tests/*` (75 tests): ahora ejecutados por el job `launcher`; no se
  han modificado en este eje.
- `backend/tests/test_beta_v3.py`: sin cambios; el gate Beta V3 sigue intacto.
