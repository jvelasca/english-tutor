# AL — Patrón de forma y longitud por nivel (V3.75.1 · pausa pedagógica)

> **Fecha:** 2026-09-19 · **Eje:** AL (5.º de los cinco) · **Baseline congelado:** `V3.75.1`.
> **Commit:** `7962d57de719ee8e4c62b0f3017c517b04714408` (`git rev-parse HEAD`).
> **Tag:** `v3.75.1` → mismo commit (`git rev-parse v3.75.1^{commit}`).
> **Versiones [A]:** `CURRICULUM_VERSION = "1.3.1"` (`backend/services/curriculum.py:205`);
> `ASSESSMENT_VERSION = "1.0.0"` (`backend/services/curriculum.py:210`).
> **Instrumento [R]:** `python -m scripts.audit_dossier item-form` (solo lectura).
> **Eje:** comportamiento del patrón de **forma y longitud** a lo largo de A1, A2,
> B1, B2, C1 y C2.
> **Regla dura:** SOLO MEDICIÓN. Este dossier no modifica contenido, motor,
> umbrales ni artefactos generados; no hace commit ni stage. La corrección de
> cada hallazgo se **propone** y se ejecuta en su fase.

---

## Alcance

**Se audita** la forma de los ítems MC **por nivel** en los dos bancos del
currículum:

| Banco | Ítems | Rango | Fuente |
|---|---|---|---|
| Checks del currículum | **368** | A1 105 · A2 55 · B1 53 · B2 35 · C1 63 · C2 57 | `docs/audit/generated/item-form.json` |
| Corpus de listening (`c*`) | **490** | A1 200 · A2 200 · B1 25 · B2 25 · C1 20 · C2 20 | `docs/audit/generated/item-form.json` |

Métricas por nivel: **reparto de posiciones** de la correcta, **tasa de correcta
más larga** (`correct_is_longest`), la variante **más larga o empatada**, el
**ratio de longitud** correcta/distractores y el **número de opciones** `k`.

**No se audita** (y por tanto este dossier no lo declara):

- El **reparto global de posiciones** ni el P0 del sesgo posicional: cerrado en
  V3.75.1 y citado como estado de partida (`AA`, §Cierre).
- **Exámenes finales y placement** (`assessments.json`): instrumentos distintos,
  eje **AI**; aquí solo se citan como frontera. Su posición muerta 2 en exámenes
  y el 17/24 del placement **no** se re-miden aquí.
- **Forma/k como eje propio** (2/3/4 opciones): eje **AJ**.
- **Señales de distractor inferible** por forma o léxico: eje **AK**.
- **Adecuación CEFR declarada** (velocidad, dificultad, `connected_speech`):
  eje **AA**; aquí solo se **cruza** lo ya auditado (§Evidencia 5).

---

## Método

1. **Unidad de longitud [D].** El instrumento define longitud como **nº de
   caracteres** de la opción (`_option_lengths` → `len(str(o))`,
   `backend/scripts/audit_dossier.py:1356`) y `ratio =
   longitud_correcta / media(longitudes_de_distractores)`
   (`_length_profile`, `backend/scripts/audit_dossier.py:1359-1396`).
   `correct_is_longest` exige que la correcta sea la **más larga única**;
   `correct_is_longest_or_tied` incluye los empates a longitud máxima
   (`:1386-1388`).
2. **Agrupación [D].** `item_form()` produce un grupo por banco y por nivel, y
   **dentro de cada grupo el desglose por `k`** (`audit_dossier.py:1522-1559`);
   una posición solo existe dentro de su `k`. Los números de este dossier salen
   literales de `docs/audit/generated/item-form.json`.
3. **Artefacto congelado [A][R].** No se re-regeneró `docs/audit/generated/`
   (fuera del alcance de escritura de AL). El artefacto en disco coincide con el
   constructor en memoria: `test_los_artefactos_generados_coinciden_con_el_disco`
   (`backend/tests/test_psy_item_form_v3751.py:255-260`), verde en la corrida de
   este eje.
