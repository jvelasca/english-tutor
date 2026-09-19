# AI · Sesgo posicional y de forma de los instrumentos de evaluación (V3.75.1 · pausa pedagógica)

> **Eje AI** de la auditoría psicométrica del banco. **Solo medición, cero
> correcciones.** Mide el reparto de la posición de la correcta y su interacción
> con la longitud en `backend/curriculum/assessments.json`: **24 ítems de
> placement** + **22 ítems de exámenes finales** (A1 10 · B1 12).
> Baseline congelado **V3.75.1** (`7962d57`, tag `v3.75.1`).
> Regla de evidencia `[D]` declarado · `[A]` leído en este commit · `[R]` ejecutado.

## Alcance

- **Se audita:** la **posición** de la opción correcta (`correct_index`) en los
  46 ítems de `assessments.json` —24 de placement y 22 de exámenes— y su cruce
  con la longitud; además, la **ruta de servido/puntuación** de esos ítems
  (`backend/services/assessment_v2.py`, `backend/domain/academy.py`,
  `backend/services/academy.py`) para saber si el orden agrava el atajo. `[D]`
  `backend/scripts/audit_dossier.py:1400-1461` (`mc_banks`, grupos `exams` y
  `placement`).
- **No se audita:** la longitud como deuda propia (eje `AH`), el número de
  opciones (eje `AJ`), la inferibilidad por forma/eco léxico (eje `AK`) ni la
  adecuación CEFR (eje `AL`). Aquí solo se **citan** esas cifras cuando componen
  con la posición. Tampoco se auditan los 368 checks del currículum: su P0
  posicional **ya está cerrado** en V3.75.1 (`release-notes-v3.75.1.md:186-208`)
  y no se re-mide.
- **Baseline:** commit `7962d57de719ee8e4c62b0f3017c517b04714408`, tag anotado
  `v3.75.1`; `CURRICULUM_VERSION = "1.3.1"` `[A]`
  `backend/services/curriculum.py:205`; `ASSESSMENT_VERSION = "1.0.0"` `[A]`
  `backend/services/curriculum.py:210`; `PLACEMENT_VERSION = "2.0.0"` `[A]`
  `backend/services/curriculum.py:211`. Los 46 ítems se cargan con
  `load_assessments()` `[A]` `backend/services/curriculum.py:436-440`.
- **Deuda conocida, no hallazgo nuevo:** V3.75.1 **no tocó `assessments.json`**.
  Está declarado en `[D]` `release-notes-v3.75.1.md:39-41,234-239` («Exámenes y
  placement (`assessments.json`) no se tocan. Sus 22 ítems siguen con la correcta
  en la posición 0 en el 63,6 % y el placement concentra la correcta en la
  posición 1 en 17 de 24») y en `[D]` `docs/audit/PARKED.md:410-413`. Lo que este
  eje **añade** es el **alcance medido** de esa deuda (ids exactos, posición
  muerta, cruce con longitud y vector de explotación en el motor), no la decisión.

## Método

1. **Fuente única de ítems** `[A]`: `mc_banks()` de
   `backend/scripts/audit_dossier.py:1400-1461` construye las filas
   `{id, level, prompt, options, correct_index}` de `exams` (22) y `placement`
   (24) desde `load_assessments()`. `mc-bias`, `item-form` y `distractor-signals`
   comparten esa fuente, de modo que la posición que se mide aquí es la misma que
   publican los artefactos.
2. **Artefactos citados (solo lectura, no se regeneran en este eje)** `[A]`:
   `docs/audit/generated/mc-position-bias.json` (grupos `exámenes finales`,
   `examen a1`, `examen b1`, `placement`) y
   `docs/audit/generated/assessment-instruments.json` (bloques `placement.mc` y
   `exams`). El desglose de posición por grupo y `k` lo publica `item-form`.
3. **Cruce longitud × posición construido en este eje** `[R]`: se reutiliza
   `_length_profile(options, correct_index)` del propio instrumento
   (`audit_dossier.py:1359-1397`) y `_signals_for` (`:1664-1670`), sin
   reimplementar ninguna heurística. Comando en §Regenerar.
4. **Cruce con el motor** `[A]`: se lee dónde se sirven y puntúan (ver §5) y se
   **simula** el selector adaptativo determinista con `ability_theta`,
   `select_next_item` y `placement_should_stop` reales, bajo políticas de
   respuesta declaradas. Las cifras de esas simulaciones se marcan como `[R]`
   (simulación), nunca como comportamiento observado.
5. **Corrección de medición ya aplicada (se cita, no se redescubre):** hasta
   V3.75.1 el grupo de `mc-bias` llamado «exámenes level/placement» **solo
   contaba los exámenes** (22); el placement (24) se mide ahora en su propio
   grupo `[D]` `audit_dossier.py:266-295` y
   `backend/tests/test_psy_item_form_v3751.py:73-90`. Por eso el 63,6 % de `AA`
   es de **exámenes**, no del conjunto con placement.

## Evidencia

### 1. Reparto de posiciones (exámenes global y por nivel · placement)

