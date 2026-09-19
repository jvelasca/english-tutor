# AM · Síntesis de la auditoría psicométrica del banco (V3.75.1)

> **Release auditada:** base **V3.75.1** · **commit:**
> `7962d57de719ee8e4c62b0f3017c517b04714408` · **tag:** `v3.75.1` (anotado, apunta
> a ese commit) · **rama:** `main` · **árbol:** limpio salvo los ficheros de esta
> auditoría
> **Fecha:** 2026-09-19
> **Documento de síntesis:** consolida los cinco ejes `AH`–`AL`. **No es un eje
> nuevo**: no añade mediciones propias.
> **Dossiers de eje:** `AH-PSICO-LONGITUD.md` · `AI-PSICO-ASSESSMENTS.md` ·
> `AJ-PSICO-FORMA.md` · `AK-PSICO-DISTRACTORES.md` · `AL-PSICO-NIVELES.md`
> **Instrumento:** `backend/scripts/audit_dossier.py` (`item-form`,
> `distractor-signals`, `mc-bias` extendido), de **solo lectura**
> **Evidencia regenerable:** `docs/audit/generated/` (`item-form`,
> `distractor-signals`, `mc-position-bias`, `cefr-adequacy`,
> `assessment-instruments`)

## Alcance

Medir la **forma de los instrumentos de evaluación** del banco MC —368 checks del
currículum, 490 ítems de corpus de listening, 22 ítems de examen final y 24 de
placement: **904 ítems**— después de que V3.75.1 cerrase el sesgo posicional de
los checks. La pregunta no es «¿hay un defecto?» (ya estaba medido), sino **si
hay un patrón sistemático de autoría detrás de las deudas de forma declaradas** y
**qué se puede y qué no se puede demostrar** con el instrumento actual.

**No entra (declarado):**

- **Corregir nada.** Ni `backend/curriculum/*.json` ni
  `backend/curriculum/assessments.json` se tocan en esta auditoría.
- **La adecuación CEFR y el contenido**, ya auditados en `AA`–`AE` (V3.70); aquí
  solo se cruzan sus cifras.
- **El motor, los umbrales y el argmax del Planner**, ya auditados en
  `docs/audit/AG-AUDITORIA-MOTOR-V375.md` (V3.75.0): este eje **no** repite la
  coherencia interna del motor. `AG` mira el cálculo; `AH`–`AL` miran la forma de
  lo que ese cálculo sirve.
- **Calibrar con alumnos.** Sin cohortes no es medible (misma frontera que
  `PARKED.md`).
- **Los gates G1–G7**, que siguen `pending`.

## Método

1. **Solo lectura.** El único diff de código es el instrumento de medición
   (`audit_dossier.py`), sus tests (`test_psy_item_form_v3751.py`) y documentos.
2. **Fuente única.** `mc_banks()` define los cuatro bancos una sola vez, de modo
   que los tres ejes que miran ítems miden exactamente el mismo conjunto.
3. **Cinco ejes en paralelo**, uno por dossier, cada uno con la regla de
   evidencia `[D]` declarado / `[A]` árbol / `[R]` reproducible.
4. **Regla de honestidad de la casa** (`Y` §28, citada en `AF`): distinguir
   siempre **«el banco no cumple»** de **«esta medición no lo demuestra»**, y
   **«defecto de contenido»** de **«punto ciego del instrumento»**.
5. **Corrección de una medición previa.** El grupo de `mc-bias` llamado
   «exámenes level/placement» **solo contaba exámenes** (22 ítems); el placement
   (24 ítems) no aparecía en esa medición. La síntesis usa ya los dos grupos
   separados. No es un hallazgo de contenido: es una corrección del instrumento.

## Matriz consolidada

