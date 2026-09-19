# AA — Adecuación CEFR real del contenido (V3.70 · Eje 1)

> **Fecha:** 2026-09-15 · **Eje:** 1 de 5 (batería `AA`…`AF`) · **Release:** `v3.70.0`.
> **Instrumento:** `python -m scripts.audit_dossier cefr-adequacy` (solo lectura).
> **Regla dura de V3.70:** *no se toca producto, banco ni currículum*. Todo
> hallazgo se registra con severidad y se traslada a su fase; aquí **no** se
> renivela, reescribe ni reetiqueta ningún ítem.
> **Criterio de desviación:** `docs/audit/CEFR-REFERENCE.md` (v0.1). Es la
> operacionalización **INTERNA** del proyecto para poder auditar de forma
> consistente: **no es un documento CEFR normativo** ni una fuente externa
> validada. Sus rangos se alinean con descriptores del marco y con materiales
> EFL prácticos, pero la tabla que manda aquí es la interna.

## Alcance

**Se audita** la adecuación CEFR **declarada** del contenido de los 6 cursos
A1..C2 frente al criterio interno:

| Fuente | Volumen auditado | Ruta |
|---|---|---|
| Currículum A1..C2 | 31 módulos · 31 unidades · 116 objetivos · **368 checks MC** · **512 actividades** · **34 `production_checks`** | `backend/curriculum/a1.json … c2.json` |
| Corpus de listening | **490 ítems** `cNNN` (A1 200 · A2 200 · B1 25 · B2 25 · C1 20 · C2 20) | `backend/curriculum/listening_corpus.json` |
| Instrumentos MC | placement `placement-v1` (24 ítems) + exámenes `a1-final`/`b1-final` (22 ítems) | `backend/curriculum/assessments.json` |

**No se audita** (y por tanto este dossier no lo declara):

- La **calidad acústica real** del audio: el manifest de audio humano sigue en
  `entries: []` y todo el listening se sintetiza con TTS on-demand. Aquí se
  audita el **texto declarado** (`speech_rate`, `connected_speech`,
  transcripción), no la onda.
- La **discriminación empírica con alumnos**: no hay datos de aprendices
  (`docs/audit/PARKED.md`). Este eje mide **adecuación declarada vs criterio
  interno**, no eficacia.
- El **corpus de speaking** (148 ítems) y los escenarios (26): eje 2.
- La **matriz CEFR** y la validez de la afirmación de maestría: eje 4.
- Los **instrumentos de nivelación** como sistema (parada adaptativa, umbrales):
  eje 5; aquí solo se mide su sesgo de forma MC.
- Los **exámenes finales B2/C1/C2** y el curso Pre-A1: son huecos de cobertura
  (eje 2), no de adecuación.

Relación con el freeze de `docs/BETA_V3.md` (§4.1–§4.4): este dossier **no**
levanta el freeze ni autoriza remediación de contenido; solo lo cuantifica.

## Método

1. **Criterio.** `docs/audit/CEFR-REFERENCE.md` (referencia **interna**): bandas
   de `speech_rate` por nivel, `difficulty_vector` típico, y los criterios por
   ítem de distractores, `inference`, `connected_speech` y pragmática C1/C2.
2. **Instrumentos automáticos (solo lectura).**
   - `python -m scripts.audit_dossier cefr-adequacy` → tabla por nivel
     (dificultad, wpm, propiedades declaradas vs realizadas, sesgo MC) y
     integridad estructural del currículum. Salida versionada en
     `docs/audit/generated/cefr-adequacy.{md,json}`.
   - `python -m scripts.audit_dossier mc-bias` → reparto de posiciones de la
     respuesta correcta en las cuatro fuentes MC.
   - `python -m scripts.audit_dossier curriculum-stats` → conteos por nivel.
