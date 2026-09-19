# Release notes — English Tutor v3.75.2

**Fecha:** 2026-09-19 · **Tipo:** release **DOCUMENTAL + INSTRUMENTO** (parche) ·
**Versión de app:** `3.75.1 → 3.75.2`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el banco, SIN tocar el currículum y SIN una
sola línea de código de producto.** Ninguna capacidad pedagógica nueva y ninguna
ruta de producto nueva: publica la **pausa pedagógica pre-baseline** —la auditoría
psicométrica del banco sobre el baseline `v3.75.1`— y publica también el **ancla
para la auditoría externa**, que estaba caduca.

> **Esto no cambia lo que ve el alumno.** No se toca ni un `id`, ni un enunciado,
> ni una opción, ni una posición del currículum ni del banco. Lo que cambia fuera
> de la documentación es el **instrumento de medición de solo lectura** y su test.
> Ninguna app, ni el launcher, ni el CI necesitan adaptarse.

---

## Qué es esta release

Es una release de **documentación y de instrumento**, el mismo tipo que V3.73.5 y
V3.73.6. Existe por dos razones concretas, y ninguna de las dos es «arreglar» el
banco:

1. **Publicar la pausa pedagógica.** El gerente decidió **no publicar una V3.75.2
   de corrección** para el sesgo de longitud medido en V3.75.1
   (`release-notes-v3.75.1.md` §8 los declara abiertos). La razón es explícita:
   seguir tocando el banco sin entender el patrón completo sería
   contraproducente. En su lugar se hace una **pausa de medición** sobre el
   baseline congelado **`v3.75.1` = `7962d57`**, y esa medición se **publica con
   un ancla estable** para que se pueda auditar desde fuera.
2. **Reparar el punto de entrada de la auditoría externa**, que había quedado
   **caduco** y habría producido un **P0 falso** en el primer comando del auditor.

---

## 1. El bloqueo que obliga a esta release: el ancla no existía y la entrada estaba caduca

### 1.1 El trabajo no era visible desde GitHub

Toda la pausa (instrumento, tests, dossiers, cierre documental) estaba **sin
commitear**. GitHub solo ve **pushes**, así que ningún auditor externo podía verla.
Y aunque se subiera a `main`, la casa ancla la auditoría externa a un **tag**, no a
una rama móvil: es la lección de V3.73.5, donde el re-anclaje quedaba fuera del tag
que él mismo declaraba y `main` iba siempre por delante en documentación.

### 1.2 La entrada vigente abría un P0 falso

`agentes/auditoria-total-externa-v375.md` declara auditar **`v3.75.0`** y su
invariante es:

```bash
git diff --stat v3.75.0..main -- backend frontend launcher scripts
```

Debe salir **vacío**; el propio documento dice que cualquier diferencia en esas
cuatro rutas entre el tag y `main` es un hallazgo **P0**.

Medido: **no sale vacío**. V3.75.1 tocó `backend/` —12 ficheros, `+980 / −637`:
`backend/curriculum/*.json`, `backend/scripts/rebalance_mc_positions.py`,
`backend/services/curriculum.py`, `backend/tests/test_ped_content_cefr_v370.py`,
`backend/config.py` y los dos `frontend/package*.json`—. Es exactamente la
regresión que V3.73.3 y V3.73.6 documentan y que V3.73.5 declaró cerrada, esta vez
causada por una release de **contenido** y no por un commit documental.

En cambio, contra el tag de esta release base:

```bash
git diff --stat v3.75.1..main -- backend frontend launcher scripts   # VACÍO
```

`v3.75.1` es hoy un ancla **válida y verificable**, y es donde se ancla la entrada
nueva.

---

## 2. El instrumento nuevo (solo lectura)

Todo vive en `backend/scripts/audit_dossier.py`, que es una herramienta de
desarrollo, **no** una ruta de producto. `mc_banks()` pasa a ser la fuente única de
los tres ejes, de modo que no pueden discrepar entre sí.