4. **Tabla por nivel construida aquí.** El artefacto no da una tabla-resumen de
   gradiente; la construí directamente desde los contadores de
   `item-form.json` (suma de `positions`, `correct_is_longest`, `n`). **Método
   declarado**, reproducible con el comando del §Regenerar:
   - porcentajes = conteo / `n` × 100 (redondeo a 1 decimal, como el artefacto);
   - **gradiente**: se ordenan los 6 niveles A1→C2 y se mira si la serie es
     monótona no decreciente; se cuentan las inversiones adyacentes;
   - **ρ de Spearman** descriptiva, ρ = 1 − 6·Σd² / (n(n²−1)) con n = 6, niveles
     ordenados A1=1…C2=6 y rangos **con empates promediados**;
   - **invariante por nivel**: peor posición = max(conteo)/n y `dead_positions`
     del artefacto; contraste con la uniformidad por χ² descriptiva.
   Son estadísticos **descriptivos** sobre los conteos versionados; no se hace
   inferencia poblacional ni se extrapola a alumnos.
5. **Contraste con el azar [D].** Para un MC de `k` opciones, bajo longitudes
   independientes la probabilidad de que la correcta sea la más larga única es
   `1/k`. Se cita como referencia (33,3 % para `k=3`, 25,0 % para `k=4`), no
   como banda CEFR.
6. **Límite declarado.** Los tamaños por nivel son **muy dispares**: checks A1
   = 105 frente a B2 = 35 (3×); corpus A1/A2 = 200 frente a C1/C2 = 20 (10×).
   Todos los porcentajes de este dossier se leen junto a su `n`; 1 ítem = 1,0 pp
   en A1-checks, 2,9 pp en B2-checks, 5,0 pp en C1/C2-corpus. No se comparan
   porcentajes de tamaños distintos sin declararlo.
7. **Tests [R].**
   `py -m pytest -q -p no:cacheprovider tests/test_psy_item_form_v3751.py`
   → **18 passed** (corrida de este eje, sin escritura de caché).

---

## Evidencia

### 1 · Checks del currículum por nivel

| Nivel | N | k | Posiciones de la correcta | Muertas | Más larga (única) | Más larga o empatada | Ratio |
|---|---|---|---|---|---|---|---|
| A1 | 105 | k=3:95 · k=4:10 | 0:35 · 1:35 · 2:33 · 3:2 | — | 27 (**25,7 %**) | 52 (49,5 %) | 1,057 |
| A2 | 55 | k=3:55 | 0:18 · 1:18 · 2:19 | — | 20 (36,4 %) | 32 (58,2 %) | 1,173 |
| B1 | 53 | k=3:53 | 0:18 · 1:18 · 2:17 | — | 27 (**50,9 %**) | 34 (64,2 %) | 1,225 |
| B2 | 35 | k=3:35 | 0:12 · 1:11 · 2:12 | — | 15 (42,9 %) | 23 (65,7 %) | 1,216 |
| C1 | 63 | k=3:63 | 0:21 · 1:21 · 2:21 | — | 23 (36,5 %) | 37 (58,7 %) | 1,147 |
| C2 | 57 | k=3:57 | 0:19 · 1:19 · 2:19 | — | 32 (**56,1 %**) | 41 (**71,9 %**) | 1,268 |
| **Todos** | **368** | k=3:358 · k=4:10 | 0:123 · 1:122 · 2:121 · 3:2 | — | 144 (39,1 %) | 219 (59,5 %) | 1,162 |

**Número de opciones:** el 4.º distractor solo existe en **A1** (10/105 checks);
A2–C2 son **100 % `k=3`**. Es un hallazgo de forma de AJ, pero condiciona la
lectura de AL: la posición 3 solo es medible en A1.

Fuente: `docs/audit/generated/item-form.json` → grupos `checks A1…C2`.
Referencia de azar: 1/3 ≈ 33,3 % (`k=3`).

### 2 · Corpus de listening por nivel

| Nivel | N | k | Posiciones de la correcta | Muertas | Más larga (única) | Más larga o empatada | Ratio |
|---|---|---|---|---|---|---|---|
| A1 | 200 | k=4:200 | 0:51 · 1:49 · 2:49 · 3:51 | — | 59 (**29,5 %**) | 90 (45,0 %) | 1,186 |
| A2 | 200 | k=4:200 | 0:51 · 1:50 · 2:50 · 3:49 | — | 79 (39,5 %) | 112 (56,0 %) | 1,252 |
| B1 | 25 | k=4:25 | 0:7 · 1:5 · 2:7 · 3:6 | — | 15 (**60,0 %**) | 19 (76,0 %) | 1,360 |
| B2 | 25 | k=4:25 | 0:6 · 1:7 · 2:6 · 3:6 | — | 10 (40,0 %) | 13 (52,0 %) | 1,227 |
| C1 | 20 | k=4:20 | 0:5 · 1:4 · 2:5 · 3:6 | — | 16 (**80,0 %**) | 16 (80,0 %) | 1,482 |
| C2 | 20 | k=4:20 | 0:5 · 1:6 · 2:5 · 3:4 | — | 16 (**80,0 %**) | 16 (80,0 %) | 1,503 |
| **Todos** | **490** | k=4:490 | 0:125 · 1:121 · 2:122 · 3:122 | — | 195 (39,8 %) | 266 (54,3 %) | 1,249 |

