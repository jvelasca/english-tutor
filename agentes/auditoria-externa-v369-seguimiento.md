# Seguimiento / reclamo — auditorías externas de V3.69 (`Z` y `Z2`)

> **Qué es este archivo.** El registro operativo de **dos auditorías externas de
> V3.69 que están entregadas (briefing listo) pero cuyos informes NO se han
> recibido**. No es una auditoría: es el **estado** + el **texto de reclamo** +
> el **protocolo de acuse**, para que el gerente pueda reclamar sin reconstruir
> el contexto.
>
> **Estado (2026-09-16):** ambas **⏳ PENDIENTES DE INFORME** (entregadas el
> 2026-09-15; sin acuse). V3.69 ya está **publicada** (`9a4e70a`, tag `v3.69.0`,
> CI 6/6) y **V3.70 también** (`9ba9c49`, tag `v3.70.0`, CI 6/6), así que si la
> ventana «pre-implementación» de `Z` pasa, el dictamen se aplicará **contra el
> código publicado** (ya está previsto en el bloque ACTUALIZACIÓN del propio
> briefing).

## 1. Estado de las dos auditorías

| Briefing (punto de entrada) | Tipo | Entregado | Informe esperado | Estado |
|---|---|---|---|---|
| `agentes/auditoria-externa-v369.md` | **DISEÑO** (pre-implementación, con bloque `ACTUALIZACIÓN` para auditar contra el código publicado) | 2026-09-15 | `docs/audit/Z-AUDITORIA-DISENO-V369.md` | ⏳ **sin recibir** |
| `agentes/auditoria-externa-release-v369.md` | **RELEASE** (sobre el código entregado y los 5 hallazgos) | 2026-09-15 | `docs/audit/Z2-AUDITORIA-RELEASE-V369.md` | ⏳ **sin recibir** |

**Verificación del hueco** (los ficheros esperados **no existen** en el árbol):

```powershell
Test-Path docs/audit/Z-AUDITORIA-DISENO-V369.md      # False
Test-Path docs/audit/Z2-AUDITORIA-RELEASE-V369.md    # False
Get-ChildItem docs/audit/[XYZ]*.md                   # solo X (V3.67) e Y (V3.68)
```

> **Nota de nomenclatura:** el prefijo `Z` está reservado al informe de diseño y
> `Z2` al de release. La auditoría de la **release de V3.70** usa el prefijo
> **`AG`** (`agentes/auditoria-externa-release-v370.md` →
> `docs/audit/AG-AUDITORIA-RELEASE-V370.md`) para no colisionar con los dossiers
> `AA`–`AF` del propio incremento.

## 2. Objeto de cada informe (qué debe entregar el auditor)

### 2.1 `Z` — auditoría de DISEÑO de V3.69

Dictaminar el **diseño** de la batería E2E (roles, cobertura frente a los 10 casos
de `X`, calidad de cada escenario) **y**, con el bloque `ACTUALIZACIÓN`, comprobar
las afirmaciones del release contra el **código publicado**:

- la regla dura (**diff de código de producto CERO**:
  `git diff v3.68.0 v3.69.0 --stat -- backend frontend ':!backend/tests' ':!frontend/tests'`
  → **2 ficheros / 2 líneas**); cualquier otra línea de producto es **P1**;
- la tabla de cobertura frente a los **10 casos** de la auditoría `X`;
- la **calidad de la aserción** de cada escenario (¿fallaría si el comportamiento
  no se cumple?);
- la **honestidad de los cinco hallazgos** aceptados como deuda.

### 2.2 `Z2` — auditoría de RELEASE de V3.69

Dictamen **por escenario** (E01–E19 + E16b), **dictamen de los cinco hallazgos**
de §C (E01(a), E08, E15, E17, §F-1) y del alcance del diff, y **veredicto de una
línea** («¿se acepta `v3.69.0` como base para V3.70, con o sin condiciones?»). El
briefing contiene **15 afirmaciones falsables**, comandos de reproducción y **13
preguntas de alto valor**, con checklist de cierre.

### 2.3 Requisitos comunes

- Formato `docs/audit/TEMPLATE.md`: `Alcance · Método · Evidencia · Hallazgos
  (| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |) ·
  Veredicto · Regenerar / Verificar`.
- Severidades `P0`/`P1`/`P2`/`P3` con `alta`/`media`/`baja`/`documental` y
  evidencia `archivo:línea`.
- Distinguir **«el test no demuestra»** de **«el motor no cumple»**.
- **Solo lectura**: no se modifica código, datos, configuración ni etiquetas.

## 3. Texto de reclamo (listo para enviar)

> **Asunto:** Recordatorio — auditorías externas de `v3.69.0` (informes `Z` y `Z2`)
>
> Hola:
>
> El 2026-09-15 os entregamos **dos puntos de entrada autocontenidos** para auditar
> `v3.69.0` (release **publicada**: commit `9a4e70a`, tag anotado `v3.69.0`, `main`
> de `jvelasca/english-tutor`, CI 6/6 run `34978215154`):
>
> 1. **Diseño** — `agentes/auditoria-externa-v369.md` → informe esperado en
>    `docs/audit/Z-AUDITORIA-DISENO-V369.md`. Incluye un bloque **ACTUALIZACIÓN**
>    para poder auditar el diseño **contra el código ya publicado**.
> 2. **Release** — `agentes/auditoria-externa-release-v369.md` → informe esperado
>    en `docs/audit/Z2-AUDITORIA-RELEASE-V369.md`, con **15 afirmaciones
>    falsables**, comandos de reproducción y **13 preguntas de alto valor**.
>
> A día de hoy **no hemos recibido ninguno de los dos informes** (los ficheros
> esperados no existen en el repositorio). Os agradeceríamos:
>
> - un **acuse** con la fecha estimada de entrega, y
> - si el alcance necesita recortarse, **qué parte** podéis cubrir.
>
> Contexto que ha cambiado desde el briefing: desde entonces se publicó también
> **`v3.70.0`** (commit `9ba9c49`, tag `v3.70.0`, CI 6/6 run `35062382562`), una
> release de **medición** (33 hallazgos pedagógicos, sin corregir nada). El
> dictamen de `Z`/`Z2` **sigue siendo válido y aplicable** contra el código
> publicado; nada de lo auditado se ha modificado.
>
> Gracias.

## 4. Protocolo cuando lleguen los informes

1. **Archivar** el informe en la ruta exacta esperada (`Z-…` / `Z2-…`) y
   **no editarlo**.
2. **Registrar** la recepción en la nota de cabecera de `docs/RELEVO.md` (nota
   nueva encima de la actual) y en la fila correspondiente del tablero de
   `PLAN.md` (hoy `⏳ lanzada` → `✔ archivada`).
3. **Triar por severidad**: los P1/P2 se asignan a fase (contenido → V4.0.x ·
   motor/acreditación → Planner 4.0 · runtime → V3.71 · UX → V3.72); los P1 que
   contradigan un veredicto previo se tratan como **corrección documental** o se
   trasladan al incremento que corresponda.
4. **No reabrir** la release cerrada `v3.69.0`: el dictamen se aplica como
   corrección documental o se traslada al roadmap, igual que se hizo con `Y`.
5. Si el informe **promueve** un hallazgo aceptado (E01(a), E08, E15, E17, §F-1) a
   P1/P2, **abrir entrada** en `docs/audit/PARKED.md` con la nueva severidad y su
   fase.