| Subcomando | Qué mide | Por qué |
|---|---|---|
| `item-form` (**nuevo**) | Nº de opciones (`k`), **posición** y **longitud** de la opción correcta, por banco, nivel y grupo de `k`, con **posiciones muertas** | El sesgo posicional se midió por nivel; la **forma** del ítem no se había medido nunca |
| `distractor-signals` (**nuevo**) | Tres heurísticas declaradas —eco de palabra clave del enunciado, outlier de longitud y literal de cantidad— más una **muestra determinista** | Buscar si la correcta es inferible **sin entender el enunciado** |
| `mc-bias` (**corregido**) | Separa **exámenes** de **placement** y desglosa por nivel de examen | Hasta ahora el grupo «exámenes level/placement» **solo contaba los 22 exámenes**: el **placement (24 ítems) no aparecía** en esa medición, así que el «63,6 % en posición 0» de V3.75.1 es de **exámenes**, no del conjunto |
| `cefr-adequacy` | **Sin cambios** | No entra en el alcance de la pausa |

Artefactos emitidos, deterministas y versionados:
`docs/audit/generated/item-form.{md,json}`,
`docs/audit/generated/distractor-signals.{md,json}` y la regeneración de
`mc-position-bias.{md,json}`.

**Las señales se declaran subestimadas a propósito.** `quantity_literal` dispara
**1 de 904** ítems y `prompt_keyword_echo` solo cuenta el **eco exclusivo** (una
palabra del enunciado que aparece en **una sola** opción). Un `0 %` en esas
columnas **no** significa «sin problema»: significa que la heurística no lo ve. Se
dice en el propio artefacto para que nadie lea el vacío como una garantía.

---

## 3. La ejecución: cinco ejes en paralelo y una síntesis

Cada eje produjo su propio dossier con una regla de evidencia explícita —`[D]`
declarado, `[A]` medido en el árbol, `[R]` reproducible por comando—:

| Eje | Dossier | Objeto |
|---|---|---|
| **AH** | `docs/audit/AH-PSICO-LONGITUD.md` | Sesgo de longitud (la correcta es la más larga) |
| **AI** | `docs/audit/AI-PSICO-ASSESSMENTS.md` | Posición correcta en los **instrumentos de evaluación** (exámenes y placement) |
| **AJ** | `docs/audit/AJ-PSICO-FORMA.md` | Forma del banco: `k`, posiciones muertas, outliers de forma |
| **AK** | `docs/audit/AK-PSICO-DISTRACTORES.md` | Distractores inferibles por forma |
| **AL** | `docs/audit/AL-PSICO-NIVELES.md` | Patrón por nivel A1→C2 |
| **AM** | `docs/audit/AM-SINTESIS-PSICOMETRIA-V3751.md` | **Síntesis** y deduplicación de cruces |

La síntesis cita también `docs/audit/AG-AUDITORIA-MOTOR-V375.md` (el dossier del
motor que ya existía sin versionar).

**Resultado: `0 P0` · `4 P1` · `12 P2` · `9 P3`** (25 hallazgos → **5 problemas
reales** tras deduplicar los cruces entre ejes). El P0 de V3.75.1 **no se reabre**.
Los cinco problemas, en corto:

1. **Sesgo de longitud real, concentrado por lote.** Corpus C1/C2 **80 %**, B1
   checks 50,9 %, C2 checks 56,1 %, placement 50 %; los checks globales 39,1 %
   (+6,0 pp sobre el azar). **No es monótono por nivel**, así que no es un
   incumplimiento de banda del `CEFR-REFERENCE.md`: es **deriva de autoría**.
2. **Los instrumentos de evaluación conservan sus dos sesgos** (V3.75.1 no los
   tocó): en los **exámenes** la **posición 2 está muerta** (0/22) y la 0 concentra
   el 63,6 %; en el **placement** la **posición 1 concentra 17/24 = 70,8 %** y la 2
   aparece **una vez**. El atajo es **latente** (ningún componente consume el
   placement) y **contenido por umbrales** en el examen.
3. **La forma del banco es heterogénea por residuo**: 10 checks de `k=4` que son un
   accidente de autoría en A1 listening, corpus entero `k=4`, checks y exámenes
   `k=3`, y **ningún** `k=2`. No hay una política de forma declarada.
4. **Dos de las tres señales del instrumento subestiman** lo que dicen medir (ver
   §2).
5. **El invariante posicional de V3.75.1 aguanta también por nivel** (ninguna
   posición muerta), pero es **emergente**, no blindado.

---

## 4. El ancla nueva para la auditoría externa

Se publica **`agentes/auditoria-total-externa-v3751.md`**, anclado a **`v3.75.1`**.
Sustituye, para auditar `main`, a `agentes/auditoria-total-externa-v375.md` (que
sigue siendo válido como historia de lo que auditó `v3.75.0`).

