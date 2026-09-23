# G7 · Matriz de lectura de los 9 ejes

> **Naturaleza:** documento de **revisión humana**, no un instrumento nuevo. No
> mide nada por su cuenta: **ordena** lo que ya midieron los nueve dossiers de
> `docs/audit/generated/` para que la revisión de G7 sea **leer y firmar**, no
> recalcular.
> **Companion de:** `docs/CONSTITUCION-PEDAGOGICA.md` (§G7 del kit,
> `docs/audit/KIT-VALIDACION-GATES.md`) y `docs/audit/AF-SINTESIS-PEDAGOGICA-V370.md`
> (la síntesis que abrió estos ejes).
> **Árbol de las cifras:** `v3.76.0` · `d7fbfabb` · 2026-09-21. Los nueve dossiers
> se regeneraron sobre el árbol congelado y salieron **byte a byte iguales**,
> también **después** del diff del PIN (Fase 3 del P0): son reproducibles, no una
> foto de un día.
> **Estado del gate:** G7 sigue **`pending`**. Esta matriz no lo cierra. Un gate se
> cierra con `record` y, sin `--notes`, el instrumento rechaza el registro.

**Cómo se lee.** Cada eje trae su cifra de cabecera y, en la última columna, **la
decisión que le toca al humano**. El detalle por eje al final es para poder
comprobar cualquier número sin volver a ejecutar el dossier.

---

## 1 · Cuadro de mando

| # | Eje | Instrumento | Cifra de cabecera | Lo que decide el humano |
|---|---|---|---|---|
| 1 | Corpus de listening | `corpus-stats` | 490 ítems · 117→164 wpm | ¿La rampa A1→C2 y los 90 ítems finos por encima de A2 son aceptables? |
| 2 | Currículum | `curriculum-stats` | 116 objetivos · 368 checks | ¿Los objetivos por nivel y su densidad son la propuesta que se congela? |
| 3 | Speaking | `speaking-stats` | 26 escenarios · 1 en A1 y C1 | ¿26 escenarios bastan, y aceptas 1 solo en A1 y 1 solo en C1? |
| 4 | Sesgo posicional | `mc-bias` | Equilibrado en corpus; desviado en nivelación | ¿El placement (17/24 en la posición 1) se corrige antes de V4.0 o se declara? |
| 5 | Adecuación CEFR | `cefr-adequacy` | Fuera de banda: A1 86 · C1 18 · C2 19 | ¿Se acepta la banda de wpm como referencia interna y no como regla? |
| 6 | Cobertura de destrezas | `skill-coverage` | 6 huecos · corpus B1 al 13.9% | ¿`reading` y `mediation` quedan declarados como no cubiertos en V4.0? |
| 7 | Feedback y corrección | `feedback-coverage` | 2 sin canal · 4 solo puntuación | ¿Basta puntuar sin explicar en listening, vocabulary y pronunciation? |
| 8 | Afirmación de maestría | `mastery-claims` | 9 / 8 / 7 registros que no cuadran | ¿Los tres registros deben coincidir antes de V4.0 o se declara el desajuste? |
| 9 | Instrumentos de nivelación | `assessment-instruments` | 0 desacuerdos · final solo en A1 y B1 | ¿A2, B2, C1 y C2 pueden no tener examen final? |

---

## 2 · Las cuatro cosas que hay que leer antes de firmar

Ninguna es un hallazgo nuevo: las cuatro ya estaban en
`AF-SINTESIS-PEDAGOGICA-V370.md`. Lo que hace el eje es **volver a medirlas sobre
este árbol**, y por eso siguen siendo lo que hay que decidir.

1. **`reading` y `mediation` están sin cubrir de verdad.** `reading.py` no existe
   como scorer y mediation no tiene ni competencias, ni corpus, ni canal de
   evidencia, ni scorer ni UI. No es una deuda de calidad: es una destreza
   declarada en la matriz CEFR que no tiene instrumento.
2. **La banda de wpm no se cumple en A1, C1 ni C2** (86, 18 y 19 ítems fuera de la
   banda declarada), y las propiedades declaradas de *connected speech* **no se
   realizan** en B2 (11→3), C1 (14→0) y C2 (20→0).
3. **El placement no puede cumplir su propio umbral de parada:** con 8 ítems, el
   mejor `SE` alcanzable es **0.7071**, y el umbral declarado es `SE < 0.5`. No es
   que no lo alcance en la práctica: **no lo puede alcanzar nunca** con su diseño
   actual.
4. **`mediation` es la única destreza con todos los huecos a la vez** (competencias,
   corpus, canal, scorer y UI), y `interaction`, que sí tiene scorer, no tiene
   canal de evidencia: se puede medir pero no se puede sustentar la afirmación.

---