| Eje | Dossier | **P0** | **P1** | **P2** | **P3** | Total |
|---|---|---|---|---|---|---|
| AH · longitud de la correcta | `AH-PSICO-LONGITUD.md` | 0 | **2** | 3 | 1 | 6 |
| AI · instrumentos de evaluación | `AI-PSICO-ASSESSMENTS.md` | 0 | **1** | 2 | 1 | 4 |
| AJ · forma del banco (`k`) | `AJ-PSICO-FORMA.md` | 0 | 0 | 2 | 3 | 5 |
| AK · inferibilidad de distractores | `AK-PSICO-DISTRACTORES.md` | 0 | 0 | 2 | 2 | 4 |
| AL · patrón por nivel | `AL-PSICO-NIVELES.md` | 0 | **1** | 3 | 2 | 6 |
| **Total** | | **0** | **4** | **12** | **9** | **25** |

**25 hallazgos, ninguno P0.** Y, como se declara en §Cruces, varios describen la
**misma causa raíz** desde ejes distintos: el número de hallazgos no es el número
de problemas.

### El P0 del sesgo posicional sigue cerrado (no se reabre)

El reparto de los 368 checks es `0:33,4 % · 1:33,2 % · 2:32,9 %` con peor
posición **33,5 %**, bajo el límite del 35 %, y `AL-5` verifica que **también se
cumple por nivel** (ninguna posición muerta; peor registro ≤34,5 %). No hay
hallazgo nuevo aquí: se cita como estado de partida.

## Los P1 (4)

| # | Eje | Hallazgo | Cifra | Naturaleza |
|---|---|---|---|---|
| **AL-1** / **AH-2** | AL, AH | **Corpus C1/C2: la correcta es la única más larga en 80 %.** «Marcar la más larga» acierta ~80 % donde el azar da 25 %. | 16/20 en cada nivel; ratio 1,48–1,50 | Atajo de forma **real, medido y explotable** |
| **AH-3** | AH | **Placement: la correcta es la más larga en 50 %** y la estrategia de longitud rinde **61,1 %** frente al 33,3 % del azar. **8/24** son «más larga» **y** «posición 1» a la vez. | 12/24; +27,8 pp | Atajo de forma que **compone** con el posicional |
| **AI-1** | AI | **Placement: la correcta está en la posición 1 en 17/24 = 70,8 %.** El adaptativo arranca en `pl-05` (pos. 1, invariante) y «marcar siempre 1» simula **6/8 y banda C2** sin comprender. **Latente**: ningún componente consume el placement. | 17/24; +37,5 pp | Atajo posicional **explotable si se publica la pantalla** |

**Por qué ninguno es P0:** el corpus C1/C2 y el placement no son el instrumento
que acredita el dominio del alumno (el corpus es práctica; el placement **no
tiene superficie** — `PARKED.md`). El P0 de V3.75.1 lo era porque afectaba a
**los 368 checks** que sí alimentan el mastery. Aquí el único instrumento de
acreditación afectado es el **examen final**, y su sesgo está **contenido por los
umbrales** (`AI-2`, P2): ninguna política posicional aprueba hoy.

## Los P2 (12), agrupados por naturaleza

**(a) Sesgo de longitud en el resto de los bancos — 4**

| # | Hallazgo | Cifra |
|---|---|---|
| AH-1 | Checks del currículum: correcta = más larga única | 144/368 = 39,1 % (+6,0 pp sobre el azar) |
| AH-4 / AL-2 | **C2 es el peor nivel de checks** y el gradiente no es monótono | C2 56,1 % (71,9 % con empates) |
| AH-6 | Exámenes finales | 36,4 % única · **68,2 %** con empates |
| AL-3 | **Pico local en B1** en los dos bancos | checks 50,9 % · corpus 60,0 % |

**(b) Forma del banco (`k`) — 2**

