# U — Auditoría total de V3.62.0 (Student Skill State 4.0: modalidad × competencia)

> **Posición auditada:** tag anotado **`v3.62.0`** → commit `f4bcee2`
> (`2008824` el objeto de la etiqueta). Cierre de V3.61: `1b4af42` (tag
> `v3.61.0` → `c7f9ce8`). El delta auditado es `1b4af42..f4bcee2` (**19 ficheros,
> +2642 / −25**, 3 commits: `f4bcee2` release, más los dos commits documentales
> `663c174` y `1a73e1a` del relevo a V3.62).
> **Autor:** auditoría externa (agente con acceso solo al repositorio).
> **Fecha:** 2026-09-14.
> **Relación con la letra `R`:** la letra `R` sigue **reservada** para el informe
> pendiente de V3.59 (`docs/audit/R-AUDITORIA-TOTAL-V359.md`, nunca publicado); de
> ahí que esta auditoría use la `U`.
> **Estado de la letra `V`:** reservada para el informe de la auditoría externa
> de V3.62 (punto de entrada en `agentes/auditoria-externa-v362.md`).

## Alcance

- **Se audita:** el salto `v3.61.0 → v3.62.0` (`services/skill_axis.py`,
  `services/skill_state.py`, la columna aditiva `learning_profile.skill_state`, el
  contrato `/api/profile` y la frontera declarada con el camino de decisión),
  además de la arquitectura acumulada desde V3.52.
- **No se audita:** el banco de contextos, el scoring, FSRS, la UI y el detalle
  interno de V3.52–V3.61 salvo en lo que el diff de V3.62 toca.

## Método

Revisión directa del diff `1b4af42..f4bcee2`, de la nota de release, de la
taxonomía nueva y del agregador, contrastados contra los contratos reales de las
cuatro fuentes de evidencia. Suites y números de verificación leídos de la
documentación de la release (evidencia **documental**).

## Evidencia

| Comprobación | Resultado | Veredicto |
|---|---|---|
| Diff `1b4af42..f4bcee2` | 19 ficheros, +2642 / −25, 3 commits | OK |
| P0 | 0 | OK |
| P1 | 2 | abiertos, aceptados |
| P2 | 5 | abiertos, aceptados |
| P3 | 2 | abiertos, aceptados |
| CI 6/6 del run `34839206611` | `statuses = []` y `workflow_runs = []` | **documental, no verificado** |
| No-op del camino de decisión | probado byte a byte por test | OK |

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| P1-01 | alta | El nuevo Skill State todavía **no gobierna** el Planner: el estado se construye, persiste y expone, pero la decisión de tareas sigue leyendo el estado de V3.61 | nota de release, frontera declarada y probada | No conectar `skill_state` al planner directamente: `Student Skill State → Decision Projection → Planner` | abierto |
| P1-02 | alta | `spontaneous_use → interaction` es defendible hoy (su único emisor es `chat`, que es TEXTO) pero la semántica debe evolucionar cuando exista conversación oral real, para distinguir interacción escrita y oral según el CANAL observado | `services/skill_axis.py` (`LEXICAL_MODALITY`) | El evento debe declarar `target_skill`/`assessed_skill`/`evidence_skill`/`modality`/`channel`/`assessment_mode` | abierto |
| P2-11 | media | `pronunciation_attempts` sigue sin competencia (`competence = ""`): se pierde información pedagógica (segmental, stress, rhythm, intonation, connected speech) | `services/skill_state.py`; tabla sin criterio curricular | Definir una rúbrica de pronunciación formal y conectarla; **no inventarla** | abierto |
| P2-12 | media | Listening mezcla subdestreza **curricular** y subdestreza **operacional** en un mismo eje (`numbers` vs `inference` vs `real_world` no son entidades equivalentes) | `SUBSKILLS["listening"]` ∪ `LISTENING_SUBSKILLS` | Descomponer por capas: comprehension / decoding / inference | abierto |
| P2-13 | media | `skill_state` puede **perder granularidad** por duplicación: `_academy_rows` expande una actividad a varias competencias del objetivo y cada una genera su muestra | `services/skill_state.py` (`_academy_rows`) | Conservar `evidence_id`/`activity_id`/`assessment_id` para distinguir observaciones de ocasiones independientes | abierto |
| P2-14 | media | El estado `functional`/`demonstrated` procede de una regla general que no tiene la misma semántica en todas las parejas (`writing:orthography` ≠ `speaking:interaction`) | `services/competence.py` reutilizado | Parametrizar el gate por modalidad/competencia/tipo de evidencia sin crear un umbral arbitrario por caso | abierto |
| P2-18 | media | **Frescura** del Student State: un intento nuevo no actualiza necesariamente el estado cacheado hasta el siguiente refresco de perfil | caché de `learning_profile.skill_state` | Invalidar la caché al escribir evidencia y recomputar una vez en la siguiente decisión | abierto |
| P2-19 | media | `confidence` es estadística (éxitos/intentos) pero no expresa la confianza de que la competencia **haya sido realmente evaluada** (audio lento, TTS, sin ruido ni distractores) | entrada del estado | Separar confianza estadística de confianza de evaluación | abierto |
| P2-20 | media | Sigue faltando la **dificultad empírica** de la tarea (`observed_difficulty` es declarado/servido, no observado por resultado) | `services/difficulty.py` | `DECLARED → SERVED → OUTCOME → OBSERVED`, separando esperada/servida/experimentada/demostrada | abierto |
| P3-01 | baja | Consolidación de los ~15 vocabularios del árbol pendiente | `services/skill_axis.py` (mapea, no consolida) | Consolidar cuando los consumidores lo pidan, y con test | aceptado |
| P3-02 | baja | CI 6/6 **documentado, no verificado de forma independiente** | `statuses = []`, `workflow_runs = []` | Mantenerlo declarado como documental | aceptado |