## 3 · Detalle por eje

### Eje 1 · Corpus de listening (`listening-corpus-stats.md`)

490 ítems `cNNN` en total, y **A1 y A2 se llevan 400**. Por encima de A2 el corpus
es fino (25, 25, 20 y 20). La dificultad declarada sube de forma suave; los wpm dan
un **salto en B1** y luego se mueven poco entre C1 y C2.

| Nivel | N | wpm medio (mín–máx) | dificultad (mín–máx) | palabras/script | connected | acentos |
|---|---|---|---|---|---|---|
| A1 | 200 | 117.22 (115–125) | 1.21 (1–2) | 8.56 (5–14) | 0 | 11 |
| A2 | 200 | 130.85 (130–135) | 2.23 (2–3) | 10.12 (5–15) | 0 | 11 |
| B1 | 25 | 143.40 (130–175) | 2.92 (2–3) | 13.56 (9–16) | 4 | 8 |
| B2 | 25 | 162.40 (150–185) | 4.04 (3–5) | 15.04 (8–23) | 11 | 8 |
| C1 | 20 | 156.15 (150–170) | 4.00 (4–4) | 25.60 (17–39) | 14 | 10 |
| C2 | 20 | 164.35 (159–175) | 4.35 (4–5) | 24.30 (16–30) | 20 | 10 |

Skills dominantes: A1/A2 `detail` (55 y 50), después `vocabulary` y `gist`; de B1
en adelante entran `inference`, `speaker_intention` y `connected_speech`.

### Eje 2 · Currículum (`curriculum-stats.md`)

116 objetivos y 368 checks. La densidad por objetivo es **la más baja en B2 (2.69
checks, 13 objetivos)** y la más alta en A1 (3.75), que es el nivel donde más
importa sostener el andamiaje.

| Nivel | Objetivos | Checks/obj | Actividades/obj | Con listening | Con escenario |
|---|---|---|---|---|---|
| A1 | 28 | 3.75 | 3.07 | 11 | 22 |
| A2 | 17 | 3.24 | 4.88 | 7 | 12 |
| B1 | 18 | 2.94 | 4.67 | 7 | 11 |
| B2 | 13 | 2.69 | 4.85 | 5 | 4 |
| C1 | 20 | 3.15 | 4.90 | 4 | 10 |
| C2 | 20 | 2.85 | 4.90 | 4 | 9 |

### Eje 3 · Speaking (`speaking-stats.md`)

26 escenarios con 5 métricas declaradas (`fluency`, `interaction`, `repair`,
`task_completion`, `turn_taking`). **A1 y C1 tienen 1 cada uno**, y las tareas se
reparten entre role play (9), discusión (8), conversación (7) y entrevista (2).

| CEFR | Escenarios | | Tipo de tarea | Escenarios |
|---|---|---|---|---|
| A1 | 1 | | role_play | 9 |
| A2 | 6 | | discussion | 8 |
| B1 | 7 | | conversation | 7 |
| B2 | 5 | | interview | 2 |
| C1 | 1 | | | |
| C2 | 6 | | | |

### Eje 4 · Sesgo posicional (`mc-position-bias.md`)

Reparto de la opción correcta. Con 4 opciones lo equilibrado es 25% por posición;
con 3, 33%. **El corpus está plano**; la nivelación no.

| Grupo | Ítems | Reparto 0/1/2/3 | Lectura |
|---|---|---|---|
| corpus listening (c*) | 490 | 125/121/122/122 | Equilibrado (25.5 / 24.7 / 24.9 / 24.9) |
| corpus A1 | 200 | 51/49/49/51 | Equilibrado |
| corpus A2 | 200 | 51/50/50/49 | Equilibrado |
| corpus B1 | 25 | 7/5/7/6 | Equilibrado |
| corpus B2 | 25 | 6/7/6/6 | Equilibrado |
| corpus C1 | 20 | 5/4/5/6 | Equilibrado |
| corpus C2 | 20 | 5/6/5/4 | Equilibrado |
| checks currículo | 368 | 123/122/121/2 | 358 de los 368 tienen 3 opciones, no 4 |
| exámenes finales | 22 | 14/8 | 63.6% / 36.4% (3 opciones) |
| **placement** | **24** | **6/17/1** | **70.8% en la posición 1** |

### Eje 5 · Adecuación CEFR (`cefr-adequacy.md`)

La referencia de wpm es **interna del proyecto** (`docs/audit/CEFR-REFERENCE.md`),
no un documento CEFR normativo, y esta es la tabla que hay que leer con eso en la
cabeza.

