# Auditoría EXTERNA del producto — punto de entrada anclado a `v3.75.1`

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **el producto publicado
> en `v3.75.1`** —el baseline que se va a sellar antes de ejecutar los 7 gates— y,
> si lo considera parte del objeto, el **acta de medición** que se publica con él.
> La revisión es **de solo lectura**: no se cambia código, datos, configuración ni
> etiquetas publicadas.
>
> **Por qué esta auditoría y por qué ahora.** `v3.75.1` es la última release que
> **cambió el currículum servido** (cerró el sesgo posicional de los 368 checks,
> `release-notes-v3.75.1.md`). Una release que altera el contenido obliga a
> **volver a sellar el baseline**: la identidad del árbol que se sella en el kit de
> validación ya no puede ser la del pre-vuelo. Este documento es el ancla de esa
> auditoría, y publica además la **pausa pedagógica pre-baseline**: la medición que
> el gerente decidió hacer **antes** de tocar el banco otra vez, en lugar de
> parchear el sesgo de longitud a ciegas.
>
> **Aviso de encuadre (léelo antes de puntuar).** `v3.75.2` —el tag que contiene
> este documento— es una release **documental y de instrumento**: **ni una línea de
> producto ni de contenido**. Puedes auditar `v3.75.2` o `v3.75.1`
> indistintamente, y el §1 te da el comando que lo demuestra. Lo que `v3.75.2`
> **no** hace es arreglar nada: mide. Si el auditor busca «qué se ha corregido», la
> respuesta honesta es **nada**; si busca «qué se ha demostrado», esta es
> exactamente la auditoría que separa lo demostrado de lo declarado.
>
> **Estado:** entregado 2026-09-19, **dentro del commit de release** de `v3.75.2`.
> **Informe esperado:** `docs/audit/AN-AUDITORIA-TOTAL-V3751.md`. Prefijo **`AN`**
> porque `AA`–`AF` los ocupan los dossiers de V3.70, `AG`–`AM` están ocupados por
> los dossiers del motor y de la pausa pedagógica de esta línea (`AG`
> motor · `AH` longitud · `AI` instrumentos · `AJ` forma · `AK` distractores ·
> `AL` niveles · `AM` síntesis), y `AG`/`AH`/`AI`/`AJ` los reservan además los
> puntos de entrada externos de V3.70/V3.71/V3.73/V3.75, **ninguno con informe
> recibido**. Ver la nota de prefijos en `PLAN.md`.

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

1. `docs/RELEVO.md` — **cabecera** (nota de la posición vigente) y **§0 «START
   HERE»**.
2. `PLAN.md` — §«Estado actual» (registro release a release) y la tabla de
   trazabilidad de briefings y auditorías.
3. `docs/audit/PARKED.md` — lo **aparcado a propósito** por fase y los pendientes
   de acción humana. Sus secciones **`V3.75`** y **`V3.75.1`** son la declaración
   honesta de lo que esta línea **no** cierra.
4. **Este documento**, hasta el final.
5. `docs/audit/AM-SINTESIS-PSICOMETRIA-V3751.md` — la **síntesis** de la pausa
   pedagógica, con los `0 P0 · 4 P1 · 12 P2 · 9 P3` y los cinco problemas reales.
   Los seis dossiers que consolida (`AH`–`AL`, más `AG`) están en `docs/audit/`.
6. `docs/audit/VERIFICACION-SEGURIDAD-V373.md` — la **contra-verificación
   interna**, hallazgo a hallazgo, de la sección de seguridad del informe externo
   sobre `v3.73.6`. El auditor debe tratarla como **una afirmación más**, no como
   evidencia.
7. Notas de las tres releases de producto: `release-notes-v3.73.7.md`,
   `release-notes-v3.74.0.md`, `release-notes-v3.75.0.md`, y de las dos de
   contenido/documentales: `release-notes-v3.75.1.md` y
   `release-notes-v3.75.2.md`.
8. `docs/BETA_GATES.md`, `docs/audit/KIT-VALIDACION-GATES.md` y
   `docs/audit/VALIDATION-RELEASE-V373.md` — los 7 gates: **siguen en `pending`**;
   el kit es la planilla de campo, no una validación.
9. `docs/ARQUITECTURA.md`, `docs/PREMISAS.md`, `docs/CONSTITUCION-PEDAGOGICA.md`,
   `CHANGELOG.md` y `docs/audit/TEMPLATE.md` (formato del informe).