Fuente `[A]`: `docs/audit/generated/mc-position-bias.json` (líneas 112-153) y
`docs/audit/generated/item-form.json` (grupos `exámenes finales (todos)`,
`examen a1`, `examen b1`, `placement`).

| Grupo | N | k | pos 0 | pos 1 | pos 2 | posición muerta |
|---|---|---|---|---|---|---|
| exámenes finales (todos) | 22 | 3 | **14 (63,6 %)** | 8 (36,4 %) | **0 (0,0 %)** | **2** |
| examen A1 | 10 | 3 | 5 (50,0 %) | 5 (50,0 %) | 0 (0,0 %) | 2 |
| examen B1 | 12 | 3 | **9 (75,0 %)** | 3 (25,0 %) | 0 (0,0 %) | 2 |
| placement | 24 | 3 | 6 (25,0 %) | **17 (70,8 %)** | 1 (4,2 %) | — |
| **46 ítems (AI)** | 46 | 3 | 20 (43,5 %) | 25 (54,3 %) | 1 (2,2 %) | — |

Lectura `[R]`:
- Los **exámenes** concentran la correcta en la **primera** opción (14/22 =
  63,6 %; B1 9/12 = 75,0 %). El placement la concentra en la **segunda**
  (17/24 = 70,8 %).
- El placement **casi no usa la tercera** (1/24 = 4,2 %); los exámenes **no la
  usan nunca** (0/22). Son **dos sesgos de dirección opuesta**, no uno solo:
  quien memorice «primera» gana en exámenes y pierde en placement, y viceversa.
- La medición coincide con la cifra declarada de partida (`[D]`
  `release-notes-v3.75.1.md:234-236`, `PARKED.md:410-412`): 63,6 % en exámenes y
  17/24 en placement. No es hallazgo nuevo; el alcance por id sí (§2 y §6).

### 2. Posiciones muertas: alcance exacto, con ids

Definición: una posición es **muerta** cuando ningún ítem del banco tiene ahí la
correcta (invariante de `item-form`, `dead_positions`). Se mide sobre `[A]`
`mc-position-bias.json` y se contrasta ítem a ítem `[R]`.

**Exámenes (22): la posición 2 está muerta en los 22 ítems.** Ningún ítem de A1
ni de B1 tiene la correcta en la tercera opción. La tercera opción es, por tanto,
un **distractor seguro de descarte** en todo el instrumento.

- Correcta en **posición 0** (14): `a1f-04`, `a1f-05`, `a1f-06`, `a1f-09`,
  `a1f-10`, `b1f-04`, `b1f-05`, `b1f-06`, `b1f-07`, `b1f-08`, `b1f-09`,
  `b1f-10`, `b1f-11`, `b1f-12`.
- Correcta en **posición 1** (8): `a1f-01`, `a1f-02`, `a1f-03`, `a1f-07`,
  `a1f-08`, `b1f-01`, `b1f-02`, `b1f-03`.
- Correcta en **posición 2** (0): ninguno.

**Placement (24): la posición 2 aparece una sola vez.** El placement **no** tiene
posición muerta, pero la 2 está casi muerta (1/24 = 4,2 %).

- Correcta en **posición 0** (6): `pl-02`, `pl-06`, `pl-09`, `pl-11`, `pl-13`,
  `pl-22`.
- Correcta en **posición 1** (17): `pl-01`, `pl-04`, `pl-05`, `pl-07`, `pl-08`,
  `pl-10`, `pl-12`, `pl-14`, `pl-15`, `pl-16`, `pl-17`, `pl-18`, `pl-19`,
  `pl-20`, `pl-21`, `pl-23`, `pl-24`.
- Correcta en **posición 2** (1): **`pl-03`** (grammar, dificultad 2,
  `"She doesn't like coffee."`).

**Alcance declarado:** en los exámenes, 1 de cada 3 opciones (la tercera) es
**estructuralmente no correcta** en el 100 % de los ítems. En el placement, la
tercera opción solo es correcta en `pl-03`. La consecuencia medible es que el
espacio efectivo de respuesta se reduce a **2 opciones** en exámenes y casi a 2
en placement; un alumno que conozca el patrón elimina la tercera sin comprender.
`[R]`.

### 3. Longitud × posición en los 46 ítems

El eje `AH` posee la deuda de longitud (`AH-3`, P1 para placement; `AH-6`, P2
para exámenes) y ya publica esta tabla cruzada. Aquí se **cita** y se confirma
con el mismo método `[R]` (ver §Regenerar); no se re-deriva su tasa como hallazgo
propio.

| Grupo | correcta = más larga (única) | de esas, en pos 0 | de esas, en pos 1 | de esas, en pos 2 |
|---|---|---|---|---|
| exámenes (22) | 8 (36,4 %) | 5 | 3 | 0 |
| placement (24) | 12 (50,0 %) | 4 | **8** | 0 |
| **46 (AI)** | **20 (43,5 %)** | 9 | 11 | 0 |

