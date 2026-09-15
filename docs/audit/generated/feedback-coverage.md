# Feedback y corrección (V3.70 · Eje 3)

> Generado por `python -m scripts.audit_dossier feedback-coverage`.
> Declara el CANAL de corrección por destreza: determinista, LLM o
> ninguno. Solo lectura.

| Destreza | Determinista | LLM |
|---|---|---|
| grammar | services/grammar.py (regex + confidence) | policy.CORRECTNESS_GUIDANCE via context.build_system_prompt |
| writing | services/writing.py (rubrica) | services/writing_llm.py (solo extrae evidencia) |
| speaking | services/speaking.py (rubrica) | services/speaking_llm.py (solo extrae evidencia) |
| pronunciation | services/phonetics.py + pronunciation.py | NO |
| listening | scoring por respuesta (MC) | NO |
| vocabulary | lexicon/evidence (ledger lexico) | NO |
| reading | NO | NO |
| interaction | services/interaction.py (telemetria) | NO |
| mediation | NO | NO |

## Cobertura de la política de corrección

- Reglas deterministas de grammar: **7** (umbral de confirmación 0.8, racha de dominio 3).
- Criterios de rúbrica: writing **6**, speaking **7**.
- Categorías formales de feedback: **5** (CORRECT, NATURAL, OPTIONAL, PRONUNCIATION, STYLE).
- Niveles con guía de corrección: A1, A2, B1, B2, C1, C2, Pre-A1.
- Niveles SIN guía declarada: ninguno.

- Destrezas SIN ningún canal de corrección: **mediation, reading**.
- Destrezas con canal SOLO de puntuación (sin feedback textual): **interaction, listening, pronunciation, vocabulary**.