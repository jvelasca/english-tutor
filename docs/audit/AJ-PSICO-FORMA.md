# AJ · Forma del banco (`k`, nº de opciones) — auditoría psicométrica V3.75.1

> **Eje:** `AJ` de la pausa pedagógica pre-baseline (`agentes/v3751-auditoria-psicometrica.md`).
> **Pregunta:** ¿qué forma tiene el banco (2/3/4 opciones) y qué implica? ¿es
> homogénea por nivel y destreza?
> **Baseline:** commit `7962d57de719ee8e4c62b0f3017c517b04714408`, tag `v3.75.1`
> (`git rev-parse HEAD` y `git rev-parse v3.75.1^{commit}`), `CURRICULUM_VERSION`
> `1.3.1`, `ASSESSMENT_VERSION` `1.0.0` (`backend/services/curriculum.py:206,210`).
> **Regla dura:** SOLO MEDICIÓN. No se toca ningún fichero salvo este dossier.

## Alcance

- **Se audita:** el **número de opciones `k`** de los 904 ítems MC del baseline:
  los **368 checks** del currículum, los **490 ítems** del corpus de listening,
  los **22 ítems** de examen y los **24 ítems** de placement. Se describe su
  reparto por banco, nivel, destreza/tipo de ítem, y su relación con la posición
  y la longitud de la correcta.
- **NO se audita:** el sesgo posicional (eje `AI`), la longitud de la correcta
  (eje `AH`), la inferibilidad de distractores (eje `AK`) ni el patrón por nivel
  (eje `AL`). Esas cifras se **citan** cuando el eje `AJ` necesita el contexto y
  **no se re-derivan**.
- **NO se corrige nada.** La conversión a un `k` único es una decisión
  pedagógica pendiente (§Decisión pendiente), no una conclusión de este eje.

## Método

1. **Instrumento principal (solo lectura):** `python -m scripts.audit_dossier item-form`
   → `docs/audit/generated/item-form.{md,json}`. Mide `k` por banco y por nivel,
   con el desglose por número de opciones (`by_options_count`) y las posiciones
   vivas por `k` (`backend/scripts/audit_dossier.py:1400-1560`). Los artefactos
   citados ya existen en el árbol; el test `test_los_artefactos_generados_coinciden_con_el_disco`
   (`backend/tests/test_psy_item_form_v3751.py:255-260`) garantiza que coinciden
   con el disco, así que **no se re-ejecuta el escritor** para no tocar
   `docs/audit/generated/`.
2. **Corte auxiliar por destreza (el instrumento no lo da):** lectura del
   currículum con el loader del proyecto, solo lectura y determinista
   (§Regenerar, comando 2). El briefing obliga a **declarar como límite** el
   corte que el instrumento no expone (`agentes/v3751-auditoria-psicometrica.md`
   §regla anti-solapamiento); aquí se declara y se documenta el comando exacto
   que lo reproduce, en lugar de improvisar cifras.
3. **Lectura de los JSON de nivel** para localizar los 10 checks de `k=4`
   (`backend/curriculum/a1.json`), requerida por la pregunta 2 del encargo.
4. **Criterios:** azar uniforme por posición ya garantizado por V3.75.1
   (regla `j % k`, `backend/scripts/rebalance_mc_positions.py:13-18`); umbral de
   dominio `DEFAULT_THRESHOLD = 0.8` (`backend/services/curriculum.py:190`).
5. **Regla de evidencia [D]/[A]/[R]** en cada afirmación.

## Evidencia

### 1. `k` por banco e instrumento

| Banco / instrumento | N | `k=2` | `k=3` | `k=4` | Reparto |
|---|---|---|---|---|---|
| Checks del currículum | 368 | 0 | **358** (97,3 %) | **10** (2,7 %) | bimodal | 
| Corpus de listening | 490 | 0 | 0 | **490** (100 %) | uniforme |
| Exámenes finales (A1+B1) | 22 | 0 | **22** (100 %) | 0 | uniforme |
| Placement | 24 | 0 | **24** (100 %) | 0 | uniforme |
| **Total MC** | **904** | **0** | **404** | **500** | — |

