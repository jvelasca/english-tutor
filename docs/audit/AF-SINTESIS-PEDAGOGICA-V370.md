# AF · Síntesis de la auditoría pedagógica V3.70

> **Release:** V3.70 (auditoría pedagógica + CEFR) · **documento de síntesis**
> **Fecha:** 2026-09-15 · **Orquestador** (no es un eje: consolida AA–AE)
> **Dossiers de eje:** `AA-PED-CONTENIDO-CEFR.md` · `AB-PED-COBERTURA.md` ·
> `AC-PED-FEEDBACK.md` · `AD-PED-MAESTRIA.md` · `AE-PED-INSTRUMENTOS.md`
> **Evidencia regenerable:** `docs/audit/generated/` (8 ficheros `.md` + `.json`)

## Alcance

Consolidar los **cinco ejes** de la auditoría pedagógica de V3.70 en una matriz
única de severidades y un veredicto, y **declarar con precisión qué no se ha
demostrado**.

**No es un eje nuevo**: no añade mediciones propias. Cada cifra de este
documento proviene de un dossier de eje y es regenerable con los comandos del
§Regenerar.

## Método

1. Los cinco dossiers de eje, cada uno con su instrumento de solo lectura en
   `backend/scripts/audit_dossier.py` (`cefr-adequacy`, `skill-coverage`,
   `feedback-coverage`, `mastery-claims`, `assessment-instruments`).
2. Cada hallazgo se elevó **solo** si tenía `archivo:línea` o un `id` real como
   evidencia. Se descartaron las afirmaciones sin evidencia reproducible.
3. **Regla de honestidad de la casa** (auditoría `Y` §28): distinguir siempre
   **«la medición no demuestra»** de **«el sistema no cumple»**.

## Matriz consolidada

| Eje | Dossier | **P0** | **P1** | **P2** | **P3** | Correcto/Corregido |
|---|---|---|---|---|---|---|
| 1 · Adecuación CEFR del contenido | `AA` | **1** | 3 | 3 | 1 | 1 |
| 2 · Cobertura de destrezas | `AB` | 0 | 4 | 2 | 2 | 0 |
| 3 · Feedback y corrección | `AC` | 0 | 3 | 2 | 0 | 1 |
| 4 · Validez de la maestría | `AD` | 0 | 2 | 2 | 1 | 1 |
| 5 · Instrumentos de nivelación | `AE` | 0 | 3 | 3 | 1 | 1 |
| **Total** | | **1** | **15** | **12** | **5** | **4** |

**33 hallazgos abiertos** (1 P0, 15 P1, 12 P2, 5 P3) y **4 propiedades positivas**
verificadas que deben preservarse.

### El P0 (único)

| # | Eje | Hallazgo | Evidencia |
|---|---|---|---|
| **P0-1** | 1 | **Sesgo posicional de los 368 checks del currículum**: la correcta está en la posición 0 en **329/368 (89,4 %)**. Un alumno que marque siempre la primera opción acierta casi 9 de cada 10. El corpus de listening sí está equilibrado (~25 % por posición). | `generated/mc-position-bias.json`; `a1.json:180`, `a1.json:579` |

Es un P0 **de instrumento**, no de motor: el contenido es correcto en dificultad
(0 de 490 ítems fuera de banda) y la integridad estructural está limpia. Lo que
falla es la **forma** de la evaluación, y afecta a todo el currículum.

### Los P1, agrupados por naturaleza

**(a) Forma de los ítems (permiten acertar sin comprender) — 3 hallazgos**

| Eje | Hallazgo |
|---|---|
| 1 | A1 sistemáticamente rápido: **86/200** ítems por encima del techo de 115 wpm; ninguno cae en la banda 80–115. |
| 1 | C1/C2 sistemáticamente lentos: **18/20** y **19/20** por debajo del suelo de su banda. |
| 5 | Sesgo de forma del placement: correcta = más larga única en **50 %** (y en **75 %** contando empates); **70,8 %** en posición 1; posición 3 **nunca** correcta. |

**(b) Propiedades declaradas sin respaldo — 4 hallazgos**