| Nivel | N | wpm medio (mín–máx) | banda declarada | fuera | dificultad media | banda | fuera |
|---|---|---|---|---|---|---|---|
| A1 | 200 | 117.22 (115–125) | 80–115 | **86** | 1.21 | 1–2 | 0 |
| A2 | 200 | 130.85 (130–135) | 110–135 | 0 | 2.23 | 2–3 | 0 |
| B1 | 25 | 143.40 (130–175) | 130–160 | 2 | 2.92 | 2–4 | 0 |
| B2 | 25 | 162.40 (150–185) | 150–185 | 0 | 4.04 | 3–5 | 0 |
| C1 | 20 | 156.15 (150–170) | 165–195 | **18** | 4.00 | 4–5 | 0 |
| C2 | 20 | 164.35 (159–175) | 175–200 | **19** | 4.35 | 4–6 | 0 |

Propiedades declaradas frente a realizadas:

| Nivel | CS declarado | CS realizado | inference | con integración |
|---|---|---|---|---|
| A1 | 0 | 0 | 0 | 0 |
| A2 | 0 | 0 | 5 | 1 |
| B1 | 4 | 4 | 2 | 1 |
| B2 | 11 | **3** | 5 | 4 |
| C1 | 14 | **0** | 3 | 3 |
| C2 | 20 | **0** | 3 | 3 |

- **Monotonía de wpm máximo entre niveles:** `False`.
- **Monotonía de dificultad media entre niveles:** `False`.
- Ítems donde la correcta es la opción más larga: corpus **39.8%**, checks
  **39.1%**, exámenes **36.4%**, placement **50.0%**.

### Eje 6 · Cobertura de destrezas (`skill-coverage.md`)

Matriz = hay matriz CEFR; canal = hay canal de evidencia; scorer = **el módulo
existe en disco**; UI = hay feature que lo muestra. El «(AUSENTE)» es la
comprobación de existencia, no una opinión.

| Modalidad | Competencias | Matriz | Canal | Objetivos | Checks | Corpus | Scorer | UI |
|---|---|---|---|---|---|---|---|---|
| vocabulary | 8 | sí | written | 110 | 180 | 0 | lexicon.py | vocabulary |
| grammar | 11 | sí | written | 56 | 104 | 0 | grammar.py | grammar |
| pronunciation | 10 | **NO** | spoken | 38 | 0 | 120 | pronunciation.py | pronunciation |
| listening | 24 | sí | receptive | 38 | 66 | 490 | listening.py | listening |
| speaking | 18 | sí | spoken | 70 | 0 | 174 | speaking.py | speaking |
| reading | 10 | sí | receptive | 15 | 18 | 0 | reading.py **(AUSENTE)** | chat:lectura |
| writing | 15 | sí | written | 67 | 0 | 0 | writing.py | writing |
| interaction | 0 | sí | **NO** | 0 | 0 | 66 | interaction.py | conversation |
| mediation | 0 | sí | **NO** | 0 | 0 | 0 | **— (AUSENTE)** | **— (AUSENTE)** |

Huecos medidos: `reading` sin scorer propio; `interaction` sin canal de evidencia;
`mediation` sin competencias, sin corpus, sin canal, sin scorer y sin UI.

Contexto: el **manifest de audio humano `1.2.0` tiene 0 entradas grabadas** (todo
el audio es TTS) y hay **539 ítems de aprendizaje validados**. Corpus frente al
objetivo declarado: A1 **100%**, A2 **100%**, B1 13.9%, B2 15.6%, C1 16.7%, C2
20.0%.

### Eje 7 · Feedback y corrección (`feedback-coverage.md`)

| Destreza | Determinista | LLM |
|---|---|---|
| grammar | `services/grammar.py` (regex + confidence) | `policy.CORRECTNESS_GUIDANCE` vía `context.build_system_prompt` |
| writing | `services/writing.py` (rúbrica) | `services/writing_llm.py` (solo extrae evidencia) |
| speaking | `services/speaking.py` (rúbrica) | `services/speaking_llm.py` (solo extrae evidencia) |
| pronunciation | `services/phonetics.py` + `pronunciation.py` | NO |
| listening | puntuación por respuesta (MC) | NO |
| vocabulary | lexicon/evidence (ledger léxico) | NO |
| **reading** | **NO** | **NO** |
| interaction | `services/interaction.py` (telemetría) | NO |
| **mediation** | **NO** | **NO** |

Política de corrección: **7** reglas deterministas de grammar (umbral de
confirmación 0.8, racha de dominio 3), rúbricas de writing **6** y speaking **7**,
**5** categorías formales de feedback (CORRECT, NATURAL, OPTIONAL, PRONUNCIATION,
STYLE) y guía de corrección en los 6 niveles **y Pre-A1** — **ningún nivel sin
guía**.

- Destrezas **sin ningún canal** de corrección: **mediation, reading**.
- Destrezas con canal **solo de puntuación** (sin feedback textual): **interaction,
  listening, pronunciation, vocabulary**.