Fuentes: `[R]` `docs/audit/generated/item-form.json` → grupos `checks del currículum (todos)`,
`corpus listening (todos)`, `exámenes finales (todos)`, `placement`; `[R]`
comando 2 del §Regenerar (comprobado: 368/490/22/24). `[D]` el propio
`release-notes-v3.75.1.md:250` declara «solo 10 de 368 checks tengan 4 opciones».

**Consecuencia directa sobre el azar (uniforme por posición tras V3.75.1):**

| `k` | Acierto por azar | Dónde |
|---|---|---|
| 2 | 50,0 % | **no existe ningún ítem** |
| 3 | **33,3 %** | 358/368 checks; 22/22 exámenes; 24/24 placement |
| 4 | **25,0 %** | 10/368 checks; 490/490 corpus |

`[A]` `backend/services/curriculum.py:555-558` exige `len(options) >= 2`, pero no
fija un `k`. No hay `k=2` en el baseline.

### 2. `k` por nivel

| Nivel | Checks (N) | Checks `k` | Corpus (N) | Corpus `k` |
|---|---|---|---|---|
| A1 | 105 | 3:95 · **4:10** | 200 | 4:200 |
| A2 | 55 | 3:55 | 200 | 4:200 |
| B1 | 53 | 3:53 | 25 | 4:25 |
| B2 | 35 | 3:35 | 25 | 4:25 |
| C1 | 63 | 3:63 | 20 | 4:20 |
| C2 | 57 | 3:57 | 20 | 4:20 |

`[R]` `item-form.json` → `checks A1…C2` y `corpus A1…C2`.
Lectura: **`k` no escala con el CEFR.** Es una propiedad del **banco**, no del
nivel: los checks son `k=3` de A2 a C2 (y 90,5 % de A1) y el corpus es `k=4` de
A1 a C2. La **única** varianza ligada al nivel es la de A1 (10 checks `k=4`).

### 3. `k` por destreza / tipo de ítem

| Fuente | Destreza / tipo | N | `k=3` | `k=4` |
|---|---|---|---|---|
| Checks | vocabulary | 180 | 180 | 0 |
| Checks | grammar | 104 | 104 | 0 |
| Checks | listening | 66 | 56 | **10** |
| Checks | reading | 18 | 18 | 0 |
| Corpus (18 etiquetas de subdestreza) | detail 111 · vocabulary 81 · attitude 63 · gist 61 · speaker_intention 61 · numbers 45 · inference 18 · connected_speech 10 · fast_speech 9 · multiple_speakers 9 · note_taking 6 · prediction 6 · sequencing 4 · word_recognition 2 · dictation 1 · phrase_recognition 1 · shadowing 1 · sound_recognition 1 | 490 | 0 | **490** |
| Exámenes | grammar 6 · vocabulary 6 · reading 5 · listening 5 | 22 | 22 | 0 |
| Placement | grammar 6 · vocabulary 3 · reading 3 · listening 3 · speaking 3 · writing 3 · pronunciation 3 | 24 | 24 | 0 |

`[R]` comando 2 del §Regenerar (checks y corpus) y `item-form.json` (exámenes y
placement). **El único cruce destreza×`k` que existe en todo el baseline es
`listening`: 66 checks (10 `k=4`) y 490 ítems de corpus (100 % `k=4`).** La
destreza no determina `k`: `grammar`, `vocabulary` y `reading` son `k=3` en
checks, exámenes y placement, y `listening` es `k=3` en el currículum A2–C2 y en
los dos exámenes y el placement.

### 4. Dónde viven exactamente los 10 checks de `k=4`

Todos son **A1**, **skill `listening`**, y están en el **tercer objetivo
(`…-o03`)** de cinco módulos, como checks `c01` y `c02`:

| # | id | Objetivo | `k` | Pos. | Opciones |
|---|---|---|---|---|---|
| 1 | `a1-m03-u01-l01-o03-c01` | `a1-m03-u01-l01-o03` | 4 | 0 | Two / One / Three / Four |
| 2 | `a1-m03-u01-l01-o03-c02` | `a1-m03-u01-l01-o03` | 4 | 1 | At six / At seven / At eight / At nine |
| 3 | `a1-m05-u01-l01-o03-c01` | `a1-m05-u01-l01-o03` | 4 | 2 | A banana / Bread / An apple / Eggs |
| 4 | `a1-m05-u01-l01-o03-c02` | `a1-m05-u01-l01-o03` | 4 | 3 | Pizza / Soup / Salad / Pasta |
| 5 | `a1-m06-u01-l01-o03-c01` | `a1-m06-u01-l01-o03` | 4 | 0 | Fifteen pounds / Five pounds / Fifty pounds / Ten pounds |
| 6 | `a1-m06-u01-l01-o03-c02` | `a1-m06-u01-l01-o03` | 4 | 1 | A drink / A jacket / A ticket / A book |
| 7 | `a1-m08-u01-l01-o03-c01` | `a1-m08-u01-l01-o03` | 4 | 2 | By bus / By car / He walked / By train |
| 8 | `a1-m08-u01-l01-o03-c02` | `a1-m08-u01-l01-o03` | 4 | 3 | At eight / At ten / At seven / At nine |
| 9 | `a1-m09-u01-l01-o03-c01` | `a1-m09-u01-l01-o03` | 4 | 0 | Excited / Sad / Angry / Tired |
| 10 | `a1-m09-u01-l01-o03-c02` | `a1-m09-u01-l01-o03` | 4 | 1 | Six fifteen / Six forty-five / Seven fifteen / Five forty-five |

`[A]` `backend/curriculum/a1.json:982,994` (m03), `:1614,1626` (m05),
`:1937,1949` (m06), `:2498,2510` (m08), `:2820,2832` (m09); opciones de 4 en
`:985,997,1617,1629,1940,1952,2501,2513,2823,2835`. `[R]` comando 2 del
§Regenerar.

**¿Conjunto coherente o residuo de autoría?** El contenido es **coherente**
(los 10 son «listen & answer» con 4 opciones nítidas, al estilo del corpus), pero
como **regla de forma es un residuo**, porque el mismo nivel, la misma destreza y
el mismo estilo de enunciado tienen **10 checks más con `k=3`** en los otros
cinco módulos de A1:

| `k=4` (4 opciones) | `k=3` (3 opciones) |
|---|---|
| m03, m05, m06, m08, m09 (objetivo `o03`, checks `c01`/`c02`) | m01 (`…-l02-o02-c01`), m02 (`…-l01-o02-c03/c04`), m04 (`…-l01-o02-c03`), m07 (`…-l01-o01-c03/c04`, `…-l01-o02-c03/c04`), m10 (`…-l01-o01-c05/c06`) |

`[A]` A1 tiene **20 checks de listening: 10 `k=4` + 10 `k=3`** (`a1.json:345,579,590,1307,2093,2104,2188,2199,2978,2989`).
`[R]` comando 2 del §Regenerar. Es decir: **A1 listening está partido 50/50 entre
3 y 4 opciones** y el corte no sigue un criterio declarado (ni orden de módulo,
ni subdestreza, ni dificultad). `[D]` la propia release lo llama «irregularidad
de autoría» (`release-notes-v3.75.1.md:250-253`).

### 5. `k` y posición de la correcta

| Grupo | `k` | N | Posiciones vivas | Muertas |
|---|---|---|---|---|
| Checks | 3 | 358 | 0:120 · 1:119 · 2:119 | — |
| Checks | 4 | 10 | 0:3 · 1:3 · 2:2 · **3:2** | — |
| Corpus | 4 | 490 | 0:125 · 1:121 · 2:122 · 3:122 | — |
| Exámenes | 3 | 22 | 0:14 · 1:8 · **2:0** | 2 |
| Placement | 3 | 24 | 0:6 · 1:17 · 2:1 | — |

`[R]` `item-form.json` → `by_options_count` de cada grupo. `[D]` V3.75.1 reparte
la correcta con `j % k` dentro de cada grupo de igual `k`
(`rebalance_mc_positions.py:13-18`).