Reglas que hereda de V3.73.5 y no se rompen:

- **El ancla es el tag**, y el commit y el objeto del tag se **resuelven con
  `git rev-parse`**, nunca se fijan a mano (§1 del propio documento).
- **El commit de release es final**: este punto de entrada viaja **dentro** del
  commit del tag `v3.75.2`, y no hay commit documental posterior.
- El estado de publicación (SHA y CI) se **verifica por comando**, no se declara
  con un valor escrito a mano.

**El invariante se declara tal y como es, no como sería cómodo.** El patrón «el
diff de `backend`, `frontend`, `launcher` y `scripts` sale vacío» **ya no puede
usarse**: esta release añade un test en `backend/tests/` y toca un fichero de
`backend/scripts/`. Así que la entrada nueva separa dos comprobaciones:

```bash
# 1) Producto y contenido: VACÍO. Ni una línea.
git diff --stat v3.75.1..v3.75.2 -- \
  backend/services backend/routers backend/repositories backend/domain \
  backend/curriculum frontend/src launcher

# 2) El diff completo: NO vacío, y declarado como lista CERRADA.
git diff --stat v3.75.1..v3.75.2
```

Y la línea que sí cambia en `backend/config.py` se acota explícitamente:

```bash
git diff v3.75.1..v3.75.2 -- backend/config.py   # solo la línea de VERSION
```

---

## 5. Verificación

| Comprobación | Resultado |
|---|---|
| Backend | **2900 passed** (2882 de V3.75.1 + **18** de `test_psy_item_form_v3751.py`) |
| `ruff` | Limpio sobre los ficheros tocados |
| `check_release_consistency` | **OK** — `3.75.2` en los **6 orígenes** (`backend/config.py`, `frontend/package.json`, `frontend/package-lock.json`, `README.md`, `CHANGELOG.md`, `PLAN.md`) |
| Diff de producto y contenido | **Cero** (comando de §4, comprobado) |
| Frontend / launcher / CI | **Sin cambios de producto**: ninguno consume el orden de las opciones ni el instrumento |

El recuento de backend sube **exactamente** por los tests nuevos; no se reformula ni
se retira ninguno existente.

---

## 6. Honestidad

1. **Esta release no arregla nada del producto.** Publica mediciones y repara un
   ancla documental. Quien busque mejoras para el alumno no encontrará ninguna.
2. **El sesgo de longitud y los dos sesgos de los instrumentos de evaluación
   siguen exactamente donde estaban.** Se miden y se declaran; no se corrigen.
3. **La pausa no añade candados que fijen el defecto.** Los invariantes de forma se
   diseñarán **con** la corrección, no antes: un test que fije el sesgo actual sería
   un candado contra el arreglo.
4. **Mide tasa de acierto explotable, no aprendizaje.** Un ítem con la correcta más
   larga no es por sí solo un ítem malo.
5. **No mide la plausibilidad semántica** de un distractor (exigiría hablantes) ni
   la **tasa real** del atajo (el motor guarda acierto, no posición marcada: la
   estrategia se **simula**, no se observa).
6. **Los instrumentos de evaluación son 46 ítems, no 904.** El placement es 17/24 →
   IC95 % ≈ [52,6 %, 89,0 %]: no se generaliza con la confianza de los 368 checks.
7. **El P0 de V3.75.1 no se reabre.**
8. **Los 7 gates siguen en `pending`** y la identidad sellada en el kit sigue siendo
   la del pre-vuelo (`3.73.6` → `13cc30b`), que es historia y no se reescribe.
9. **El baseline queda declarado como `v3.75.1` = `7962d57`** (tag anotado objeto
   `2cd0e6d`): es el punto de reinicio, no esta release.

---

## 7. Notas de actualización

- **Para el usuario:** nada que hacer. No hay migración, ni cambio de contenido, ni
  cambio de contrato de API.
- **Para el auditor externo:** usar
  **`agentes/auditoria-total-externa-v3751.md`**, no la entrada `-v375`. La nueva
  declara la posición auditada, el invariante honesto y el kit en el orden de
  lectura.
- **Para el desarrollo:** `agentes/v3751-auditoria-psicometrica.md` es el briefing
  autocontenido que originó los cinco ejes, por si hay que re-auditar el banco tras
  la reautoría de V4.0.x.