**C1 y C2, caso extremo:** en 16/20 cada uno la correcta es la **única** opción
más larga (80,0 %); los 4 restantes son estrictamente más cortos (no hay
empates: `or_tied` = `is_longest` = 16). Un alumno que marque siempre la opción
más larga acierta ~**80 %** en un ítem de 4 opciones donde el azar da 25 %.
Con `n=20`, la cola inferior del IC95 binomial aproximado ronda el 62 %: el
atajo sigue siendo claro, pero **1 ítem mueve 5 pp** y la cifra no debe leerse
como si tuviera la precisión de los 200 de A1.

Fuente: `docs/audit/generated/item-form.json` → grupos `corpus A1…C2`.
Referencia de azar: 1/4 = 25,0 % (`k=4`).

### 3 · ¿El gradiente por nivel es monótono?

Serie de `correct_is_longest` en orden A1→C2:

| Banco | A1 | A2 | B1 | B2 | C1 | C2 | ρ Spearman | Inversiones |
|---|---|---|---|---|---|---|---|---|
| Checks | 25,7 | 36,4 | 50,9 | 42,9 | 36,5 | 56,1 | **0,77** | B1→B2 (−8,0) · B2→C1 (−6,4) |
| Corpus | 29,5 | 39,5 | 60,0 | 40,0 | 80,0 | 80,0 | **0,93** | B1→B2 (−20,0) |

- **No es monótono en ningún banco.** Hay una tendencia positiva global
  (ρ = 0,77 checks · 0,93 corpus), pero se rompe: en checks, **dos** inversiones
  adyacentes (B1→B2 y B2→C1); en corpus, **una** (B1→B2, −20 pp).
- **Pico local en B1**, no en el techo: B1 es 50,9 % en checks (el 2.º más alto
  tras C2) y **60,0 %** en corpus (por encima de A2 y de B2). C1 cae a 36,5 % en
  checks antes del salto final a C2 56,1 %.
- La versión **más larga o empatada** repite el patrón: checks
  49,5 → 58,2 → 64,2 → 65,7 → 58,7 → 71,9 (baja en C1); corpus
  45,0 → 56,0 → 76,0 → 52,0 → 80,0 → 80,0 (baja en B2).
- **Lectura:** no hay una escalera de forma que acompañe a A1→C2. El patrón es
  **deriva de autoría agrupada por nivel** (B1 y la franja C2/C1-corpus), no una
  propiedad CEFR: el criterio interno `docs/audit/CEFR-REFERENCE.md:53` prohíbe
  que la correcta sea la más larga como criterio **por ítem**, y **no define
  ninguna banda de longitud por nivel** (a diferencia de wpm o dificultad, que sí
  tienen banda en `CEFR-REFERENCE.md:16-30`).

### 4 · El invariante de V3.75.1 medido por nivel (¿esconde el agregado una posición muerta?)

V3.75.1 cierra el P0 con la regla **global** «por grupo de `k`, ordenado por `id`
ascendente, la correcta va a `j % k`»
(`backend/scripts/rebalance_mc_positions.py:88-103`). Ese reparto se mide sobre
los 368 checks juntos, **no por nivel**. Comprobación por nivel, por `k`:

| Nivel | k=3 posiciones | Peor posición k=3 | k=4 posiciones | Peor posición k=4 | Muertas |
|---|---|---|---|---|---|
| A1 | 32 · 32 · 31 | 33,7 % | 3 · 3 · 2 · 2 | 30,0 % | — |
| A2 | 18 · 18 · 19 | 34,5 % | — | — | — |
| B1 | 18 · 18 · 17 | 34,0 % | — | — | — |
| B2 | 12 · 11 · 12 | 34,3 % | — | — | — |
| C1 | 21 · 21 · 21 | 33,3 % | — | — | — |
| C2 | 19 · 19 · 19 | 33,3 % | — | — | — |

Corpus (todo `k=4`):