| # | Hallazgo | Cifra |
|---|---|---|
| AJ-1 | **Los 10 checks de `k=4` son un residuo accidental**: todos A1 + `listening` + objetivo `o03` de 5 módulos, mientras los otros 5 módulos de A1 tienen listening con `k=3`. A1 queda 10 `k=4` / 10 `k=3` sin criterio declarado. | 10/368 |
| AJ-2 | **Tres regímenes de autoría conviven**: corpus 100 % `k=4`, checks 97,3 % `k=3`, exámenes/placement 100 % `k=3`. El suelo de azar difiere entre práctica (25 %) y evaluación (33,3 %) y `k` **no escala con el nivel CEFR**. | 0 ítems `k=2` |

**(c) Instrumentos de evaluación — 2**

| # | Hallazgo | Cifra |
|---|---|---|
| AI-2 | Exámenes: correcta en posición 0 y **posición 2 muerta en los 22 ítems**. Contenido por umbrales, pero B1 está a una destreza de ser explotable. | 14/22 = 63,6 % (B1 9/12 = 75 %) |
| AI-3 | La posición del examen **es función del bloque de destreza** (grammar → pos. 1; vocabulary/listening → pos. 0) y el orden de servido es el del JSON: atajo **aprendible por bloque**. | `a1f-*`, `b1f-*` |

**(d) Puntos ciegos del instrumento — 2**

| # | Hallazgo | Cifra |
|---|---|---|
| AK-01 | `quantity_literal` es **prácticamente inerte**: dispara 1/904 pese a **87 enunciados de cantidad**. El `0,0 %` de tres bancos es un **falso negativo**, no una ausencia de atajo. | 1/904 |
| AK-02 | `prompt_keyword_echo` mide **eco exclusivo**: la correcta contiene una palabra del enunciado en **80/904 (8,9 %)**, pero 51 casos se suprimen porque un distractor también la contiene. La cifra declarada es un **suelo** (~2,8× menor). | 29/904 reportado |

## Los P3 (9)

Metodológicos, en su mayoría, y **aceptados**: `shape_outlier` no es
independiente de la longitud (`AK-03`: coincide en **167/172 = 97,1 %**);
`AH-5` longitud y posición **no son ortogonales** (pos 0 = 44,7 % vs ~36,5 % en
pos 1–2 en checks); `AI-4` la intersección longitud × posición en los 46 ítems
(20/46) ; `AJ-3`/`AJ-4`/`AJ-5` (azar vs umbral 0,8, estratificación por `k`,
inexistencia de `k=2`); `AL-5` el reparto por nivel es **emergente y frágil**
(n=20–35, sin candado por nivel); `AL-6` el 4.º distractor solo existe en A1;
`AK-04` el solapamiento léxico no mide sinonimia (85/368 dominado por ítems de
permutación, que no son defecto).

## Cruces entre ejes (lo que solo se ve mirando los cinco juntos)

1. **Deduplicación: 25 hallazgos, 5 problemas.** `AH-2`≡`AL-1` y `AH-4`≡`AL-2`
   miden el mismo hecho desde ejes distintos; `AH-3`⊂`AI-1`+`AI-4` describen el
   mismo atajo de placement por dos vías. La síntesis los cuenta una vez:
   **(1)** sesgo de longitud, **(2)** sesgo posicional de los instrumentos de
   evaluación, **(3)** heterogeneidad de `k`, **(4)** puntos ciegos del
   instrumento, **(5)** gradiente no monótono por nivel.
2. **Longitud y posición se refuerzan, no son independientes** (`AH-5`, `AH-3`,
   `AI-4`): 8 de 24 ítems de placement son *a la vez* «más larga» y «posición 1».
   Corregir una sin la otra deja el atajo parcialmente vivo.
3. **El sesgo de longitud no es uniforme: es un patrón por lote de autoría.**
   A1 (25,7 %) y A2/B2 (~37–43 %) están dentro de lo tolerable; **B1 (50,9 %)**,
   **C2 (56,1 %)** y el **corpus C1/C2 (80 %)** son lotes con el defecto
   concentrado. `AL-4` demuestra que el gradiente **no es monótono** y que
   `CEFR-REFERENCE.md` **no define** una banda de longitud por nivel: por tanto
   **no es un incumplimiento CEFR, es deriva de autoría**.
