# Métricas del corpus de listening por nivel

> Generado por `python -m scripts.audit_dossier corpus-stats`. 
> Banda de velocidad de referencia: `docs/audit/CEFR-REFERENCE.md`.

| Nivel | N | wpm media (min–max) | dificultad (min–max) |
| palabras/script (min–max) | connected | acentos | skills (top 3) |
|---|---|---|---|---|---|---|---|
| A1 | 200 | 117.22 (115.0–125.0) | 1.21 (1–2) | 8.56 (5–14) | 0 | 11 | detail 54, vocabulary 40, gist 28 |
| A2 | 200 | 130.85 (130.0–135.0) | 2.23 (2–3) | 10.12 (5–15) | 0 | 11 | detail 50, vocabulary 39, gist 29 |
| B1 | 25 | 143.4 (130.0–175.0) | 2.92 (2–3) | 13.6 (9–16) | 4 | 8 | inference 3, speaker_intention 3, detail 3 |
| B2 | 25 | 162.4 (150.0–185.0) | 4.04 (3–5) | 14.84 (8–23) | 11 | 8 | inference 5, fast_speech 3, multiple_speakers 3 |
| C1 | 20 | 156.15 (150.0–170.0) | 4.0 (4–4) | 25.6 (17–39) | 14 | 10 | inference 3, attitude 3, speaker_intention 2 |
| C2 | 20 | 164.35 (159.0–175.0) | 4.35 (4–5) | 24.3 (16–30) | 20 | 10 | inference 3, multiple_speakers 3, speaker_intention 2 |

Fuente: `services.listening.QUESTION_BANK` (solo ítems `cNNN` del corpus).