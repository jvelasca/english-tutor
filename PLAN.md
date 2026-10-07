# Plan de proyecto — English Tutor (100% local)

> Mantenido por el gerente del proyecto (yo). Los subagentes se ejecutan desde
> agentes locales: cada tarea se describe en `agentes/<nombre>.md`.
>
> **Premisas y reglas:** `docs/PREMISAS.md` · **Arquitectura:** `docs/ARQUITECTURA.md` ·
> **Guía de desarrollo:** `docs/DESARROLLO.md`.

## Estado actual

- **V3.95.0 — El diccionario deja de mentir: guardarraíl de retrotraducción, glosario curado, corrección manual del webmaster y léxico externo (2026-10-07)** (**Versión estable `3.95.0`**, app `3.94.10 → 3.95.0`). **Release de PRODUCTO (minor) CON backend y CON frontend**, **CON migración aditiva** (tablas `dictionary_curated` y `dictionary_lexicon`) y **CON endpoints nuevos** de administración del diccionario. **`GENERATOR_VERSION` sube `1.7.0 → 1.8.0`** (la caché anterior se regenera bajo el guardarraíl); `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**; **no se añade ni se retira gate** (siguen los **8**, todos `pending`) y `validation-evidence.json` sigue sin existir. **(A) Guardarraíl.** Un equivalente ES→EN no retrotraducible se descarta en vez de cachearse: «broca» ya no puede guardar «rock». Si no hay contenido verificable, degrada a `definition_source="none"`. **(B) Autoridades.** Corrección manual del webmaster → glosario curado (`es_en_glossary.json`) → packs → inversa instantánea → léxico externo → generación con guardarraíl. **(C) Herramientas.** `dictionary_validate_cache.py` (purga solo la inversa; la directa es asesora), lote/warmup `--direction es-en` e `import_freedict.py` con `--accept-license`. **Verificación local:** `pytest` del diccionario **157/157** · `vitest` **211/211** · `tsc` limpio · `npm run build` correcto · `i18n --strict` verde · `check_release_consistency` OK (`3.95.0`). **Operador:** purga aplicada (6 filas borradas); `broca → drill bit`, `sierra → circular saw`, `serrucho → handsaw`. **Honestidad.** (i) El frontend **sigue sin pintar** `new_sense_exposure`. (ii) FSRS sigue **sin cartas por acepción**. (iii) Los **8 gates humanos siguen `pending`**. (iv) El tag espera a la CI. (v) La dirección EN→ES del validador es asesora: marca sinónimos legítimos. Detalle en `docs/releases/release-notes-v3.95.0.md`.
- **V3.94.10 — Estudiar en los dos sentidos, los temas son mazos y Mazos se elige en una rejilla (2026-10-05)** (**Versión estable `3.94.10`**, app `3.94.9 → 3.94.10`). **Release de PRODUCTO (patch) CON backend y CON frontend**, **CON migración aditiva** (`flashcard_decks.source_collection_id`) y **SIN cambio de contrato** en el complete. `PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**; **no se añade ni se retira gate** (siguen los **8**, todos `pending`) y `validation-evidence.json` sigue sin existir. **No abre V3.95.** **(A) Sentido.** Español → Inglés escribe y silabea el lema inglés. El español se oye en la voz de España. **(B) Donuts.** A repasar, No aprendidas, Difíciles, Bien y Todas. Fácil sigue siendo la nota. **(C) Mazos.** Dieciocho temas de cien palabras, cada uno un mazo que no se borra. Rejilla con icono en Mazos y en Tarjetas. Estadísticas sigue siendo el diccionario entero. Los tres P2 de V3.94.6 siguen aparcados. **Honestidad.** (i) El ledger de Listening sigue vacío. (ii) El frontend **sigue sin pintar** `new_sense_exposure`. (iii) FSRS sigue **sin cartas por acepción**. (iv) Los **8 gates humanos siguen `pending`**. (v) El tag espera a la CI. (vi) El catálogo crece sin subir `CURRICULUM_VERSION`. Detalle en `docs/releases/release-notes-v3.94.10.md`.

- **V3.94.9 — Atrás, adelante, quiz del diccionario, editor de esa ficha y pista (2026-10-04)** (**Versión estable `3.94.9`**, app `3.94.8 → 3.94.9`). **Release de PRODUCTO (patch) CON backend y CON frontend**, **SIN migración de BD** y **SIN cambio de contrato**. El complete sigue siendo el `item_id` de la cola. Hay dos endpoints nuevos (`/api/vocabulary/study/quiz` y `/hint`) que no cierran la lección. `PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**; **no se añade ni se retira gate** (siguen los **8**, todos `pending`) y `validation-evidence.json` sigue sin existir. **No abre V3.95.** **(A) Flechas** junto al título, apagadas en los extremos. **(B) ¿Cuál es?** Distractores del diccionario, parecidos en sílabas, fuera de la sesión. **(C) El lápiz** abre el editor de esa ficha. **(D) Pista** muestra el recordatorio o lo genera y lo guarda. Los tres P2 de V3.94.6 siguen aparcados. **Honestidad.** (i) El ledger de Listening sigue vacío. (ii) El frontend **sigue sin pintar** `new_sense_exposure`. (iii) FSRS sigue **sin cartas por acepción**. (iv) Los **8 gates humanos siguen `pending`**. (v) El tag espera a la CI.

- **V3.94.8 — La tarjeta de Estudiar lleva iconos, la frase en el anverso, el lápiz de la ficha y anota el fallo de «¿Cuál es?» (2026-10-03)** (**Versión estable `3.94.8`**, app `3.94.7 → 3.94.8`). **Release de PRODUCTO (patch) CON frontend**, **SIN migración de BD** y **SIN cambio de contrato**. El complete sigue siendo el `item_id` de la cola. `PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**; **no se añade ni se retira gate** (siguen los **8**, todos `pending`) y `validation-evidence.json` sigue sin existir. **No abre V3.95.** **(A) La tarjeta.** Icono y nombre en cada acción. Frase abre el ejemplo sin revelar. El lápiz abre el editor de la ficha manual, o guarda la traducción del léxico. **(B) El fallo.** La primera opción incorrecta queda en rojo y guarda Otra vez una sola vez. Escribir mal no cierra. **(C) Fuera.** Los tres P2 de V3.94.6 siguen aparcados. **Honestidad.** (i) El ledger de Listening sigue vacío. (ii) El frontend **sigue sin pintar** `new_sense_exposure`. (iii) FSRS sigue **sin cartas por acepción**. (iv) Los **8 gates humanos siguen `pending`**. (v) El tag espera a la CI. Detalle en `docs/releases/release-notes-v3.94.8.md`.

- **V3.94.7 — Estudiar guarda la nota, y la tarjeta deja escribir, revelar una sílaba y conservar varias frases (2026-10-03)** (**Versión estable `3.94.7`**, app `3.94.6 → 3.94.7`). **Release de PRODUCTO (patch) CON frontend**, **SIN migración de BD** y **SIN cambio de contrato**. El complete sigue siendo el `item_id` de la cola. `PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**; **no se añade ni se retira gate** (siguen los **8**, todos `pending`) y `validation-evidence.json` sigue sin existir. **No abre V3.95.** **(A) La nota.** La interfaz compilada enviaba el cierre antiguo, sin `item_id`, y Bien no guardaba. **(B) La tarjeta.** Escribir revela si acierta. La sílaba es un grupo vocálico. Otra frase se suma, hasta cuatro. **(C) Fuera.** Los tres P2 de V3.94.6 y colección con nivel siguen aparcados. **Honestidad.** (i) El ledger de Listening sigue vacío. (ii) El frontend **sigue sin pintar** `new_sense_exposure`. (iii) FSRS sigue **sin cartas por acepción**. (iv) Los **8 gates humanos siguen `pending`**. (v) El tag espera a la CI. Detalle en `docs/releases/release-notes-v3.94.7.md`.

- **V3.94.6 — Estudiar muestra la palabra y el significado se revela (2026-10-03)** (**Versión estable `3.94.6`**, app `3.94.5 → 3.94.6`). **Release de PRODUCTO (patch) CON backend y CON frontend**, **SIN migración de BD** y **CON un endpoint nuevo** (`POST /api/vocabulary/study/example`). El complete no cambia. `PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**; **no se añade ni se retira gate** (siguen los **8**, todos `pending`) y `validation-evidence.json` sigue sin existir. **No abre V3.95.** **(A) Una tarjeta.** Se lee la palabra. Oír, una pista, el recordatorio y seis opciones no agendan. La nota sigue siendo Otra vez / Difícil / Bien / Fácil. **(B) Otra frase.** El modelo local escribe una frase nueva; si falla, se conserva la anterior y no hay escrituras de estudio. **(C) Fuera.** Colección y nivel juntos siguen sin pintarse. **Honestidad.** (i) El ledger de Listening sigue vacío. (ii) El frontend **sigue sin pintar** `new_sense_exposure`. (iii) FSRS sigue **sin cartas por acepción**. (iv) Los **8 gates humanos siguen `pending`**. (v) El tag espera a la CI. Detalle en `docs/releases/release-notes-v3.94.6.md`.

- **V3.94.5 — Estudiar cierra cada ítem servido una sola vez, y esa nota mueve una sola carta FSRS (2026-10-03)** (**Versión estable `3.94.5`**, app `3.94.4 → 3.94.5`). **Release de PRODUCTO (patch) CON backend y CON frontend**, **CON migración aditiva** (`study_lesson_items`) y **CON cambio de contrato** en `POST /api/vocabulary/study/complete` (el cuerpo lleva `item_id`). `PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**; **no se añade ni se retira gate** (siguen los **8**, todos `pending`) y `validation-evidence.json` sigue sin existir. **No abre V3.95.** **`v3.94.4` no se etiqueta como cierre.** **(A) Una transición.** La cola emite el id; el complete lo resuelve y, si se repite, no vuelve a agendar. Una ficha manual califica su carta y deja el léxico sin nota. El alta, las facetas, el FSRS y el libro van en una transacción. **(B) Aprendida es derivado.** Depende de `required_facets` actual. `state == review` no es mastery. Los pasos los afirma el cliente. **(C) Fuera.** Colección y nivel juntos siguen sin pintarse. **Verificación local:** `pytest` del banco y del cierre **15/15** · `vitest` de Estudiar **30/30**. **Honestidad.** (i) El ledger de Listening sigue vacío. (ii) El frontend **sigue sin pintar** `new_sense_exposure`. (iii) FSRS sigue **sin cartas por acepción**. (iv) Los **8 gates humanos siguen `pending`**. (v) El tag espera a la CI. Detalle en `docs/releases/release-notes-v3.94.5.md`.

- **V3.94.4 — Estudiar usa el banco del ámbito (pendientes, falladas o todas) y Flashcards deja de resembrar el léxico por mazo (2026-10-03)** (**Versión estable `3.94.4`**, app `3.94.3 → 3.94.4`). **Release de PRODUCTO (patch) CON backend y CON frontend**, **CON migración aditiva** y **CON endpoints nuevos** de la cola de Estudiar. `PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**; **no se añade ni se retira gate** (siguen los **8**, todos `pending`) y `validation-evidence.json` sigue sin existir. **No abre V3.95.** **(A) Ámbito.** Un mazo manual no hereda el repaso global. **(B) Modos.** Pendientes, Falladas (última nota Otra vez) y Todas de nuevo, con un solo inicio. **(C) Carga.** Una sincronización por listado de mazos y traducciones en lote. **Verificación local:** `pytest` del banco **8/8** · `vitest` de Estudiar **30/30** · `npm run build` correcto. **Honestidad.** (i) El ledger de Listening sigue vacío. (ii) El frontend **sigue sin pintar** `new_sense_exposure`. (iii) FSRS sigue **sin cartas por acepción**. (iv) Los **8 gates humanos siguen `pending`**. (v) El tag espera a la CI. Detalle en `docs/releases/release-notes-v3.94.4.md`.

