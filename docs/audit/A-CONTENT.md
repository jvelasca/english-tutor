# A — Curriculum Content Quality (auditoría V3.0)

- **Fecha:** 2026-09-02
- **Alcance:** contenido de `backend/curriculum/{a1..c2}.json` (104 objetivos, 331 checks MC), `speaking_scenarios.json` y referencias cruzadas a los bancos de listening/scenarios. Muestreo por nivel + métricas del Quality Dashboard.
- **Relación con freeze:** contenido (`BETA_V3.md` §4.1).
- **Golden:** ninguno de A es nuevo (A protege contenido ya cubierto por `content_validation` + `curriculum_coverage`); las muestras citadas se reproducen con `python -m scripts.audit_dossier sample --bank objectives`.

## Método

1. `python -m scripts.audit_dossier curriculum-stats` → `docs/audit/generated/curriculum-stats.{md,json}`.
2. `python -m scripts.audit_dossier mc-bias` (sesgo posicional también en checks del currículo).
3. `python -m scripts.content_validation` y `python -m scripts.curriculum_coverage --quality` (gate de contenido existente).
4. Revisión cualitativa de objetivos muestreados (3 por nivel): coherencia `can_do`↔CEFR, skills/subskills correctas, fases del Unit Learning Loop, refs a bancos.

## Evidencia

Quality Dashboard (reproducido el 2026-09-02): **Overall 95.7** (coverage 85.7, depth 84.2, listening/speaking/interaction/assessment/review 100).

| Nivel | Objetivos | checks/obj | act/obj | con listening | con escenario | Veredicto muestral |
|---|---|---|---|---|---|---|
| A1 | 28 | 3.8 | 3.1 | 11 | 22 | OK (escenarios A1: solo `introductions`) |
| A2 | 17 | 3.2 | 4.9 | 7 | 12 | OK |
| B1 | 18 | 2.9 | 4.7 | 7 | 11 | OK |
| B2 | 13 | 2.7 | 4.9 | 5 | 4 | OK |
| C1 | 14 | 3.2 | 4.9 | 4 | 8 | OK |
| C2 | 14 | 2.7 | 4.9 | 4 | 8 | OK |

Notas muestrales por nivel:

- **A1**: can-dos con skills coherentes y subskills del foco de escucha (`word_recognition`, `sound_recognition`); refs a 4 ítems de corpus por objetivo de escucha; checks de opción múltiple simples y directos.
- **A2**: objetivos con `gist`/`detail`; verbos de experiencia; correcto.
- **B1**: objetivo de narrativa escucha/lectura con `connected_speech`+`phrase_recognition`; checks con `tenses`/`word_families`.
- **B2**: discourse markers (`however`, `nevertheless`, `whereas`), register formal/informal, argumentación; coherente.
- **C1**: inversión para énfasis, idioms, argumento complejo; coherente. 
- **C2**: dispositivos retóricos (metaphor, parallelism, hyperbole), mediar conflicto con lenguaje preciso; coherente.

## Hallazgos

| # | Sev. | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| A1 | **alta** | Sesgo posicional en checks del currículo: **88,2 % de los 331 checks tienen la respuesta en la opción 0** (292/331). Mismo defecto que B1 pero en contenido de práctica/assessment. | `mc-bias` | Rebalancear checks (rotación determinista) igual que el corpus; **fix pendiente de tu aprobación**. | abierto |
| A2 | media | Speaking A1 se apoya en un único escenario (`introductions`) reutilizado por 22 objetivos; C1/C2 repiten pocos escenarios para muchos objetivos. No es un bug (cefr_target alineado) pero limita variedad comunicativa. | `curriculum-stats` + cruce escenarios | Autoría de 1–2 escenarios A1 adicionales y ampliar catálogo C1/C2 en fase de contenido. | abierto |
| A3 | baja | Cobertura (85.7) y depth (84.2) son los dos puntos débiles del dashboard frente a los 100 de listening/assessment: hay huecos `partial` no `empty`. | quality dashboard | No urgente para Beta; revisar en la siguiente pasada de autoría. | abierto |
| A4 | info | Todos los objetivos muestreados declaran exactamente 5 actividades (practice/retrieve/transfer/review/assess); el resto de fases del loop (introduce/listen/speak/interact) se distribuyen a nivel de unidad, no de objetivo. Diseño válido y verificado por `learning_loop`; no es defecto. | muestras | — | aceptado |

No se han detectado violaciones estructurales (`content_validation` y `validate_level` limpios), skills no canónicas, ni ids duplicados.

## Veredicto

**Contenido curricular estructuralmente sano y bien alineado CEFR en la muestra revisada.** El único defecto de calidad serio es el sesgo posicional de las respuestas de los checks (A1), que comparte causa con el corpus y debería corregirse en el mismo movimiento de rebalanceo (decisión tuya). Sin esa corrección, la calibración de Assessment 2.0 mide parcialmente la posición, no el dominio.

## Tests que respaldan

- Suite existente: `content_validation`, `test_curriculum*`, `test_*_quality` (gate CI).
- Reproducible: `python -m scripts.audit_dossier sample --bank objectives --level C1 --count 5 --json`.

## Regenerar / Verificar

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.content_validation
.venv\Scripts\python.exe -m scripts.curriculum_coverage --quality
.venv\Scripts\python.exe -m scripts.audit_dossier curriculum-stats
.venv\Scripts\python.exe -m scripts.audit_dossier mc-bias
```