**Punto de partida git:**

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor
git fetch --tags
git log --oneline -3 main
```

---

## 1. Punto de entrada verificado (contra GitHub, no contra un árbol local)

- Repositorio: `jvelasca/english-tutor` (**público**), rama por defecto `main`.
- **Release auditada: el tag anotado `v3.75.1`.** Los identificadores exactos se
  **resuelven con git** en vez de fijarse aquí a mano:

```bash
git fetch --tags
git rev-parse v3.75.1            # objeto del tag anotado
git rev-parse v3.75.1^{commit}   # commit de release (el SHA exacto que se audita)
git log -1 --format='%H %s' v3.75.1^{commit}
```

- **Dónde vive este documento:** dentro del tag **`v3.75.2`**, que existe
  precisamente para que haya un ancla estable desde la que auditar `v3.75.1` (el
  trabajo de la pausa estaba sin publicar, y GitHub solo ve pushes).

- **Por qué este documento NO fija el SHA ni el run a mano (desde V3.73.5).** Un
  commit **no puede contener** su propio SHA ni el id de la run de CI que dispara su
  push: son datos que solo existen **después** de publicar. Fijarlos obligaba a un
  commit de re-anclaje **posterior al tag**, que quedaba a su vez fuera del tag
  siguiente, y por eso `main` iba siempre por delante en documentación. Desde
  V3.73.5 el ancla es el **tag**, el estado de publicación se **verifica por
  comando** y este archivo es coherente **dentro de su propio tag**, de modo que el
  commit de release es **final**. Si un documento de este tipo vuelve a fijar un SHA
  o un run a mano, es una **regresión**.

- **Base de comparación sugerida:** `v3.75.0` (la release inmediatamente anterior
  con cambios de producto) y, para el arco largo, `v3.73.6` (el árbol de la última
  auditoría externa). El código **de producto** **sí** cambió en V3.73.7 → V3.74.0 →
  V3.75.0; lo que **no** cambió desde `v3.75.0` es el **banco de contenido**; y lo
  que **no** cambia entre `v3.75.1` y `v3.75.2` es **ni el producto ni el
  contenido**.

- **Sin GitHub Release** para `v3.75.2`: es una decisión declarada del gerente
  (solo tag anotado, que es la convención real del repo desde `v3.34.0`). El último
  Release object publicado es `v3.33.0`.

### 1.1 Invariante del producto y del contenido — **el honesto, no el cómodo**

Aviso para el auditor: **el patrón clásico de esta casa ya no sirve**. Hasta
V3.75.1 el invariante era «el diff de `backend frontend launcher scripts` sale
vacío». Esta release **añade un test** (`backend/tests/test_psy_item_form_v3751.py`)
y **toca un fichero de `backend/scripts/`** (`audit_dossier.py`), así que ese
invariante **no puede declararse** sin mentir. Lo que se declara es esto:

**(a) Producto y contenido: vacío.** Ni una línea.

```bash
git diff --stat v3.75.1..v3.75.2 -- \
  backend/services backend/routers backend/repositories backend/domain \
  backend/curriculum frontend/src launcher
