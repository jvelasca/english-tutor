# Auditoría EXTERNA de RELEASE de V3.71 — punto de entrada (listo para lanzar)

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **`v3.71.0` ya
> publicada**, no un plan. La revisión es **de solo lectura**: no se cambia código,
> datos, configuración ni etiquetas publicadas.
>
> **Por qué una auditoría de RELEASE y no de diseño.** Igual que V3.70, **V3.71 no
> tuvo auditoría de diseño externa**: su briefing maestro
> (`agentes/v371-runtime-offline-instalacion.md`) declaró las **cuatro decisiones de
> alcance** con el gerente (A: medir y declarar la frontera de `npm run dev` · B:
> verificar y guiar el bootstrap de Ollama · C: corregir la documentación a favor de
> `config.py` · D: añadir el job del launcher al CI) y se ejecutó como **seis ejes
> internos** (`RE`–`RF`). Este documento cubre el hueco y audita **lo entregado**:
> la diferencia entre «la medición es correcta» y «lo publicado demuestra lo que
> dice demostrar».
>
> **Estado:** entregado 2026-09-16. **Informe esperado:**
> `docs/audit/AH-AUDITORIA-RELEASE-V371.md` (los prefijos `AA`–`AF` los ocupan los
> dossiers de V3.70; `AG` lo reserva el punto de entrada de V3.70, **pendiente de
> informe**; `AH` evita colisión y mantiene la trazabilidad del mismo incremento).

## Punto de entrada

- Repositorio: `jvelasca/english-tutor` (**público**), rama `main`.
- **Release auditada:** commit **`2eff6ea`** (`2eff6eadc9e5dd13df26e3892d2e508167def649`,
  `release(v3.71.0): runtime real, offline verificado e instalacion limpia`) con el
  **tag anotado `v3.71.0`** (objeto **`6ac22db`**, `6ac22db9cb3190fb55627ab41045d5a25d5b1ab8`,
  que apunta a `2eff6ea`).
- **Base de comparación:** `v3.70.0` → release **`9ba9c49`**, tag `v3.70.0`, cierre
  documental `2db93ba`/`f93499d`.
- **Los números de línea citados** corresponden al árbol publicado en `v3.71.0`.

**Estado de publicación (verificado, no declarado):**