3. **Muestreo cualitativo determinista** (semilla `7`, reproducible):
   - `python -m scripts.audit_dossier sample --bank listening --level C1 --count 5 --seed 7`
     → `c102`, `c103`, `c105`, `c111`, `c113`.
   - `python -m scripts.audit_dossier sample --bank objectives --level B1 --count 5 --seed 7`
     → `b1-m01-u01-l01-o01`, `b1-m01-u01-l02-o11`, `b1-m02-u01-l02-o14`,
     `b1-m03-u01-l01-o09`, `b1-m04-u01-l01-o18`.
   - A1 fuera de banda, C1/C2 con `connected_speech`, `inference` de A2 y checks
     con la correcta en 0 se revisan por enumeración completa (no muestreo), con
     los `id` reales de la tabla de muestra.
4. **Verificación de la deriva.** Las métricas de `docs/audit/generated/` se
   regeneraron antes de este dossier y las tres que arrastraban cifras
   divergentes (`curriculum-stats`, `listening-corpus-stats`, `mc-position-bias`)
   **coinciden ya con el disco** (hallazgo 8).

## Evidencia

### 1 · Corpus de listening por nivel

| Nivel | N | dificultad media (min–max) | banda dif. | fuera dif. | wpm media (min–max) | banda wpm | **fuera wpm** |
|---|---|---|---|---|---|---|---|
| A1 | 200 | 1,21 (1–2) | 1–2 | 0 | 117,22 (115–125) | 80–115 | **86** |
| A2 | 200 | 2,23 (2–3) | 2–3 | 0 | 130,85 (130–135) | 110–135 | 0 |
| B1 | 25 | 2,92 (2–3) | 2–4 | 0 | 143,40 (130–175) | 130–160 | 2 |
| B2 | 25 | 4,04 (3–5) | 3–5 | 0 | 162,40 (150–185) | 150–185 | 0 |
| C1 | 20 | 4,00 (4–4) | 4–5 | 0 | 156,15 (150–170) | 165–195 | **18** |
| C2 | 20 | 4,35 (4–5) | 4–6 | 0 | 164,35 (159–175) | 175–200 | **19** |

- **Dificultad escalar: 0 de 490 ítems fuera de banda** en los seis niveles. El
  problema **no** es la dificultad global.
- **Velocidad: es el problema.** A1 entero por encima del techo y 18/20 + 19/20
  de C1/C2 por debajo del suelo.
- **Monotonía de wpm máximo entre niveles: `False`** (máx. B2 185 > máx. C1 170).
- **Monotonía de dificultad media entre niveles: `False`** (C1 4,00 < B2 4,04);
  los 20 ítems C1 declaran el mismo valor 4 y ninguno llega al 5 de su banda.

### 2 · Propiedades declaradas frente a realizadas

| Nivel | `connected_speech` declarado | realizado (reducción real en la transcripción) | `inference` | con integración real |
|---|---|---|---|---|
| A1 | 0 | 0 | 0 | 0 |
| A2 | 0 | 0 | 5 | 1 |
| B1 | 4 | 4 | 2 | 1 |
| B2 | 11 | **3** | 5 | 4 |
| C1 | 14 | **0** | 3 | 3 |
| C2 | 20 | **0** | 3 | 3 |

«Realizado» = la transcripción contiene una **reducción real** (`gonna`,
`wanna`, `gotta`, `dunno`, `whaddaya`, `whatcha`, `kinda`, `sorta`, `lemme`,
`gimme`, `ain't`, `oughta`, `shoulda`, `woulda`, `coulda`, `y'know`). Las
contracciones suaves (`we're`, `it's`, `I'll`) **no** cuentan, y el criterio
interno las excluye explícitamente.

### 3 · Ítems de opción múltiple (sesgo de forma)

| Fuente | N | correcta = opción más larga | reparto de posiciones |
|---|---|---|---|
| corpus de listening | 490 | 195 (39,8 %) | 0:125 · 1:121 · 2:122 · 3:122 (equilibrado) |
| **checks del currículum** | 368 | 144 (39,1 %) | V3.70: **0:329 (89,4 %) · 1:37 · 2:2** → V3.75.1: **0:123 (33,4 %) · 1:122 · 2:121 · 3:2** (P0 cerrado, §Cierre) |
| exámenes (a1/b1) | 22 | 8 (36,4 %) | 0:14 (63,6 %) · 1:8 (36,4 %) |
| placement | 24 | 12 (**50,0 %**) | 0:6 · 1:17 (70,8 %) · 2:1 |

