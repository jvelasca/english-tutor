# Release notes — English Tutor v3.73.3

**Fecha:** 2026-09-17 · **Tipo:** release de **PARCHE** (prepara la ejecución de los
7 gates y corrige una deriva de protocolo; **sin** capacidad pedagógica nueva y
**sin** cambios de producto) · **Versión de app:** `3.73.2 → 3.73.3`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el banco y SIN tocar el currículum.** El
backend de producto, el frontend de producto y el launcher están **intactos**: el
diff es el **arnés de validación**, sus **tests** y **documentación**. El contenido
funcional de esta línea sigue siendo el de V3.73.1.

---

## Qué es esta release

V3.73.0 construyó el instrumento de los 7 gates y V3.73.1/V3.73.2 cerraron la GUI
y su CI. Lo que faltaba era lo único que el instrumento **no puede hacer por sí
mismo**: que alguien los ejecute. Esta release entrega el **kit de campo** para esa
ejecución, **corrige la deriva que habría hecho probar el artefacto equivocado** y
**re-ancla el punto de entrada de la auditoría externa**, que había quedado
caduco y habría producido un hallazgo falso.

**Lo que NO hace:** no toca producto (ni backend, ni frontend, ni launcher), no
abre arquitectura y **no cierra los 7 gates físicos**, que siguen `pending` por
diseño (`status --strict` sigue **rojo**).

---

## 1 · El kit: que la ejecución no haya que improvisarla

El instrumento de V3.73 sabe **registrar** un gate (`record`) y **exigirlo**
(`status --strict`), pero la ejecución física seguía sin planilla: los protocolos
existen y están bien, pero están repartidos en seis documentos y no dicen en qué
orden hacerlos ni qué comando exacto apuntar.

`docs/audit/KIT-VALIDACION-GATES.md` es esa planilla, y su regla de diseño es **no
duplicar los protocolos**: los enlaza. Contiene:

- **Pre-vuelo** (una vez): `npm run build` + `auto --require-dist` en 10/10, la
  identidad del árbol que se sella en cada `record` (`VERSION` y `HEAD`), el
  manifiesto offline y las URLs de producto.
- **Reglas del instrumento:** un gate no se cierra con una opinión; sin `--notes`
  el registro se rechaza; `fail` y `skip` se registran con su motivo.
- **Hoja por gate (G1–G7):** protocolo enlazado, precondiciones, pasos numerados,
  qué cuenta como FALLO, qué evidencia capturar y el comando `record` copiable.
- **Agrupación por sesión:** G3+G5 (Windows real), G1 (sin red), G6 (recorridos),
  G4 (dispositivos), G2 (máquina limpia) y G7 (despacho con instrumentos).

---

## 2 · La deriva: se iba a probar otro artefacto

Los dos protocolos que se ejecutan **a pie de máquina** seguían apuntando al
**dev server de Vite**:

| Documento | Antes | Ahora |
|---|---|---|
| `docs/audit/RA-RUNTIME-OFFLINE.md` (E5 flujo 1 y §5) | «Vite dev server (Node) sirviendo `src/`» · `https://localhost:5173` | backend sirviendo `dist` en `https://localhost:8000` (Node solo para **compilar**) |
| `docs/audit/G-DEVICES.md` (preparación) | `https://<ip>:5173` | `https://<ip>:8000` |

Desde V3.72 el runtime de producto es **un solo origen HTTPS en `:8000`**; el
`:5173` es modo de desarrollo. Un auditor de dispositivos que siguiera el runbook
al pie de la letra habría certificado **otro artefacto** — y el resultado de G1 y
G4 habría sido inválido sin que nada lo delatara.

Se corrige también `docs/audit/RB-INSTALACION.md`, que llamaba a Node y npm
requisito de **ejecución** cuando desde V3.72 son requisito de **compilación**.

## 3 · El guard: que la deriva no vuelva por la puerta de al lado

El arnés ya vigilaba la matriz de dispositivos (`check_device_matrix`), pero **solo
esa**. Los otros dos protocolos podían derivar sin que `auto` se enterara: es
exactamente lo que había pasado.

`check_device_matrix` se generaliza a **`check_gate_protocol_origins`** (id
`gate-origins`), que recorre los **tres** protocolos funcionales y falla si alguno
contiene `:5173` o no contiene `:8000`. **5 tests nuevos** fijan el contrato (falla
con dev server, falla sin `:8000`, pasa con `:8000`, falla si el protocolo
desaparece, y los tres existen).

## 4 · El re-anclaje de la auditoría externa (en el cierre)

`agentes/auditoria-total-externa-v373.md` es el prompt autocontenido que se le da
al auditor externo. Estaba anclado a `v3.73.0` y afirmaba:

> `git diff --stat v3.73.0..main -- backend frontend launcher scripts` debe salir
> **vacío** (…) Si el auditor encuentra una diferencia en esas cuatro rutas entre
> el tag y `main`, tiene un hallazgo **P0**.

Ese diff **no** sale vacío: V3.73.1 cambió `frontend/**` y V3.73.2 cambió
`backend/config.py`, `backend/scripts/audit_dossier.py` y `backend/tests/**`. Es
decir: el auditor habría abierto un **P0 falso en su primer comando**, y sus
cifras (versión, `pytest`, número de tests del arnés) ya no eran las publicadas.
El punto de entrada se re-ancla al tag de esta release —con el invariante
**verificado**, las cifras reales y el kit en el orden de lectura— **en el cierre
documental**, una vez comprobado el CI de publicación: ese documento declara un
estado verificado contra GitHub, no contra un árbol local, así que no puede
escribirse antes de publicar.

---

## Verificación (lo que se ejecutó)

```powershell
# Backend
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q      # 2784 passed
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
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py            # 6 orígenes (3.73.3)
backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py --strict         # 0/0/0
```

La autoridad final es el **checkout limpio del CI**: V3.73.2 dejó escrito que un
invariante que depende de rutas del árbol solo se puede verificar ahí, así que la
verificación no se da por buena hasta que el run de publicación sale verde.

---

## Honestidad

- **Los 7 gates siguen en `pending`.** Esta release **no** ha cortado la red, no
  ha instalado en una máquina limpia, no ha probado un móvil real ni un micrófono
  real. Entrega el kit para hacerlo y el guard para que el protocolo no mienta;
  **la ejecución sigue siendo humana**.
- **`status --strict` sigue saliendo 1** y eso sigue siendo lo correcto: es la
  puerta de V4.0, no un fallo.
- **El kit no sustituye a los protocolos.** Si un protocolo cambia, manda el
  protocolo; el kit solo ordena y registra.
- **El guard es estático.** Comprueba que los documentos apuntan al origen de
  producto, no que la app funcione: eso lo fijan los flujos de G1–G7.
- **Sigue abierto** `RA-02` (endpoint de Ollama sin declarar en `config.py`), y
  `RA-07`/`RD-05` como deuda aceptada.

## Criterio de V4.0 (sin cambios)

V4.0 se declara cuando `validation_gate.py status --strict` salga **0**: los 7
gates en `pass`. Con el kit y el guard en su sitio, el siguiente hito es
exactamente el que estaba: **ejecutar físicamente G1–G7**.
