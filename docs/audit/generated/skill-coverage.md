# Cobertura de destrezas (V3.70 · Eje 2)

> Generado por `python -m scripts.audit_dossier skill-coverage`.
> Matriz modalidad × artefacto declarado, con la EXISTENCIA comprobada
> en disco. Solo lectura.

| Modalidad | Competencias | Matriz | Canal | Objetivos | Checks | Corpus | Scorer | UI |
|---|---|---|---|---|---|---|---|---|
| vocabulary | 8 | sí | written | 110 | 180 | 0 | lexicon.py | vocabulary |
| grammar | 11 | sí | written | 56 | 104 | 0 | grammar.py | grammar |
| pronunciation | 10 | NO | spoken | 38 | 0 | 120 | pronunciation.py | pronunciation |
| listening | 24 | sí | receptive | 38 | 66 | 490 | listening.py | listening |
| speaking | 18 | sí | spoken | 70 | 0 | 174 | speaking.py | speaking |
| reading | 10 | sí | receptive | 15 | 18 | 0 | reading.py (AUSENTE) | reading |
| writing | 15 | sí | written | 67 | 0 | 0 | writing.py | writing |
| interaction | 0 | sí | NO | 0 | 0 | 66 | interaction.py | conversation |
| mediation | 0 | sí | NO | 0 | 0 | 0 | — (AUSENTE) | — (AUSENTE) |

## Huecos medidos

| Modalidad | Hueco |
|---|---|
| reading | sin scorer propio |
| interaction | sin canal de evidencia |
| mediation | sin competencias ni corpus |
| mediation | sin canal de evidencia |
| mediation | sin scorer propio |
| mediation | sin feature de UI |

## Audio y objetivos de corpus

- Manifest de audio humano `1.2.0`: **0** entradas grabadas.
- Ítems de aprendizaje validados: **539**.

| Nivel | Corpus declarado | Objetivo | % del objetivo |
|---|---|---|---|
| A1 | 200 | 200 | 100.0% |
| A2 | 200 | 200 | 100.0% |
| B1 | 25 | 180 | 13.9% |
| B2 | 25 | 160 | 15.6% |
| C1 | 20 | 120 | 16.7% |
| C2 | 20 | 100 | 20.0% |

- Escenarios speaking por `cefr_target`: A1:1, A2:6, B1:7, B2:5, C1:1, C2:6