# v3.33.1 — Hardening de Recognition (auditoría V3.33.0)

**Endurecimiento del peldaño Recognition publicado en V3.33.0, a partir de la
auditoría externa. Dos correcciones P1 sin tocar la arquitectura de evidencia ni
la seguridad del scoring (el GET sigue sin exponer la correcta):

1. la posición de la respuesta correcta deja de ser fija por palabra: el
   `GET drill/recognition` entrega un `question_id` (nonce por intento) que
   funciona como seed del barajado y el `POST` reenvía para reconstruir la misma
   permutación (premisa 21: sigue sin estado servidor). Reintentar la misma
   palabra rebaraja las opciones, así que no se puede memorizar «la primera es la
   correcta»;
2. el drill arranca de verdad en el primer peldaño (`Practicar → Recognize →
   Recall → Sentence`) y solo degrada a Recall si no hay pregunta
   (`available=false`).

La evidencia sigue siendo SOLO informativa (V3.13): el acierto de Recognition no
escribe en `vocabulary`, no mueve FSRS/mastery/usage y no saca la palabra de
candidatas. Cambio de contrato HTTP **aditivo** (`question_id` opcional); sin
cambios de esquema de BD.

Versión de app `3.33.0 → 3.33.1`. Backend (hash + seed + schemas) + frontend
(arranque del drill + API + tests) + docs.

## Qué cambia

### 1. P1-01 — Seed de intento stateless (`dictionary_mcq.py`)

`backend/services/dictionary_mcq.py`:

- `recognition_options_for(word, entries, seed="")` deriva la permutación de
  `palabra + seed` (`_place_options(f"{target_word}:{seed}", …)`). La selección
  de distractores NO cambia: sigue siendo determinista por palabra; el seed solo
  altera el orden.
- **P2:** `_stable_int` pasa de la suma ponderada por posición (colisionaba entre
  palabras distintas) a `SHA-256(text)` (primeros 8 bytes): estable entre
  procesos/máquinas y con mejor dispersión del índice de la correcta. Se aplica
  SOLO al MCQ de diccionario: `listening_bottom_up` conserva su hash porque sus
  ids derivados son content-stable y cambiarlo re-barajaría ítems ya publicados.

**Sin firma del seed.** El seed solo permuta; la correcta se identifica en el
servidor por texto y nunca viaja en el GET (además, la traducción ya es visible
en el lookup). Manipularlo no permite acertar ni filtrar la respuesta, así que
firmarlo añadiría clave/estado sin nada real que proteger.

### 2. Dominio, endpoints y schemas (contrato aditivo)

`domain/vocabulary.py`:

- `get_recognition_question(user_id, word)` genera
  `question_id = secrets.token_urlsafe(8)`, lo usa como seed y lo devuelve:
  `{word, available, options, question_id}`. La correcta se sigue sin exponer.
- `submit_recognition_attempt(user_id, word, selected_index, question_id="")`
  recomputa con el MISMO seed → misma permutación → scoring consistente.

`schemas/vocabulary.py`: `RecognitionQuestionOut.question_id: str = ""` y
`RecognitionAttemptIn.question_id: str = Field(default="", max_length=64)`.
Ambos opcionales: un cliente antiguo (sin el campo) sigue funcionando con el
seed por defecto `""`.

`routers/vocabulary.py`: el POST reenvía `body.question_id`. El evento
`drill:<word>:recognition:ok|ko` y los códigos (409 sin pregunta, 422 índice/
palabra) no cambian.

Cliente: `types/api.ts` (`DrillRecognitionQuestion.question_id`),
`api/vocabulary.ts` (`submitDrillRecognitionAttempt(..., questionId)`).

### 3. P1-02 — El drill arranca en Recognition (`wordDrill.tsx`)

- `WordDrill` abre en `step="recognition"` (antes `"recall"`) y carga la pregunta
  sola, sin exigir un clic manual en `1 · Recognize`.
- `loadRecognition()` siempre pide una pregunta nueva (nuevo `question_id` por
  intento) y reinicia opción/feedback; se invoca al montar/cambiar de palabra y
  cada vez que se entra en el peldaño desde otro.
- Si la respuesta llega con `available=false`, degrada a Recall con
  `setStep(current => current === "recognition" ? "recall" : current)`: la
  degradación no pisa una elección manual de otro paso (p. ej. el alumno ya está
  en Sentence). Si falla la red, se mantiene Recognize con su aviso y Recall
  sigue accesible.

Flujo resultante:

```
Practicar esta palabra
  ├── Recognition disponible → 1 · Recognize → 2 · Recall → 3 · Sentence
  └── Recognition no disponible → 2 · Recall → 3 · Sentence
```

## Verificación

- Backend: `pytest` → **1723 passed** (+1 neto) + `ruff check .` limpio.
  `test_dictionary_recognition_v333.py`:
  - nuevo test puro de permutación por seed: mismo seed ⇒ misma pregunta y mismo
    orden; seeds distintos ⇒ mismas opciones pero la correcta cambia de posición;
  - determinismo y aislamiento A/B reescritos sobre `question_id` (comparación
    de `set(options)`, el GET nunca expone `correct_index`, cada GET trae seed);
  - acierto/fallo siguen registrando solo `drill:<word>:recognition:ok|ko` con
    cero cambios en `vocabulary`/`vocabulary_events`; sin entrada/sin
    distractores → `available=false` con `question_id=""` y POST 409 sin evento.
- Frontend: `vitest` → **63 ficheros / 547 tests passed** (+1) + `tsc --noEmit`
  limpio. Novedades: el drill abre en Recognize y carga solo (sin clic);
  «reentrar en `1 · Recognize` pide una pregunta nueva»; `available=false`
  degrada a Recall y la escalera sigue accesible. Los tests existentes del
  puente V3.32 que abren el drill conservan su intención declarando Recognition
  no disponible.
- `python scripts/check_release_consistency.py` → **3.33.1** exit 0.

## Documentación

- `CHANGELOG.md` con la entrada `[3.33.1]`; `PLAN.md` con el hito estable
  V3.33.1 al frente de «Estado actual»; nota de cierre en `docs/RELEVO.md`.
- `agentes/v3331-recognition-hardening.md` (briefing: hallazgos de la auditoría,
  decisiones y contrato).

## Fuera de alcance (diferido, según la auditoría)

- Banco de distractores con similitud semántica/CEFR/campo léxico (siguiente fase
  del Dictionary Bridge; sigue determinista, sin LLM en tiempo real).
- `event_role` (evidence/telemetry/informative) en `learning_events`.
- Latencia como señal de automaticity; `recognition_attempts`/retention.
- Trocear `wordDrill.tsx` en `RecognitionStep`/`RecallStep`/`SentenceStep`.
- **V3.34**: recall demorado con FSRS + transferencia contextual.
