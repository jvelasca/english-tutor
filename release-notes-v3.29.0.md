# v3.29.0 — Listening Engine 4.0 (Fase 3, núcleo): `word_alignment_proxy` offline, karaoke palabra a palabra, controles precisos (seek + bucle A/B) y salto a la palabra fallada

**V3.29 implementa el núcleo de la Fase 3 de la especificación
`docs/LISTENING_ENGINE_4.0.md` (§14) a través del plan
`v3.29_nucleo_fase_3…plan.md` (P1–P6): alineación por palabra generada offline
(`word_alignment_proxy` con faster-whisper `word_timestamps=True`), karaoke
palabra a palabra en el transcript, controles de audio precisos (seek slider +
bucle A/B), salto a la palabra fallada en dictado/cloze (normal y slow) y
evidencia de palabra fallada (`word_breakdown_json`). El candidato diccionario
de consulta se reprioriza a **V3.30**.
Versión de app `3.28.1 → 3.29.0`.**

## Qué cambia

### P1 — Motor de alineación por palabra (backend, offline)

- `backend/services/stt.py::transcribe_words(audio_bytes, language="en")`: nueva
  transcripción con `word_timestamps=True` que devuelve `[{word, start, end}]`
  de `Segment.words` (duck-typed, testeable con dobles, sin cargar modelo en
  import).
- Nuevo módulo puro `backend/services/word_alignment_proxy.py`:
  - `sidecar_path` / `write_sidecar` / `read_sidecar` / `sidecar_words` —
    sidecar `{wav}.words.json` junto a la caché de audio, con `source_text`,
    `engine: "faster-whisper-small"`, `sync: "asr_word_proxy"` y `coverage`.
  - `align_words(asr_words, text)` — alinea el ASR contra el **texto audible**
    (`SequenceMatcher` sobre tokens normalizados con apóstrofo interno); las
    palabras que el ASR no reconoció se **interpolan de forma monótona** entre
    vecinas y la cobertura se reporta; por debajo de **`MIN_COVERAGE = 0.8`**
    la señal se descarta (`[]` → degradación controlada al sync de frase).
  - `ensure_word_alignment(wav_path, source_text)` — idempotente (`--force`
    para regenerar), nunca lanza en producción, transcriptor inyectable.
- Hooks de generación: `generate_listening_audio.py` (tras cada síntesis),
  `domain/listening.py::get_audio` (primeras síntesis bajo demanda de una voz/
  variante no pre-renderizada) e `import_audio.py` (WAV humanos con
  transcripción literal). Nuevo script `generate_word_alignments.py` para
  **backfill** de la caché existente.

### P2 — `word_timings` en el payload

- `backend/services/listening.py::word_timings_for(question, voice=PIPER_VOICE)`:
  resuelve el WAV canónico (`{cache_id}-{digest}.wav`; los ítems derivados `d-`
  reutilizan el sidecar del padre vía `derived_from`), lee el sidecar y asigna a
  cada palabra su frase **por tiempo** comparando `start` con los intervalos de
  `coarse_sentence_timings` (sin mapear tokens canónicos → audibles; funciona
  con `repetition_policy="twice"` y sin `duration`/frases, donde `sentence`
  queda a `-1` y la UI degrada a una línea continua).
- `ListeningQuestion.word_timings: list[dict] = []` — campo opcional junto a
  `sentence_timings`, con comentario de señal proxy.
- `_public_with_flow` y la rama adaptativa de `next_question` lo exponen solo
  cuando `audio_type == "tts"` y `audio_ready`; `mastered` compacto no (igual
  que hoy).

### P3 — Evidencia de palabra fallada

- Migración idempotente inline en `repositories/db.py`: `ALTER TABLE
  listening_attempts ADD COLUMN word_breakdown_json TEXT` (aditiva, nullable;
  los intentos legacy conservan `NULL`).
- `record_attempt(..., word_breakdown: dict | None = None)` serializa con
  `json.dumps`; `list_attempts` incluye la columna en el SELECT.
