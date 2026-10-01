# Release notes — English Tutor v3.73.5

**Fecha:** 2026-09-17 · **Tipo:** release de **PARCHE** (cierra el ancla del punto de
entrada de la auditoría externa; **sin** capacidad pedagógica nueva y **sin** cambios
de producto) · **Versión de app:** `3.73.4 → 3.73.5`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el banco y SIN tocar el currículum.** El backend
de producto, el frontend de producto y el launcher están **intactos**, y **el arnés de
validación, sus tests y el contrato de los 7 gates no se tocan**: el diff es
**documentación**. El contenido funcional de esta línea sigue siendo el de V3.73.1.

---

## Qué es esta release

Hasta V3.73.4, el **punto de entrada de la auditoría externa**
(`agentes/auditoria-total-externa-v373.md`) se publicaba **fuera del tag que él mismo
declaraba**: el re-anclaje era un commit **posterior** al tag.

La causa no era de redacción, era **estructural**. El documento fijaba a mano tres
datos:

- el SHA del commit de release,
- el objeto del tag anotado,
- el id numérico del run de CI y el de cada job.

**Ninguno de los tres puede existir cuando se escribe el commit.** Un commit no puede
contener su propio SHA ni el id de la run que dispara su push: son datos que solo
existen **después** de publicar. Así que el documento nacía desfasado, y el
re-anclaje que lo corregía volvía a nacer fuera del tag siguiente. El ciclo estaba
admitido en la propia nota de historial («es un invariante de la release vigente: se
re-ancla en cada cierre»), pero nombrar el síntoma no cerraba la causa: `main` iba
**siempre** por delante del tag en documentación y el auditor que hacía
`git checkout v3.73.4` leía un documento que hablaba de `v3.73.3`.

Esta release cierra la causa.

**Lo que NO hace:** no toca producto (ni backend, ni frontend, ni launcher), no toca
el arnés `scripts/validation_gate.py` ni sus tests, no añade ni retira gates, y **no
cierra los 7 gates físicos**, que siguen `pending` por diseño (`status --strict` sigue
**rojo**).

---

## 1 · El ancla pasa a ser el tag, no el SHA

El documento declara la release auditada **por su tag** y entrega los comandos que
resuelven los identificadores, en lugar de congelar valores que no puede conocer:

```bash
git fetch --tags
git rev-parse v3.73.5            # objeto del tag anotado
git rev-parse v3.73.5^{commit}   # commit de release (el SHA exacto que se audita)
git log -1 --format='%H %s' v3.73.5^{commit}
```

Esto tiene una consecuencia que es el objetivo de la release: **el commit de release
es final**. No hace falta ningún commit documental posterior, así que **el tag
contiene su propio punto de entrada** y `main` deja de ir por delante.

## 2 · El estado de publicación se verifica por comando

El run de CI deja de ser un dato fijado a mano (que envejece en cuanto entra un
commit) y pasa a ser una **comprobación reproducible** que el auditor ejecuta en el
momento de auditar:

```bash
gh run list --commit $(git rev-parse v3.73.5^{commit}) --limit 1
```

Debe salir **`success`** con los **11 jobs** en verde. Los nombres de los jobs y su
condición (bloqueante / informativo declarado) siguen listados en el documento, pero
**sin ids de job congelados**.

## 3 · El invariante se enuncia entre el tag y `main`

El invariante del código ya no se afirma «en el momento de redactar» (una promesa que
el documento no puede cumplir desde dentro del tag), sino como una **comprobación que
el auditor ejecuta**:

```bash
git diff --stat v3.73.5..main -- backend frontend launcher scripts
```

Debe salir **vacío**: da igual clonar `main` o hacer `git checkout v3.73.5`, el
código de producto y el arnés son los mismos. Si hay diferencia en esas cuatro rutas,
es un hallazgo **P0**.

## 4 · La nota de historial nombra la causa raíz

La nota deja de admitir la rutina («se re-ancla en cada cierre») y describe el
defecto y su cierre, con una regla explícita para el futuro: **si un documento de este
tipo vuelve a fijar un SHA o un run a mano, es una regresión**.

---

## Verificación (lo que se ejecutó)

```powershell
# Backend (esta release NO toca producto ni arnés: se comprueba que no ha derivado)
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q      # 2798 passed
.venv\Scripts\python.exe -m ruff check .           # limpio

# Frontend
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
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py            # 6 orígenes (3.73.5)
backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py --strict         # 0/0/0
git diff --stat -- docs/audit/generated/release-validation.md docs/audit/generated/release-validation.json
# tras regenerar con `auto --require-dist`: debe salir VACÍO
```

| Dato | Valor |
|---|---|
| `VERSION` | `3.73.5` |
| Cambios de código (producto y arnés) | **ninguno**: el diff frente a `v3.73.4` es solo documentación |
| Orígenes de versión consistentes | **6/6** (`scripts/check_release_consistency.py`) |
| `auto --require-dist` | **10/10**, e informe regenerado **idéntico** al commiteado |
| Gates | **7 en `pending`** (no se mueve ninguno) |

---

## Honestidad

- **Los 7 gates siguen en `pending`.** Esta release **no** ha cortado la red, no ha
  instalado en una máquina limpia, no ha probado un móvil ni un micrófono reales. Es
  una release de **coherencia documental**; la validación física sigue siendo el único
  hito pendiente para V4.0.
- **`status --strict` sigue saliendo 1** y eso sigue siendo lo correcto: es la puerta
  de V4.0, no un fallo.
- **Esto no es «arreglar un documento»: es retirar un mecanismo que producía
  documentos desfasados por construcción.** El desfase de `v3.73.4` se documenta como
  defecto cerrado; el tag `v3.73.4` y su run se conservan **intactos** y quedan como
  base de comparación.
- **Los identificadores ya no están «citados», están «derivados».** El auditor pierde
  la comodidad de leer un SHA en el texto, y gana que ese dato sea siempre el correcto
  en el momento de auditar. Es el intercambio que exige un documento que vive dentro
  del artefacto que describe.

## Criterio de V4.0 (sin cambios)

V4.0 se declara cuando `validation_gate.py status --strict` salga **0** y, con el
árbol congelado, `status --strict --same-tree` salga **0** también: los 7 gates en
`pass` **contra el mismo commit**. El siguiente hito sigue siendo el que estaba:
**ejecutar físicamente G1–G7**.