| Eje | Hallazgo |
|---|---|
| 1 | `connected_speech: true` sin reducción real: **C1 14/14** y **C2 20/20**. |
| 4 | `novel_required = 0` en las 48 celdas pese a que el emisor real existe desde V3.26. |
| 5 | Sub-bandas `a2+`/`b1+`/`b2+` y `pre-a1` declaradas en la escalera y **no emitidas** por ningún estimador. |
| 2 | Biblioteca de audio humano **versionada y vacía** (`entries: []`): todo el listening es TTS. |

**(c) Cobertura y volumen — 4 hallazgos**

| Eje | Hallazgo |
|---|---|
| 2 | Corpus de listening **B1–C2 al 13,9–20,0 %** de su objetivo declarado. |
| 2 | `reading` declara 15 objetivos y 18 checks y **no tiene scorer propio**. |
| 4 | **`interaction` y `mediation` no pueden acreditar evidencia** por ninguna vía. |
| 1 | `mediation` — misma raíz que la anterior, medida desde el contenido: 0/0/0. |

**(d) Instrumentos que no pueden cumplir su función — 3 hallazgos**

| Eje | Hallazgo |
|---|---|
| 5 | El criterio de parada por precisión del placement **es inalcanzable**: pide `SE < 0,5` y la mejor cota con 8 ítems es `0,7071`. |
| 5 | El examen de **B1 tiene los 12 ítems en dificultad 1**, igual que el de A1: no se escala. |
| 5 | **Cuatro de seis niveles sin examen final** (A2, B2, C1, C2). |

**(e) Acreditación perdida — 1 hallazgo**

| Eje | Hallazgo |
|---|---|
| 4 | Filas de speaking assessment y misión escriben `objective_id=''` ⇒ `result 1,0` **no acredita éxito** ni cruza la puerta espaciada (F-K3). |

## Cruces entre ejes (lo que solo se ve mirando los cinco juntos)

1. **`reading` está roto en tres planos a la vez**: contenido declarado sin
   scorer (eje 2), sin canal de corrección (eje 3) y con el banco de remediación
   más pequeño (eje 5, 3 ítems). No es un hueco de contenido: es un cableado que
   falta.
2. **`mediation` está roto en cinco planos**: 0 competencias, 0 corpus, sin
   canal, sin scorer, sin UI (eje 2); exigida por la matriz (eje 4); declarada
   inerte (eje 4). Es la única modalidad **totalmente** inerte.
3. **La forma de los ítems es el patrón más extendido**: sesgo posicional en los
   checks (eje 1, P0), sesgo de posición y longitud en el placement (eje 5, P2) y
   sesgo de longitud en el corpus (eje 1, P2). Los tres son el mismo defecto de
   autoría.
4. **Lo declarado supera a lo realizado de forma sistemática**: `connected_speech`
   (eje 1), `novel_required` (eje 4), sub-bandas (eje 5), biblioteca de audio
   (eje 2), `mediation` (ejes 2/4). Cinco instancias del mismo patrón.
5. **El volumen alto está en los niveles bajos y el hueco en los altos**: A1/A2 al
   100 % de su objetivo de corpus frente a B1–C2 al 14–20 %; y los exámenes
   existen justo en A1 y B1. El producto está **más completo donde el alumno
   empieza** que donde debería llegar.

## Veredicto

**Auditoría superada en arquitectura pedagógica; suspenso en instrumentos y
contenido de la mitad superior.**

Lo que está **bien y medido**: el contenido no está mal nivelado (0 de 490 ítems
fuera de su banda de dificultad); la integridad estructural del currículum está
limpia (116 objetivos, 368 checks, 512 actividades, 0 objetivos sin actividades o
sin checks, 0 checks fuera de las `skills` de su objetivo); el sistema **no
afirma nada sin evidencia** (9/9 modalidades en `not_started`, banda `—`); el gate
de maestría es duro y coherente (producción real, espaciado 2×2, mínimos que
crecen con el nivel, `transfer_required` 0→4); los tres estimadores de banda
coinciden al 100 %; la política de corrección cubre los 7 niveles con 5
categorías formales; y el LLM **no** decide la nota (extrae evidencia, el scorer
determinista puntúa).