4. **La forma y la adecuación CEFR son ortogonales.** A1 es la **más sana** en
   forma (25,7 %) y la **más rota** en velocidad (`AA`: 86/200 ítems por encima
   del techo); C1/C2 lo están en ambas. No hay un único «nivel bueno» ni un único
   «nivel malo»: son dos ejes independientes.
5. **El instrumento no puede leer lo que no mide.** `AK-01` y `AK-02` son el
   hallazgo más incómodo de esta auditoría: dos de las tres señales declaradas
   **subestiman** el atajo (una es inerte y la otra reporta un suelo). Cualquier
   síntesis futura que lea «`quantity_literal = 0 %`» como «sin problema» se
   equivocará. Se declara aquí para que no ocurra.
6. **El invariante de V3.75.1 aguanta, pero es global.** El reparto se cumple
   también **por nivel** (`AL-5`), lo cual no estaba garantizado: la regla `j % k`
   es global. Es una propiedad **emergente**, no blindada: con n=20–35 un ítem
   mueve 3–5 pp y no existe candado por nivel.

## Veredicto

**Banco no aprobado en neutralidad de forma; instrumento aprobado tras corregir
una medición; ninguna deuda de arquitectura ni de motor.**

- **Lo que se ha demostrado:** hay un **sesgo de longitud real y medible** en los
  cuatro bancos, **concentrado por lote** (C1/C2 del corpus, B1, C2 y el
  placement) y **no uniforme**; los **instrumentos de evaluación** conservan sus
  dos sesgos (posicional y de longitud) porque V3.75.1 no los tocó, con **una
  posición muerta en los exámenes** y **dos en el placement**; la **forma del
  banco es heterogénea por residuo**, no por diseño declarado; y **dos de las tres
  señales del instrumento subestiman** lo que dicen medir.
- **Lo que no ha cambiado:** el P0 de V3.75.1 sigue cerrado, también por nivel; la
  estructura del currículum sigue íntegra; ningún hallazgo es un defecto de
  cálculo, de motor ni de acreditación.
- **Lo que esto significa para el baseline:** la V3.75.1 **es la base correcta**
  para sellar, y estas 25 mediciones son su **acta de deuda de forma**. Nada de lo
  medido obliga a reabrir el desarrollo general; todo pide **contenido** o
  **decisión pedagógica**.

## Propuesta de fase de cierre (NO implementada)

El plan de esta auditoría prohíbe diseñar el arreglo aquí. Lo que se propone es la
**fase**, no el cambio:

| Problema | Fase propuesta | Condición / orden |
|---|---|---|
| Sesgo de longitud (5) | **V4.0.x contenido** | Normalizar longitudes **en la misma pasada** que el reposicionamiento (cruces 2 y 3) |
| Sesgo posicional de exámenes y placement (2) | **V4.0.x contenido** | Antes de que exista cualquier pantalla de nivelación (`AE-04`); reutilizar la regla `j % k` **por destreza**, no solo global, y garantizar **ninguna posición muerta** |
| Heterogeneidad de `k` (2) | **Decisión pedagógica de V4.0.x** | Fijar una política de forma por banco **antes** de reautorar. **No** convertir todo a `k=4` por defecto |
| Puntos ciegos del instrumento (2) | **Instrumento (bajo coste)** | Ampliar el léxico de `quantity_literal` y publicar el eco no exclusivo; el candado de forma se diseña **con** la corrección |
| Gradiente por nivel (4) | **Declaración, no corrección** | `CEFR-REFERENCE.md` no define banda de longitud: es deriva de autoría. Si se quiere progresión de forma, diseñarla explícitamente |

**Ningún candado que fije el defecto se ha añadido**, por decisión explícita de
esta fase: los invariantes de forma se diseñan con la corrección, cuando se sepa
cuál es el valor correcto.