Complemento (no-longest) `[R]`: en placement los **otros 9** ítems con correcta
en posición 1 **no** son los más largos, así que la coincidencia exacta
«más larga **y** posición 1» es **8/24 = 33,3 %** del instrumento; en exámenes es
**3/22 = 13,6 %**. Es decir: los dos atajos **no son redundantes**, se solapan en
parte y se suman en el resto. La estrategia de longitud vale 61,11 % en placement
y 50,76 % en exámenes (`AH` §4 `[R]`); la estrategia posicional vale 70,83 % y
63,64 % respectivamente (§4 de este eje). **El vector más fuerte del placement es
la posición, no la longitud; el eje AH lo subordina al cruce.** `[R]`.

### 4. Valor de la estrategia posicional pura (marcar siempre la misma opción)

Medido sobre las 46 filas, equivale a la frecuencia de la posición. No es una
simulación: es el recuento exacto de `correct_index == p` `[R]`.

| Política | exámenes (22) | placement (24) | 46 ítems |
|---|---|---|---|
| marcar siempre posición 0 | **14 (63,6 %)** | 6 (25,0 %) | 20 (43,5 %) |
| marcar siempre posición 1 | 8 (36,4 %) | **17 (70,8 %)** | 25 (54,3 %) |
| marcar siempre posición 2 | 0 (0,0 %) | 1 (4,2 %) | 1 (2,2 %) |
| azar uniforme (k=3) | 33,3 % | 33,3 % | 33,3 % |

Margen sobre el azar: exámenes-pos0 **+30,3 pp**; placement-pos1 **+37,5 pp**.
El azar de referencia es 1/3 = 33,3 % en ambos bancos (todos `k=3`). `[R]`.

**Guarda del motor:** aunque el placement se explota con «marcar 1» (70,8 %), los
**exámenes no se aprueban** con ninguna política posicional pura, porque exigen
`min_per_skill = 0.75` **por destreza** y un `overall` de nivel de **0.80**
(`PASS_THRESHOLDS["level"]`). Medido ítem a ítem `[R]`:

| Examen | política | overall | por destreza | ¿aprueba? |
|---|---|---|---|---|
| A1 | marcar 0 | 0,50 | grammar 0,0 · vocab 1,0 · reading 0,0 · listening 1,0 | **No** |
| A1 | marcar 1 | 0,50 | grammar 1,0 · vocab 0,0 · reading 1,0 · listening 0,0 | **No** |
| A1 | marcar 2 | 0,00 | todas 0,0 | **No** |
| B1 | marcar 0 | 0,75 | grammar **0,0** · vocab 1,0 · reading 1,0 · listening 1,0 | **No** (grammar y overall < 0,80) |
| B1 | marcar 1 | 0,25 | grammar 1,0 · resto 0,0 | **No** |
| B1 | marcar 2 | 0,00 | todas 0,0 | **No** |

`[R]` `backend/services/academy.py:1221-1240` (`exam_result`) +
`backend/services/assessment_v2.py:332-366,370-404` (`score_answers`,
`evaluate`). **Honestidad:** el sesgo posicional de los exámenes **no** produce
hoy un aprobado falso; los umbrales por destreza lo bloquean. Pero B1 está a
**una destreza** de ser explotable: «marcar 0» da 9/12 = 75 % global y las tres
destrezas no-grammar al 100 %, y solo grammar (0/3) y el umbral 0,80 lo frenan.

### 5. Cruce con el motor: dónde se sirven y puntúan, y si el orden agrava el atajo

**Rutas (declaradas y leídas)** `[A]`:

| Instrumento | Servido | Puntuado | Orden |
|---|---|---|---|
| placement (lista) | `get_placement()` `domain/academy.py:3596-3614` | `submit_placement()` `:3637-3652` → `placement_result()` `services/academy.py:931-962` | orden de `assessments.json`; primer ítem **`pl-01`** (correcta en pos 1) |
| placement adaptativo | `start_placement()` `:3655-3689` y `next_placement()` `:3703-3805` | `placement_result_adaptive()` `services/academy.py:1195-1218` | `select_next_item()` `services/academy.py:1048-1061` |
| exámenes (legacy) | `get_exam()` `:3807-3821` | `submit_exam()` `:3824-3900` → `exam_result()` | orden de `assessments.json`; primeros `a1f-01` / `b1f-01` (correcta en pos 1) |
| exámenes (escalera 2.0) | `build_level(exam.items, …)` `assessment_v2.py:290-312`, invocado en `domain/academy.py:1656-1661` | `submit_assessment_v2()` re-resuelve `correct_index` desde el examen `domain/academy.py:1790-1799` | **el mismo orden del JSON** |