| Nivel | Posiciones | Peor posición | Muertas |
|---|---|---|---|
| A1 | 51 · 49 · 49 · 51 | 25,5 % | — |
| A2 | 51 · 50 · 50 · 49 | 25,5 % | — |
| B1 | 7 · 5 · 7 · 6 | 28,0 % | — |
| B2 | 6 · 7 · 6 · 6 | 28,0 % | — |
| C1 | 5 · 4 · 5 · 6 | 30,0 % | — |
| C2 | 5 · 6 · 5 · 4 | 30,0 % | — |

- **Ningún nivel tiene posición muerta** y el peor registro por nivel está bajo
  el límite del 35 % de la casa (máximo 34,5 % en A2-checks; 30,0 % en
  C1/C2-corpus). El χ² descriptivo frente a uniforme es ≈ 0,0–0,4 en todos los
  niveles por `k` (el único valor alto, 29,97, sale de mezclar `k=3` y `k=4` en
  A1 y **no** es el test correcto: por `k`, A1 k=3 da χ²≈0,02 y A1 k=4 ≈0,4).
- **Límite del hallazgo:** ese equilibrio por nivel es **emergente** de la regla
  global, no un invariante impuesto por nivel; con `n` = 20–35 en corpus
  B1/C1/C2 y checks B2, un solo ítem mueve 3–5 pp y el margen hasta el 35 % es
  fino. No se puede afirmar que el reparto por nivel esté **blindado**.
- **No se re-mide el P0 global:** se cita su resultado (`0:33,4 % · 1:33,2 % ·
  2:32,9 % · 3:0,5 %`, peor 33,5 %) tal como lo dejó `AA` §Cierre.

### 5 · Cruce con la adecuación CEFR ya auditada (AA)

Forma y adecuación CEFR son propiedades **ortogonales** y no co-varían:

| Nivel | Forma (este eje) | CEFR declarado (`AA` / `cefr-adequacy`) |
|---|---|---|
| A1 | La más sana: checks 25,7 % (ratio 1,057), corpus 29,5 % | La más rota en velocidad: **86/200** ítems por encima del techo de 115 wpm (`AA` #2) |
| A2 | Intermedia: 36,4 % checks · 39,5 % corpus | Fuera de banda en wpm: 0 |
| B1 | Pico de forma: 50,9 % checks · **60,0 %** corpus | 2/25 fuera de banda wpm; 4 `connected_speech` declarados y 4 realizados |
| B2 | 42,9 % checks · 40,0 % corpus | 0 fuera de banda wpm; solo 3/11 `connected_speech` realizados (`AA` #5) |
| C1 | 36,5 % checks · **80,0 %** corpus | La más rota en velocidad: **18/20** por debajo del suelo de 165 wpm (`AA` #3); 0/14 `connected_speech` realizados |
| C2 | **56,1 %** checks · **80,0 %** corpus | **19/20** por debajo del suelo de 175 wpm (`AA` #3); 0/20 `connected_speech` realizados |

- El criterio interno **no fija longitud de opción por nivel**: `CEFR-REFERENCE.md`
  solo dice, como criterio por ítem, «el distractor correcto no debe ser el más
  largo ni el único con palabra del audio» (`:53`). Por tanto **el gradiente
  observado no se puede atribuir al CEFR**: es autoría.
- Hay **co-ocurrencia** en C1/C2-corpus (lentos **y** correcta-más-larga) y
  **divergencia** en A1 (forma sana, velocidad rota). No hay un nivel
  globalmente «sano» ni «roto»: cada eje dibuja su propio mapa. Que ambas
  deudas de C1/C2 compartan probablemente la misma mano de autoría es una
  **hipótesis** que esta medición **no** demuestra.
- La escalera no monótona ya estaba declarada para **wpm** y **dificultad**
  (`AA` #4: `monotonic_max_wpm = false`, `monotonic_mean_difficulty = false`).
  AL añade una **tercera** escalera no monótona (forma/longitud). No es
  casualidad de un eje: el banco no tiene una noción de progresión validada
  para varias dimensiones a la vez.

---

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| AL-1 | **P1** | **C1/C2-corpus: la correcta es la única más larga en 80,0 % (16/20 cada uno), ratio 1,482/1,503; en los otros 4/20 es estrictamente más corta (sin empates).** En un ítem de 4 opciones donde el azar da 25 %, «marcar la más larga» acierta ~80 %: atajo de forma que permite acertar sin comprender justo en los niveles de pragmática. Localizado en 40 de 490 ítems del corpus. | `item-form.json` → `corpus C1`, `corpus C2`; `item-form.md` §Longitud | Reescribir distractores de C1/C2 para igualar longitudes y añadir el invariante de longitud en la reautoría de V4.0.x; re-medir. | abierto |
| AL-2 | **P2** | **C2-checks es el nivel de checks con mayor sesgo:** 32/57 (56,1 %) única más larga y 41/57 (**71,9 %**) más larga o empatada, ratio 1,268 (el más alto de los checks). Rompe la bajada B1→B2→C1. | `item-form.json` → `checks C2` | Revisar por enumeración los 57 checks de C2 en la fase de contenido; no normalizar a ciegas. | abierto |
| AL-3 | **P2** | **Pico local en B1:** checks 27/53 (50,9 %) y corpus 15/25 (**60,0 %**), por encima de A2 **y** de B2 en ambos bancos. No sigue una escalera: es un grupo de autoría con el defecto concentrado. | `item-form.json` → `checks B1`, `corpus B1` | Tratar B1 como lote de reautoría propio, no como punto de una rampa. | abierto |
| AL-4 | **P2** | **El gradiente por nivel no es monótono en ningún banco:** checks 25,7→36,4→50,9→42,9→36,5→56,1 (ρ=0,77; inversiones B1→B2 y B2→C1); corpus 29,5→39,5→60,0→40,0→80,0→80,0 (ρ=0,93; inversión B1→B2). El criterio interno no define banda de longitud por nivel (`CEFR-REFERENCE.md:53`), luego **no es una propiedad CEFR incumplida: es deriva de autoría por nivel**. | §Evidencia 3; `CEFR-REFERENCE.md:53` | Declarar la forma como deriva de autoría y no como escalera; si se quiere una progresión de forma, diseñarla explícitamente (decisión pedagógica). | abierto |
| AL-5 | **P3** | **El invariante de reparto POR NIVEL se cumple hoy, pero es emergente y frágil:** ninguna posición muerta por nivel y peor posición ≤34,5 % (k=3) / 30,0 % (k=4, solo A1); corpus ≤30,0 %. Sin embargo la regla `j % k` es global (`rebalance_mc_positions.py:88-103`) y con `n`=20–35 un ítem = 3–5 pp. | §Evidencia 4; `item-form.json` → `by_options_count` | Si se quiere blindar el reparto **por nivel**, añadir un candado por nivel en la fase de corrección; hoy no existe. | abierto |
| AL-6 | **P3** | **Número de opciones desigual por nivel:** el 4.º distractor solo existe en A1 (10 checks); A2–C2 son 100 % `k=3`. La homogeneidad de `k` y su impacto son de AJ, pero condiciona toda lectura de posiciones por nivel (la posición 3 solo es medida en A1). | `item-form.json` → `checks A1…C2` | Trasladar a AJ; aquí se declara como límite de medición. | abierto |

**Limpio / sin hallazgo en este eje:**

- Reparto de posiciones **equilibrado por nivel** (checks y corpus): sin posición
  muerta y bajo el 35 % (AL-5 documenta el matiz de fragilidad).
- El corpus no tiene posiciones muertas en ningún nivel.
- La tasa global (39,1 % checks · 39,8 % corpus) ya está registrada como sesgo de
  longitud en `AA` #7 y **no se reabre**; AL añade **dónde** se concentra.

---

## Veredicto

**No aprobado en forma por nivel; aprobado en reparto de posiciones por nivel.**

La forma **no es homogénea a lo largo de A1→C2**. El defecto no es un parámetro
global único: hay una tendencia de fondo (39,1 % checks · 39,8 % corpus de
correcta más larga) con **agravamiento concentrado por nivel**: C1/C2-corpus al
**80 %** y C2-checks al **56,1 %/71,9 %**, más un **pico local en B1** (50,9 %
checks · 60,0 % corpus). El gradiente **no es monótono** en ninguno de los dos
bancos (ρ=0,77 checks · 0,93 corpus; inversión B1→B2 en ambos, y B2→C1 además en
checks). Como `CEFR-REFERENCE.md` no define longitud de opción por nivel, el
patrón es **deriva de autoría agrupada por nivel**, no un requisito CEFR
incumplido.

El **único** aspecto de forma que resiste por nivel es el que V3.75.1 acaba de
cerrar: el reparto de posiciones. Medido por nivel y por `k`, ningún nivel tiene
posición muerta y todos quedan bajo el 35 % (`≤34,5 %` en checks, `≤30,0 %` en
corpus). El agregado **no esconde** ninguna posición muerta; sí puede esconder,
por tamaño, que el margen es fino (B2-checks 35 ítems; corpus C1/C2 20).

**Qué demuestra y qué no.** Demuestra que la **tasa** de correcta-más-larga se
concentra por nivel (C1/C2-corpus, C2-checks, B1) y que el gradiente no es
monótono. **No** demuestra que cada ítem con la correcta más larga sea un ítem
malo —puede ser el más claro del banco—, ni mide discriminación empírica con
alumnos (no hay aprendices en el bucle, `docs/audit/PARKED.md`). El mapa
forma≠CEFR (A1 sana en forma pero rota en wpm; C1/C2 rotas en ambas) muestra que
no hay un nivel globalmente sano: **cada eje tiene su propio mapa de deuda.**

---

## Regenerar / Verificar

Todos los comandos son de **solo lectura** salvo el primero, que **escribe** el
par `docs/audit/generated/item-form.{md,json}`. En esta auditoría **no se
re-regeneró** ese artefacto (queda fuera del alcance de escritura del eje AL); la
comprobación de que el artefacto en disco coincide con el constructor es el test
`test_los_artefactos_generados_coinciden_con_el_disco`.

```powershell
cd backend
# Reproduce la evidencia base de este dossier (el artefacto ya está versionado).
.\.venv\Scripts\python.exe -m scripts.audit_dossier item-form
# Contrato del instrumento y anti-deriva del artefacto (18 tests).
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_psy_item_form_v3751.py
```

Cortes derivados de §Evidencia 3 y 4 (leídos del artefacto versionado; peor
posición y χ² descriptivo por nivel, sin escribir nada):

```powershell
cd backend
.\.venv\Scripts\python.exe -c "import json; d=json.load(open(r'..\docs\audit\generated\item-form.json',encoding='utf-8')); gs=[g for g in d['groups'] if g.get('n') and 'todos' not in g['name'] and (g['name'].startswith('checks ') or g['name'].startswith('corpus '))]; [print(g['name'],'| n=',g['n'],'| pos=',list(g['positions'].values()),'| max%=',round(100*max(g['positions'].values())/g['n'],1),'| chi2=',round(sum((v-g['n']/len(g['positions']))**2/(g['n']/len(g['positions'])) for v in g['positions'].values()),2)) for g in gs]"
```

ρ de Spearman (descriptiva) de §Evidencia 3: se ordenan los niveles A1…C2 y las
tasas `correct_is_longest_pct` de cada banco; ρ = 1 − 6·Σd²/(n(n²−1)), n=6,
empates con rango promedio → checks **0,77**, corpus **0,93**. Reproducible a
mano desde los valores de las tablas 1 y 2.

---

## Tests que respaldan

`backend/tests/test_psy_item_form_v3751.py` (18 tests, verdes) fija el
**contrato del instrumento**, no las cifras del defecto (la auditoría es de
medición y los candados de forma se diseñan **con** la corrección, no antes):

| Test | Qué garantiza |
|---|---|
| `test_mc_banks_son_los_cuatro_bancos_declarados` · `test_cada_fila_de_banco_es_un_mc_completo` | Los tres ejes (`item-form`, `distractor-signals`, `mc-bias`) miden el **mismo** conjunto (368/490/22/24). |
| `test_el_placement_tiene_sus_24_items_y_no_esta_fundido_con_los_examenes` | Exámenes y placement son instrumentos separados (frontera con AI). |
| `test_item_form_posiciones_y_k_suman_y_las_muertas_lo_son` | Las posiciones y `k` suman `n`; las posiciones muertas son reales. |
| `test_item_form_marca_el_reparto_por_grupo_no_solo_el_agregado` | El desglose por `k` existe: el agregado de 368 escondería el 4.º distractor de los 10 checks de A1. |
| `test_los_artefactos_generados_coinciden_con_el_disco` | El `item-form.json` que cita este dossier coincide con el constructor en memoria (anti-deriva). |
| `test_length_profile_*` · `test_shape_outlier_*` | La unidad de longitud y la definición de «más larga única» / empate. |
| `test_item_form_es_determinista` · `test_el_instrumento_no_escribe_en_data_ni_en_curriculum` | Determinismo y solo lectura. |