### Eje 8 · Validez de la afirmación de maestría (`mastery-claims.md`)

Tres registros que deberían coincidir y no coinciden:

| Registro | Cuántos | No aparecen en él |
|---|---|---|
| Modalidades de `MASTERY_SKILLS` | 9 | — |
| Destrezas de la matriz CEFR (`2.1.0`) | 8 | `pronunciation` |
| Canales de evidencia (`MODALITY_CHANNEL`) | 7 | `interaction`, `mediation` |

- Sin canal de evidencia: **interaction, mediation**. Sin competencias declaradas:
  **interaction, mediation**. Sin requisitos en matriz: **pronunciation**.
- Estados: `not_started`, `developing`, `functional`, `demonstrated`. Destrezas de
  producción: grammar, speaking, writing. Destrezas de apoyo (tope `functional`):
  vocabulary.
- Gate espaciado: **2 muestras × 2 días**. Tipos de ítem de producción: speaking,
  writing, pronunciation, controlled_production.
- `transfer_required` sumado en la matriz: **80**. `novel_required`: **0**.
- Los mínimos por nivel son **idénticos para las 9 modalidades** y aun así dos de
  ellas no tienen canal con el que demostrarlos: es la contradicción que este eje
  deja escrita.
- Sin evidencia, las **9** destrezas quedan en `not_started` con `demostrado =
  False`, y la profundidad es `low` (`meets_matrix = False`).

### Eje 9 · Instrumentos de nivelación (`assessment-instruments.md`)

**Exámenes finales:** solo hay en **A1** (10 ítems) y **B1** (12), ambos con umbral
**0.75 por destreza** y las mismas cuatro destrezas evaluadas (grammar, listening,
reading, vocabulary). **Sin examen final: A2, B2, C1 y C2.**

**Placement:** 24 ítems, máximo 8 por sesión, mínimo 4, dificultades 1 y 6 con 4
ítems cada una. El umbral de parada declarado `SE < 0.5` es **inalcanzable**: el
mejor caso con 8 ítems da `SE ≈ 0.7071`. La correcta es la opción más larga en 12
de 24 (50.0%).

**Remediación y gate de unidad:** cinco bancos con 26 ítems en total (grammar 6,
vocabulary 6, listening 5, speaking 6, reading 3). Secciones de unidad: vocabulary,
grammar, listening, speaking, interaction, review, assessment. Umbrales de gate:
vocabulary 0.8, grammar 0.8, listening 0.75, speaking 0.7.

**Umbrales de banda:** los tres estimadores emiten los mismos 6 niveles y
**concuerdan: 0 desacuerdos**. Bandas alcanzables por `band_for_numeric`: a1, a2,
a2+, b1, b1+, b2, b2+, c1, c2, pre-a1. **Sub-bandas declaradas (a2+, b1+, b2+):
ninguna las emite**, así que la escalera declara más granularidad de la que los
estimadores usan.

---

## 4 · Qué falta para cerrar G7

- **Hecho:** los 9 dossiers están regenerados y el árbol no deriva; esta matriz es
  la lectura.
- **Falta:** la revisión humana de los 9 ejes y su firma. G7 **no** se cierra con
  una regeneración: se cierra con `record pedagogia`.
- **Recordatorio del instrumento:** un `pass` **sin commit no se registra**, y sin
  `--notes` tampoco. Un `fail` o un `skip` son resultados válidos y se registran con
  su motivo; lo prohibido es declarar `pass` sin haberlo hecho.
- **Árbol:** el que se certifica es el de **`v3.81.0`** (re-anclaje del 2026-09-23,
  tras V3.78.0/V3.79.0/V3.80.0/V3.80.1 y la Fase 3 del P0 —cuentas de usuario—), no
  el de `v3.75.8` ni el de `v3.76.0`: la campaña tenía **0 `record`** cuando se movió
  el árbol, así que no había nada que invalidar. Se ancla **por tag, sin fijar SHA a
  mano** (regla de V3.73.5). Los dossiers de G7 **no** se re-derivan por estos
  cambios, porque ninguna de esas releases toca currículum, corpus, evaluaciones ni
  banco de listening, y los instrumentos del dossier no leen mazos, tarjetas,
  traducción propia, cuentas ni correo. **Ojo con el contrato:** `v3.81.0` **retira**
  `PUT /api/session/pin` y **cambia** `POST /api/session` (exige contraseña si la
  cuenta la tiene), así que un instrumento de campo que abriera sesión con un
  `user_id` a secas debe conocerlo. Todo queda declarado en la sección
  «Re-congelación» de `docs/audit/KIT-VALIDACION-GATES.md`. Los **7 gates siguen en
  `pending`**.