```

Debe salir **vacío**. Es decir: **puedes auditar `v3.75.2` o `v3.75.1` y estás
auditando el mismo producto y el mismo contenido.** Si no sale vacío, tienes un
hallazgo **P0**.

**(b) El diff completo: no vacío, y declarado como lista CERRADA.**

```bash
git diff --stat v3.75.1..v3.75.2
```

La lista esperada es exactamente esta, y **nada más**:

| Ruta | Qué es |
|---|---|
| `backend/config.py` | **Solo** la línea `VERSION` (`3.75.1` → `3.75.2`) |
| `backend/scripts/audit_dossier.py` | El instrumento de medición (**no** es ruta de producto) |
| `backend/tests/test_psy_item_form_v3751.py` | **Nuevo**: 18 casos que fijan el contrato del instrumento |
| `docs/audit/generated/item-form.{md,json}` | **Nuevos**: artefacto determinista |
| `docs/audit/generated/distractor-signals.{md,json}` | **Nuevos**: artefacto determinista |
| `docs/audit/generated/mc-position-bias.{md,json}` | **Regenerados** (`mc-bias` separa exámenes de placement) |
| `docs/audit/AG-AUDITORIA-MOTOR-V375.md` | Dossier del motor, antes sin versionar |
| `docs/audit/AH-PSICO-LONGITUD.md` … `AM-SINTESIS-PSICOMETRIA-V3751.md` | Los seis dossiers de la pausa |
| `docs/audit/PARKED.md` | Lo aparcado, con la fase propuesta |
| `agentes/v3751-auditoria-psicometrica.md`, `agentes/auditoria-total-externa-v3751.md` | El briefing de la pausa y **este** punto de entrada |
| `CHANGELOG.md`, `PLAN.md`, `README.md`, `docs/RELEVO.md`, `release-notes-v3.75.2.md` | Documentación de release |
| `frontend/package.json`, `frontend/package-lock.json` | **Solo** el campo `version` |

Si aparece **cualquier otra ruta**, o si alguna de estas trae cambios que no sean
los declarados, es un hallazgo.

**(c) La línea de `config.py`, acotada:**

```bash
git diff v3.75.1..v3.75.2 -- backend/config.py   # debe mostrar SOLO la línea VERSION
```

**(d) `main` sirve el mismo producto** (verificado en el momento de publicar;
puede dejar de ser cierto en cuanto aterrice trabajo nuevo, y por eso el ancla es
el tag):

```bash
git diff --stat v3.75.1..main -- \
  backend/services backend/routers backend/repositories backend/domain \
  backend/curriculum frontend/src launcher