- **CI 7/7 verde** en
  [run 35136141089](https://github.com/jvelasca/english-tutor/actions/runs/35136141089)
  (HEAD `2eff6ea`, `success`), con el **job nuevo incluido** —es decir, la decisión
  **D** del briefing está verificada **en GitHub**, no solo en local—:
  - `Launcher (ruff + pytest)` `104928880868` ← **el job que añade V3.71**
  - `Backend (ruff + pytest)` `104928881073` · `Frontend (tsc + vitest + build)`
    `104928880539` · `Playwright E2E (visual)` `104928880854` · `Content validation`
    `104928880771` · `Beta V3.0 gate` `104928880924` · `Release consistency`
    `104928880910`.
- **Nota para el auditor:** el run se disparó con el **push de `main`**; el tag
  `v3.71.0` se publicó en el mismo push y apunta al mismo commit. En la API de
  GitHub se pueden comprobar los **7** jobs y el objeto del tag.

**Artefactos nuevos de la release (objeto de la auditoría):**

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `backend/scripts/audit_dossier.py` (**+1 subcomando**) | `runtime-audit`: medición **de SOLO LECTURA** de los puntos de red del backend, el manifiesto offline y (opcional, aparte) el sondeo de Ollama | Que las dependencias de Internet del proyecto están **declaradas y son falsables**, y que la medición es **determinista** y no escribe en `data/` ni `curriculum/` |
| `docs/audit/generated/runtime-audit.{md,json}` | Par generado regenerable | Reparto por tipo (`loopback` 1 · `lan` 2 · `internet` 6) y manifiesto de artefactos offline |
| `backend/tests/test_runtime_audit_v371.py` (**11 tests**) | Guard del instrumento | Que no aparece **ninguna** primitiva de red en producto sin declarar, que el par es reproducible y que el instrumento es de solo lectura |
| `backend/tests/test_docs_drift_v371.py` (**8 + los de RC**) | Guard anti-deriva documental | Que las **4 derivas** corregidas (RE) **y** las 2 nuevas de RC (runtime real, modelo por defecto) no vuelven |
| `backend/tests/test_install_bootstrap_v371.py` (**13 tests**) | Guard del bootstrap | Que la **voz inglesa por defecto** es alcanzable por el catálogo, que el bootstrap **no** tiene primitivas de red propias y que la verificación previa es de solo lectura |
| `backend/download_models.py` (**reescrito**) | Bootstrap + verificación previa (`--check`/`--json`) | Qué falta, **qué es descarga y qué es local**, y que Ollama **no** lo comprueba este script (`exists=None`) |
| `backend/services/voice_downloads.py` (`CATALOG` + `_download_file`) | Catálogo curado + descarga | La voz por defecto está en el catálogo; el timeout es **real** y se verifica `Content-Length` |
| `backend/services/llm.py` (`LLM_PING_TIMEOUT_SECONDS`) | Sonda de Ollama acotada | Que un Ollama **lento** no se disfraza de backend caído |
| `frontend/src/api/health.ts` + `components/ConnectionIndicator.tsx` + `utils/i18n.ts` | Salud honesta | Tres estados (`connected`/`degraded`/`disconnected`) sobre `/api/health/dependencies`, no sobre `/api/health` |
| `docs/audit/RE-GATES-DERIVA.md`, `RA-RUNTIME-OFFLINE.md`, `RB-INSTALACION.md`, `RC-RUNTIME-PRODUCTO.md`, `RD-DEPENDENCIAS-OCULTAS.md`, `RF-SINTESIS-RUNTIME-V371.md` | Seis dossiers de eje, con el formato de `docs/audit/TEMPLATE.md` | Cada hallazgo con severidad, evidencia `archivo:línea`, comando de reproducción y estado |
| `release-notes-v3.71.0.md` | Nota de release | Alcance, tabla consolidada, §«Honestidad» y §«Fuera de alcance» |
| `docs/RELEVO.md` (nota + «0. START HERE»), `CHANGELOG.md` `[3.71.0]`, `PLAN.md`, `docs/audit/PARKED.md` | Relevo y coherencia | Estado, verificación, **CIERRE** con run id y lo que queda abierto con su fase |

## Alcance y enfoque

**Qué se audita.** La afirmación central del incremento, que tiene dos mitades:

1. **Negativa (lo que el proyecto dice NO tener):** «no hay dependencias de Internet
   en código de producto fuera de las declaradas», y las declaradas son
   exactamente las que el instrumento censa.
2. **Positiva (lo que el proyecto dice tener):** que los endurecimientos cierran
   defectos **reales** y que sus tests **fallan sin el cambio**.

**Qué NO se audita** (para no confundir declaración con demostración):

- La **eficacia pedagógica** (V3.70) y el **motor adaptativo** (V3.69).
- El **offline en vivo**: **no existe** todavía (`RA-05`). Cualquier comprobación
  offline en CI es **simulada** (premisa 12).
- El **hardware** (matriz de dispositivos **10/10 ⬜**).
- La **calidad acústica** de STT/TTS.

## Preguntas falsables (lo que el auditor debe intentar REFUTAR)

Cada una se puede comprobar **desde el clon**, sin credenciales ni servicios.

1. **¿Es cierto que no hay más dependencias de Internet declaradas que las censadas?**
   Ejecutar `runtime-audit` y comparar el censo con `RUNTIME_TOUCHPOINTS`. Después
   **buscar por su cuenta** primitivas de red (`urlopen`, `urlretrieve`,
   `requests.`, `httpx.`, `socket.`, `aiohttp`) en `backend/services`,
   `backend/routers`, `backend/repositories`, `backend/domain` y comparar con lo
   declarado. **Si encuentra una sin declarar, el hallazgo central del incremento
   es falso.**
2. **¿El instrumento es realmente de solo lectura y determinista?** Tomar la huella
   (mtimes/tamaños) de `backend/data/` y `curriculum/`, ejecutar `runtime-audit`
   dos veces y comparar el par generado **byte a byte** y las huellas.
3. **¿El `timeout` de la descarga de voces es real, o volvió a ser decorativo?**
   Leer `_download_file` y comprobar que el valor **llega** a `urlopen` (el defecto
   histórico era pasar el timeout a `urlretrieve`, que no lo acepta) y que hay
   verificación de `Content-Length`. **Intentar refutarlo** con un servidor local
   que no responda.
4. **¿El test del bootstrap falla sin el cambio?** Revertir `en_US-lessac-medium`
   del `CATALOG` y comprobar que
   `test_la_voz_inglesa_por_defecto_esta_en_el_catalogo_curado` y
   `test_el_ingles_por_defecto_se_puede_auto_descargar` **fallan**. Si pasan, el
   hallazgo RB-01 es retórico.
5. **¿El indicador de la UI distingue de verdad tres estados?** Leer
   `connectionState()` y su test, y comprobar que el endpoint consultado
   (`/api/health/dependencies`) es el que **gatea** la utilidad de la app y que
   `audio_library` queda **fuera** a propósito.
6. **¿La documentación publicada dice la verdad sobre su propio runtime?** El
   incremento declara que la UI la sirve el dev server de Vite y que Node es
   requisito de **ejecución**. Comprobar en el código que **no** hay servido de
   `frontend/dist` en el backend ni en el launcher, y que el `README.md` lo dice.
   **Y comprobar lo contrario:** si encuentra un `StaticFiles`/`FileResponse` que
   sirva el `dist`, la declaración es falsa.
7. **¿Las derivas documentales corregidas lo están de verdad?** Verificar que
   `PREMISAS.md`/`README.md` nombran `llama3.1:8b` como modelo por defecto y que
   `config.DEFAULT_MODEL` coincide; que `ARQUITECTURA.md` lista el árbol real del
   launcher; que `BETA_GATES.md` **no** da ✅ a la matriz de dispositivos.
8. **¿La coherencia de versión se sostiene en los 6 orígenes?** Ejecutar
   `python scripts/check_release_consistency.py` (fuente única:
   `backend/config.py::VERSION`).
9. **¿La síntesis (`RF`) se pasa de optimista?** Leer su §«Honestidad» y comprobar
   que los tres hallazgos abiertos por acción humana y los dos declarados con
   condición de salida **no** se cuentan como cerrados en el veredicto.

## Reglas duras para el auditor

1. **Solo lectura.** No se modifica nada; no se abren PRs correctivos.
2. **Separar lo verificado de lo declarado.** Toda afirmación del release que el
   auditor no pueda reproducir se marca como **declaración**, no como hecho.
3. **Severidad `P0`–`P3`**, y **una afirmación por hallazgo**, con `archivo:línea`
   del árbol publicado y comando de reproducción.
4. **Falsabilidad primero:** un hallazgo que no se pueda refutar con un comando no
   es un hallazgo. **Nada de «podría», «convendría» ni «en el futuro»** sin dato.
5. **Lo que no se pueda comprobar se declara NO COMPROBABLE**, con el motivo.
6. **Sin cortesía:** si el incremento no demuestra lo que dice, decirlo. Si lo
   demuestra, decirlo también.

## Honestidad esperada del informe

El auditor debe pronunciarse explícitamente sobre estas tres, que el propio
incremento declara:

- **«Offline verificado» es una afirmación acotada.** Significa «sin dependencias
  de Internet **declaradas**», no «producto empaquetado y distribuible» ni «probado
  sin red». **No hay corte de red ejecutado** (`RA-05`): los 12 flujos tienen
  veredicto estático.
- **La instalación limpia está documentada, no ejecutada** en una máquina
  físicamente limpia (`RB-05`).
- **El runtime sigue siendo el de desarrollo** (`RC-01`): la frontera se mide y se
  declara, no se cambia.

## Cierre

**CERRADO (2026-09-16).** Verificado contra GitHub, no contra el árbol local:

- **Commit de release:** `2eff6ea` (`2eff6eadc9e5dd13df26e3892d2e508167def649`).
- **Tag anotado:** `v3.71.0` (objeto `6ac22db`), apuntando a `2eff6ea`.
- **CI 7/7 verde** en
  [run 35136141089](https://github.com/jvelasca/english-tutor/actions/runs/35136141089):
  `Launcher (ruff + pytest)` `104928880868` · `Backend (ruff + pytest)`
  `104928881073` · `Frontend (tsc + vitest + build)` `104928880539` ·
  `Playwright E2E (visual)` `104928880854` · `Content validation` `104928880771` ·
  `Beta V3.0 gate` `104928880924` · `Release consistency` `104928880910`.
- **Consistencia de versión:** `check_release_consistency.py` verde en los **6
  orígenes**, y el job `Release consistency` del CI también.

**Informe esperado:** `docs/audit/AH-AUDITORIA-RELEASE-V371.md`.