## Honestidad: qué NO demuestra esta auditoría

1. **No demuestra que un alumno aprenda peor.** Mide tasas de acierto explotable,
   no aprendizaje. Un ítem con la correcta más larga **no** es por sí solo un ítem
   malo: puede ser el ítem más claro del banco.
2. **No mide la plausibilidad semántica de un distractor.** Requiere hablantes
   nativos; `AK` lo declara y se niega a inventar una métrica.
3. **No conoce la tasa real del atajo.** El motor guarda el acierto, no la
   posición marcada: la estrategia se **simula**, no se observa en uso.
4. **Los instrumentos de evaluación son 46 ítems, no 904.** Los intervalos de
   confianza son anchos (placement 17/24 → IC95 % ≈ [52,6 %, 89,0 %]) y **no** son
   generalizables con la confianza de los 368.
5. **El placement es latente.** Hoy ningún componente lo consume; su P1 mide un
   riesgo **si** se publica la pantalla, no un daño actual.
6. **No es una auditoría de contenido.** Nadie ha leído los 904 ítems uno a uno:
   son mediciones de forma más una muestra determinista.
7. **El instrumento tiene los puntos ciegos que él mismo declara** (`AK-01`,
   `AK-02`): las cifras de las tres señales son un **suelo**, no un techo.

## Regenerar / Verificar

```powershell
cd backend

# --- Instrumento: forma y señales ---
.\.venv\Scripts\python.exe -m scripts.audit_dossier item-form
.\.venv\Scripts\python.exe -m scripts.audit_dossier distractor-signals

# --- Instrumentos de evaluación y sesgo posicional (extendido en V3.75.1) ---
.\.venv\Scripts\python.exe -m scripts.audit_dossier mc-bias
.\.venv\Scripts\python.exe -m scripts.audit_dossier assessment-instruments
.\.venv\Scripts\python.exe -m scripts.audit_dossier cefr-adequacy

# --- Contrato del instrumento y anti-deriva de los artefactos ---
.\.venv\Scripts\python.exe -m pytest tests/test_psy_item_form_v3751.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_ped_content_cefr_v370.py -q
.\.venv\Scripts\python.exe -m ruff check scripts/audit_dossier.py

# --- Baseline ---
git rev-parse HEAD          # 7962d57de719ee8e4c62b0f3017c517b04714408
git rev-list -n 1 v3.75.1   # el mismo commit
```

Los §Regenerar de los cinco dossiers de eje contienen los cortes auxiliares
(tabla cruzada longitud × posición, simulación de la estrategia posicional,
corte por destreza, patrones ad-hoc del eje AK), todos de solo lectura y
reproducibles.

## Tests que respaldan

| Fichero | Protege | Relación con esta síntesis |
|---|---|---|
| `backend/tests/test_psy_item_form_v3751.py` | Contrato del instrumento nuevo: fuente única, coherencia de `k`/posiciones, determinismo, solo lectura, anti-deriva de los artefactos | Es el respaldo del instrumento que produce `AH`, `AJ` y `AK` |
| `backend/tests/test_ped_content_cefr_v370.py` | El invariante de reparto `≤ 35 %` por grupo de `k` y la integridad estructural (368 checks) | Verifica que el P0 de V3.75.1 **sigue cerrado** (§El P0) |
| `backend/tests/test_ped_instruments_v370.py` | Placement, exámenes, umbrales de banda | Respalda las cifras de `AI` |
| `backend/tests/test_runtime_audit_v371.py` | Patrón de instrumento de solo lectura y determinista | Modelo del contrato que sigue `test_psy_item_form_v3751.py` |

**Lectura de esta tabla:** el instrumento está cubierto en su contrato; lo que no
existe —a propósito— es un candado que fije las cifras del defecto. Esa decisión
es de esta fase y está declarada en §Propuesta de fase de cierre.