Lo que está **mal y medido**: un P0 de forma en los checks (89,4 % de respuestas
correctas en la primera posición); dos destrezas declaradas evaluables que **no
pueden** acreditar (`interaction`, `mediation`); `reading` sin scorer ni canal de
corrección; cinco propiedades declaradas que la realidad no respalda
(`connected_speech` en C1/C2, `novel_required`, sub-bandas, biblioteca de audio,
`mediation`); un placement cuyo criterio de parada no puede dispararse y con
sesgo de forma; un examen de B1 que no se escala respecto al de A1; cuatro de
seis niveles sin examen final; y la mitad superior del corpus (B1–C2) al 14–20 %
de lo que el propio proyecto se exige.

**Ninguna de estas conclusiones pide cambiar la arquitectura.** Todas piden
**contenido**, **cableado** o **instrumentos** — exactamente las fases que el
`PLAN.md` ya tiene previstas: volumen de contenido → **V4.0.x**; motor y
acreditación → **Planner 4.0**; forma de los instrumentos → **V4.0.x / V3.72**.

## Honestidad: qué NO demuestra V3.70

1. **No demuestra eficacia pedagógica.** Se ha medido **adecuación declarada
   frente a un criterio interno** (`docs/audit/CEFR-REFERENCE.md`, que **no** es
   un documento CEFR normativo). No se ha medido aprendizaje de ningún alumno.
2. **No valida el nivel real de un alumno.** El placement se ha auditado como
   instrumento (banco, sesgo, criterio de parada), **no** contra una evaluación
   externa. No se sabe si la banda que estima coincide con la banda real.
3. **No audita la calidad acústica** de un solo ítem: no hay audio humano
   grabado, así que toda la auditoría de listening es sobre **metadatos
   declarados** (wpm, vector de dificultad, transcripción), no sobre el sonido.
4. **No audita el texto que produce el LLM** en ejecución. Se auditó la política
   declarada y la cobertura de canales, no la calidad del feedback real.
5. **No audita el frontend.** V3.70 no toca ni mide la UI; la existencia de una
   feature por modalidad se usó solo como señal de cableado.
6. **No cierra los 6 P2 de la auditoría de V3.69** (cold start, `abandoned_count`,
   reopening, `SCAFFOLDING_PENALTY`, `invalid_transition` por `StrictMode`,
   verificabilidad del CI): siguen abiertos por decisión de alcance.
7. **No corrige nada.** Las 33 insuficiencias quedan **declaradas y asignadas a
   fase**, no remediadas. El valor de V3.70 es que dejan de ser opinión.
8. **La cota del placement es analítica, no empírica.** `SE ≥ 0,7071` se deduce
   del modelo 1PL declarado, no de simular respuestas reales.

## Regenerar / Verificar

```powershell
cd backend
# Los ocho instrumentos de medición (solo lectura).
.\.venv\Scripts\python.exe -m scripts.audit_dossier corpus-stats
.\.venv\Scripts\python.exe -m scripts.audit_dossier curriculum-stats
.\.venv\Scripts\python.exe -m scripts.audit_dossier speaking-stats
.\.venv\Scripts\python.exe -m scripts.audit_dossier mc-bias
.\.venv\Scripts\python.exe -m scripts.audit_dossier cefr-adequacy
.\.venv\Scripts\python.exe -m scripts.audit_dossier skill-coverage
.\.venv\Scripts\python.exe -m scripts.audit_dossier feedback-coverage
.\.venv\Scripts\python.exe -m scripts.audit_dossier mastery-claims
.\.venv\Scripts\python.exe -m scripts.audit_dossier assessment-instruments

# Los cinco ficheros de test de la auditoría.
.\.venv\Scripts\python.exe -m pytest -q tests/test_ped_content_cefr_v370.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_ped_coverage_v370.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_ped_feedback_v370.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_ped_mastery_v370.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_ped_instruments_v370.py
```

## Tests que respaldan

| Fichero | Tests | Eje |
|---|---|---|
| `tests/test_ped_content_cefr_v370.py` | 8 | 1 |
| `tests/test_ped_coverage_v370.py` | 10 | 2 |
| `tests/test_ped_feedback_v370.py` | 10 | 3 |
| `tests/test_ped_mastery_v370.py` | 10 | 4 |
| `tests/test_ped_instruments_v370.py` | 10 | 5 |
| **Total** | **48** | |

Cada test fija un hallazgo **medido**: si alguien cierra un hueco, el test falla y
obliga a re-auditar el eje. Esa es la diferencia entre una auditoría y un
informe.