**El selector adaptativo no empieza por `pl-01`.** `start_placement()` llama a
`select_next_item(items, set(), PLACEMENT_START_THETA)` con
`PLACEMENT_START_THETA = 3.0` `[A]` `services/academy.py:987` y
`domain/academy.py:3671-3673`. La
información de Fisher `p·(1−p)` es máxima en `dificultad ≈ θ = 3`, y el
desempate es `(info, −dificultad)` y luego **el primero en el orden de `items`**
`[A]` `services/academy.py:1044-1061`. Resultado medido `[R]`: el primer ítem
servido es **`pl-05`** (dificultad 3), cuya correcta está en la **posición 1** —
no `pl-01` como sugiere la hipótesis del enunciado. La cohorte de dificultad 3 es
`pl-05`:pos1, `pl-06`:pos0, `pl-14`:pos1, `pl-23`:pos1 (3 de 4 en posición 1).

**El orden adaptativo puede agravar el atajo.** Simulación determinista del
selector real (no telemetría) para tres políticas declaradas `[R]`:

| Política | Ítems servidos (orden) | Aciertos | θ | nivel emitido |
|---|---|---|---|---|
| marcar siempre 1 | `pl-05, pl-09, pl-07, pl-10, pl-15, pl-11, pl-24, pl-12` | **6/8 (75,0 %)** | 5,963 | **C2** |
| marcar siempre 0 | `pl-05, pl-01, pl-02, pl-16, pl-22, pl-03, pl-04, pl-13` | 3/8 (37,5 %) | — | — |
| marcar siempre 2 | `pl-05, pl-01, pl-02, pl-16, pl-22, pl-03, pl-04, pl-13` | 1/8 (12,5 %) | — | — |

`[R]` con `ability_theta`, `placement_standard_error`,
`placement_should_stop` y `select_next_item` reales. El sesgo **no se neutraliza
por adaptatividad**: el selector es **ciego al contenido** (solo mira
`difficulty`), así que sirve los ítems cuya correcta está en posición 1 y un
alumno que marque siempre 1 llega a **6/8 y a la banda C2** sin comprender. El
primer ítem (`pl-05`, pos 1) es **invariante a las respuestas**.

**Exámenes: el orden es fijo y por bloques.** `AssessmentLadder.tsx:194-227`
pinta `session.instrument.items` **en el orden del servidor** (que preserva el de
`assessments.json`), y cada bloque de destreza es homogéneo en posición. Medido
`[R]`:

- **A1** — grammar (`a1f-01..03`) y reading (`a1f-07..08`) → **todas pos 1**;
  vocabulary (`a1f-04..06`) y listening (`a1f-09..10`) → **todas pos 0**.
- **B1** — grammar (`b1f-01..03`) → **todas pos 1**; vocabulary (`b1f-04..06`),
  reading (`b1f-07..09`) y listening (`b1f-10..12`) → **todas pos 0**.

La posición es, por tanto, **una función del bloque de destreza**, no aleatoria
dentro del instrumento (ver AI-3). Un alumno que note el patrón puede acertar
bloques enteros sin comprender; los umbrales por destreza (§4) son lo que hoy
evita el aprobado falso.

**Lo que NO se puede demostrar (declarado):**
1. **El placement no tiene superficie de producto.** El cliente API existe
   (`frontend/src/api/academy.ts:85-113`) pero **ningún componente lo consume**:
   el barrido de `placement` en `frontend/src` fuera de `api/` y `types/` solo
   devuelve el propio tipo. Coincide con `[D]` `PARKED.md:104,208-212` («hoy no
   existe superficie; la pantalla de nivelación sigue fuera de alcance → V4.0.x»).
   Por eso el atajo del placement es **latente**: es un P0 de instrumento, pero
   capado a P1 por no ser alcanzable por un alumno real todavía.
2. **No hay telemetría de posiciones.** La calibración observacional
   `placement_calibration` `[A]` `domain/academy.py:3616-3635` acumula
   aciertos/fallos por ítem, **no** la posición marcada; con los datos actuales no
   se puede medir la tasa real del atajo, solo la de la política simulada.
3. **No demuestro que el resultado del placement fije la banda del alumno.**
   Se persiste en `academy_assessment_results` (`domain/academy.py:3753`) y
   `reassessment_due` consume el historial (`domain/academy.py:696-704`), pero no
   he encontrado una ruta que derive la banda/nivel del placement. Se declara como
   límite, no como ausencia probada.
4. **El orden de pintado depende del cliente.** `AssessmentLadder` respeta el
   orden del servidor; un cliente futuro que baraje opciones rompería este vector
   (y `correct_index` se re-resuelve en servidor, así que barajar sería inocuo para
   la nota, no para el sesgo).
5. **La simulación adaptativa no es comportamiento observado.** Las políticas
   «marcar siempre p» son un escenario declarado; el conjunto servido real depende
   de las respuestas y no hay datos de alumnos.

### 6. Muestra determinista de los 46 ítems (cualitativa, acotada)

Muestra = **censo** de los 46 ítems del instrumento (no hay submuestreo: el
universo es pequeño). `pos` = `correct_index`; `L` = longitud de cada opción en
caracteres; `señal` = heurística declarada de `_signals_for` (`shape_outlier`,
`prompt_keyword_echo`, `quantity_literal`). **Medido** = pos/L/señal;
**lectura** = interpretación acotada del ítem.

**Exámenes finales (22)**