### 4 · Currículum por nivel

| Nivel | Módulos | Unidades | Objetivos | Checks | Actividades | Production | Sin act. | Sin checks |
|---|---|---|---|---|---|---|---|---|
| A1 | 10 | 10 | 28 | 105 | 86 | 6 | 0 | 0 |
| A2 | 7 | 7 | 17 | 55 | 83 | 6 | 0 | 0 |
| B1 | 4 | 4 | 18 | 53 | 84 | 6 | 0 | 0 |
| B2 | 3 | 3 | 13 | 35 | 63 | 6 | 0 | 0 |
| C1 | 4 | 4 | 20 | 63 | 98 | 6 | 0 | 0 |
| C2 | 3 | 3 | 20 | 57 | 98 | 4 | 0 | 0 |
| **Total** | **31** | **31** | **116** | **368** | **512** | **34** | **0** | **0** |

`checks_out_of_objective_skills = 0`: ningún check declara una destreza fuera de
las `skills` de su objetivo. La integridad **estructural** está limpia; lo que
falla es la integridad **de forma** (hallazgo 1).

### 5 · Muestra cualitativa revisada (ids reales)

| Categoría | id | Evidencia textual | Cita |
|---|---|---|---|
| A1 fuera de banda (120 wpm > 115) | `c001` | `backend/curriculum/listening_corpus.json:5` | «A: Excuse me, is there a bank near here? B: Yes, it's next to the supermarket.» |
| A1 fuera de banda (125 wpm) | `c003` | `listening_corpus.json:95` | «The train to London will leave from platform three at ten fifteen.» |
| A1 fuera de banda (125 wpm) | `c005` | `listening_corpus.json:185` | «Hi, it's me. I'm so happy about the party tonight!» |
| C1 `connected_speech: true` sin reducción | `c101` | `listening_corpus.json:4505` · flag en `:4546` | «A: We're a fully remote team… B: That sounds manageable. How do you handle the time zones?» (solo contracciones) |
| C1 `connected_speech: true` sin reducción | `c102` | `listening_corpus.json:4550` | «B: I'm sure your accounting team is just as busy as everyone else…» (solo contracciones) |
| C1 `connected_speech: true` sin reducción | `c104` | `listening_corpus.json:4640` | «Attention please: due to signalling problems, the fourteen thirty-two service to Brighton…» (ni una contracción) |
| C2 `connected_speech: true` sin reducción | `c121` | `listening_corpus.json:5405` | «B: Stability is the luxury you can only afford after you've earned the right to take risks.» |
| C2 `connected_speech: true` sin reducción | `c123` | `listening_corpus.json:5495` | «It is, of course, entirely coincidental that the loudest critics of the reform happen to be…» |
| `inference` A2 resoluble por palabra | `c019` | `listening_corpus.json:815` | Audio «Wash the vegetables, then cut them into small pieces»; correcta = «Wash the vegetables». |
| `inference` A2 resoluble por palabra | `c064` | `listening_corpus.json:2840` | Audio «I'd love to, but I've hurt my knee»; correcta = «They hurt their knee». |
| Check con la correcta en posición 0 | `a1-m01-u01-l01-o02-c02` | `backend/curriculum/a1.json:180` | «Choose the correct question» → opciones `["What is your name?", "What your name is?", "What name your is?"]` con `correct_index: 0`. |
| Check con la correcta en posición 0 | `a1-m02-u01-l01-o02-c03` | `a1.json:579` | «Listen: 'quarter past eight'. What time is it?» → `["8:15", "8:30", "8:45"]` con `correct_index: 0`. |
| Check con la correcta en posición 0 | `a1-m03-u01-l01-o01-c01` | `a1.json:781` | «Which word is a family member?» → `["sister", "table", "park"]` con `correct_index: 0`. |