## Lo que V3.62 cierra (verificado)

- **Ya no hay dos Student Models aislados.** El estado es UNO:
  `{modalidad: {competencia: entry}}`, y `skill_state = {modalidad: {competencia: entry}}`
  se alimenta de cuatro fuentes reales (`learning_evidence`, `academy_evidence`,
  `listening_attempts`, `pronunciation_attempts`).
- **El P1 anterior de V3.60 («Student Skill State demasiado agregado») queda
  cerrado:** ahora la modalidad es la de `MASTERY_SKILLS` (9 canónicas) y el eje
  de competencia vive DENTRO de la modalidad, así que se distingue la **carga del
  contenido** de la **competencia demostrada** (`syntax` **no** es `grammar`).
- **No se inventan competencias.** `canonical_competence(modality, raw)` normaliza
  (casefold + strip) y **no** usa fuzzy matching: lo desconocido devuelve `""`.
- **Las cadenas ambiguas se resuelven por modalidad**, no por un mapa global
  (`AMBIGUOUS_STRINGS`: `register`, `discourse`, `nuance`, `pragmatics`,
  `coherence`, `interaction`, `vocabulary`, `grammar`, `pronunciation`,
  `spelling`).
- **La puerta 2 éxitos / 2 días se reutiliza** (`OBSERVED_MIN_SAMPLES` /
  `OBSERVED_MIN_DAYS` y `competence_state`), sin umbrales nuevos.
- **La evidencia léxica no se convierte artificialmente en competencia.**
- **Dificultad ≠ competencia** se mantiene como frontera.
- **El no-op del camino de decisión está demostrado** byte a byte, con un test
  estructural que fija que ningún módulo del camino de decisión menciona el estado
  nuevo.
- **Persistencia conservadora:** columna `TEXT NOT NULL DEFAULT ''`, migración
  aditiva/idempotente y escritor dedicado `set_skill_state`.

## Veredicto

**9,5 / 10 — APROBADA.** 0 P0. Los dos puntos realmente importantes (P1-01 y
P1-02) son alcance consciente, no defectos. Roadmap recomendado tras V3.62:
**V3.63 Observed Task Difficulty 2.0** (`declared → served → outcome → observed`),
**V3.64 Decision Projection + Planner 3.0**, **V3.65 Instance Generator 2.0** y
después la capa de sentido/semántica.

## Límites declarados de esta auditoría

- El CI 6/6 de `f4bcee2` es evidencia **documental**: la consulta directa de
  `status`/`workflow_runs` para ese commit no devuelve runs, así que no se afirma
  verificación independiente.
- Los P2 se aceptan como deuda declarada del siguiente escalón, no como defectos
  de V3.62.