| id | prompt (abreviado) | opciones 0 · 1 · 2 | pos | L | señal | lectura acotada |
|---|---|---|---|---|---|---|
| `a1f-01` | Choose the correct sentence | He go to school. · **He goes to school.** · He going to school. | 1 | 16·18·19 | — | Corrección gramatical; la correcta ni siquiera es la más larga. Atajo posicional puro. |
| `a1f-02` | Choose the correct question | What your name is? · **What is your name?** · What is your name | 1 | 18·18·17 | — | Empata a máximo; la 3.ª falla puntuación. Posicional. |
| `a1f-03` | Complete: There ___ two bedrooms | is · **are** · be | 1 | 2·3·2 | shape_outlier | Correcta = más larga única (1 carácter). Longitud + posición. |
| `a1f-04` | Which word is a family member? | **sister** · table · Monday | 0 | 6·5·6 | — | Empata a máximo con «Monday». Posicional. |
| `a1f-05` | Which word is food? | **bread** · chair · bus | 0 | 5·5·3 | — | Empata; semántica clara. Posicional. |
| `a1f-06` | What day comes after Sunday? | **Monday** · Saturday · Friday | 0 | 6·8·6 | — | La correcta es la **más corta** de las tres; aquí la longitud no ayuda. |
| `a1f-07` | Read … Where is Ana from? | Madrid · **Spain** · England | 1 | 6·5·7 | — | Correcta intermedia. Posicional. |
| `a1f-08` | Read … What does he do at eight? | Gets up · **Has breakfast** · Goes to work | 1 | 7·13·12 | prompt_keyword_echo | «eight»/«breakfast»: eco + más larga. Atajo compuesto. |
| `a1f-09` | tutor will say a number (practice) | **15** · 50 · 5 | 0 | 2·2·1 | — | Empata a máximo; ítem de audio, la posición es incidental. |
| `a1f-10` | tutor will say a time (practice) | **8:00** · 9:00 · 10:00 | 0 | 4·4·5 | — | Correcta más corta; audio. |
| `b1f-01` | Choose the correct sentence | I have lived here since five years. · **I have lived here for five years.** · I live here since five years. | 1 | 35·33·29 | — | La correcta ni es la más larga; corrección gramatical. Posicional. |
| `b1f-02` | Choose the correct sentence | If it will rain… · **If it rains, we will cancel the picnic.** · If it rains, we cancel the picnic. | 1 | 38·39·34 | — | Correcta más larga única (1 car.). Longitud + posición. |
| `b1f-03` | …smoking is not allowed | You don't have to… · **You mustn't smoke here.** · You must not to smoke here. | 1 | 29·23·27 | — | Correcta la **más corta**; longitud no ayuda. Posicional. |
| `b1f-04` | Which word means 'de acuerdo'? | **agree** · argue · avoid | 0 | 5·5·5 | — | Longitudes idénticas; semántica. |
| `b1f-05` | informal form of 'going to' | **gonna** · gotta · wanna | 0 | 5·5·5 | — | Idénticas; léxico. |
| `b1f-06` | phrase introduces a personal opinion | **In my opinion** · By the way · At last | 0 | 13·10·7 | prompt_keyword_echo, shape_outlier | «opinion» en el enunciado y más larga. Atajo doble. |
| `b1f-07` | …they enjoyed every minute | **They enjoyed the journey despite its length.** · They hated the journey. · The journey was short. | 0 | 44·23·22 | shape_outlier | Correcta casi el doble de larga. Longitud fuerte + posición. |
| `b1f-08` | …She had never seen the ocean | **She saw the ocean for the first time after moving.** · …before moving. · She never moved. | 0 | 50·32·16 | shape_outlier | Outlier extremo (2,1×). Longitud fuerte + posición. |
| `b1f-09` | Unless we book in advance… | **Book in advance.** · Not book. · Arrive late. | 0 | 16·9·12 | shape_outlier | Correcta la más larga (1,33×); sin eco (un distractor repite «book»). Longitud + posición. |
| `b1f-10` | I'd rather stay in tonight | **To stay at home** · To go out · To travel | 0 | 15·9·9 | prompt_keyword_echo, shape_outlier | «stay» eco + más larga. Doble. |
| `b1f-11` | What does 'whaddaya' mean? | **what do you** · what did you · where do you | 0 | 11·12·12 | — | Correcta la **más corta**; longitud no ayuda. Posicional. |
| `b1f-12` | The meeting's been put off… | **The meeting was postponed.** · …started. · …cancelled. | 0 | 26·20·26 | — | Empata a máximo con «cancelled». Posicional. |

**Placement (24)**