- `submit_production` persiste `word_breakdown=result["breakdown"]` (dictado
  fallado: missing/substituted → palabras que el alumno no oyó bien);
  `submit_answer` persiste `{"target": question.options[answer_index]}` (la
  palabra diana) en un acierto incorrecto de cloze/segmentation y `None` en el
  resto. Sin consumo en agregados todavía (V3.30).

### P4 — Karaoke palabra a palabra (frontend)

- `ListeningWordTiming { index, text, start, end, sentence }` +
  `word_timings?: ListeningWordTiming[]` en `ListeningQuestion` (`types/api.ts`).
- Helpers puros en `microFlow.ts`: `wordTimingsOf`, `activeWordIndex` (regla
  monótona análoga a `activeSentenceIndex`), `wordsForSentence`,
  `scaleWordTimings(timings, factor)` y `variantTimeScale(question, variant)`
  (ratio `speech_rate` normal/variante para slow/fast).
- Nuevo `KaraokeTranscript.tsx` (patrón de `CoarseTranscript`): Card con
  `lang="en"`, palabras como chips flex-wrap; pinta solo las palabras de las
  frases reveladas por `revealSentenceIndexes`; resalta la palabra activa
  (`bg-primary/15`) según `currentTime`; cada palabra es clickeable →
  `onSeekToWord(word.start)` (seek del AudioController). Con `wordTimings`
  vacío devuelve `null` (se sigue usando `CoarseTranscript`).
- `ListeningPractice.tsx`: `transcriptVisible` cubre flujo receptivo
  (hidden/partial/full) **y** la revelación completa tras un resultado de
  producción (dictado/shadowing); renderiza karaoke cuando hay `wordTimings` y
  `CoarseTranscript` en caso contrario.

### P5 — Controles de audio precisos (seek + loop)

- `AudioController`: la duración se notifica también en **`loadedmetadata`**
  (nuevo callback `onDuration`; el hook `useAudioController` expone `duration`
  sin esperar al primer `timeupdate`). El bucle de segmento pasa a un scheduler
  **`requestAnimationFrame` inyectable** (`AudioFrameScheduler`: `frame`/
  `cancelFrame`) que rebobina en cuanto `currentTime >= segment.end`; el chequeo
  en `timeupdate` queda como respaldo sin rAF. `loop`/`markSegmentStart`/
  `clearLoop`/`play`/`pause`/`dispose` arrancan/paran el scheduler.
- `ListeningPractice.tsx`: en la tarjeta de audio (solo `audio_ready` y
  duración real > 0) un **seek slider** (`<input type="range">` min 0 / max
  duración / step 0.05, `onChange → audioController.seek(t)`) y el control de
  **bucle A/B**: «marcar inicio» (fija A en `currentTime`), «bucle A–B»
  (`loop(A, currentTime)`), «quitar bucle» (`clearLoop`). El estado se resetea
  al cargar una nueva pregunta.

### P6 — Salto a la palabra fallada

- `microFlow.ts`: `wordTokensOf`, `firstFailedWord(breakdown)` (dictado:
  primer token de `missing` o `expected` del primer `substituted`) y
  `failedWordTiming(target, wordTimings, sentenceTimings)`: busca el target como
  secuencia contigua de tokens normalizados en los timings; si no aparece
  (p. ej. reducción/expansión `going to` → `gonna`) cae al intervalo de la
  frase de `sentenceTimings` que lo contiene; `null` sin respaldo.
- `ListeningPractice.tsx`: botones **«repetir palabra fallada»** en `normal` y
  `slow` — visibles solo cuando la ref resuelve (`audio_ready` + `wordTimings`)
  — en el resultado de un **dictado fallado** y en la tarjeta de reintento de un
  **MCQ cloze incorrecto**. Acción: `seek(start − 0.05s)` + `loop(start, end)` +
  `play(url(variante))`, con los timings escalados a la variante reproducida.

## Verificación

- Backend: `pytest backend/tests` + `pytest launcher/tests` + `ruff check .`
  limpios (conteos finales en el cierre P8).
- Frontend: `vitest run` + `tsc --noEmit` limpios.
- `python scripts/check_release_consistency.py` → **3.29.0** exit 0.