```

**Estado de publicación (verificado por comando, no fijado a mano):**

```bash
git rev-parse v3.75.2^{commit}      # SHA exacto del commit del tag
gh run list --commit $(git rev-parse v3.75.2^{commit}) --limit 1
```

La run del commit del tag debe estar en **`success`** con los **12 jobs** en verde
(un nombre por línea, para que un `grep` literal funcione):

- `Backend (ruff + pytest)`
- `Frontend (tsc + vitest + build)`
- `Release consistency`
- `Validation gate (checks automáticos)`
- `Beta V3.0 gate`
- `Content validation`
- `Playwright E2E (visual)`
- `Launcher (ruff + pytest)`
- `Dependency audit (pip-audit + npm audit)` (**bloqueante**)
- `Product origin (UI served over HTTPS)`
- `Launcher (Windows, ruff + pytest)` (**bloqueante**)
- `Product origin (Windows, informativo)` (**informativo declarado**,
  `continue-on-error: true`)

**Consistencia de versión:** `backend/config.py::VERSION` es la fuente única
(`scripts/check_release_consistency.py`) y `3.75.2` debe aparecer en **6 orígenes**:
`backend/config.py`, `frontend/package.json`, `frontend/package-lock.json`,
`README.md`, `CHANGELOG.md` y `PLAN.md`.

---

## 2. Qué trae esta línea, y con qué palabras

### 2.1 `v3.75.1` — el sesgo posicional del currículum (release de CONTENIDO)

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `backend/curriculum/{a1,a2,b1,b2,c1,c2}.json` | Los 368 checks, con la correcta **reposicionada** | Que **329 de 368** (89,4 %) tenían la correcta en la posición 0, y que ahora el reparto **por grupo de `k`** es ≤ 35 % por posición |
| `backend/scripts/rebalance_mc_positions.py` (nuevo) | Instrumento de **contenido** con `--write` y `--check`; `--check` **no escribe** y sale **1** si algo no cumple | Que el invariante es **re-ejecutable** y actúa de tripwire para la reautoría de V4.0.x |
| `backend/tests/test_ped_content_cefr_v370.py` | El test se **reformula en sitio**: de declarar el sesgo a **fijar el invariante** | Que una reautoría que vuelva a concentrar la correcta **hace fallar la suite** |
| `backend/services/curriculum.py`, `backend/config.py` | `CURRICULUM_VERSION` 1.3.0 → 1.3.1 | Que la constante identifica **qué contenido** se evaluó. Se **sella** en cada fila de evidencia y **nunca se compara** (verificado): no invalida estado de alumno |

**Lo que `v3.75.1` declara abierto (y `v3.75.2` no toca):** la correcta sigue siendo
la opción **más larga** en el **39,1 %** de los checks y en el **50 %** del
placement; `assessments.json` **no se toca** y sus 22 ítems siguen con la correcta
en la posición 0 en el **63,6 %**; solo **10 de 368** checks tienen 4 opciones.

### 2.2 `v3.75.2` — la pausa pedagógica y el ancla (release DOCUMENTAL)

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `backend/scripts/audit_dossier.py` | `item-form` y `distractor-signals` **nuevos**; `mc-bias` **corregido** | Que el grupo «exámenes level/placement» **solo contaba los 22 exámenes**: el **placement (24 ítems) no aparecía** en esa medición |
| `backend/tests/test_psy_item_form_v3751.py` (nuevo) | 18 casos: fuente única, coherencia de `k`/posiciones, determinismo, **solo lectura** y anti-deriva de los artefactos | Que el instrumento **no** puede escribir en `data/` ni en `curriculum/`, y que el `.md`/`.json` versionado coincide con lo que el instrumento emite |
| `docs/audit/AH`…`AM` + `AG` | Cinco ejes + síntesis + motor | Los `0 P0 · 4 P1 · 12 P2 · 9 P3` y los cinco problemas reales de §3 |
| `agentes/auditoria-total-externa-v3751.md` | **Este** punto de entrada | Que el anterior (`-v375`) abría un **P0 falso**: su invariante `git diff --stat v3.75.0..main -- backend frontend launcher scripts` **ya no salía vacío** porque V3.75.1 tocó `backend/` |

---

## 3. El acta de la pausa — qué se midió y qué se encontró

Los cinco problemas reales, deduplicados en
`docs/audit/AM-SINTESIS-PSICOMETRIA-V3751.md`:

1. **Sesgo de longitud, concentrado por lote** (corpus C1/C2 **80 %**, B1 checks
   50,9 %, C2 checks 56,1 %, placement 50 %; checks globales 39,1 %, +6,0 pp sobre
   el azar). **No monótono por nivel** ⇒ es **deriva de autoría**, no incumplimiento
   de banda del `CEFR-REFERENCE.md`.
2. **Los instrumentos de evaluación conservan sus dos sesgos** (V3.75.1 no los
   tocó): en los **exámenes** la **posición 2 está muerta** (0/22) y la 0 concentra
   el 63,6 %; en el **placement** la **posición 1 concentra 17/24 = 70,8 %** y la 2
   aparece **una vez**. El atajo es **latente** (ningún componente consume el
   placement) y **contenido por umbrales** en el examen.
3. **Forma del banco heterogénea por residuo**: 10 checks de `k=4` como accidente de
   autoría en A1 listening, corpus entero `k=4`, checks y exámenes `k=3`, **ningún**
   `k=2`. No hay política de forma declarada.
4. **Dos de las tres señales subestiman lo que dicen medir**: `quantity_literal`
   dispara **1/904** y `prompt_keyword_echo` solo cuenta el **eco exclusivo**. Un
   `0 %` ahí **no** es «sin problema».
5. **El invariante posicional aguanta también por nivel** (ninguna posición muerta),
   pero es **emergente**, no blindado.

**Lo que el acta declara que NO hace:** no corrige, **no añade candados que fijen el
defecto** (los invariantes de forma se diseñan **con** la corrección) y **no decide**
la política de forma ni el arreglo de `assessments.json`: **propone la fase**.

---

## 4. Batería automática — reproducir, no creer

El auditor **debe** ejecutar esto y comparar con lo declarado:

```powershell
# Backend
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q          # declarado: 2900 casos
.venv\Scripts\python.exe -m ruff check .              # declarado: limpio

# Instrumento de la pausa (solo lectura, no escribe nada)
.venv\Scripts\python.exe -m scripts.audit_dossier item-form
.venv\Scripts\python.exe -m scripts.audit_dossier distractor-signals
.venv\Scripts\python.exe -m scripts.audit_dossier mc-bias

# Los artefactos generados deben coincidir con los versionados:
git diff --stat docs/audit/generated/   # declarado: VACÍO tras regenerar

# Consistencia de versión
.venv\Scripts\python.exe ..\scripts\check_release_consistency.py   # declarado: 3.75.2 en 6 orígenes

# Frontend (sin cambios de producto en esta release; cifras de V3.75.0/V3.75.1)
cd ..\frontend
npx tsc --noEmit                                      # declarado: limpio
npx vitest run                                        # declarado: 721 passed (87 ficheros)
npm run build                                         # declarado: OK
npm audit --omit=dev --audit-level=high               # declarado: 0 vulnerabilidades