| id | prompt (abreviado) | opciones 0 · 1 · 2 | pos | L | señal | lectura acotada |
|---|---|---|---|---|---|---|
| `pl-01` | Choose the correct sentence | I is a student. · **I am a student.** · I are a student. | 1 | 15·15·16 | — | Correcta intermedia; posición 1. |
| `pl-02` | opposite of 'big' | **small** · tall · fast | 0 | 5·4·4 | — | Correcta la más larga; único antónimo. Longitud + posición (leve). |
| `pl-03` | Choose the correct sentence | She don't like coffee. · She doesn't likes coffee. · **She doesn't like coffee.** | 2 | 22·25·24 | — | **Único ítem con correcta en pos 2 de los 46.** Correcta intermedia. Quien elimine la 3.ª opción falla este ítem. |
| `pl-04` | Read … When does he go to work? | At night · **At eight** · At noon | 1 | 8·8·7 | prompt_keyword_echo, quantity_literal | «at eight» literal + eco. Atajo compuesto (el test lo cita). |
| `pl-05` | Choose the correct sentence | I have seen that film yesterday. · **I saw that film yesterday.** · I seen that film yesterday. | 1 | 32·26·27 | — | **Primer ítem servido por el adaptativo.** Correcta intermedia; atajo posicional puro. |
| `pl-06` | word means 'the money you earn…' | **salary** · holiday · weather | 0 | 6·7·7 | — | Correcta la más corta; longitud no ayuda. |
| `pl-07` | Choose the correct sentence | If I will see him… · **If I see him, I will tell him.** · If I saw him… | 1 | 30·30·30 | — | Longitudes idénticas; posición 1 pura. |
| `pl-08` | Despite the rain… | The match was cancelled. · **The match was played.** · The match was delayed a week. | 1 | 24·21·29 | — | Correcta la más corta; longitud no ayuda. Posicional. |
| `pl-09` | closest in meaning to 'He is said to be rich.' | **People say he is rich.** · He says he is rich. · He said he was rich. | 0 | 22·19·20 | — | Correcta la más larga. Longitud + posición. |
| `pl-10` | synonym of 'ubiquitous' | rare · **everywhere** · hidden | 1 | 4·10·6 | shape_outlier | Correcta 2,0× la media. Longitud fuerte + posición. |
| `pl-11` | Choose the most natural sentence | **Little did she know the truth.** · Little she knew… · Little knew she… | 0 | 30·26·26 | — | Correcta la más larga; inversión gramatical. Longitud + posición. |
| `pl-12` | …What is the tone? | Negative · **Neutral-positive** · Confused | 1 | 8·16·8 | shape_outlier | Correcta 2,0× la media. Longitud fuerte + posición. |
| `pl-13` | Where did she go? | **To the market** · To the park · To the bank | 0 | 13·11·11 | prompt_keyword_echo | «market» eco + más larga. Doble. |
| `pl-14` | I'd have gone if I'd known | He went · **He didn't go** · He will go | 1 | 7·12·10 | — | Correcta la más larga (1,4×). Longitud + posición. |
| `pl-15` | …speaker's attitude? | Full agreement · **Hesitant doubt** · Anger | 1 | 14·14·5 | — | Empata a máximo con la 0. Posicional. |
| `pl-16` | correct way to introduce yourself | I name is John. · **My name is John.** · Me name John. | 1 | 15·16·13 | — | Correcta la más larga. Longitud + posición (leve). |
| `pl-17` | job interview, most appropriate reply | Gimme the job, mate. · **I'd be delighted to contribute to your team.** · You should hire me now. | 1 | 20·44·23 | shape_outlier | Outlier extremo (2,0×). Longitud fuerte + posición. |
| `pl-18` | disagreeing politely in a formal meeting | You're totally wrong. · **I see your point, but I'd argue that…** · Nah, that's dumb. | 1 | 21·39·17 | shape_outlier | Outlier extremo (2,1×). Longitud fuerte + posición. |
| `pl-19` | correctly punctuated | Its a nice day. · **It's a nice day.** · Its' a nice day. | 1 | 15·16·16 | — | Empata a máximo; corrección de puntuación. Posicional. |
| `pl-20` | passive correctly | The report was wrote by Ana. · **The report was written by Ana.** · The report was writing by Ana. | 1 | 28·30·30 | — | Empata a máximo; gramática. Posicional. |
| `pl-21` | most concise and formal version | Due to the fact that we have no funds, we must stop. · **Because we lack funds, we must stop.** · On account of the reason that funds are absent, we must stop. | 1 | 52·36·61 | — | **Contrapunto: la correcta es la MÁS CORTA** (el ítem pide concisión). La longitud invertida («elegir la más corta») acertaría; la longitud «más larga» falla. Posicional. |
| `pl-22` | word rhymes with 'cat' | **bat** · cot · cut | 0 | 3·3·3 | — | Longitudes idénticas; fonética. |
| `pl-23` | '-ed' pronounced as /t/ | played · **watched** · needed | 1 | 6·7·6 | — | Correcta la más larga (1 carácter). Longitud leve + posición. |
| `pl-24` | primary stress on second syllable | PHOtograph · **phoTOGraphy** · PHOtoGRAPH | 1 | 10·11·10 | — | Correcta la más larga (1 carácter). Longitud leve + posición. |

**Patrón cualitativo acotado** `[R]` (interpretación, no medición):
- **La posición está correlacionada con el bloque de destreza** (ver AI-3): en A1,
  grammar y reading van a la posición 1 y vocabulary y listening a la 0; en B1,
  solo grammar va a la 1. El alumno que aprenda el patrón por bloque no necesita
  comprender.