> **Nota (V3.75.1).** Las tres filas de «check con la correcta en posición 0» son
> la evidencia cualitativa de la **medición de V3.70**: en el árbol actual esos tres
> checks ya **no** tienen `correct_index: 0`, porque el P0 se cerró (§Cierre). Se
> conservan tal cual como registro de lo medido, que es lo que documenta este
> dossier.

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| 1 | **P0** | **Sesgo posicional de los 368 checks del currículum:** la respuesta correcta está en la posición 0 en 329/368 (**89,4 %**); un alumno que marque siempre la primera opción acierta casi 9 de cada 10. El corpus de listening, en cambio, está equilibrado (~25 % por posición). | `docs/audit/generated/mc-position-bias.json` (grupo «checks currículo») · `a1.json:180`, `a1.json:579`, `a1.json:781` | Reequilibrar `correct_index` de los 368 checks de forma determinista y añadir un test de invariante de reparto (≤ 35 % por posición). Remediar en la fase de contenido (V4.0.x), no aquí. | **cerrado en V3.75.1** (§Cierre) |
| 2 | **P1** | **A1 sistemáticamente rápido:** 86 de 200 ítems (43 %) superan el techo de 115 wpm; *todo* el corpus A1 vive en [115, 125], es decir, el mínimo ya toca el techo y ninguno cae en la banda 80–115. | `cefr-adequacy.json` → `levels.A1.wpm_out_of_band = 86` · `listening_corpus.json:5` (`c001` 120 wpm), `:95` (`c003` 125), `:185` (`c005` 125) | Bajar `speech_rate` de los 200 ítems A1 a 80–115 wpm (TTS) y re-auditar. V4.0.x. | **abierto** |
| 3 | **P1** | **C1/C2 sistemáticamente lentos:** 18 de 20 ítems C1 (90 %) y 19 de 20 C2 (95 %) quedan por debajo del suelo de su banda; la media está 9–11 wpm por debajo. Un C1 a 150 wpm no llega ni al suelo de su propia banda (165). | `cefr-adequacy.json` → `C1.wpm_out_of_band = 18`, `C2.wpm_out_of_band = 19` · `listening_corpus.json:4505` (`c101` 150 wpm, banda 165–195), `:5405` (`c121` 165 wpm, banda 175–200) | Subir la velocidad TTS de C1 a 165–195 y C2 a 175–200. V4.0.x. | **abierto** |
| 4 | **P2** | **La escalera de velocidad no es monótona:** el ítem más rápido de B2 (185 wpm) supera al de C1 (170) y al de C2 (175). Además la dificultad media se invierte (C1 4,00 < B2 4,04) y C1 declara el mismo valor 4 en sus 20 ítems, sin alcanzar nunca el 5 de su banda. | `cefr-adequacy.json` → `monotonic_max_wpm = false`, `monotonic_mean_difficulty = false` · `C1.difficulty_max = 4` | Definir la escalera objetivo por nivel (wpm máx. y dificultad ≥) y validarla como invariante antes de añadir corpus. Diseño pedagógico (V4.0.x). | **abierto** |
| 5 | **P1** | **`connected_speech` declarado sin respaldo textual:** C1 14/14 y C2 20/20 ítems marcados `connected_speech: true` no contienen **ninguna** reducción real en la transcripción; en B2 fallan 8 de 11. Las contracciones suaves no cuentan según el criterio interno. | `cefr-adequacy.json` → `C1.connected_speech_realized = 0`, `C2 = 0`, `B2 = 3` · `listening_corpus.json:4546` (flag `true`) con script en `:4521` (solo `We're`) | Reescribir los guiones con reducciones reales o reclasificar el ítem (bajar el factor declarado). V4.0.x. | **abierto** |
| 6 | **P2** | **`inference` mal etiquetado en A2:** 4 de los 5 ítems A2 etiquetados `inference` se resuelven con una palabra literal del audio, lo que los convierte en `detail`/`gist`. | `cefr-adequacy.json` → `A2.inference_items = 5`, `inference_requiring_integration = 1` · `listening_corpus.json:815` (`c019`), `:2840` (`c064`) | Reetiquetar a `detail` o reescribir el distractor/pregunta para exigir integración de dos claves. V4.0.x. | **abierto** |
| 7 | **P2** | **Sesgo de longitud:** la opción correcta es además la más larga en 39,1 % de los checks del currículum, 39,8 % del corpus y **50,0 % del placement** (donde la posición correcta se concentra en 1 con 17/24 = 70,8 %). Son atajos de forma que permiten acertar sin comprender. | `cefr-adequacy.json` → `mc.curriculum_checks.correct_is_longest_pct`, `mc.corpus…`, `mc.placement…` · `backend/curriculum/assessments.json:8` (`pl-01`, correcta en 1) · `assessments.json:209` (`a1f-01`, correcta en 1) | Normalizar longitudes de opciones y reparto de posiciones al regenerar contenido. Contenido + instrumentos (V4.0.x). | **abierto** |
| 8 | **P3** | **Deriva de las métricas generadas (documental):** `curriculum-stats` declaraba C1 = 14 y C2 = 14 objetivos frente a los **20 y 20** reales; `listening-corpus-stats` y `mc-position-bias` arrastraban recuentos divergentes. Las auditorías previas se apoyaron en cifras derivadas. | `docs/audit/generated/curriculum-stats.json` vs `load_all_levels()` (comprobado por test) | Regenerado en esta release; el test `test_generated_metrics_match_disk` impide que vuelva a divergir. | **corregido** |