Lectura: **la posición 3 existe únicamente en `k=4`.** En todo el banco de checks
la cuarta posición está viva en **2 de 368 ítems**: `a1-m05-u01-l01-o03-c02` (#4)
y `a1-m08-u01-l01-o03-c02` (#8). Por construcción de V3.75.1 esto es estructural,
no un sesgo: **una posición solo puede existir dentro de su `k`**. La regla ya lo respeta, y el instrumento lo
declara al estratificar por `k` (`audit_dossier.py:1498-1519`). No se detecta
relación adicional entre `k` y posición más allá de esa disponibilidad.

### 6. `k` y longitud de la correcta

| Grupo | `k` | N | correcta = más larga única | correcta/distractores |
|---|---|---|---|---|
| Checks | 3 | 358 | 39,4 % | 1,161 |
| Checks | 4 | 10 | 30,0 % | 1,179 |
| Corpus | 4 | 490 | 39,8 % | 1,249 |

`[R]` `item-form.json` → `by_options_count`. Lectura: **`k` no predice el sesgo de
longitud.** El corpus, que es 100 % `k=4`, tiene un sesgo de longitud (39,8 %)
prácticamente idéntico al de los checks `k=3` (39,4 %); el `k=4` de los checks
(30,0 %) se apoya en n=10 y no es concluyente. El sesgo de longitud es un eje
propio (`AH`) y **no se re-deriva** aquí.

### 7. Azar, CEFR y capacidad de discriminación

- **Azar vs umbral.** Con `k=3` el suelo es 33,3 % y con `k=4`, 25,0 %. El umbral
  de dominio por destreza es `0.8` (`curriculum.py:190`): **ninguno de los dos
  suelos permite «demostrar» dominio**, así que el cambio de `k` no altera el
  veredicto de maestría por sí solo. `[D]` `[A]`.
- **Asimetría práctica/evaluación.** El banco de **práctica** (corpus de
  listening) es `k=4` → 25 % de azar; los instrumentos que **gatean** (checks y,
  sobre todo, exámenes y placement) son mayoritariamente `k=3` → 33,3 % de azar.
  La forma más «adivinable» no está en la práctica, sino en la evaluación.
- **CEFR.** No hay evidencia de que `k` se ajuste al nivel: los checks son `k=3`
  de A1 a C2 y el corpus `k=4` de A1 a C2 (§2). La CEFR **no** exige un número de
  opciones, así que esto no es una violación normativa; es una decisión de autoría
  sin escalado por nivel. Lo que **sí** es un atajo medible por nivel es la
  longitud en C1/C2 (80 % de correcta más larga, eje `AL`), no el `k`.
- **Por destreza.** `vocabulary`, `grammar` y `reading` comparten el mismo suelo
  del 33,3 % (checks/exámenes/placement); `listening` es el único que cambia de
  suelo (25 % en el corpus, 33,3 % en los checks `k=3` y en los exámenes). No hay
  un `k` diferenciado por lo que cada destreza puede discriminar.

### 8. Los regímenes de autoría (dos, y su frontera)

| Régimen | `k` | N | Fichero / evidencia |
|---|---|---|---|
| **Corpus de listening** | **4 uniforme** | 490/490 | `[D]` `backend/scripts/_corpus_frames_a1.py:78-94` construye `[answer, d1, d2, d3]` (respuesta + 3 distractores); `backend/scripts/generate_listening_corpus.py:161-166` baraja esas 4 opciones. `[A]` `backend/curriculum/listening_corpus.json`. |
| **Checks del currículum** | **3 de facto** (con 10 fugas a 4) | 358/368 | `[A]` `backend/curriculum/a1.json` y `a2..c2.json`; `[D]` sin regla escrita que fije `k=3`; la fuga de 10 checks a 4 opciones está declarada en `release-notes-v3.75.1.md:250`. |
| **Exámenes y placement** | **3 uniforme** | 46/46 | `[A]` `backend/curriculum/assessments.json`; `[D]` `rebalance_mc_positions.py:29` nota que no se tocan. |

**Diferencia medida:** 490 a 4 opciones frente a 358 a 3 (y 46 a 3). Son **dos
reglas de autoría declaradas** (dos pipelines: un generador de corpus con frame
de 4 opciones y un currículum escrito a mano con 3), más un tercer instrumento
(exámenes/placement) que sigue la convención del currículum. La frontera entre
regímenes es **deliberada**.

**Lo que no es deliberado:** los **10 checks de `k=4`** cruzan esa frontera sin
regla que los gobierne y parten A1 listening 10/10 (§4). Ahí la heterogeneidad es
**accidental**.

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación propuesta | Estado |
|---|---|---|---|---|---|
| AJ-1 | **P2** | **Los 10 checks de `k=4` son residuo de autoría, no un conjunto coherente por nivel/destreza.** Todos son A1 + `listening` + objetivo `…-o03` de m03/m05/m06/m08/m09 (checks `c01`/`c02`), mientras los otros 5 módulos de A1 tienen 10 checks de listening idénticos en estilo («Listen: '…'») con `k=3`: **A1 listening queda 10 `k=4` / 10 `k=3`** sin criterio declarado. | `[A]` `a1.json:982,994,1614,1626,1937,1949,2498,2510,2820,2832` vs `a1.json:345,579,590,1307,2093,2104,2188,2199,2978,2989`; `[R]` §1 y comando 2; `[D]` `release-notes-v3.75.1.md:250-253` («irregularidad de autoría»). | Unificar la convención de `k` de listening (probablemente 4, la del corpus) y aplicarla a **todos** los checks de listening, no solo a 5 módulos de A1. Re-medir tras V4.0.x. | abierto |
| AJ-2 | **P2** | **Heterogeneidad de forma entre bancos: corpus 100 % `k=4`, checks 97,3 % `k=3`, exámenes/placement 100 % `k=3`.** Dos (tres) regímenes conviven; la frontera es deliberada por pipeline, pero deja el suelo de azar desalineado entre práctica (25 %) y evaluación (33,3 %), y el `k` no escala con el nivel CEFR (A1→C2 con el mismo `k` por banco). | `[R]` §1 y §2 (`item-form.json`); `[D]` `_corpus_frames_a1.py:78-94` y `generate_listening_corpus.py:161-166` (corpus), `rebalance_mc_positions.py:13-18` (checks), `release-notes-v3.75.1.md:252-254` (P2 de forma declarado abierto). | Decidir una política de forma por banco **antes** de la reautoría de V4.0.x: fijar un `k` único o un `k` por instrumento/nivel, y documentarla. No es un bug: es una deuda de consistencia. | abierto |
| AJ-3 | **P3** | **El azar no rompe el umbral de dominio, pero el instrumento que gatea tiene el suelo más alto.** `k=3` → 33,3 %; `k=4` → 25 %; umbral `0.8`. El corpus de práctica es `k=4` y los checks/exámenes/placement son `k=3`. | `[R]` §1 y §7; `[A]` `curriculum.py:190`; `[D]` V3.75.1 ya reparte la correcta con `j % k`, así que el azar es uniforme y solo depende de `k`. | Mantener la estratificación por `k` en la medición posicional (ya hecha) y, si se unifica la forma (AJ-1/AJ-2), reevaluar el umbral con el nuevo suelo. | aceptado |
| AJ-4 | **P3** | **`k` determina qué posiciones existen (la 4.ª solo vive en `k=4`, 2/368 checks) pero no predice el sesgo de longitud** (39,4 % en `k=3` vs 39,8 % en corpus `k=4`). | `[R]` §5 y §6 (`item-form.json`); `[D]` `rebalance_mc_positions.py:13-18`. | Ninguna corrección: es una advertencia de medición. Toda métrica posicional debe seguir publicándose **desglosada por `k`**, nunca agregada. | aceptado |
| AJ-5 | **P3** | **No hay ningún ítem con `k=2`** (ni en checks, ni corpus, ni exámenes, ni placement): 0/904. | `[R]` §1. | Ninguna. Se deja constancia de que «2 opciones» (50 % de azar) no está en el baseline. | aceptado |

## Veredicto

**Aprobado con matices en forma; el banco NO está roto.** Tras V3.75.1 el azar es
uniforme por posición y ningún suelo de azar (25 % / 33,3 %) permite alcanzar el
umbral de dominio 0,8. La heterogeneidad de `k` es en su mayor parte
**deliberada** (corpus `k=4` por generador; checks y assessments `k=3` por
autoría). Lo que no es deliberado es un **residuo de 10 checks de `k=4`** que
parte A1 listening 10/10 y cruza la frontera entre pipelines sin regla. Eso es
`P2` de forma, ya declarado abierto por la propia release, y no un defecto de
evaluación sistemática.

**Qué demuestra y qué no.** Este eje demuestra la **forma** (`k`) y su
consecuencia aritmética sobre el azar, con lectura del `k` por banco, nivel y
destreza. **No** demuestra discriminación empírica con alumnos (no hay aprendices
en el bucle): la parte de «qué puede discriminar cada destreza» se argumenta con
el suelo de azar y el umbral, no con datos de respuesta. El corte fino por
destreza dentro del corpus (18 etiquetas) es una lectura del JSON, no un corte
del instrumento, y así se declara.

## Decisión pedagógica pendiente (NO es una propuesta de este eje)

**No se propone convertir todo el banco a `k=4`.** Este eje **mide** y **declara**;
no decide. Pasar de 3 a 4 opciones cambia el coste de autoría, la carga de lectura
en A1/A2, la longitud de los ítems y el suelo de azar, y esa es una **decisión
pedagógica pendiente de cierre en V4.0.x** (el briefing `agentes/v3751-...md:120-124`
lo prohíbe explícitamente como conclusión automática). Las recomendaciones de
§Hallazgos son opciones a decidir, no una orden de conversión: la única
afirmación de este eje es que **la forma actual es heterogénea y que su parte no
deliberada (AJ-1) conviene resolverla con una regla explícita**.

## Regenerar / Verificar

```powershell
# 1. Instrumento principal (regenera docs/audit/generated/item-form.{md,json};
#    el par ya existe en el baseline y el test anti-drift garantiza que coincide)
cd backend
.\.venv\Scripts\python.exe -m scripts.audit_dossier item-form

# 2. Corte auxiliar SOLO LECTURA por destreza y nivel (el instrumento no lo expone).
#    No escribe nada; documentado aquí para reproducir §3 y §4.
.\.venv\Scripts\python.exe -c "import collections; from services.curriculum import load_all_levels; from services.listening import QUESTION_BANK; L=[(lv.level,o.id,c) for lv in load_all_levels() for o in lv.objectives() for c in o.checks]; print('TOTAL',len(L)); print('checks skill x k:', {k:v for k,v in collections.Counter((c.skill,len(c.options)) for _,_,c in L).items()}); print('k=4:', [(lv,o,c.id,c.skill,c.options) for lv,o,c in L if len(c.options)==4]); C=[q for q in QUESTION_BANK if str(q['id']).startswith('c')]; print('corpus level x k:', {k:v for k,v in collections.Counter((q['level'],len(q.get('options') or [])) for q in C).items()})"
```

## Tests que respaldan

- `backend/tests/test_psy_item_form_v3751.py:105-119` — posiciones y `k` suman, y
  las posiciones muertas lo son de verdad (base de §5).
- `backend/tests/test_psy_item_form_v3751.py:122-128` — el desglose por `k` no
  puede faltar: `by_options_count["4"]["n"] == 10` (base de §1 y AJ-1).
- `backend/tests/test_psy_item_form_v3751.py:255-260` — anti-drift: el artefacto
  generado coincide con el disco (permite citar `item-form.json` sin re-ejecutar
  el escritor y sin tocar `docs/audit/generated/`).
- `backend/tests/test_psy_item_form_v3751.py:50-65` — `mc_banks()` mide los cuatro
  bancos declarados (368/490/22/24).