- **En placement, posición 1 y longitud se refuerzan** en 8/24 (p. ej. `pl-10`,
  `pl-12`, `pl-17`, `pl-18`); en el resto de la posición 1 la longitud **no**
  ayuda (p. ej. `pl-05`, `pl-07`, `pl-08`), así que el atajo dominante es la
  posición.
- **`pl-21` es el contraejemplo útil:** la correcta es la más corta por diseño
  (el enunciado pide concisión). Demuestra que «más larga» no es una regla del
  instrumento, sino una tasa; generalizar a «la correcta siempre es la más larga»
  sería un error que un ítem como `pl-21` castiga.
- **`pl-03` es el único ítem que rompe la eliminación de la tercera opción** en
  todo el instrumento: es también la única evidencia de que el sesgo no es un
  invariante duro, sino un patrón de autoría corregible.

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación (propuesta, no implementada) | Estado |
|---|---|---|---|---|---|
| AI-1 | **P1** | **Placement: la correcta se concentra en la posición 1 en 17/24 = 70,8 %** (+37,5 pp sobre el azar) y la posición 2 solo aparece en `pl-03` (1/24). El adaptativo **no** empieza por `pl-01` sino por `pl-05` (pos 1, invariante), y un alumno que marque siempre 1 obtiene **6/8 y banda C2** (simulación `[R]`). Latente: **ningún componente consume el placement** (`[D]` `PARKED.md:104,208-212`), por eso es P1 y no P0. | §1, §2, §4, §5; `mc-position-bias.json:143-153`; `assessment-instruments.json` (`placement.mc`) | Corregir junto con el sesgo de longitud del placement (`AH-3`) y la forma (`AJ`), en la fase de contenido de V4.0.x, **antes** de publicar la pantalla de nivelación. No añadir candado que fije el defecto. | abierto |
| AI-2 | **P2** | **Exámenes: 14/22 = 63,6 % en la posición 0** (B1 9/12 = 75,0 %) y **posición 2 muerta en los 22 ítems**: la tercera opción nunca es correcta. El atajo «marcar 0» da 63,6 % global, pero **ninguna política posicional aprueba** (A1 máx 0,50; B1 «marcar 0» 0,75 con grammar 0,0 y umbral *level* 0,80). Riesgo **latente**: B1 está a una destreza/umbral de ser explotable. | §1, §2, §4; `mc-position-bias.json:112-141`; `domain/academy.py:1790-1808`; `services/academy.py:1221-1240` | Reposicionar los 22 ítems con la misma regla `j % k` que V3.75.1 aplicó a los 368 (mover la correcta, no rotar), garantizando que **ninguna posición quede muerta**. Medir de nuevo tras el cambio. | abierto |
| AI-3 | **P2** | **La posición de los exámenes es función del bloque de destreza, no aleatoria:** en A1 grammar y reading → posición 1, vocabulary y listening → posición 0; en B1 grammar → posición 1 y vocabulary/reading/listening → posición 0. El orden de servido (`AssessmentLadder.tsx:194-227` pinta en orden del JSON) agrupa el patrón en bloques contiguos. Es un atajo **aprendible por bloque**, hoy contenido por los umbrales por destreza. | §5; `assessments.json` (ids `a1f-*`, `b1f-*`); `AssessmentLadder.tsx:194-227` | Al reposicionar, distribuir la posición **dentro de cada destreza**, no solo en el global, para que un bloque no sea homogéneo. | abierto |
| AI-4 | **P3** | **Cruce longitud × posición en los 46:** 20/46 = 43,5 % con correcta = más larga; de esas, 11 en posición 1. En placement 8/24 = 33,3 % son **a la vez** «más larga» y «posición 1». Los atajos no son redundantes: se solapan en 8 y se suman en el resto. La deuda de longitud es de `AH` (`AH-3` P1); aquí solo se aporta la intersección. | §3; `AH-PSICO-LONGITUD.md` §3-4 `[R]` | Corregir AI y AH **juntos**: normalizar longitud y reparto en la misma pasada de contenido. | abierto |

**Honestidad (regla del briefing):** el instrumento tiene **24 + 22 ítems**, no
368. Con n=24, el 17/24 = 70,8 % tiene un intervalo de confianza aproximado
(Wald 95 %) de **[52,6 %, 89,0 %]**; el 14/22 = 63,6 % de exámenes, **[43,5 %,
83,7 %]**. Son instrumentos **pequeños**: la dirección del sesgo es estable y
extrema, pero **no se puede generalizar con la confianza de los 368 checks**, y
las tasas por nivel (A1 n=10, B1 n=12) son aún más frágiles. Un ítem con la
correcta en posición 1 **no** es por sí solo un ítem malo; lo medido es la
**tasa** y su capacidad de **predecir la correcta sin comprender**. Nada de esto
se corrige en esta auditoría: se mide y se declara.

## Veredicto