**Limpio (sin hallazgo):** dificultad escalar 0/490 fuera de banda; 0 objetivos
sin actividades ni sin checks; 0 checks fuera de las `skills` de su objetivo;
corpus de listening con reparto de posiciones equilibrado y 4 opciones siempre;
34 `production_checks` presentes en los 6 niveles.

## Veredicto

**Aprobado con matices, no aprobado en forma.** La **dificultad declarada** del
contenido es correcta (0 de 490 ítems fuera de banda, integridad estructural
limpia), pero la **velocidad** y las **propiedades declaradas** no lo son: A1
entero por encima de su banda, C1/C2 casi enteros por debajo, escalera de
velocidad no monótona y `connected_speech` sin respaldo textual en C1/C2. El
hallazgo más severo era de forma, no de contenido: el **89,4 %** de los checks del
currículum tenía la correcta en la posición 0 (**P0 cerrado en V3.75.1**,
§Cierre).

**Qué demuestra y qué no.** Este eje ha medido **adecuación declarada frente al
criterio interno** `docs/audit/CEFR-REFERENCE.md` (que **no** es un documento CEFR
normativo). **No** demuestra eficacia pedagógica ni discriminación empírica con
alumnos: no hay aprendices en el bucle. En términos de la regla §28, aquí «el
test **no demuestra**» validez empírica; lo que sí demuestra es que «el motor
**no cumple**» su propia tabla interna en velocidad, `connected_speech` y sesgo
posicional de los checks.

## Cierre del P0 (V3.75.1)

El P0 se cerró el **2026-09-19** (`release-notes-v3.75.1.md`, `CURRICULUM_VERSION`
1.3.0 → 1.3.1). La recomendación se ejecutó con una variante **medida, no
supuesta**:

- **Regla.** Dentro de cada grupo de checks con el mismo nº de opciones `k`,
  ordenados por `id` ascendente, el check en la posición `j` lleva la correcta a
  **`j % k`**. Se agrupa por `k` porque una posición solo existe dentro de su
  número de opciones: agregar los 368 escondería que el 4.º distractor (los 10
  checks de 4 opciones) nunca fuese la correcta.
- **Reposicionamiento, no rotación.** Se **mueve la correcta** y los distractores
  conservan su **orden relativo**. La primera implementación fue una rotación
  cíclica y se descartó al verificarla: al extraer la correcta, el distractor que
  la precedía pasa a seguirla, así que se rompe el orden de las opciones
  autoriadas en orden natural (`["8:15", "8:30", "8:45"]`).
- **Instrumento.** `backend/scripts/rebalance_mc_positions.py` (`--check` /
  `--write`), idempotente, con **tres invariantes** antes de escribir: forma
  canónica (misma correcta y mismos distractores en el mismo orden relativo), nº
  de líneas intacto y JSON válido. Diff: **614/614 líneas**, cero formato.