# Launcher (sin cambios de producto en esta release)
cd ..\launcher
..\backend\.venv\Scripts\python.exe -m pytest tests/ -q  # declarado: 142 passed
..\backend\.venv\Scripts\python.exe -m ruff check .      # declarado: limpio
```

**Nota honesta sobre el reparto de la suite de backend.** `2900 passed` es el
recuento **medido en el árbol de desarrollo** (con `frontend/dist` construido y los
modelos presentes). En un **clon limpio** el reparto no es idéntico: algunos casos
se **saltan** por artefactos no versionados. El **invariante** es el total de casos
(`2900`); el reparto `passed`/`skipped` **no** lo es. Si el auditor ve un número
distinto de `passed` en un clon limpio, **no** es un hallazgo por sí mismo: cuente
los casos.

---

## 5. Áreas y preguntas falsables

Cada pregunta debe responderse con **evidencia del árbol publicado**
(`archivo:línea`), **comando de reproducción** y **qué la falsaría**. Si no se puede
comprobar sin hardware o persona: **NO COMPROBABLE**.

### A. El ancla y la release documental

1. ¿Se sostiene el **invariante de producto y contenido** de §1.1(a) contra el tag
   real? ¿Y el de §1.1(b) coincide **exactamente** con la lista declarada?
2. ¿Cambia `backend/config.py` **solo** la línea `VERSION`?
3. ¿Está `3.75.2` en los **6 orígenes** y coinciden entre sí?
4. ¿Contiene el tag `v3.75.2` **este mismo documento** (y no un commit posterior)?
5. ¿Es el commit del tag **final** (sin commits documentales posteriores)?

### B. El instrumento de medición

6. ¿Escribe `audit_dossier.py` en `data/` o en `curriculum/`? El test declara que
   **no**. ¿Qué pasa si se le da un banco inválido?
7. ¿Es `item-form` **determinista** entre ejecuciones? ¿Y `distractor-signals`, con
   su muestra?
8. ¿Coincide el artefacto regenerado con el versionado, byte a byte?
9. ¿Es `mc_banks()` **de verdad** la fuente única de los tres ejes, o hay un camino
   que lea el banco por otra vía?
10. El `mc-bias` corregido **separa** exámenes y placement. ¿Declara cada grupo su
    `k`? ¿Coinciden las sumas de posiciones con el total de ítems de cada banco?
11. Las tres señales declaran **subestimar**. ¿Es correcta esa declaración, o hay
    alguna que **sobre**estime y pueda producir falsos positivos?

### C. Los hallazgos de la pausa

12. Verifique el **39,1 %** de longitud en checks y el **80 %** del corpus C1/C2.
    ¿Es reproducible?
13. Verifique la **posición 2 muerta** en los exámenes (0/22) y el **17/24 = 70,8 %**
    de la posición 1 en el placement. Con `n = 24`, ¿es defendible el intervalo
    declarado?
14. ¿Es cierto que **ningún componente consume el placement**, como afirma el
    dossier `AI`? Si alguno lo consumiera, el atajo dejaría de ser latente.
15. El claim de que el sesgo de longitud es **deriva de autoría** y no
    incumplimiento CEFR se apoya en que no es monótono por nivel. ¿Se sostiene con
    los datos, o hay una banda del `CEFR-REFERENCE.md` que lo incumpla?
16. ¿Sobrevive el invariante posicional de V3.75.1 al **desglose por nivel** que
    hace `AL`, o hay un nivel con posición muerta?

### D. El producto (heredado de la auditoría anterior)

17. **Identidad:** ¿`POST /api/session` acepta cualquier `user_id` **existente** sin
    credencial? El proyecto lo declara y lo llama «no autenticación». ¿Lo es?
18. ¿Se puede **forjar** una sesión sin el secreto del equipo? ¿Y leer la cookie
    desde JavaScript (`HttpOnly`)?
19. ¿Cierra `PATCH /api/users/{id}` el borde de **autorización** (403 si el id no es
    el de la sesión)?
20. **Frontera de red:** ¿es `lan_mode()` **fail-closed** con valores raros
    (`ausente`, `0`, `false`, `no`, `off`)?
21. ¿Pueden discrepar las dos mitades de la política de CORS (la regex compilada por
    `CORSMiddleware` y `security.origin_allowed`)? Hay un test que lo compara:
    ¿muerde?
22. ¿Viaja `session.secret` en los **backups**? ¿Y qué pasa al **restaurar**?
23. **Superficie sin sesión:** ¿responde `/api/system/status` sin sesión y **no**
    devuelve datos de alumno? ¿Está la lista completa, o hay un endpoint sin sesión
    que devuelva algo más de lo declarado?
24. **Listening:** ¿hay audio humano, evaluación acústica o feedback correctivo?
    (El proyecto declara que **no**.) ¿Es adaptativa su dificultad?
25. **Cadena de suministro:** ¿están las Actions fijadas por **SHA de commit**? ¿Es
    `deps-audit` **bloqueante** de verdad?
26. **Gates:** ¿están los **7** en `pending`? ¿Marca el código `human: bool = True`
    en los 7, y coincide con la cifra que da la documentación?

### E. Deriva documental

27. ¿Declara `docs/RELEVO.md` la posición vigente correcta en su **cabecera**?
28. ¿Está `PLAN.md` sin declarar ningún prefijo de auditoría como libre cuando ya
    está ocupado? (Ver la nota de prefijos.)
29. ¿Sigue `docs/DEVICE_MATRIX.md` **entero en ⬜**? El proyecto lo declara: si el
    auditor encuentra una celda rellena sin evidencia, es un hallazgo al revés.

---

## 6. Matriz de cierre (la rellena el auditor)

Cada fila debe sostenerse en **evidencia de código o de test** del árbol publicado.
Si un área no se puede comprobar sin hardware o sin persona, se marca **NO
COMPROBABLE** con el motivo; **no** se puntúa por lo que la documentación promete.

| Área | 🟢/🟡/🔴 | Evidencia (archivo:línea, test o comando) | DEMOSTRADO / DECLARADO / NO COMPROBABLE |
|---|---|---|---|
| Arquitectura | | | |
| Backend | | | |
| Adaptive Engine | | | |
| Pedagogía | | | |
| **Contenido (banco y currículum)** | | | |
| **Instrumento psicométrico** | | | |
| **Los 5 hallazgos de la pausa** | | | |
| GUI | | | |
| Responsive | | | |
| Listening | | | |
| Speaking | | | |
| TTS/STT | | | |
| Offline | | | |
| Instalación | | | |
| Identidad y sesión | | | |
| Superficie sin sesión | | | |
| Cadena de suministro | | | |
| Seguridad | | | |
| CI | | | |
| **Ancla y release documental** | | | |
| Documentación | | | |

**Criterio de veredicto:** `APROBADO` / `APROBADO CON OBSERVACIONES` / `NO APROBADO`
para **el baseline `v3.75.1` y su acta de medición**, con la lista de lo que debe
cerrarse. Recordatorio: la puerta declarada de V4.0 sigue siendo
`validation_gate.py status --strict` saliendo **0**, y **no** depende de esta
release.

---

## 7. Reglas duras para el auditor

1. **Solo lectura.** No se modifica nada; no se abren PRs correctivos.
2. **Separar lo verificado de lo declarado.** Toda afirmación que no se pueda
   reproducir desde el clon se marca como **DECLARACIÓN**, no como hecho.
3. **Severidad `P0`–`P3`** (`P0` rompe una garantía central, `P3` es documental), y
   **una afirmación por hallazgo**, con `archivo:línea` del árbol publicado y
   comando de reproducción.
4. **Falsabilidad primero:** un hallazgo que no se pueda refutar con un comando no es
   un hallazgo. **Nada de «podría», «convendría» ni «en el futuro»** sin dato.
5. **Lo que no se pueda comprobar se declara NO COMPROBABLE**, con el motivo.
6. **Sin cortesía:** si el producto no demuestra lo que dice, decirlo; si lo
   demuestra, decirlo también.
7. **No confundir el instrumento con la validación.** Que exista un gate, un
   candado, un kit o un informe **no** es evidencia de que el hecho esté verificado.
8. **No confundir «firmado» con «autenticado».** Una cookie firmada por el servidor
   prueba **quién emitió** la identidad, no **quién tiene derecho** a ella.
9. **Regla nueva (V3.75.2): no confundir «medido» con «corregido».** Esta release
   **mide** el sesgo de longitud y los sesgos de los instrumentos de evaluación; **no
   los arregla**. Un hallazgo que trate la pausa como una corrección debe declarar esa
   distinción.
10. **Regla nueva (V3.75.2): no confundir un `0 %` de una heurística con ausencia de
    problema.** Dos de las tres señales del instrumento **subestiman** lo que dicen
    medir, y el propio artefacto lo declara.

---

## 8. Honestidad esperada del informe

El auditor debe pronunciarse **explícitamente** sobre estas declaraciones del propio
proyecto, que acotan lo que puede leerse como demostrado:

- **Esta release no arregla nada del producto.** Publica mediciones y repara un ancla
  documental. Quien busque mejoras para el alumno no encontrará ninguna.
- **El sesgo de longitud y los dos sesgos de los instrumentos de evaluación siguen
  donde estaban.** Se miden y se declaran; no se corrigen.
- **La pausa no añade candados que fijen el defecto**, a propósito: un test que fije
  el sesgo actual sería un candado **contra** el arreglo.
- **La pausa mide tasa de acierto explotable, no aprendizaje.** Un ítem con la
  correcta más larga no es por sí solo un ítem malo. **Comprobación:**
  `AM-SINTESIS-PSICOMETRIA-V3751.md`.
- **No mide la plausibilidad semántica** de un distractor (exigiría hablantes) ni la
  **tasa real** del atajo: el motor guarda acierto, **no** posición marcada, así que
  la estrategia se **simula**, no se observa.
- **Los instrumentos de evaluación son 46 ítems, no 904.** El placement es 17/24 →
  IC95 % ≈ [52,6 %, 89,0 %]: no se generaliza con la confianza de los 368 checks.
- **El P0 de V3.75.1 no se reabre.**
- **El baseline queda declarado como `v3.75.1` = `7962d57`**: es el punto de
  reinicio, no esta release.
- **Esto no es autenticación y la Fase 3 no está decidida.** `POST /api/session`
  acepta cualquier `user_id` **existente** sin credencial y `GET/POST /api/users`
  siguen abiertos: en modo LAN, quien alcance la API puede **abrir sesión para
  cualquier perfil**. Cerrarlo exige credencial y contradice «sin cuentas, sin
  contraseñas» de `docs/PREMISAS.md`: es decisión de producto, no pendiente técnico.
- **Los 7 gates están en `pending`.** Nadie ha hecho el corte de red real (`RA-05`),
  ni una instalación en máquina limpia (`RB-05`), ni pruebas en móvil real, ni
  pruebas con audio real. El código marca los **7** gates como `human: bool = True`.
- **El kit es una planilla, no una validación.** `KIT-VALIDACION-GATES.md` ordena y
  registra la ejecución humana; **no** mueve ningún gate a `pass`. Y la identidad
  sellada en el kit sigue siendo la del pre-vuelo (`3.73.6` → `13cc30b`): es
  historia y **no** se reescribe.
- **`product-origin-windows` es informativo**, no bloqueante, y así se declara.
- **El fail-closed cubre el arranque, no la ejecución degradada.**
- **El adaptador de `conftest` reduce lo que prueban 109 suites.** Ya no prueban «la
  identidad viene de la cookie»; eso lo cubren los tests nuevos, marcados
  `identidad_cruda`.
- **La accesibilidad y la matriz de dispositivos no tienen evidencia ejecutada:**
  `docs/DEVICE_MATRIX.md` está **en ⬜** y no hay motor de accesibilidad (`axe`). Lo
  que hay son **cuatro contratos de UI** en Playwright: acotado, no es una auditoría.
- **Sigue abierto y aceptado:** `RA-02` (endpoint de Ollama sin declarar en
  `config.py`), `RA-07`, `RD-05`.

---

## 9. Cierre

**Estado del punto de entrada: entregado (2026-09-19), dentro del commit de release
de `v3.75.2`.** Verificado por comando contra GitHub, no contra el árbol local:

- **Release auditada:** el tag anotado **`v3.75.1`**; el commit y el objeto del tag
  se resuelven con `git rev-parse` (§1), **no** se fijan a mano.
- **Ancla del documento:** el tag anotado **`v3.75.2`**, que contiene este fichero.
- **Producto y contenido:** **idénticos** entre `v3.75.1`, `v3.75.2` y `main` (§1.1).
- **CI:** se resuelve por comando sobre el commit del tag (`gh run list`).
- **Consistencia de versión:** `3.75.2` en los **6 orígenes**.
- **Lo que queda después de esto:** sellar el baseline y ejecutar **G1–G7**; los 7
  gates siguen en `pending` y **nada** de esta línea los adelanta.