**No aprobado en el invariante de neutralidad posicional de los instrumentos de
evaluación; aprobado con matices en el resto.** Los 46 ítems de
`assessments.json` presentan **dos sesgos de dirección opuesta** (exámenes hacia
la posición 0 con la posición 2 muerta; placement hacia la posición 1 con la 2
casi muerta), una **correlación posición-destreza** por bloques y un cruce
relevante con la longitud. El placement es un **exploit latente** (6/8 y C2 sin
comprender) que hoy no es alcanzable porque no tiene superficie; los exámenes son
un sesgo **contenido** por los umbrales por destreza, con B1 en el límite. Es
**deuda conocida y declarada** por V3.75.1, no un hallazgo nuevo de esa release;
lo nuevo es el **alcance medido**. Se cierra con la corrección de contenido de
V4.0.x (reposicionar exámenes y placement, idealmente en la misma pasada que la
deuda de longitud), **no** con un candado que fije el defecto.

## Regenerar / Verificar

Procedencia de las cifras y comandos desde `backend` (PowerShell 5.1; sin `&&`):

```powershell
# 1. Artefactos de origen (SOLO LECTURA: no se regeneran para no escribir en
#    docs/audit/generated/, regla dura de este eje). Si en el futuro se
#    regeneran, estos son los comandos declarados:
.\.venv\Scripts\python.exe -m scripts.audit_dossier mc-bias
.\.venv\Scripts\python.exe -m scripts.audit_dossier item-form
.\.venv\Scripts\python.exe -m scripts.audit_dossier assessment-instruments

# 2. Reparto exacto, posiciones muertas con ids, cruce longitud x posicion,
#    estrategia posicional y umbrales de examen (reutiliza las funciones del
#    propio instrumento; solo lectura).
@'
import json
from collections import Counter
from scripts.audit_dossier import mc_banks, _length_profile
from services import academy
from services.curriculum import load_assessments

banks = mc_banks()
for grp in ("exams", "placement"):
    rows = banks[grp]
    pos = Counter(r["correct_index"] for r in rows)
    ids = {p: [r["id"] for r in rows if r["correct_index"] == p] for p in range(3)}
    print(grp, "n=", len(rows), "pos=", dict(sorted(pos.items())), "ids=", ids)
    print("  longest=", sum(1 for r in rows
          if _length_profile(r["options"], r["correct_index"])["correct_is_longest"]))
    cross = {p: sum(1 for r in rows if r["correct_index"] == p
             and _length_profile(r["options"], r["correct_index"])["correct_is_longest"])
             for p in range(3)}
    print("  longest x pos=", cross)

# Simulacion adaptativa de la politica "marcar siempre 1"
items = load_assessments().placement.items
answers = {}
for _ in range(8):
    resp = [(it.difficulty, answers[it.id] == it.correct_index)
            for it in items if it.id in answers]
    theta = academy.ability_theta(resp)
    se = academy.placement_standard_error(theta, resp)
    if academy.placement_should_stop(len(answers), len(items), se):
        break
    nxt = academy.select_next_item(items, set(answers), theta)
    if nxt is None:
        break
    answers[nxt.id] = 1
res = academy.placement_result_adaptive(items, answers)
print("primer item=", academy.select_next_item(items, set(), academy.PLACEMENT_START_THETA).id)
print("marcar siempre 1:", res["correct"], "/", res["answered"], "theta=", res["theta"],
      "nivel=", res["level"])

# Estrategia posicional pura contra los umbrales del examen
data = load_assessments()
from services.assessment_v2 import evaluate
for lid, exam in data.exams.items():
    for p in range(3):
        scored = academy.exam_result(exam, {it.id: p for it in exam.items})
        ev = evaluate("level", scored, min_per_skill=exam.min_per_skill)
        print(lid, "marcar", p, scored["overall"],
              {s: b["score"] for s, b in scored["skills"].items()}, "passed=", ev["passed"])
'@ | .\.venv\Scripts\python.exe -X utf8 -

# 3. Baseline (verificacion)
git rev-parse HEAD                                   # 7962d57...
git rev-parse "v3.75.1^{commit}"                     # 7962d57...
```

## Tests que respaldan

`[A]` `backend/tests/test_psy_item_form_v3751.py` (contrato del instrumento, no
las cifras del defecto):

- `test_mc_banks_son_los_cuatro_bancos_declarados` y `TAMANO_BANCOS` (líneas
  30-56): fija 22 exámenes y 24 placement, la misma base que mide este eje.
- `test_el_placement_tiene_sus_24_items_y_no_esta_fundido_con_los_examenes`
  (73-79): garantiza que el placement no vuelve a desaparecer de la medición.
- `test_bias_separa_examenes_de_placement_y_declara_el_k` (85-95): el nombre
  «level/placement» ya no existe y cada grupo declara su `k`.
- `test_item_form_posiciones_y_k_suman_y_las_muertas_lo_son` (107-118): las
  posiciones muertas que se citan en §2 son ciertas por construcción.
- `test_el_instrumento_no_escribe_en_data_ni_en_curriculum` (150-160): respalda
  que esta medición es de solo lectura.
