# B — Listening CEFR Calibration (auditoría V3.0)

- **Fecha:** 2026-09-02
- **Alcance:** `backend/curriculum/listening_corpus.json` (490 ítems `c001`–`c490`; A1/A2 → 200 c/u tras la expansión V3.2.0) contra la tabla de referencia `docs/audit/CEFR-REFERENCE.md`. Banco legacy (`l1`–`l23`) fuera de alcance salvo nota.
- **Relación con freeze:** contenido + calibración (`BETA_V3.md` §4.1/§4.2). Sin features nuevas.
- **Golden:** `tests/golden/listening/level_bands.json`, `tests/golden/listening/samples.json`, `backend/tests/test_golden_listening.py`.

## Método

1. Métricas cuantitativas por nivel (`python -m scripts.audit_dossier corpus-stats` → `docs/audit/generated/listening-corpus-stats.{md,json}`).
2. Sesgo posicional de respuestas (`python -m scripts.audit_dossier mc-bias` → `docs/audit/generated/mc-position-bias.{md,json}`).
3. Muestreo cualitativo de 4 ítems por nivel (muestras del golden) revisando script, pregunta, distractores, `difficulty_vector`, `connected_speech` real y etiqueta de destreza.

## Evidencia cuantitativa (resumen)

| Nivel | N | wpm (min–max) | dificultad (min–max) | palabras (min–max) | connected | acentos |
|---|---|---|---|---|---|---|
| A1 | 200 | 115–125 | 1–2 | 5–14 | 0 | 11 |
| A2 | 200 | 130–135 | 2–3 | 5–15 | 0 | 11 |
| B1 | 25 | 130–175 | 2–3 | 9–16 | 4 | 8 |
| B2 | 25 | 150–185 | 3–5 | 8–23 | 11 | 8 |
| C1 | 20 | 150–170 | 4 (plano) | 17–39 | 14 | 10 |
| C2 | 20 | 159–175 | 4–5 | 16–30 | 20 | 10 |

Veredicto por nivel (detalle cualitativo en el golden `samples.json`):

- **A1 — Aceptable.** ítems literales claros, distractores plausibles y de la misma categoría. Velocidad TTS ~120 wpm por encima de la banda normativa (80–115): aceptada por ser síntesis clara y dificultad 1, pero debe bajar a 90–110 cuando existan grabaciones humanas.
- **A2 — Aceptable con matices.** `inference` (5 ítems) y `vocabulary` de registro B1 (p. ej. `c058` *freezing/boiling*). Las muestras de inferencia son genuinas pero de techo A2; no aumentar la cuota.
- **B1 — Bien.** Connected speech auténtico (*gonna*, *whaddaya*), sequencing, predicción. `c027`/`c079` duplican patrón (instrucciones con marcadores); patrón, no defecto.
- **B2 — Bien.** Multihablante, actitud, cortesía indirecta; registro hasta C1 suave en el techo. Es el único nivel con `fast_speech` real hacia 185 wpm.
- **C1 — Bien pero dificultad plana.** Los 20 ítems tienen `difficulty` 4: el vector no discrimina dentro del nivel. Léxico/registro y longitud excelentes. La velocidad máxima (170) queda por debajo del techo B2 (185).
- **C2 — Bien.** Pragmática genuina (ironía `c123`, advertencia velada `c131`, lenguaje indirecto `c136`), 100% connected speech, 10 acentos. `c126` es registro informal sofisticado más que C2 estructural; aceptable.

**Actualización V3.2.0 (expansión pedagógica A1/A2).** El corpus pasa de 140 a 490 ítems mediante un pipeline reproducible (`scripts/generate_listening_corpus.py`): A1/A2 alcanzan 200 ítems cada uno dentro de las bandas auditadas (velocidad 115–125 / 130–135, dificultad 1–2 / 2–3, ≤ 14 / 15 palabras, 0 connected) y con **rotación posicional uniforme de opciones** (123/122/122/123 en los 490). Los ítems nuevos se validan por invariantes (`validate_listening_bank` + guardas de banda del pipeline y de los frames); la revisión cualitativa muestral de los nuevos ítems queda anotada para la próxima auditoría.

## Hallazgos

| # | Sev. | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| B1 | **alta** | **Sesgo posicional extremo:** B1–C2 tenían el 100 % de las respuestas en la opción 0 (corpus global 90,7 %; 127/140 en índice 0). Un alumno podía aprobar por posición, no por comprensión. | `mc-bias` | Rebalancear opciones (rotación determinista por ítem) hasta ~25 % por posición. **Aplicado en V3.2.0** por el pipeline (`rebalance_option_positions`, `crc32(id) % n`): distribución final 123/122/122/123 en 490. | **resuelto** |
| B2 | media | A2 concentra `inference` (5) y vocabulario de registro B1; A1 tiene `attitude`/`speaker_intention` (5) que son deseos/actitudes literales. | muestras | No crecer estas cuotas por debajo de B2; en la próxima autoría reetiquetar a `detail`/`gist`. | abierto |
| B3 | media | C1/C2 más lentos que B2 (techo 170/175 vs 185) y C2 sin ítems ≥ 180 wpm de discurso rápido real. | corpus-stats | Añadir en C2 un bloque `fast_speech` 180–200 (autoría nueva). El ítem más rápido del nivel debe vivir donde el nivel lo exige. | abierto |
| B4 | baja | C1 con `difficulty` plana (4/4): el escalar no discrimina. | corpus-stats | Diversificar vector dentro de C1 (4–5) al editar; el `difficulty_from_vector` ya soporta la banda. | abierto |
| B5 | baja | A1 a ~120 wpm TTS vs banda 80–115. | corpus-stats | Compromiso TTS aceptado; revisar al importar audio humano (fase audio). | aceptado (con nota) |
| B6 | info | El manifest de audio humano sigue vacío: 0 grabaciones, todo `tts`. La realización de `prosody` (ironía, sarcasmo) y de `connected_speech` real depende de TTS que no las produce de forma fiable. | `services.audio_library.load_manifest()` | No bloquea la calibración del contenido escrito; queda anotado como límite conocido hasta la fase de audio. | aceptado (con nota) |

## Tests de regresión añadidos

- `test_golden_listening.py::test_level_bands_are_stable` — congela bandas por nivel (velocidad, dificultad, longitud, connected, acentos).
- `test_golden_listening.py::test_reviewed_samples_still_exist_and_match_level` — las 23 muestras revisadas no desaparecen ni cambian de nivel.
- `test_golden_listening.py::test_difficulty_derived_from_vector_is_authoritative` — no se introduce `difficulty` redundante en el corpus.
- Comando reproducible `python -m scripts.audit_dossier mc-bias` para re-medir el sesgo posicional tras cualquier edición.

## Veredicto

**Calibración escrita CEFR buena en el eje de contenido (B1–C2 destacan en connected speech, acentos y pragmática), y con el sesgo posicional corregido en V3.2.0 la banda ya es auditable** (ver hallazgo B1 → resuelto). La expansión A1/A2 a 200 ítems por nivel se entrega con los invariantes de banda y de banco verdes; la revisión cualitativa muestral de esos ítems nuevos y el resto de hallazgos abiertos (B2–B4) quedan para la siguiente iteración de auditoría. Sin audio humano real, la capa acústica (prosodia/ironía) es un proxy documentado, no un defecto del contenido escrito.

## Regenerar / Verificar

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.audit_dossier corpus-stats
.venv\Scripts\python.exe -m scripts.audit_dossier mc-bias
.venv\Scripts\python.exe -m pytest tests/test_golden_listening.py -q
```