- **V3.94.3 — Formación enseña la ruta de Listening de Aprender, y un acierto ya no pide un segundo toque para seguir (2026-10-01)** (**Versión estable `3.94.3`**, app `3.94.2 → 3.94.3`). **Release de PRODUCTO (patch) CON backend y CON frontend**, **SIN migración de BD**, **SIN endpoints nuevos** y **SIN cambio de contrato incompatible** (`listening_route` es aditivo en el mapa del curso). `PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**; **no se añade ni se retira gate** (siguen los **8**, todos `pending`) y `validation-evidence.json` sigue sin existir. **No abre V3.95.** **(A) Dos puertas.** La sección de Listening de Formación lee `route_gate` del mismo nivel. Mostrarlo no mueve el dominio del curso, no abre el nivel siguiente y no certifica. **(B) Repaso.** El contador se refresca también al acertar; el botón solo aparece si quedan frases falladas; «Repasar después» reentra al vencer. **(C) Siguiente.** Un acierto salta el shadowing opcional. En móvil el botón va antes que la transcripción. **Verificación local:** `pytest` focalizado **44/44** · `tsc --noEmit` limpio · `vitest` del micro-flujo **42/42**. **Honestidad.** (i) El ledger de producción sigue vacío: la sonda no escribe en `tutor.db`. (ii) El frontend **sigue sin pintar** `new_sense_exposure`. (iii) FSRS sigue **sin cartas por acepción**. (iv) Los **8 gates humanos siguen `pending`**. Detalle en `docs/releases/release-notes-v3.94.3.md`.

- **V3.94.2 — Un conflicto de ocurrencias no se colapsa en un único `mismatch`, y un corpus de polisemia fija la heurística en CI (2026-10-01)** (**Versión estable `3.94.2`**, app `3.94.1 → 3.94.2`). **Release de PRODUCTO (patch) CON backend y CON frontend** (Ayuda: los textos largos y el correo parten línea; el barrido responsive incluye Formación), **SIN migración de BD**, **SIN endpoints nuevos** y **SIN cambio de contrato incompatible** (`sense_match` conserva sus tres valores; razón nueva `occurrence:split`). `PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**; **no se añade ni se retira gate** (siguen los **8**, todos `pending`) y `validation-evidence.json` sigue sin existir. **(A) Ocurrencias en conflicto.** Un `mismatch` probado junto a otro veredicto de la misma palabra agrega a `ambiguous` / `occurrence:split`. No es exposición. La carta débil sube; la fuerte deja fila sin tocar FSRS, y esa fila no entra en `difficulty_evidence` ni en `sense_exposures`. **(B) Corpus.** 95 frases y 15 familias; CI fija `resolver_expected` y cuenta cuatro discrepancias con el `gold` humano (`bank-07`, `bank-08`, `bank-10`, `run-07`). **(C) Responsive.** Ayuda con `break-words` / `break-all`; Formación entra en `responsiveOverflow`. **Verificación local:** `pytest` **3496/3496** · Playwright overflow **4 passed · 2 skipped**. **Honestidad.** (i) El 2 sigue siendo solape, no confianza semántica. (ii) El corpus no sustituye volumen real del ledger. (iii) El frontend **sigue sin pintar** `new_sense_exposure`. (iv) FSRS sigue **sin cartas por acepción**. (v) Los **8 gates humanos siguen `pending`**. Detalle en `release-notes-v3.94.2.md`.

- **V3.94.1 — El sentido se resuelve SIEMPRE (también en cartas fuertes) y el `mismatch` solo se declara con PRUEBA: una acepción nueva en una palabra dominada deja de ser invisible y un único token ya no suprime evidencia (2026-10-01)** (**Versión estable `3.94.1`**, app `3.94.0 → 3.94.1`). **Release de PRODUCTO (patch) CON backend y SIN frontend**, **SIN migración de BD**, **SIN endpoints nuevos** y **SIN cambio de contrato incompatible** (`sense_match` conserva `matched`/`mismatch`/`ambiguous`; el veredicto añade `mismatch_strength` interno y la razón `gloss:other:weak`; `new_sense_exposure: {words, count}` conserva su forma). `GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**; **no se añade ni se retira gate** (siguen los **8**, todos `pending`) y `validation-evidence.json` sigue sin existir. **(A) Resolver antes de filtrar por debilidad (P1).** `_apply_difficulty_evidence` iteraba `select_targets()`, que descartaba las cartas fuertes ANTES de resolver: `palabra fuerte + acepción nueva` daba FSRS intacto Y `new_sense_exposure = 0`. Ahora se resuelve el sentido para TODAS las palabras y se separa «resolver» de «escribir»: un `mismatch` probado en carta fuerte registra la exposición sin tocarla, y una carta fuerte en su propia acepción conserva su dominio. **(B) `mismatch` exige PRUEBA.** La regla pasa de simétrica a ASIMÉTRICA (un `mismatch` SUPRIME evidencia; un `matched` solo tolera duda): `best_other_overlap >= PROVEN_OTHER_OVERLAP` (2) o desempate gramatical fuerte; un solo token cae a `ambiguous` (`gloss:other:weak`, `mismatch_strength="possible"`) y CONSERVA la evidencia. **(C) tsconfig.** Se retira `baseUrl` de `frontend/tsconfig.json`. **Verificación:** `ruff` limpio (backend) · `pytest` backend **3486/3486** · `vitest` **1108/1108** · `tsc --noEmit` limpio · `npm run build` correcto · `check_release_consistency` OK en los **6 orígenes** (`3.94.1`). **Honestidad.** (i) El caso de un solo token (`«...of the river»`) pasa de `mismatch` a `ambiguous`: conserva evidencia y queda medible como `possible_mismatch`. (ii) El frontend **sigue sin pintar** `new_sense_exposure`. (iii) FSRS sigue **sin cartas por acepción** y el ledger **sin poda**. (iv) Los **8 gates humanos siguen `pending`**. Detalle en `release-notes-v3.94.1.md`.

- **V3.94.0 — ENFORCE: la evidencia de Listening deja de ser lemma-based y DECIDE con la acepción; un `mismatch` probado ya no penaliza la acepción aprendida y se registra como exposición a un sentido nuevo (2026-09-30)** (**Versión estable `3.94.0`**, app `3.93.2 → 3.94.0`). **Release de PRODUCTO (minor) CON backend y SIN frontend** (la conducta cambia solo donde el resolver PRUEBA una acepción distinta), **SIN migración de BD** (el ledger de V3.93 ya tenía `sense_key`/`sense_match`/`sense_reason`), **SIN endpoints nuevos** y **SIN cambio de contrato incompatible** (`new_sense_exposure: {words, count}` es **aditivo** en `POST /api/listening/answer`; `difficulty_evidence` conserva su forma). `GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**; **no se añade ni se retira gate** (siguen los **8**, todos `pending`) y `validation-evidence.json` sigue sin existir. **(A) `mismatch` pasa a ser ALCANZABLE.** `services/listening_bridge.py::alternatives_index` reúne las acepciones de la caché del diccionario (`dictionary_repo.find_by_words`) y el puente las pasa al resolver: sin alternativas conocidas `mismatch` no podía dispararse (V3.93 llamaba con `senses=()`) y aplicar la política habría sido un no-op. **(B) Política MÍNIMA y declarada.** `services/sense_context.py::allows_difficulty_evidence` **suprime SOLO ante un `mismatch` PROBADO**; `matched`, `ambiguous` y la ausencia de veredicto **conservan** la evidencia de V3.92 —la duda no RESTA evidencia igual que no la FABRICA—. La decisión sobre `declared:none` es explícita: ausencia de declaración **no es** contradicción, y suprimirla «apagaría la mayor parte del puente». Con el ledger **vacío (0 filas)** no había datos: es **DECISIÓN declarada, no medición**, y **reversible**. **(C) La exposición se registra, no se castiga.** El `mismatch` deja su fila con `difficulty_before == difficulty_after` (idempotente por la clave del intento), la respuesta publica `new_sense_exposure` y `services/daily_plan.py::day_metrics` publica `sense_exposures` **aparte** (no lo cuenta como dificultad). **Verificación:** `ruff` limpio (backend) · `pytest` backend **3471/3471** · `scripts/sense_shadow_report.py` proyecta con la MISMA política que decide en producción · `check_release_consistency` OK en los **6 orígenes** (`3.94.0`). **Honestidad.** (i) Ledger vacío ⇒ proyección vacía: la política se revisará cuando haya volumen. (ii) El frontend **no pinta todavía** `new_sense_exposure` (campo aditivo sin consumidor). (iii) FSRS sigue **sin cartas por acepción** y el ledger **sin poda**. (iv) Los **8 gates humanos siguen `pending`**. Detalle en `release-notes-v3.94.0.md`.

- Estado de las versiones anteriores (V3.93.2 hacia atrás): [`docs/archive/PLAN-historico.md`](docs/archive/PLAN-historico.md).

## Hitos (roadmap)

### M0 — Esqueleto modular  [HECHO ✔]
- Refactor sin cambios de comportamiento: separar backend (`routers/`, `services/`, `schemas/`)
  y frontend (`api/`, `components/`, `hooks/`, `types/`) según `docs/ARQUITECTURA.md`.
- Verificado: backend arranca y responde, frontend compila (`tsc`), chat funciona de punta a punta.
- Subagente (ejecutado por el gerente): `agentes/m0-esqueleto-modular.md`.

### M1 — Streaming de respuestas  [HECHO ✔]
- El texto aparece mientras se genera (SSE/streaming), en vez de esperar la respuesta completa.
- Backend: `POST /api/chat/stream` (SSE). Frontend: `streamChat` consume e incrementa la burbuja.
- Verificado: múltiples `data: {"content":...}` + `data: {"done":true}`; `tsc` sin errores.
- Subagentes (ejecutados por el gerente): `agentes/m1-backend-streaming.md`, `agentes/m1-frontend-streaming.md`.

### M2 — Voz 100% local  [HECHO ✔]
- **Oído (STT):** voz → texto con **Whisper** (`faster-whisper`, `small`, CPU). ✔
- **Boca (TTS):** texto → voz con **Piper** (`en_US-lessac-medium`, CPU). ✔
- Backend: `POST /api/transcribe` y `POST /api/tts` (modelos en `backend/models/`).
- Frontend: botón micrófono (grabar → transcribir) y altavoz (escuchar respuesta).
- Verificado: TTS genera WAV válido; Whisper transcribe el audio generado correctamente.
- Subagentes (ejecutados por el gerente): `agentes/m2-backend-voz.md`, `agentes/m2-frontend-voz.md`.

### M3 — Memoria e historial  [HECHO ✔]
- Guardar conversaciones, poder retomarlas, contexto persistente.
- Backend: `services/store.py` (SQLite) + CRUD `/api/conversations`.
- Frontend: sidebar con lista de conversaciones, nuevo chat, cargar y eliminar.
- Verificado: crear → guardar → leer → listar → borrar funciona.
- Subagente (ejecutado por el gerente): sin briefing previo; implementación directa del gerente.

### M4 — Modo profesor de inglés  [HECHO ✔]
- **Modos de tutor**: `conversation`, `grammar`, `exercises`, `pronunciation` (system prompts por modo).
- **Corrección de pronunciación**: `POST /api/pronunciation` (audio + texto esperado → score).
- Frontend: selector de modo + tarjeta de práctica de pronunciación (grabar → evaluar).
- Verificado: backend 13 tests, frontend 10 tests, `tsc` sin errores.
- Subagentes (ejecutados por el gerente): `agentes/m4-backend-modo.md`, `agentes/m4-frontend-modo.md`.

### M5 — Modelo conversacional  [HECHO ✔]
- Evaluar cambiar a un modelo no-coder (ej. `llama3.1:8b` o `mistral`) para mejor calidad de tutor.
- Criterio: calidad como profesor (correcciones, explicaciones, tono) + tamaño/VRAM (RTX 4060 Ti 4 GB).
- Entregable: script de evaluación repetible + decisión documentada del modelo por defecto.
- Subagente (ejecutado por el gerente): `agentes/m5-modelo-conversacional.md`.
- **Decisión:** se mantiene **`qwen3.5:9b`** como `DEFAULT_MODEL`. Tras evaluar ambos con
  `scripts/eval_model.py` (4 prompts de tutor), `qwen3.5:9b` gana en calidad como tutor:
  correcciones más estructuradas, ejercicios con contexto y una guía de pronunciación IPA
  mucho más detallada y **correcta**. `llama3.1:8b` es ~6x más rápido (21s vs 125s) pero
  comete un error de pronunciación (confunde la fricativa sorda /θ/ de *through* con la
  sonora /ð/ de *this/that*), así que **no es claramente mejor**. `llama3.1:8b` queda
  instalado como alternativa selectable en el frontend.
- **Descarga desbloqueada:** con VPN iba lenta (~400-900 KB/s) y se atascaba cada ~30 min.
  Al **quitar la VPN** la descarga terminó en ~1 min a 52 MB/s y sin error de certificado
  (el MITM del ISP ya no afectaba a esa conexión). `ollama pull llama3.1:8b` completado.
- **Fix:** `scripts/eval_model.py` ahora fuerza UTF-8 en stdout/stderr (Windows usaba cp1252
  y fallaba al imprimir emojis/símbolos fonéticos).

### M6 — Release a GitHub  [HECHO ✔]
- Repositorio **público**: https://github.com/jvelasca/english-tutor
- V1.0 (tag `v1.0.0`) subida con release e issues de seguimiento.

### M7 — Multi-usuario  [HECHO ✔]
- Perfiles locales con **seguimiento independiente** (conversaciones, progreso, puntuaciones, ajustes).
- Selección simple de perfil al abrir; aislamiento total de datos entre usuarios (premisa 13).
- Backend: tabla `users`, columna `user_id` en `conversations` (migración idempotente no
  destructiva con usuario por defecto `Usuario`), `GET/POST /api/users` y CRUD de
  conversaciones filtrado por `user_id` (query param).
- Frontend: selector de perfil (`UserSelect`) en la cabecera, creación de usuarios, y
  aislamiento al cambiar de perfil (resetea conversación y recarga la lista del nuevo usuario).
- Verificado: backend 20 tests, frontend 14 tests, `tsc` sin errores.
- Subagentes (ejecutados por el gerente): `agentes/m7-backend-multiusuario.md`, `agentes/m7-frontend-multiusuario.md`.