- **Resultado medido** (`mc-bias`): `0:33,4 % · 1:33,2 % · 2:32,9 % · 3:0,5 %`;
  por grupo, `k=3` → `33,5 / 33,2 / 33,2 %` y `k=4` → `30 / 30 / 20 / 20 %`. Peor
  posición **33,5 %**, bajo el límite del 35 %. **A2, B2, C1 y C2 dejan de estar
  al 100 % en la posición 0.**
- **Candados.** `--check` como tripwire re-ejecutable para la reautoría de
  V4.0.x, y `test_mc_position_of_curriculum_checks_is_balanced` (≤ 35 % por
  grupo y **sin posiciones muertas**).

**Lo que este cierre NO toca** (y sigue abierto): el hallazgo **#7** (sesgo de
longitud: 39,1 % de los checks y 50,0 % del placement) y las posiciones de
`assessments.json` (exámenes al 63,6 % en la posición 0, placement al 70,8 % en la
1), que son **otro instrumento**. Y no mejora los ítems: **elimina el atajo** de
marcar siempre la primera opción, sin cambiar distractores ni enunciados.

## Regenerar / Verificar

```powershell
cd backend
# Evidencia del eje 1 (reproduce las tablas de este dossier).
.venv\Scripts\python.exe -m scripts.audit_dossier cefr-adequacy
.venv\Scripts\python.exe -m scripts.audit_dossier mc-bias
.venv\Scripts\python.exe -m scripts.audit_dossier curriculum-stats
# Muestreo cualitativo determinista (semilla 7).
.venv\Scripts\python.exe -m scripts.audit_dossier sample --bank listening --level C1 --count 5 --seed 7
.venv\Scripts\python.exe -m scripts.audit_dossier sample --bank objectives --level B1 --count 5 --seed 7
# Gates.
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest -q tests/test_ped_content_cefr_v370.py
```

Ninguno de estos comandos escribe en `backend/curriculum/` ni en `backend/data/`;
solo dejan sus pares en `docs/audit/generated/`.

El **candado del P0** (V3.75.1) es aparte y sí puede escribir, pero solo con
`--write`:

```powershell
cd backend
# Tripwire: no escribe nada; sale 1 si el reparto se desvió de la regla.
.venv\Scripts\python.exe -m scripts.rebalance_mc_positions --check
# Aplica el reposicionamiento (idempotente: repetirlo no mueve nada).
.venv\Scripts\python.exe -m scripts.rebalance_mc_positions --write
```

## Tests que respaldan

`backend/tests/test_ped_content_cefr_v370.py` (8 tests, verdes) **pinnea lo
medido**: si el contenido se corrige, fallan y obligan a re-auditar el hallazgo.
La excepción es el test del P0: ya se corrigió y se reescribió para fijar el
**invariante** en lugar del defecto (V3.75.1), de modo que ahora muerde en las dos
direcciones — si la correcta vuelve a concentrarse, falla.

| Test | Qué hallazgo fija |
|---|---|
| `test_mc_position_of_curriculum_checks_is_balanced` | #1 (**cerrado en V3.75.1**) — invariante ≤ 35 % **por grupo de `k`**, sin posiciones muertas, y corpus ≤ 35 % por posición. |
| `test_a1_corpus_is_faster_than_its_reference_band` | #2 — 86/200 A1 por encima de 115 wpm y banda real [115, 125]. |
| `test_c1_c2_corpus_is_slower_than_its_reference_band` | #3 — 18/20 C1 y 19/20 C2 por debajo del suelo de su banda. |
| `test_speed_ladder_is_not_monotonic_is_declared` | #4 — máx. B2 185 > máx. C1 170 y dificultad media B2 > C1. |
| `test_connected_speech_declared_without_textual_support` | #5 — 0/14 C1 y 0/20 C2 con reducción real (B2 3/11). |
| `test_inference_items_of_a2_are_resolvable_by_literal_word` | #6 — 4/5 `inference` A2 resolubles con palabra literal (`c011` es la excepción). |
| `test_curriculum_structural_integrity_is_clean` | Integridad: 116/368/512/34, sin huecos ni checks fuera de objetivo. |
| `test_generated_metrics_match_disk` | #8 — `content_stats()` y `curriculum-stats.json` coinciden con el disco (anti-deriva). |