### M8 — Diseño y UX nivel top  [HECHO ✔]
- Rediseño al nivel de apps líderes (ChatGPT/Duolingo): sistema de tokens, tema claro/oscuro,
  responsive, micro-interacciones y estados vacíos/carga/error (premisa 14).
- Sistema de **tokens** en `index.css` (`--color-*`, `--font-*`, `--text-*`, `--space-*`,
  `--radius-*`, `--shadow-*`, motion). Tema **claro/oscuro** (`data-theme`, hook `useTheme`,
  toggle accesible, persistencia en `localStorage`, anti-FOUC en `index.html`).
- **Responsive** (≤768px): sidebar drawer + hamburguesa. **a11y**: `:focus-visible`,
  `aria-*`, `prefers-reduced-motion`.
- Verificado: frontend 19 tests (5 nuevos de tema), `tsc` sin errores, `npm run build` OK.
- Subagente (ejecutado por el gerente): `agentes/m8-diseno-ux.md`.

### M9 — Seguimiento de progreso del alumno  [HECHO ✔]
- Registrar el progreso por usuario: nº de ejercicios, correcciones y puntuaciones de
  pronunciación; mostrar un resumen en el frontend (issue #2, pendiente diferido de M4).
- Backend: tabla `pronunciation_attempts` + columna `mode` en `messages` (migración
  idempotente), `GET /api/progress?user_id=<id>` y `POST /api/pronunciation` con `user_id`
  opcional. Frontend: panel `ProgressSummary` + api `progress.ts`.
- Verificado: backend 27 tests, frontend 26 tests, `tsc` sin errores, `npm run build` OK.
- Subagentes (ejecutados por el gerente): `agentes/m9-backend-progreso.md`, `agentes/m9-frontend-progreso.md`.

### M10 — Conversación por voz continua (manos libres)  [HECHO ✔]
- Modo continuo: VAD (detección de silencio vía Web Audio API), transcripción automática y
  respuesta hablada sin pulsar botones (issue #3). Sin cambios de backend
  (transcribe/tts/stream ya existían).
- Frontend: refactor `useChat.sendText(text): Promise<string>`, `utils/vad.ts` (RMS +
  `shouldEndUtterance`), `hooks/useHandsFree.ts` (bucle de estados + VAD por energía),
  `components/HandsFreeToggle.tsx` (toggle + indicador de estado accesible).
- Verificado: frontend 37 tests, `tsc` sin errores, `npm run build` OK.
- Subagente (ejecutado por el gerente): `agentes/m10-voz-continua.md`.

### M11 — Lanzador de escritorio + release estable  [HECHO ✔]
- Lanzador de escritorio (`launcher/`, GUI `tkinter` sin dependencias nuevas) que arranca/detiene
  la app (backend + frontend) y muestra el estado de servicios, base de datos y usuarios.
- Acceso directo del escritorio con icono (`launcher/install_shortcut.ps1` + `make_icon.ps1`).
- Versión unificada `1.1.0` (backend `config.py::VERSION` expuesta en `/api/health` y `/`, y
  frontend `package.json`).
- Verificado: launcher 22 tests + ruff limpio; backend 217 tests, frontend 88 tests, build OK.
- Subagentes (ejecutados por el gerente): `agentes/endurecimiento/a1-launcher-core.md`,
  `agentes/endurecimiento/a2-launcher-gui.md`.

### M12 — Release Audit 1.1 + versión 1.1.1  [HECHO ✔]
- Cierre de los 6 puntos señalados por la auditoría externa antes de congelar la arquitectura.
  1. Unificar `current_user` en todos los endpoints sensibles.
  2. Fluidez ya expuesta como `FluencyStats` en `PronunciationResponse` (verificado, sin cambios).
  3. Renombrar "CEFR estimate" → `estimated_level/bands/descriptor`.
  4. Corregir semántica de vocabulario: `occurrences` → `appearances` (+ migración idempotente).
  5. Añadir `confidence`/`source`/`confirmed` a gramática y filtrar el prompt a errores confirmados.
  6. Tests de aislamiento cross-user + tests del Learning Context/Prompt.
- Selector de perfil: no auto-seleccionar el primer usuario si hay varios.
- Versión unificada `1.1.1`.
- Verificado: backend 231 tests, frontend 92 tests, launcher 22 tests, ruff limpio, build OK.
- Subagentes (ejecutados por el gerente): `agentes/endurecimiento/ra-*.md` (RA1–RA7).

### M13 — Etapa 2: Pedagogía (Learning Engine v2)  [EN CURSO]
- Arquitectura congelada; solo se añade rigor pedagógico a lo ya medido (ver
  `docs/PLAN-ETAPA-PEDAGOGICA.md`).
- **Cierre del motor adaptativo (V3.68, 2026-09-15):** tras V3.68 el **diseño**
  del motor adaptativo queda **CONGELADO** (decisión de la auditoría de V3.67,
  **confirmada por la auditoría externa `Y` de V3.68**: 9,3/10, **0 P1**, y
  ningún hallazgo que justifique otra gran modificación arquitectónica del
  Adaptive Engine). El camino declarado hasta el producto terminado ya **no**
  añade capas arquitectónicas: **V3.68** cierre de la arquitectura adaptativa
  (hecho) → **V3.69** **E2E + Adaptive Engine Validation** (**HECHO** el
  2026-09-15: batería **E01–E19** por HTTP en
  `backend/tests/test_adaptive_e2e_v369.py`, **20 tests**, más el contrato de
  frontend con red mockeada en `frontend/tests/visual/drillProvenance.spec.ts`;
  **cero líneas de lógica de producto** y **cinco hallazgos aceptados como deuda**
  en la release note) → **V3.70** auditoría pedagógica (CEFR/competencias)
  (**HECHA** el 2026-09-15: **cinco ejes AA–AE + síntesis AF**, **1 P0 · 15 P1 ·
  12 P2 · 5 P3** y **4 propiedades positivas**; **5 subcomandos de medición solo
  lectura** en `audit_dossier.py` y **48 tests** nuevos; **cero líneas de lógica
  de producto**; los tracks P1–P6 quedan **medidos y acotados, no cerrados**) →
  **V3.71** runtime/offline/instalación (**HECHA** el 2026-09-16: **seis ejes
  RA–RF**, **P0 = 0 · P1 = 1 (cerrado) · P2 = 15 · P3 = 14**; cierra el **P1 de
  TTS/offline** diferido desde V3.46, pone el **launcher en CI (7/7)**, corrige
  **4 derivas documentales** y hace **honesta la salud de la UI**; **76 tests**
  nuevos; los ejes RA-05/RB-05/G5 quedan como **acción humana declarada**) →
  **V3.72** UX/product completion **(siguiente)** → **V3.73** auditoría final
  técnica → **V4.0** release
  final —«English Tutor, primera versión completa y estable»— y a partir de ahí
  `V4.0.x` de mantenimiento (bug fixes, calibración, UX, contenido,
  rendimiento).
- Tracks (un subagente a la vez): P1 política pedagógica formal, P2 error mastery,
  P3 vocabulario exposure/production/mastery, P4 listening como competencia, P5 CEFR basado
  en evidencia, P6 pronunciación fonémica.
- **Auditoría pedagógica de V3.70 (2026-09-15):** los seis tracks se **midieron**
  por primera vez con instrumentos deterministas y **solo lectura** (dossiers
  `docs/audit/AA…AF-*.md`). El resultado es que **el hueco es real y está
  acotado**: de los 33 hallazgos (1 P0 · 15 P1 · 12 P2 · 5 P3), los que tocan
  **contenido** (adecuación CEFR del banco, corpus de listening, forma de los
  ítems) se asignan a **V4.0.x**, y los que tocan **motor y acreditación**
  (validez de la maestría, `novel_required`, canales de evidencia de `interaction`
  y `mediation`, feedback que no genera explicación) a **Planner 4.0**; los
  **instrumentos** de nivelación, a **V4.0.x/V3.72**. Es decir: la etapa
  pedagógica **no se cierra en V3.70**, se cierra **sabiendo exactamente qué
  falta**.
- Subagentes (ejecutados por el gerente): `agentes/pedagogia/p-*.md` (P1–P6) y, para
  la auditoría, `agentes/v370-a1..a5-*.md`.

### M14 — Evidence & Performance + Listening + Placement  [HECHO ✔]
- **Evidence & Performance Engine (V1.3)**: ciclo `Evidence → Mastery → Skill Profile →
  Remediación` para speaking, writing y pronunciation (scorer determinista + extracción de
  evidencia con LLM + puente a mastery). CEFR Skill Profile (`/api/academy/profile`) y
  remediación adaptativa (`/api/academy/remediation`); el tutor lee el perfil CEFR.
- **Modelo de olvido (V1.4)**: `services/forgetting.py` (retrieval_probability + `review_due`
  real en función del tiempo).
- **Listening Engine**: sub-destrezas + dificultad + diagnóstico adaptativo
  (`/api/listening/diagnostic`).
- **Placement Engine (V1.5)**: IRT-lite adaptativo (`POST /api/academy/placement/next`).
- Verificado: backend 406 tests + ruff limpio; frontend 137 tests + `tsc`/`build` OK.

### M15 — Listening 2.0 + Placement 2.0  [HECHO ✔]
- **Listening 2.0 (V1.6)**: audio como entidad de primer nivel (`ListeningAsset` con metadatos
  de audio), vector de dificultad de 8 dimensiones con dificultad derivada por construcción,
  15 sub-destrezas (9 nuevas) y métrica de automaticidad (fluidez procesal).
- **Placement 2.0 (V1.7)**: calibración observacional de ítems (tabla
  `placement_item_calibration` con contadores poblacionales) y perfil **multiskill**
  (θ/nivel/confianza por destreza) sobre el motor IRT-lite/1PL. Endpoint
  `POST /api/academy/placement/profile` y banco de placement ampliado a las 7 destrezas.
- Verificado: backend 480 tests + ruff limpio; frontend 137 tests + `tsc`/`build` OK.

### M16 — FASE 1–5 de la auditoría externa (LAN/móvil → Speaking 2.0)  [HECHO ✔]
> Ejecutadas **directamente por el gerente** (sin briefings separados); ver `CHANGELOG.md` y
> `docs/RELEVO.md` (sección 37.6–37.11).
- **V1.30 LAN + Mobile 100%**: mDNS real (`local_url_available`), recuperación de permisos de
  micrófono, test de micrófono con medidor, QR de conexión y `/help/connect`.
- **V1.31 Adaptive Engine 2.0**: Priority Engine (`priority_signals`/`priority_score`/
  `explain_priority`) + "Why this activity?" en la tarjeta de siguiente mejor actividad.
- **V1.32 Curriculum 2.0**: escalera CEFR Pre-A1→C2 con bandas "plus" + Can-Do por 9 dimensiones
  (`/api/academy/cefr-ladder`).
- **V1.33 Listening 2.0**: Listening Resilience por condición de escucha + `context` del corpus.
- **V1.34 Speaking 2.0**: pronunciation proxy + Interaction Quality por sub-dimensión +
  Conversation Endurance (`/api/academy/speaking/endurance`).
- Verificado: backend 843 tests + ruff limpio; frontend 234 tests + `tsc`/`build` OK; launcher 64
  tests; Playwright 14 passed + 10 skipped.

## Decisiones tomadas

- Hitos M1 y M2 en paralelo (tras M0).
- STT → Whisper (`faster-whisper`). TTS → Piper.
- Ritmo: poco a poco, hito a hito.
- Requisitos nuevos (premisas 13 y 14): **multi-usuario** y **diseño nivel top**. Quedan como M7 y M8.

## Tablero de subagentes

| Subagente | Archivo | Estado |
|---|---|---|
| M0 Esqueleto modular | `agentes/m0-esqueleto-modular.md` | ✔ hecho |
| M1 Backend streaming | `agentes/m1-backend-streaming.md` | ✔ hecho |
| M1 Frontend streaming | `agentes/m1-frontend-streaming.md` | ✔ hecho |
| M2 Backend voz | `agentes/m2-backend-voz.md` | ✔ hecho |
| M2 Frontend voz | `agentes/m2-frontend-voz.md` | ✔ hecho |
| M4 Backend modo profesor | `agentes/m4-backend-modo.md` | ✔ hecho |
| M4 Frontend modo profesor | `agentes/m4-frontend-modo.md` | ✔ hecho |
| M5 Modelo conversacional | `agentes/m5-modelo-conversacional.md` | ✔ hecho |
| M7 Backend multi-usuario | `agentes/m7-backend-multiusuario.md` | ✔ hecho |
| M7 Frontend multi-usuario | `agentes/m7-frontend-multiusuario.md` | ✔ hecho |
| M8 Diseño y UX | `agentes/m8-diseno-ux.md` | ✔ hecho |
| M9 Backend progreso | `agentes/m9-backend-progreso.md` | ✔ hecho |
| M9 Frontend progreso | `agentes/m9-frontend-progreso.md` | ✔ hecho |
| M10 Voz continua | `agentes/m10-voz-continua.md` | ✔ hecho |
| A.1 Launcher núcleo puro | `agentes/endurecimiento/a1-launcher-core.md` | ✔ hecho |
| A.2 Launcher GUI + procesos + atajo | `agentes/endurecimiento/a2-launcher-gui.md` | ✔ hecho |
| RA1–RA7 Release Audit 1.1 | `agentes/endurecimiento/ra-*.md` | ✔ hecho |
| P1 Política pedagógica formal | `agentes/pedagogia/p1-politica-pedagogica.md` | ✔ hecho |
| P2 Error Mastery | `agentes/pedagogia/p2-error-mastery.md` | ✔ hecho |
| P3–P6 Etapa pedagógica | `agentes/pedagogia/p-*.md` | ✔ hecho |
| V1.15 Speaking 3.0 | `agentes/pedagogia/p9-speaking-3.0.md` | ✔ hecho |
| V1.18 P1 listening (retention + dictado/shadowing + variantes) | `agentes/pedagogia/p13-p15.md` | ✔ hecho |
| V1.19 Refresco UI profesional (frontend) | plan Cursor `refresco_ui_profesional` | ✔ hecho |
| V1.21 UI Learning Home (HOME como centro) | plan Cursor `v1.21_ui_learning_home` | ✔ hecho |
| V1.30–V1.34 FASE 1–5 auditoría (LAN/móvil → Speaking 2.0) | directo del gerente (sin briefings) | ✔ hecho |
| V2.7 Depth B1 (piloto) | directo del gerente (plan Cursor `v2.7_curriculum_depth`) | ✔ hecho |
| V2.7 Depth A2 | `agentes/curriculum/v27-depth-a2.md` | ✔ hecho |
| V2.7 Depth B2 | `agentes/curriculum/v27-depth-b2.md` | ✔ hecho |
| V2.7 Depth C1 | `agentes/curriculum/v27-depth-c1.md` | ✔ hecho |
| V2.7 Depth C2 | `agentes/curriculum/v27-depth-c2.md` | ✔ hecho |
| V2.8 Listening Curriculum | directo del gerente | ✔ hecho |
| V2.9 Speaking Mission Performance | directo del gerente | ✔ hecho |
| V2.10 Assessment 2.0 | directo del gerente | ✔ hecho |
| V2.11 SRS / FSRS | directo del gerente | ✔ hecho |
| V2.12 Evidence Graph | directo del gerente | ✔ hecho |
| V3.0 Beta freeze | directo del gerente | ✔ hecho |
| V3.18 Deuda del grafo (P3) | directo del gerente | ✔ hecho |
| V3.19 Léxico por destreza + Speaking micro-drill | directo del gerente (plan Cursor `v3.19_lexico_microdrill`) | ✔ hecho |
| V3.20–V3.52 (Dictionary→Learning Bridge, Listening 3.0/4.0, Transfer 2.0 y posteriores) | briefings en `agentes/` (`v324`, `v332`–`v352`) | ✔ hecho (histórico; fuente de verdad `CHANGELOG.md` + `docs/RELEVO.md`) |
| Auditoría profunda V3.18 pre-V3.19 (6 áreas) | `agentes/auditoria-profunda-v318.md` | ✔ hecho (dossier `docs/audit/I-AUDITORIA-PROFUNDA-V318.md`) |
| Auditoría TOTAL externa (v3.18.0) | `agentes/auditoria-total-externa.md` | ⚠️ sin dossier propio; la serie TOTAL continuó con `agentes/auditoria-total-externa-v321/v322/v323.md` y los dossiers `docs/audit/J-…`, `L-…`–`P-…` |
| Auditoría EXTERNA de V3.52.0 | `agentes/auditoria-externa-v352.md` | ✔ hecho (dossier `docs/audit/Q-AUDITORIA-TOTAL-V352.md`) |
| Auditorías de V3.60 | `agentes/auditoria-externa-v360.md`, `agentes/auditoria-externa-v359.md` | ✔ archivadas (`docs/audit/S-…` y `T-…`; la `R` de V3.59 sigue sin publicar) |
| Auditoría profunda de V3.62 + entrada externa | `docs/audit/U-AUDITORIA-TOTAL-V362.md`, `agentes/auditoria-externa-v362.md` | ✔ archivada (9,5/10 APROBADA); informe externo esperado en `docs/audit/V-AUDITORIA-TOTAL-V362.md` |
| V3.63 Observed Task Difficulty 2.0 + honestidad del modelo | `agentes/v363-observed-task-difficulty-2.md` | ✔ hecho (2026-09-14; release `v3.63.0`) |
| V3.64 Decision Projection + Planner 3.0 (cierre de P1-01) | directo del gerente | ✔ hecho (2026-09-14; release `v3.64.0`) |
| V3.65 Observed Difficulty 3.0 (`P(éxito | alumno, tarea)` empírica) | `agentes/v365-observed-difficulty-3.md` | ✔ hecho (2026-09-15; release `v3.65.0`) |
| V3.66 Task-Level Empirical Success + Decision Provenance | directo del gerente | ✔ hecho (2026-09-15; release `v3.66.0`) |
| V3.67 Task Identity 2.0 + Decision Lifecycle + Provenance Analytics | directo del gerente | ✔ hecho (2026-09-15; release `v3.67.0`) |
| V3.68 Adaptive Engine Hardening & Integrity (cierre de los P1 de 2.ª generación + P2-08) | directo del gerente (plan Cursor `v3.68_adaptive_engine_hardening`) | ✔ hecho (2026-09-15; release `v3.68.0`; auditada por `docs/audit/Y-AUDITORIA-TOTAL-V368.md`: 9,3/10, 0 P1) |
| V3.69 E2E + Adaptive Engine Validation (batería E01–E19; validación, no capacidad nueva) | `agentes/v369-e2e-adaptive-validation.md` | ✔ hecho (2026-09-15; release `v3.69.0`; **20 tests E2E** + 2 specs de navegador; diff de producto **CERO en lógica** (solo los bumps de versión de `config.py`/`package.json`); 5 hallazgos aceptados) |
| V3.70 Auditoría pedagógica + CEFR (cinco ejes AA–AE + síntesis AF; medición, no capacidad nueva) | `agentes/v370-auditoria-pedagogica.md` + `agentes/v370-a1-contenido-cefr.md`, `v370-a2-cobertura-destrezas.md`, `v370-a3-feedback-correccion.md`, `v370-a4-validez-maestria.md`, `v370-a5-instrumentos-nivelacion.md` | ✔ hecho (2026-09-15; release `v3.70.0`; **5 subcomandos de medición solo lectura** en `audit_dossier.py` + 6 dossiers `AA…AF` + **48 tests** nuevos; diff de producto **CERO en lógica**); hallazgos: **1 P0 · 15 P1 · 12 P2 · 5 P3** y 4 propiedades positivas. **Publicada (2026-09-16):** commit `9ba9c49` (+ docs `2db93ba`), tag `v3.70.0`, **CI 6/6** run `35062382562` |
| Auditoría EXTERNA de DISEÑO de V3.69 (pre-implementación: briefing + batería E01–E19 + derivación P2/P3) | `agentes/auditoria-externa-v369.md` | ⏳ lanzada (informe esperado en `docs/audit/Z-AUDITORIA-DISENO-V369.md`); **la implementación ya está cerrada** (commit `9a4e70a`, tag `v3.69.0`, CI 6/6 en `34978215154`), así que el dictamen se aplicará como corrección documental o se trasladará a V3.70+, y el punto de entrada de `agentes/auditoria-externa-v369.md` lleva un bloque **ACTUALIZACIÓN** con el estado de entrega para poder falsar el diseño **contra el código publicado** |
| Auditoría EXTERNA de V3.69 (post-implementación, sobre el código y los 5 hallazgos) | `agentes/auditoria-externa-release-v369.md` | ⏳ **lanzada** (informe esperado en `docs/audit/Z2-AUDITORIA-RELEASE-V369.md`): punto de entrada autocontenido con el estado de entrega (commit `9a4e70a`, tag `v3.69.0`, CI 6/6 `34978215154`), **15 afirmaciones falsables** con `archivo:línea`, comandos de reproducción y **13 preguntas de alto valor**; instruye a dictaminar los 5 hallazgos de §C uno a uno y a distinguir «el test no demuestra» de «el motor no cumple» |
| Auditoría EXTERNA de la RELEASE de V3.70 (post-implementación, sobre los cinco ejes AA–AF, los 48 tests y los 5 subcomandos de medición) | `agentes/auditoria-externa-release-v370.md` | ⏳ **entregada (2026-09-16)** (informe esperado en `docs/audit/AG-AUDITORIA-RELEASE-V370.md`; el prefijo `AG` evita colisión con los dossiers `AA`–`AF` del propio incremento): punto de entrada autocontenido con el estado de entrega (commit `9ba9c49`, tag `v3.70.0`, CI 6/6 `35062382562`), **12 afirmaciones falsables** con `archivo:línea`, comandos de reproducción (incluida la regeneración determinista de los 10 subcomandos) y **10 preguntas de alto valor**; instruye a dictaminar los 48 tests (demuestran vs describen), el P0 y las 4 propiedades positivas |
| Auditoría EXTERNA de la RELEASE de V3.71 (post-implementación, sobre los seis ejes RE–RF, los 43 + 2 tests nuevos y los 6 dossiers) | `agentes/auditoria-externa-release-v371.md` | ⏳ **entregada (2026-09-16)** (informe esperado en `docs/audit/AH-AUDITORIA-RELEASE-V371.md`; el prefijo `AH` evita colisión con los dossiers `AA`–`AF` de V3.70 y con el `AG` reservado por el punto de entrada de V3.70): punto de entrada autocontenido con el estado de entrega **verificado contra GitHub, no contra el árbol local** (commit `2eff6ea`, tag anotado `v3.71.0` objeto `6ac22db`, CI **7/7** run `35136141089` —con el job nuevo `Launcher (ruff + pytest)` `104928880868`, que es la decisión **D** del briefing verificada en remoto—), **9 preguntas falsables** con `archivo:línea` del árbol publicado, comandos de reproducción (censo de primitivas de red frente a `RUNTIME_TOUCHPOINTS`, determinismo byte a byte del par `runtime-audit`, refutación del `timeout` con un servidor local que no responde, reversión de `en_US-lessac-medium` para ver el test caer) y **6 reglas duras**; instruye a separar lo **verificado** de lo **declarado** y a pronunciarse sobre las tres honestidades que el propio incremento declara (`RA-05` sin corte de red real, `RB-05` instalación documentada pero no ejecutada en máquina limpia, `RC-01` runtime de desarrollo con condición de salida) |
| Auditoría EXTERNA de CIERRE del producto (antes de la decisión de V4.0), anclada en `v3.73.4` (post-implementación; **alcance total** sobre todo el stack + auditoría visual de toda la GUI) | `agentes/auditoria-total-externa-v373.md` | ⏳ **entregado y re-anclado (2026-09-17)** (informe esperado en `docs/audit/AI-AUDITORIA-CIERRE-V373.md`; el prefijo `AI` es el primer libre: `AA`–`AF` los ocupan los dossiers de V3.70 y `AG`/`AH` están reservados por los puntos de entrada de V3.70/V3.71, **ambos sin informe recibido**): punto de entrada autocontenido con el estado de entrega **verificado contra GitHub** (commit de release `5007c3a`, tag anotado `v3.73.4` objeto `3f2ec88`, **invariante del código** `git diff --stat v3.73.4..main -- backend frontend launcher scripts` **vacío** y CI **11/11** en el run `35251738073`); **43 preguntas falsables** en 7 áreas (arquitectura/backend, Adaptive Engine/evidencia/procedencia, pedagogía/contenido y claims de nivel, listening bajo escrutinio especial, GUI y navegación, runtime/instalación/entorno, CI-CD y release) con `archivo:línea`, comandos de reproducción y **qué falsa cada una**; **matriz de cierre de 15 áreas** que rellena el auditor con la regla de marcar **NO COMPROBABLE** lo que exija hardware o persona; **7 reglas duras**; y **sección de honestidad** que le obliga a pronunciarse sobre los 7 gates en `pending`, el job `product-origin-windows` informativo, el alcance del fail-closed (**arranque, no ejecución degradada**) y que **no** hay audio humano, evaluación acústica ni feedback textual de listening. **Tres discrepancias declaradas a propósito para que el auditor las dictamine en vez de darlas por buenas:** (i) el hub de Aprender tiene **4** tarjetas primarias (Listening, Speaking, Vocabulary, Grammar) —y **no** las 6 que se venían describiendo— más un **bloque secundario** con Reading y Writing que abre `/chat/lectura` y `/chat/escritura` (V3.73.1), con la asimetría real de que Reading **no** tiene directorio de feature versionado mientras Writing sí; (ii) el código marca los **7** gates como `human` (`scripts/validation_gate.py`) mientras la documentación dice «5 de ellos acción humana»; y (iii) `docs/DEVICE_MATRIX.md` sigue **en ⬜**, de modo que la matriz de dispositivos **no** está verificada. **Motivo del re-anclaje (2026-09-17):** la versión anterior afirmaba el invariante de código contra `v3.73.0`, y ese diff ya **no** salía vacío (V3.73.1 tocó `frontend/**`; V3.73.2, `backend/tests/**` y `backend/scripts/audit_dossier.py`), así que el auditor habría abierto un **P0 falso** en su primer comando |
| Auditoría EXTERNA del producto tras la Fase 2 del P0 de identidad, anclada en `v3.75.0` (post-implementación; **alcance total** sobre todo el stack, con foco en las tres releases de seguridad V3.73.7 → V3.74.0 → V3.75.0) | `agentes/auditoria-total-externa-v375.md` | ⏳ **entregado (2026-09-18)** (informe esperado en `docs/audit/AJ-AUDITORIA-TOTAL-V375.md`; el prefijo `AJ` es el primer libre: `AA`–`AF` los ocupan los dossiers de V3.70, `AG`/`AH` los puntos de entrada de V3.70/V3.71 y `AI` el de cierre de V3.73, **los tres sin informe recibido**): punto de entrada autocontenido con el estado de entrega **que se verifica contra GitHub** con los comandos de §1 (tag anotado `v3.75.0` e **invariante del código** `git diff --stat v3.75.0..main -- backend frontend launcher scripts` **vacío**, resueltos por comando — **sin** SHA ni run fijados a mano, la lección de V3.73.5), **CI de 12 jobs** (entra `deps-audit`, bloqueante) cuyo **estado se resuelve por comando** (`gh run list --commit $(git rev-parse v3.75.0^{commit})`), con la **primera run real sobre el commit de release en 11/12** (`Playwright E2E (visual)`: el arnés visual no conocía el contrato de sesión y se corrigió **antes** de publicar el tag; ver `release-notes-v3.75.0.md` §7.1) y versión en los **6 orígenes**; **60 preguntas falsables en 8 áreas** (arquitectura/backend, Adaptive Engine/evidencia, pedagogía/contenido, listening bajo escrutinio especial, GUI, **seguridad/identidad/cadena de suministro**, runtime/instalación y CI/CD) con `archivo:línea`, comandos de reproducción y qué falsa cada una; **invariante de la suite** (2882 casos) con el reparto `passed`/`skipped` por artefactos no versionados (2879+3 en clon limpio); **matriz de cierre de 18 áreas** (se añaden identidad/sesión, superficie sin sesión y cadena de suministro) que rellena el auditor con la regla de marcar **NO COMPROBABLE** lo que exija hardware o persona; **8 reglas duras** (la nueva: no confundir «firmado» con «autenticado»); y **sección de honestidad** que le obliga a pronunciarse sobre la Fase 3 sin decidir, la apertura de sesión sin credencial, el adaptador de `conftest` que reduce lo que prueban 109 suites, el salto mayor de `starlette`, el alcance de `VG-N6` como lista y no demostración, y los 7 gates en `pending` |
| Auditoría EXTERNA del baseline tras el cierre del sesgo posicional, anclada en `v3.75.1` (post-implementación; **alcance total** sobre todo el stack + el **acta de la pausa pedagógica** y la reparación del ancla) | `agentes/auditoria-total-externa-v3751.md` | ⏳ **entregado (2026-09-19)**, dentro del commit de release de `v3.75.2` (informe esperado en `docs/audit/AN-AUDITORIA-TOTAL-V3751.md`; ver la **nota de prefijos** al final de este tablero): punto de entrada autocontenido con el estado de entrega que se **resuelve por comando** (`git rev-parse`, `gh run list` — **sin** SHA ni run fijados a mano, la lección de V3.73.5) y el **invariante honesto**: `git diff --stat v3.75.1..v3.75.2 -- backend/services backend/routers backend/repositories backend/domain backend/curriculum frontend/src launcher` **vacío** (producto y contenido idénticos), con el diff completo declarado como **lista cerrada** y `backend/config.py` acotado a la línea `VERSION`; **29 preguntas falsables en 5 áreas** (ancla y release documental, instrumento de medición, los hallazgos de la pausa, el producto heredado, deriva documental) con `archivo:línea`, comando de reproducción y qué falsa cada una; **matriz de cierre de 21 áreas** (se añaden contenido, instrumento psicométrico, los 5 hallazgos y el ancla) y **10 reglas duras** (dos nuevas: no confundir «medido» con «corregido», ni un `0 %` de una heurística con ausencia de problema); y **sección de honestidad** que le obliga a pronunciarse sobre que esta release **no arregla nada**, que el sesgo de longitud y los dos sesgos de los instrumentos siguen donde estaban, que la pausa mide **tasa de explotación** y no aprendizaje, que los instrumentos de evaluación son **46 ítems y no 904**, y que los 7 gates siguen en `pending`. **Motivo del ancla nueva:** la entrada `-v375` declaraba el invariante `git diff --stat v3.75.0..main -- backend frontend launcher scripts` **vacío**, y V3.75.1 lo **rompió** al tocar `backend/` (12 ficheros, +980/−637), así que el auditor habría abierto un **P0 falso** en su primer comando |
| Auditoría EXTERNA del producto tras el cierre de listening y el P1 del banco heredado, anclada en `v3.75.7` (post-implementación; **alcance total** sobre el stack, las cinco iteraciones `V3.75.3`–`V3.75.7` y el **P1** que destapó la auditoría interna de la propia tanda) | `agentes/auditoria-total-externa-v3757.md` | ⏳ **entregado (2026-09-20)**, dentro del commit de release de `v3.75.7` (informe esperado en `docs/audit/AP-AUDITORIA-TOTAL-V3757.md`; prefijo `AP` = primer libre, con `AN` reservado por la entrada de `v3.75.1` y `AO` ocupado por la política psicométrica): punto de entrada autocontenido cuyo estado de entrega se **resuelve por comando** (`git rev-parse`, `gh run list` — **sin** SHA ni run fijados a mano) y que, **como esta release SÍ cambia producto**, **NO declara el invariante clásico** («diff de producto vacío») porque sería falso: declara **tres invariantes acotados** que sí pueden cumplirse —**currículum y evaluaciones VACÍOS**, corpus de listening en **exactamente 3 líneas** (`c071`, `c084` + la versión) y **banco heredado en exactamente 2 etiquetas** (`l18`, `l19`)— más una **lista cerrada** del diff, con el **rango `v3.75.2..v3.75.7` de ocho commits** —**siete** que post-datan el tag `v3.75.2` más **el commit de release**; el recuento se corrige en la errata §0.1 del propio punto de entrada— declarados aparte; **34 preguntas falsables en 6 áreas** (ancla e historial · el P1 del banco heredado · identidad y frontera de red · TTS/voz y disco · el icono del desplegable y la rampa · deriva documental) y una **matriz de cierre de 24 filas**; incluye la advertencia del reparto `passed`/`skipped` en clon limpio y la declaración de que **cinco iteraciones llevan una sola etiqueta**, para que el auditor la dictamine |
| Auditoría EXTERNA **de ARCO** sobre las cuatro releases no auditadas desde `v3.75.7`, anclada en `v3.77.1` (post-implementación; **alcance total** sobre el stack de `V3.75.8` + `V3.76.0` + `V3.77.0` + `V3.77.1`, con el **parche** dictaminado por su causa) | `agentes/auditoria-total-externa-v3771.md` | ⏳ **entregado (2026-09-21)** como **adendo DOCUMENTAL POSTERIOR al tag `v3.77.1`** —un tag publicado no se recrea—, **sin tag nuevo**, con el ancla en `v3.77.1` (informe esperado en `docs/audit/AQ-AUDITORIA-TOTAL-V3771.md`; prefijo **`AQ` = primer libre**, con `AP` reservado por la entrada de `v3.75.7` **sin informe recibido**, `AN` por la de `v3.75.1` y `AO` ocupado por la política psicométrica): punto de entrada autocontenido cuyo estado de entrega se **resuelve por comando** (`git rev-parse`, `gh run list` — **sin** SHA ni run fijados a mano) y que, **como este arco SÍ cambia producto, NO declara el invariante clásico** («diff de producto vacío») porque sería falso —producto = **80 ficheros, +8 539 / −300**—: declara **cinco invariantes acotados** que sí pueden cumplirse —**contenido de currículum y evaluaciones VACÍO**, **sin bumps** de `CURRICULUM_VERSION`/`LISTENING_BANK_VERSION`/`GENERATOR_VERSION`/`DECISION_POLICY_VERSION`, currículum en **exactamente 3 ficheros nuevos** (`vocab_packs/{food,travel,work}.json`, +102, 0 borrados), la versión de producto en **solo** el triplete declarado, y el **adendo documental sin mover producto** (`git diff --stat v3.77.1..HEAD -- backend frontend launcher scripts` **vacío**)— más una **lista cerrada** del diff, con el **rango `v3.75.7..v3.77.1` de DIEZ commits** —**el primero** (`5ae4950`) **post-data el tag `v3.75.7`**: es su **errata**, declarada aparte para que el recuento no se repita mal— y las **cuatro releases bajo una sola etiqueta de auditoría**; **58 preguntas falsables en 7 áreas** (ancla e historial · el diccionario de consulta de `V3.75.8` · el PIN por perfil de `V3.76.0` y su freno · la retención léxica de `V3.77.0` con el reto **retención ≠ dominio** y el puente candidato→añadido · los perfiles con autorización del webmaster · el parche `V3.77.1` y la sonda del arnés · deriva documental) y una **matriz de cierre de 36 filas**; incluye el aviso de que **el CI no corre en tags** (`on: push: branches: [main]`) y de que **la run de `v3.77.0` está en ROJO a propósito** —es el defecto que arregla `V3.77.1`—, cuatro **reglas duras nuevas** (no confundir retención con dominio · no confundir «tiene PIN» con autenticación de persona · no leer un PIN compartido como un rol · no confundir «la petición existe» con «la petición hace algo») y **seis discrepancias declaradas a propósito** para que las dictamine: (i) el **token en fichero sustituido por el PIN** (`agentes/v377-perfiles-webmaster.md` §4bis), (ii) **sin GitHub Release** y el `Latest: v3.33.0` engañoso, (iii) **CI no corre en tags** y el commit de `v3.77.0` en rojo, (iv) **el invariante clásico no se declara**, (v) los flags `admin_required` que **pasan de mentir a decir la verdad sin cambio de comportamiento**, y (vi) `agentes/README.md` **no indexa los puntos de entrada desde `v3.73.4`** |
| Auditoría EXTERNA **de ARCO** sobre las cuatro releases no auditadas desde `v3.77.1`, anclada en `v3.80.0` (post-implementación; **alcance total** sobre el stack de `V3.77.2` + `V3.78.0` + `V3.79.0` + `V3.80.0`, con la migración aditiva, el **rate limiter por clase de ruta**, el patrón de diálogo y las dos pantallas que el alumno estrenó —el diccionario en tres modos y Flashcards— dictaminadas por su causa) | `agentes/auditoria-total-externa-v380.md` | ⏳ **entregado (2026-09-22)** como **adendo DOCUMENTAL POSTERIOR al tag `v3.80.0`** —un tag publicado no se recrea—, **sin tag nuevo**, con el ancla en `v3.80.0` (informe esperado en `docs/audit/AR-AUDITORIA-TOTAL-V380.md`; prefijo **`AR` = primer libre**, con `AG`/`AH`/`AI`/`AJ` reservados por los puntos de entrada de motor y pausa pedagógica, `AP` por el de `v3.75.7` y `AQ` por el de `v3.77.1`, **los seis sin informe recibido**): punto de entrada autocontenido cuyo estado de entrega se **resuelve por comando** (`git rev-parse`, `gh run list` — **sin** SHA ni run fijados a mano) y que, **como este arco SÍ cambia producto, NO declara el invariante clásico** («diff de producto vacío») porque sería falso —producto = **61 ficheros, +9 950 / −589**—: declara **cinco invariantes acotados** que sí pueden cumplirse —**contenido de currículum y evaluaciones VACÍO** (packs incluidos: se leen, no se reescriben), **sin bumps** de `CURRICULUM_VERSION`/`LISTENING_BANK_VERSION`/`GENERATOR_VERSION`/`DECISION_POLICY_VERSION`, el **producto sin mover desde el tag** (`git diff --stat v3.80.0..main -- backend frontend launcher scripts` vacío — **el lanzador NO aparece en el diff del arco**), la **migración aditiva, idempotente y que NO rellena nada** (`vocabulary.translation`, con el candado preexistente `test_fk_migration_idempotent` que **muerde** —`duplicate column name: translation`— y la demostración sobre una BD con el esquema de `v3.79.0`) y la **precedencia de la cara B declarada** en `card_face` (alumno → pack → caché) con su test de 9 casos que **muerde**— más una **lista cerrada** del diff por área y las **cuatro releases bajo una sola etiqueta de auditoría** (**solo `v3.80.0` con tag**, decisión declarada); **37 preguntas falsables en 6 áreas** (el ancla y el historial · el endurecimiento de `V3.77.2` con el **IDOR** y los hallazgos de la auditoría anterior H4/cola de repaso · los tres modos y la **superficie de estudio única** de `V3.78.0` · el perfil de `V3.79.0` —rate limiter, portal, `Retry-After`— · Flashcards a fondo de `V3.80.0` —precedencia, D3, parser compartido, topes, mazos listos, filtro y calendario— · deriva documental) y una **matriz de cierre de 37 filas**; incluye el aviso de que **el CI no corre en tags** (`on: push: branches: [main]`: la run que certifica el commit del tag es la del push a `main` de ese mismo commit, 12/12 en verde al entregar) y **ocho discrepancias declaradas a propósito** para que las dictamine: (i) el **`Retry-After` es una constante de 5 s** (`backend/security.py:247`) con ventana de 60 s, mientras la ruta de sesión **sí** calcula el tiempo real (`routers/session.py:97`) —`V3.79.0` hizo **visible** el freno, no lo volvió **exacto**—, (ii) **el primer commit del rango es documental y post-data el tag `v3.77.1`** (§0.1), (iii) los candados del diálogo son de **dos clases distintas** (un test que lee el **texto del CSS** y un test **visual** de un solo viewport: no son dos candados equivalentes), (iv) la cifra **«139 de 145» no es reproducible** desde el repositorio (mide la BD real del alumno, que no se publica), (v) los **topes del pegado masivo son silenciosos** (`CARDS_BULK_MAX=200`, anverso 400, reverso 2 000), (vi) la **precedencia hace que el pack curado no vuelva a verse** para una palabra que el alumno corrigió (borrar la propia corrección lo devuelve), (vii) **`V3.78.0` cambió el defecto de vista a `lookup`** y `V3.80.0` cambió el mazo a **selección única compartida** —cambios de comportamiento para quien ya usaba la app— y (viii) la **página de Releases no cuenta la historia** (estaba en `v3.33.0`; se publica solo la de `v3.80.0`, el ancla es el **tag**) |
| Pausa pedagógica pre-baseline: **política psicométrica del banco** (decisión de diseño, no medición ni release) | `docs/audit/AO-POLITICA-PSICOMETRICA-V40.md` | ✅ **HECHO (2026-09-19)**: convierte los 5 problemas deduplicados de `AH`–`AM` en una **política de autoría falsable** para que la reautoría de V4.0.x no sea una ronda de parches. Fija **`POLITICA_PSICOMETRICA_VERSION = "1.0.0 (V4.0)"`** y cuatro reglas: **A** posición (`≤ 35 %` por `k`, nivel y **destreza**, sin posiciones muertas, extensible a `assessments.json`, `j % k` por destreza) · **B** longitud (`≤ 1,5 × azar` de su `k` por lote → `k=3 ≤ 50 %`, `k=4 ≤ 37,5 %`; tres casos: diferencia pequeña / artificialmente reveladora / **longitud justificada declarada**) · **C** `k` (`3` en lo que gatea —checks, exámenes, placement— · `4` en el corpus de práctica · los 10 checks de `k=4` de A1 listening alineados a `3` · `k=2` prohibido · `k` **no** escala con CEFR) · **D** distractores (rúbrica D1–D5: misma categoría, recuperable, ≥1 *misconception*, prohibido el descartable solo por forma, el ítem debe fallar con solo forma/eco). Incluye **tabla de invariantes**, **orden de aplicación por riesgo** (checks B1/C2 → exámenes → placement → corpus C1/C2 → resto), **criterios de aceptación** y **protocolo de re-medición** con los cinco subcomandos ya existentes. **No corrige nada, no añade candados y no toca banco, runtime ni artefactos** (los invariantes se codifican **con** la corrección, principio 6) |
| Seguimiento de las auditorías EXTERNAS de V3.69 (`Z` y `Z2`, sin informe recibido) | `agentes/auditoria-externa-v369-seguimiento.md` | ⏳ **entregado (2026-09-16)**: registro del estado, verificación del hueco (`Z`/`Z2` no existen), objeto de cada informe, **texto de reclamo listo para enviar** y protocolo de acuse/triaje |
| V3.71 Runtime real, offline verificado e instalación limpia (ejes RA–RF; verificación con endurecimiento mínimo) | `agentes/v371-runtime-offline-instalacion.md` | ✅ **HECHO (2026-09-16; release `v3.71.0`)**: **seis ejes RA–RF** con sus seis dossiers. **RE** (CI 7/7 con el job `launcher` + 4 derivas fijadas por test) · **RA** (instrumento de solo lectura + protocolo de 12 flujos; **entregado pero ABIERTO**: RA-05 corte de red, acción humana) · **RB** (la voz inglesa por defecto entra en el catálogo, bootstrap delegado y verificación previa) · **RC** (salud honesta de 3 estados y sondeo acotado) · **RD** (P1 de TTS/offline cerrado) · **RF** (síntesis). Hallazgos: **P0 = 0 · P1 = 1 (cerrado) · P2 = 15 · P3 = 14**; del total, **8 P2 cerrados**, **3 declarados con fase/condición de salida**, **3 de acción humana** (RA-02, RA-05, G5) y **1 parcial** (RA-01). **43 tests** nuevos de backend (+2 de frontend); backend **2643**, frontend **661**, launcher **75** |
| Eje RE de V3.71 (gates/CI/deriva documental) — evidencia interna | `docs/audit/RE-GATES-DERIVA.md` | ✅ **cerrado (2026-09-16)**: 7/7 jobs de CI (entra `launcher` con los 75 tests), derivas D1–D4 corregidas y **pinchadas por test** (`backend/tests/test_docs_drift_v371.py`, 8 tests), nota de corrección en `docs/BETA_GATES.md` y **G5 declarado abierto**; hallazgos P0 = 0 · P1 = 0 · P2 = 2 · P3 = 4 (1 deuda aceptada) |
| Eje RA de V3.71 (runtime y offline real) — evidencia interna | `docs/audit/RA-RUNTIME-OFFLINE.md` | 🔄 **instrumento + protocolo entregados (2026-09-16)**; **eje ABIERTO**: falta ejecutar los 12 flujos de `Y` §22 con la red cortada (**RA-05**, acción humana). Hallazgos P0 = 0 · P1 = 0 · **P2 = 5** (RA-03 cerrado por RD, RA-04 cerrado por RB, RA-01 parcial, RA-02 abierto, RA-05 abre el cierre) · P3 = 2. Nuevo subcomando de solo lectura `runtime-audit` (determinista, con guard por test de 11 tests) y **3 dependencias de Internet no declaradas en ruta de producto** (RA-01) |
| Eje RD de V3.71 (dependencias ocultas y degradación) — evidencia interna | `docs/audit/RD-DEPENDENCIAS-OCULTAS.md` | ✅ **cerrado con alcance acotado (2026-09-16)**: cierra el **P1 de TTS/offline** diferido en 4 sitios desde V3.46 (**2 de 3 vectores**; el de UI se re-declara con fase a V3.72) y con él **RA-03** y parte de **RA-01**. Hallazgos P0 = 0 · **P1 = 1 (cerrado)** · P2 = 3 (2 cerrados, 1 con fase) · P3 = 3. El hallazgo central: el `timeout` de la descarga de voces era **código muerto** (`urlretrieve` no lo acepta) ⇒ la única dependencia de Internet en ruta de producto estaba **sin límite**; ahora es real y acotado, con verificación de tamaño y degradación declarada (`X-TTS-Voice`/`X-TTS-Degraded`). **6 tests nuevos**, todos fallan sin el cambio |
| Eje RC de V3.71 (runtime de producto y salud honesta) — evidencia interna | `docs/audit/RC-RUNTIME-PRODUCTO.md` | ✅ **cerrado con una declaración (2026-09-16)**: el runtime real es **uvicorn de un solo proceso + dev server de Vite**, y `frontend/dist` **no lo sirve nadie** ⇒ **Node + npm son requisito de EJECUCIÓN**; por la decisión **(A)** se **declara con condición de salida** (V3.72/V3.73) en vez de implementarse. Cierra **RC-02** (el sondeo de Ollama no tenía cota y el launcher solo espera 1,5 s ⇒ un Ollama **lento** se disfrazaba de backend caído; ahora `LLM_PING_TIMEOUT_SECONDS = 1.0`) y **RC-03** (el indicador de cabecera leía `/api/health`, 200 siempre ⇒ decía «Conectado» con Ollama o la BD caídos; ahora **Conectado / Degradado / Desconectado** con `connectionState()`). Hallazgos P0 = 0 · P1 = 0 · **P2 = 3** · P3 = 2. Suites verdes: **2643 backend · 661 frontend**; 2 derivas documentales nuevas fijadas por test (`PREMISAS.md` §3 y `ARQUITECTURA.md`) |
| Eje RB de V3.71 (instalación limpia desde cero) — evidencia interna | `docs/audit/RB-INSTALACION.md` | ✅ **cerrado con una deuda declarada (2026-09-16)**: absorbe **RA-04** y **RD-06**. **RB-01**: la **voz inglesa por defecto** (`en_US-lessac-medium`) **no estaba en el catálogo curado**, así que `ensure_voice_for_language("en")` salía **sin intentar la descarga** y en una instalación limpia el **español sí se auto-descargaba y el inglés no** —falsado empíricamente—. **RB-02**: el bootstrap deja de usar `urlretrieve`/URLs propias y delega en el catálogo. **RB-03**: verificación previa de solo lectura (`--check`/`--json`) que distingue **descarga** de **local**. **RB-04**: runbook con el `ollama pull` explícito. Hallazgos P0 = 0 · P1 = 0 · **P2 = 2 (cerrados)** · P3 = 3 (2 cerrados, **RB-05** = máquina limpia real, acción humana). **13 tests** |
| Eje RF de V3.71 (síntesis del incremento) — evidencia interna | `docs/audit/RF-SINTESIS-RUNTIME-V371.md` | ✅ **cerrado (2026-09-16)**: matriz consolidada de los seis ejes (**P0 = 0 · P1 = 1 cerrado · P2 = 15 · P3 = 14**), veredicto por área y sección de **honestidad** (no hay offline en vivo ni máquina limpia real, y «offline verificado» **no** significa «producto empaquetado») |

> **Nota de prefijos (2026-09-19 · V3.75.2).** Los prefijos de dos letras de
> `docs/audit/` **ya no significan una sola cosa**, y conviene leerlos con esta
> tabla delante: `AA`–`AF` son los dossiers de V3.70; `AG`–`AM` están **ocupados por
> esta línea** (`AG` motor · `AH` longitud · `AI` instrumentos · `AJ` forma · `AK`
> distractores · `AL` niveles · `AM` síntesis de la pausa); y los puntos de entrada
> externos de V3.70/V3.71/V3.73/V3.75 siguen **reservando** `AG`, `AH`, `AI` y `AJ`
> para sus informes (`AG-AUDITORIA-RELEASE-V370.md`, `AH-AUDITORIA-RELEASE-V371.md`,
> `AI-AUDITORIA-CIERRE-V373.md`, `AJ-AUDITORIA-TOTAL-V375.md`), **ninguno recibido**.
> No hay colisión de **nombre de fichero**, pero sí de **prefijo**: un informe que
> llegue como `AJ-AUDITORIA-TOTAL-V375.md` **no** pertenece a la serie psicométrica.
> Por eso el informe de la auditoría anclada en `v3.75.1` toma el primer prefijo
> libre, **`AN`** (`docs/audit/AN-AUDITORIA-TOTAL-V3751.md`), y no se renombra ningún
> dossier ya publicado: la reserva la declararon los propios puntos de entrada
> **dentro de sus tags**, y reescribirla sería falsear historia.
>
> **Añadido (2026-09-19 · pausa pedagógica).** El primer prefijo **libre** después
> de la serie es **`AO`**, y lo ocupa el dossier de **decisión de política**
> `docs/audit/AO-POLITICA-PSICOMETRICA-V40.md` (no es un eje de medición: cierra
> conceptualmente la pausa de `AH`–`AM`). No colisiona con ningún punto de entrada
> externo reservado.
>
> **Añadido (2026-09-21 · arco `v3.75.7..v3.77.1`).** Después de `AO`, el punto de
> entrada de `v3.75.7` **reservó `AP`** (`docs/audit/AP-AUDITORIA-TOTAL-V3757.md`),
> **sin informe recibido**. El **primer libre** es por tanto **`AQ`**, y lo ocupa el
> informe de la auditoría **de arco** anclada en `v3.77.1`:
> `docs/audit/AQ-AUDITORIA-TOTAL-V3771.md`. No se renombra ningún dossier ya
> publicado: la reserva la declararon los propios puntos de entrada **dentro de sus
> tags**, y reescribirla sería falsear historia. Recuento vigente de reservas **sin
> informe recibido**: `AG`, `AH`, `AI`, `AJ` (motor y pausa pedagógica) y `AP`
> (`v3.75.7`).
>
> **Añadido (2026-09-22 · arco `v3.77.1..v3.80.0`).** Después de `AQ`, el punto de
> entrada anclado en `v3.80.0` **reserva `AR`**
> (`docs/audit/AR-AUDITORIA-TOTAL-V380.md`), que es por tanto el **primer libre**.
> No se renombra ningún dossier ya publicado: la reserva la declararon los propios
> puntos de entrada **dentro de sus tags**, y reescribirla sería falsear historia.
> Recuento vigente de reservas **sin informe recibido**: `AG`, `AH`, `AI`, `AJ`
> (motor y pausa pedagógica), `AP` (`v3.75.7`) y `AQ` (`v3.77.1`) — **seis** entradas
> externas entregadas y **ningún** informe dictaminado, que es la deuda de proceso
> que la pregunta A5 del punto de entrada de `v3.80.0` pone encima de la mesa.

**Regla de proceso (premisa 5 y 12):** todo trabajo se descompone en subagentes
autocontenidos (`agentes/*.md`), vigilando la saturación de contexto de todos los agentes.
Antes de alucinar, se reinicia el contexto apoyándose en `docs/`.

## Siguiente incremento (planificado)

- **✅ V3.70 — Auditoría pedagógica + CEFR (cinco ejes AA–AE + síntesis AF)**
  (**release `v3.70.0`, 2026-09-15**): **HECHA** (release de **medición**, no de
  capacidad). Con el motor adaptativo **cerrado y validado** por V3.69 (cadena
  completa demostrada por HTTP y **diff de producto cero**), el foco pasó del
  núcleo adaptativo al **rigor pedagógico de lo que ese núcleo sirve**. Se auditó
  en cinco ejes con instrumentos **deterministas y solo lectura** (5 subcomandos
  nuevos en `backend/scripts/audit_dossier.py`, salida regenerable en
  `docs/audit/generated/`): **AA · contenido/CEFR**, **AB · cobertura de
  destrezas**, **AC · feedback/corrección**, **AD · validez de la maestría**,
  **AE · instrumentos de nivelación**, más la síntesis **AF**. Resultado:
  **1 P0 · 15 P1 · 12 P2 · 5 P3** (33 hallazgos abiertos) y **4 propiedades
  positivas** verificadas, con **48 tests** nuevos que fijan cada hallazgo
  (si alguien cierra un hueco, el test falla y obliga a re-auditar el eje).
  Los 6 P2 de la auditoría de V3.69 **siguen abiertos** por decisión de alcance.
  **V3.70 no corrige nada**: asigna cada insuficiencia a su fase (contenido →
  V4.0.x · motor y acreditación → Planner 4.0 · instrumentos → V4.0.x/V3.72).
  Dossiers: `docs/audit/AA-PED-CONTENIDO-CEFR.md` … `AF-SINTESIS-PEDAGOGICA-V370.md`.

- **✅ V3.71 — Runtime / offline / instalación** (**release `v3.71.0`,
  2026-09-16**): **HECHA**. Incremento **de verificación con endurecimiento
  mínimo** en **seis ejes** sobre el briefing
  `agentes/v371-runtime-offline-instalacion.md` (offline real con red desconectada
  · instalación limpia desde cero · runtime de producto y salud honesta ·
  dependencias ocultas y degradación · gates/CI/deriva documental · síntesis), con
  las **cuatro decisiones de alcance** del gerente aplicadas: **(A)** medir y
  **declarar** la frontera de `npm run dev` · **(B)** verificar y **guiar** el
  bootstrap de Ollama · **(C)** corregir la documentación **a favor de
  `config.py`** · **(D)** añadir el **job del launcher al CI**.
  **Resultado:** **CI 7/7** (el launcher deja de ser el único subsistema sin
  gate), **4 derivas documentales** corregidas y fijadas por **8 tests**, el **P1
  de TTS/offline cerrado** (el `timeout` era **código muerto** y la única
  dependencia de Internet en ruta de producto estaba **sin límite**), la **salud
  de la UI honesta** (tres estados; antes decía «Conectado» con la BD caída), el
  **sondeo de Ollama acotado** (un Ollama lento se disfrazaba de backend caído),
  la **voz inglesa por defecto** alcanzable por la vía de producto (antes **no se
  podía auto-descargar**), **verificación previa de instalación** de solo lectura
  y **runbook** con el `ollama pull` explícito.
  **Hallazgos: P0 = 0 · P1 = 1 (cerrado) · P2 = 15 · P3 = 14.** Quedan **3
  abiertos que exigen acción humana** (RA-02 endpoint de Ollama sin declarar en
  `config.py`, RA-05 corte de red real de los 12 flujos, G5 matriz de
  dispositivos), **1 parcial** (RA-01, con su mitad de UI fechada en V3.72) y
  **2 declarados con condición de salida** (RC-01 Node como requisito de
  ejecución; RB-05 máquina limpia real). Dossiers:
  `docs/audit/RE-GATES-DERIVA.md`, `RA-RUNTIME-OFFLINE.md`, `RB-INSTALACION.md`,
  `RC-RUNTIME-PRODUCTO.md`, `RD-DEPENDENCIAS-OCULTAS.md` y
  `RF-SINTESIS-RUNTIME-V371.md`. Los
  tracks **P1–P6 de M13** (política pedagógica formal,
  error mastery, vocabulario exposure/production/mastery, listening como
  competencia, CEFR basado en evidencia y pronunciación fonémica) quedan
  **medidos y acotados** por V3.70 pero **no cerrados**: su corrección se asignó
  a **V4.0.x** (contenido) y **Planner 4.0** (motor y acreditación).

- **🔄 V3.72 — UX / product completion**: **siguiente incremento** declarado por
  el roadmap (**sin cambios**). Debe recoger lo que V3.71 dejó **fechado** en vez
  de cerrado: **(a)** el **vector UI del P1 de TTS/offline** (aviso de descarga,
  progreso y **consentimiento** del usuario, y consumo de las cabeceras
  `X-TTS-Voice`/`X-TTS-Degraded`, que el backend **ya expone** para que la UI no
  tenga que inventarse el dato); **(b)** la **reevaluación de RC-01** con la
  pregunta «¿qué debe tener instalado el usuario?» (servir `frontend/dist` si se
  decide que Node deje de ser requisito de ejecución); **(c)** lo que la revisión
  de UX del producto determine. Roadmap posterior: **V3.73** auditoría final
  técnica → **V4.0** release final («English Tutor, primera versión completa y
  estable») y a partir de ahí `V4.0.x` (mantenimiento y calibración, **no**
  construcción del núcleo).

- **✅ V3.69 — E2E + Adaptive Engine Validation (el circuito completo de una
  pieza)** (**release `v3.69.0`, 2026-09-15**): **HECHA**. Origen: roadmap
  acordado en la auditoría `X` de V3.67 y **revisado por la auditoría `Y` de
  V3.68**, tras **congelar el diseño del motor adaptativo** (0 P1 y ningún
  hallazgo que justifique otra capa arquitectónica). La prioridad **no** era
  añadir funcionalidad, sino **demostrar experimentalmente** que el circuito
  funciona como uno solo:
  `Evidence → Student State → Decision Projection → Task selection → Decision →
  Serving → Attempt → Outcome → Evidence`.
  **Regla dura declarada (auditoría `Y` §28):** *V3.69 no debe introducir
  arquitectura nueva salvo que una prueba E2E demuestre que la arquitectura
  actual es insuficiente.* **Resultado: ningún escenario la demostró
  insuficiente ⇒ no se tocó producción** (el diff de producto es **cero en lógica**:
  solo los bumps de versión); las
  cinco desviaciones medidas se registran como **deuda aceptada** en la release
  note.
  **Batería obligatoria E01–E19, escrita y verde** (briefing ejecutable
  `agentes/v369-e2e-adaptive-validation.md`): E01 alumno nuevo · E02 skill débil
  (`speaking` débil/`writing` fuerte) · E03 retención (`mastered` → review due →
  repaso) · E04 brecha de transferencia (reconocimiento/recall fuertes y
  producción débil) · E05 transferencia de contexto (misma tarea, dos contextos →
  `task_key` igual, `task_instance_key` distinto) · E06 fallo (`ok, ok, ko` →
  cambia el `p_success`) · E07 incertidumbre ASR (`unclear` no penaliza mastery,
  no entra en calibración, conserva provenance) · E08 abandono (no contamina
  `ko`) · E09 refresh (`GET ×3` → un solo `decision_id`, sin duplicar decisiones)
  · E10 doble submit (idempotente) · E11 submit contradictorio (rechazado) · E12
  usuario ajeno (no modifica nada) · E13 target ajeno (rechazado) · E14
  transición inválida (`computed → completed`, rechazada) · E15 serving stale
  (`> 24 h` → `abandoned`) · **E16 determinismo del Planner** (mismo estado +
  fingerprint + candidatos + política → mismo task, `p_success`, ELV, razón y
  `decision_id`, **siempre**) · **E17 dependencia de apoyo** (hueco servido −
  acreditado → penalización declarada `SCAFFOLDING_PENALTY = 0.2`, aserción
  **diferencial**) · **E18 evidencia entrando DURANTE la decisión** (frescura por
  HTTP + reproducción determinista del TOCTOU de V3.64.1) · **E19 dos alumnos
  activos** (coexistencia sin mezcla de estado/cola/`decision_id`, **en ambas
  direcciones**; E12 cubre el rechazo de propiedad ajena). Con E17/E18/E19 el
  mapeo con los **10 casos originales** de la auditoría `X` queda **completo**
  (casos (3), (8) y (10), que la batería inicial no cubría o cubría solo
  parcialmente). Se cierra además el endpoint huérfano
  `GET /api/learning/decisions` (calibración + provenance health), que **ya
  tiene cobertura HTTP** (`test_e16b_decisions_endpoint_reports_calibration_and_health`),
  y el contrato del cliente queda fijado con red mockeada en
  `frontend/tests/visual/drillProvenance.spec.ts` (2 specs de navegador).
  **Entregado:** `backend/tests/test_adaptive_e2e_v369.py` (**20 tests**,
  2552 backend en total), 2 specs de navegador, `release-notes-v3.69.0.md` con
  la tabla de los **5 hallazgos aceptados** (E01(a), E08, E15, E17 y §F-1).
  Roadmap posterior declarado (**sin cambios**):
  **V3.70** auditoría pedagógica/CEFR (**siguiente**) →
  **V3.71** runtime/offline/instalación →
  **V3.72** UX/product completion → **V3.73** auditoría final técnica →
  **V4.0** release final («English Tutor, primera versión completa y estable») y
  a partir de ahí `V4.0.x` (mantenimiento y calibración, **no** construcción del
  núcleo).

- **✅ V3.68 — Adaptive Engine Hardening & Integrity**
  (**release `v3.68.0`, 2026-09-15**): plan Cursor
  `v3.68_adaptive_engine_hardening` ejecutado. Origen: la auditoría de V3.67
  (tres P1 de segunda generación + P2-08). Entregado: **Task vs Task Instance**
  (`task_key` de definición, sin contexto, que es lo que el Planner puede
  calcular antes de elegir instancia, frente a `task_instance_key` de
  instancia: el cierre real del P1-01, porque la firma de V3.67 incluía el
  contexto y el candidato lo construía vacío, de modo que una tarea de
  transferencia del ledger **nunca** casaba), **FSM real y probada** del ciclo
  de vida (`_ALLOWED_TRANSITIONS` + compare-and-set + `close_stale`),
  **integridad y propiedad** del provenance (guardas de `user_id`/`target_id`
  con fallo best-effort no-op contabilizado en `transition_health()`),
  **calibración honesta** (P2-08: `unclear`/`abandoned` fuera del denominador)
  y — por primera vez en la serie — el **eslabón de FRONTEND** que hace que el
  ciclo se ejecute de verdad (`decision_id` en cada GET/POST del peldaño y
  `started`/`abandoned` al cargar/desmontar el drill). Detalle en
  `release-notes-v3.68.0.md`.

- **✅ V3.65 — Observed Difficulty 3.0 (`P(éxito | alumno, tarea)` empírica)**
  (**release `v3.65.0`, 2026-09-15**): briefing `agentes/v365-observed-difficulty-3.md`
  ejecutado. Origen: el roadmap de la auditoría `W` de V3.63 y
  `release-notes-v3.64.0.md` §«Honestidad». Entregado: lector de telemetría
  completa (`list_attempt_rows`, éxitos + fallos + `target_id`), identidad de tarea
  en la fila canónica, estimador puro `empirical_success(rows)` por pareja (misma
  puerta espaciada de V3.54) y seam aditivo en Decision Projection + Planner 3.0
  (`p_success` empírico cuando la pareja lo declara, **byte-idéntico** si no).
  Detalle en `release-notes-v3.65.0.md`.

- **🗄️ V3.66 — Adaptive Instance Selection (histórico, superado por V3.67)**:
  bloque **obsoleto** conservado solo como traza del plan: V3.66 se entregó
  finalmente como **Task-Level Empirical Success + Decision Provenance**
  (`release-notes-v3.66.0.md`) y la **selección adaptativa de instancia** quedó
  declarada **fuera de alcance** en V3.68 (el nivel de instancia se **nombra,
  deriva y observa** con `task_instance_key`/`empirical_success_by_task_instance`,
  pero **no puntúa el argmax**). Candidatos que siguen abiertos de aquella lista:
  el **Sense Engine** (`surface ≠ sense`), el **Decision Provenance completo**
  (identidad lógica `serving_id`/`attempt_id`, P2-03/P2-04 de la auditoría `Y`) y
  la **calibración real** con datos (P2-05).

- **✅ V3.63 — Observed Task Difficulty 2.0 y honestidad del Student Skill State**
  (**release `v3.63.0`, 2026-09-14**): briefing autocontenido y ejecutado
  `agentes/v363-observed-task-difficulty-2.md`. Origen: la auditoría profunda de
  V3.62 (`docs/audit/U-AUDITORIA-TOTAL-V362.md`, 9,5/10 APROBADA) y su punto de
  entrada externo (`agentes/auditoria-externa-v362.md`). Alcance entregado:
  dificultad **empírica** de la tarea (`declared → served → outcome → observed`)
  con tablas declaradas sobre las filas canónicas, **identidad de
  evidencia y ocasiones** (observaciones vs ocasiones independientes), **canal
  observado** (P1-02: `spontaneous_use` escrito → `interaction`, oral → `speaking`),
  **confianza de evaluación** separada de la estadística, **criterio declarado de
  pronunciación** (lo que la ruta ya puntúa, sin inventar rúbrica), **eje declarado
  de capas de listening** (reutilizando `SKILL_LAYER`), **frescura de la caché del
  estado** (fingerprint + columna aditiva `skill_state_source`) y el **seam de
  política del gate**. **La decisión de tareas siguió intacta** (ELV, planner,
  `difficulty` y `transfer.context_for` byte-idénticos; guard estructural de V3.62
  verde **sin tocarse**). Detalle en `release-notes-v3.63.0.md`.

- **⏳ V3.53+ — candidatos abiertos (histórico; auditoría externa de V3.52 EJECUTADA
  y sus P2 CERRADOS en V3.52.2)**: informe en `docs/audit/Q-AUDITORIA-TOTAL-V352.md`
  (→ sin P0/P1). **Cerrados en V3.52.2:** P2-01 (`CEFR_CAPACITY` = envelope
  monótono del banco + invariante de encaje por nivel) y P2-02 (tolerancia
  documentada como red de seguridad con test de inercia y de discriminación
  sintética); etiqueta `v3.52.1` creada (P3-04). **Siguen abiertos y aceptados:**
  P3-01 (fila legacy etiquetada `practice` en vez de `estimated`) y P3-02
  (`_context_vector` trata un contexto sin vector como vector). Candidatos de
  producto ya documentados: **Sense Engine 2.0**
  (`surface→lemma→sense→semantic_fit`), **P1-02 Learner Skill State 2.0 +
  `observed_difficulty` persistido por evento** (**briefing listo para lanzar:
  `agentes/v353-learner-skill-state.md`**), **P1-03 Planner 2.0 /
  `expected_learning_value`**, **deuda de planner confirmada**
  (`assessed_skill` → decisión del planner y `skill_priorities` → `select_task`,
  con el doble conteo de `written_production` por resolver; V3.55), **entrega
  oral real del transfer** (audio + STT), Context Bank Family/Instance, offline
  TTS y code splitting del frontend. Del backlog histórico siguen abiertos los
  P2/P3 del dossier K (F-K3…F-K7) y los ítems de `docs/audit/PARKED.md`;
  comprobar su estado contra el árbol antes de adoptarlos.

- ~~**⏳ V3.38 — `situación` + planner (Optimal Next Task)**~~ ✅ **cerrado
  (2026-09-10, v3.38.0 + v3.38.1)**: implementado y publicado (ver «Estado
  actual» arriba, `release-notes-v3.38.0.md`/`v3.38.1.md` y
  `agentes/v338-situacion-planner.md`). El enunciado situacional, el planner
  (Optimal Next Task) y la automaticidad por skill están en producción; la
  historia posterior a V3.38 vive en `CHANGELOG.md` y `docs/RELEVO.md`.

- ~~**⏳ V3.37 — Cues graduados y planner sobre la evidencia**~~ ✅ **cerrado
  (2026-09-10, v3.37.0)**: implementado y publicado (ver «Estado actual» arriba y
  `release-notes-v3.37.0.md`). La escalera graduada
  (`translation < definition < cloze`), la automaticidad espaciada y la cola de
  repaso con `recommended_cue`/`automatic` ya están en producción; `situación` y
  el planner se rebasan a V3.38.

- ~~**⏳ V3.36 — Learning Evidence 2.0**~~ ✅ **cerrado (2026-09-10, v3.36.0)**:
  implementado y publicado (ver «Estado actual» arriba y
  `release-notes-v3.36.0.md`). `support_level`, `difficulty`, `response_time_ms`,
  `error_type`, `context_id`/`activity_id` ya se capturan y agregan. Los cues
  graduados y el planner se rebasan a V3.37.

- ✅ **V3.29 — Listening Engine 4.0 Fase 3 (núcleo) cerrado (2026-09-09,
  v3.29.0)**: implementado (ver "Estado actual" arriba,
  `release-notes-v3.29.0.md`). Núcleo de la Fase 3 de
  `docs/LISTENING_ENGINE_4.0.md` cerrado (alineación por palabra offline
  `word_alignment_proxy`, karaoke, controles precisos, salto a la palabra
  fallada y evidencia `word_breakdown_json`). El diccionario de consulta se
  reprioriza a V3.30 (siguiente candidato).

- ~~**⏳ V3.30 — Diccionario de consulta con marcas de uso y aprendizaje**~~ ✅
  **cerrado (2026-09-09, v3.30.0)**: implementado y publicado (ver «Estado
  actual» arriba, `release-notes-v3.30.0.md` y `docs/DISENO-V330-DICCIONARIO-CONSULTA.md`).
  Quedan abiertos hacia **V3.31** los candidatos que V3.30 había diferido:
  consumo de `word_breakdown_json` en agregados / práctica dirigida de las
  palabras falladas y palabras tocables en transcripts/chat.

- ~~**⏳ V3.30.1 — Endurecimiento del diccionario (auditoría V3.30.0)**~~ ✅
  **cerrado (2026-09-09, v3.30.1)**: implementado y publicado (ver «Estado
  actual» arriba y `release-notes-v3.30.1.md`). Cierra los tres P1 de la
  auditoría (single-flight de generación, política `UNUSABLE_MODELS` frente al
  modelo explícito, caché versionada con `generator_version`) y el P2 del
  parser JSON. **Próximo candidato (rebasado a V3.32 por el cierre de V3.31)**:
  Dictionary → Learning Bridge (borrador en `agentes/v332-dictionary-learning-bridge.md`)
  — convertir la consulta en puerta al aprendizaje con «Practicar» explícito
  sin contaminar evidencia (D3 intacta), más los diferidos de V3.30.

- ~~**⏳ V3.31 — Cierre de la auditoría V3.30.1 (robustez y contrato del
  diccionario)**~~ ✅ **cerrado (2026-09-09, v3.31.0)**: implementado y
  publicado (ver «Estado actual» arriba y `release-notes-v3.31.0.md`). Cierra
  los hallazgos residuales de la auditoría de V3.30.1: cancelación del dueño
  del vuelo sin colgar a los waiters + tope de espera defensivo, invalidación
  del contenido de caché previo a V3.31 (`GENERATOR_VERSION` `1.1.0` + marca
  `DICTIONARY_LEGACY_VERSION` en la migración), tests de la migración de
  upgrade y del path real con modelo no utilizable, y contrato frontend del
  diccionario (tipo `DictionaryLookupRequest`, test del endpoint y timeout de
  cliente). **Próximo candidato V3.32**: Dictionary → Learning Bridge
  (borrador en `agentes/v332-dictionary-learning-bridge.md`).

- ~~**⏳ V3.31.1 — Hardening del diccionario (cierre de la auditoría V3.31.0)**~~ ✅
  **cerrado (2026-09-09, v3.31.1)**: implementado y publicado (ver «Estado
  actual» arriba y `release-notes-v3.31.1.md`). Cierra el P1-01 residual y los
  P2 de robustez del diccionario: `pick_model` con explícito instalado +
  utilizable, negative cache con TTL de generación, rate limit de generación
  nueva por usuario/global y tope servidor del dueño del vuelo (90 s), más la
  semántica documentada del contenido canónico. **Próximo candidato V3.32**:
  Dictionary → Learning Bridge (borrador en
  `agentes/v332-dictionary-learning-bridge.md`).

- ~~**⏳ V3.32 — Dictionary → Learning Bridge (primer eslabón)**~~ ✅ **cerrado
  (2026-09-09, v3.32.0)**: implementado y publicado (ver «Estado actual» arriba
  y `release-notes-v3.32.0.md`). Primer eslabón del puente: «Practicar esta
  palabra» en la tarjeta del lookup reutiliza la escalera de drill existente
  (Recall → Sentence) con evidencia idéntica a practicar fuera del diccionario
  (D3 intacta). Siguiente incremento hacia **V3.33**: los diferidos de V3.30
  (consumo de `word_breakdown_json` en agregados/práctica dirigida de las
  falladas y palabras tocables en transcripts/chat) y los siguientes eslabones
  del puente (escaleras por destreza — reconocimiento MCQ, recall demorado con
  FSRS — y transferencia por contexto, según `agentes/v332-dictionary-learning-bridge.md`).

- ~~**⏳ V3.33 — Recognition (MCQ definición ↔ palabra), eslabón 2 del
  puente**~~ ✅ **cerrado (2026-09-09, v3.33.0)**: implementado y publicado
  (ver «Estado actual» arriba y `release-notes-v3.33.0.md`). Segundo eslabón
  del Dictionary → Learning Bridge: peldaño `1 · Recognize` en la escalera
  compartida con pregunta determinista servida y puntuada por el backend y
  evidencia SOLO informativa. Siguiente incremento hacia **V3.34**: los
  diferidos de V3.30 (consumo de `word_breakdown_json` en agregados/práctica
  dirigida de las falladas y palabras tocables en transcripts/chat) y los
  eslabones restantes del puente — recall demorado con FSRS y transferencia
  por contexto de actividad V3.23 (según `agentes/v332-dictionary-learning-bridge.md`).

- ~~**⏳ V3.34 — Recall 2.0 (recuperación por texto + FSRS), eslabón 3 del
  puente**~~ ✅ **cerrado (2026-09-10, v3.34.0)**: implementado y publicado
  (ver «Estado actual» arriba, `release-notes-v3.34.0.md` y
  `agentes/v334-recall-2.0.md`). El peldaño intermedio del drill pasa a ser
  recuperación real por texto (cue = significado, nunca la palabra): señal de
  recall propia (`recall_successes`/`recall_days` + ledger `recalled`),
  recuperación demorada si supera el intervalo y reprogramación FSRS `lexicon`
  con intervalos reales; la escalera queda `1 · Recognize` · `2 · Recall` ·
  `3 · Sentence`, con el micrófono solo en Sentence. Siguiente incremento hacia
  **V3.35**: los diferidos de V3.30 (consumo de `word_breakdown_json` en
  agregados/práctica dirigida de las falladas y palabras tocables en
  transcripts/chat), la transferencia por contexto de actividad V3.23 y el
  Lexical Evidence Engine / Evidence Graph como fuente longitudinal.

- ~~**⏳ V3.19 — Léxico por destreza + Speaking micro-drill**~~ ✅ **cerrado
  (2026-09-07, v3.19.0)**: implementado con las decisiones cerradas de diseño
  (ver "Estado actual" arriba, `release-notes-v3.19.0.md` y la entrada 37.37 de
  `docs/RELEVO.md`). Tests: pytest 1371 + ruff limpio, vitest 417 + `tsc`/
  `vite build` OK, `check_release_consistency` 3.19.0 exit 0, curriculum
  `--strict --quality` exit 0; CONSTITUCIÓN sin cambios (R8/R9 propuesta
  abierta). Fuera de alcance de V3.19 (decisión (b)/futura): micro-drill 3
  niveles + integración con el grafo (GRAPH-01), flag de modalidad oral/tecleo,
  WR-UI-01, siembra FSRS sin señal (LEX-03).
- **V3.24 — Calibración de salida del Student Model (diseño cerrado
  2026-09-08)**: alcance decidido por el gerente = los 2 hallazgos **P1** del
  dossier `docs/audit/K-AUDITORIA-STUDENT-MODEL-V323.md` + **F-K8** (prerequisito
  de test de F-K2). Decisiones cerradas:
  - **F-K1 (decisión b) — relajar a lo emisible**: `MASTERY_EVIDENCE_REQUIREMENTS`
    queda `familiar×2 + transfer×2 + delayed` (sin `novel`); `novel_required=0`
    en las 12 celdas macro (B2/C1/C2 × listening/speaking/reading/writing) de
    `cefr_matrix.json`; el kind `novel` queda **reservado** y la frontera se
    documenta (sin emisor real, ningún gate debe exigirlo).
  - **F-K2 (decisión a) — anclaje por niveles completados + progreso en el
    tramo actual**: `adaptive.estimated_level` deja de proyectar `1 + 5·overall`
    y pasa a anclar: con niveles completados, el suelo es `CEFR_NUMERIC[mayor
    completado]`; sin completados, el suelo es el centro Pre-A1 (0.5, tramo
    A1) y la etiqueta nunca supera el nivel actual sin certificación previa.
    `build_student_model` pasa `current_level` + `completed_levels`.
  - **F-K8**: tests e2e del salto A1→A2 (premisa 12 del dossier K), escritos
    primero (fallan hoy) y que fijan: (a) dominar A1 no estima ≥ B2; (b) aprobar
    el examen A1 no baja el estimado por debajo de A1.
  El briefing autocontenido (rol/tarea/aceptación) vive en
  `agentes/v324-calibracion-salida.md`. **Todo lo pendiente hacia V3.24 queda
  consolidado en `docs/RELEVO.md` → sección 38** (backlog completo, fronteras y
  primeros pasos). El dossier K supera en contexto al briefing antiguo de
  auditoría TOTAL v3.18 (`agentes/auditoria-total-externa.md`).

