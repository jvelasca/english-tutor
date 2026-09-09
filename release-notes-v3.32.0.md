# v3.32.0 — Dictionary → Learning Bridge, primer eslabón: «Practicar esta palabra»

**La consulta del diccionario (V3.30, D3: solo lectura) se convierte en puerta
a la práctica real: la tarjeta del lookup gana «Practicar esta palabra», que
monta in-line la escalera de drill existente (Recall → Sentence) para la
palabra consultada. Sin un solo endpoint nuevo —los endpoints de drill ya
aceptan palabras arbitrarias—, sin etiquetas de origen en la evidencia y con
D3 intacto: el lookup sigue sin escribir nada; solo la acción explícita
«Practicar» y su resultado escriben en el Student Model.**
Versión de app `3.31.1 → 3.32.0`. Frontend (UI + refactor de extracción) +
backend de tests de aceptación; sin cambios de esquema de BD ni de contrato
HTTP.

## Qué cambia

### 1. «Practicar esta palabra» en la tarjeta del lookup (`DictionaryLookup.tsx`)

El puente es una acción explícita del alumno sobre una palabra consultada. La
tarjeta de resultado del diccionario (`ResultCard`) gana, junto al
`ListenButton` de la cabecera de la palabra, una acción secundaria que pone
`practiceWord = entry.word`; `DictionaryLookup` mantiene ese estado local y, al
activarse, monta el `WordDrill` in-line bajo la tarjeta (userId + word). Gating
idéntico al resto de la práctica: sin `userId` el botón no aparece. Al producir
la palabra en el drill (`onProduced`), la entrada se re-consulta en silencio
(`refreshEntry`) para actualizar las marcas de uso —`usage.tracked` y su
producción— sin interrumpir la escalera ni resetear el estado del lookup.
Nuevas claves i18n es/en `dictionary.lookup.practiceCta` y
`dictionary.lookup.practiceHint`; el contenido de la escalera reutiliza las
claves `dictionary.drill.*` existentes.

Se puede practicar **cualquier palabra consultada**, también `usage.tracked=false`
(sin fila previa en `vocabulary`): el intento con éxito crea su fila como
producción pura (`speaking_prod=1`, `production_count=1`, `exposure_count=0`),
igual que si se practicara fuera del diccionario.

### 2. Refactor de extracción neutro (`wordDrill.tsx`)

`WordDrill`, `SpeakingDrillSection`, el tipo `DrillStep` y el helper
`isSentenceAttempt` eran privados de `PersonalDictionary.tsx`. Se extraen a
`frontend/src/features/vocabulary/wordDrill.tsx` como módulo compartido y
`PersonalDictionary.tsx` pasa a importarlos: misma UI, mismo comportamiento,
cero cambio de contrato. Regresión cubierta por `PersonalDictionary.test.tsx`
y por la suite vitest completa (sin tocar `vocabulary.test.ts`).

### 3. Cierre del puente: evidencia idéntica, sin etiquetas de origen

Practicar desde el diccionario usa exactamente los mismos endpoints que el hub
de Vocabulario (`POST drill/attempt`, `GET drill/sentence-context`,
`POST drill/sentence-attempt`): un éxito llama
`record_production_text(user, word, "speaking", as_unit=True, activity="drill")`
(con retrieval si hay ancla) y registra `learning_events` `drill:<word>:ok`
(o `drill:<word>:sentence:ok` en el paso frase). El Student Model no persiste
«vino del diccionario» como campo de evidencia: la fila creada al practicar
desde el lookup es bit a bit la misma que al practicar esa palabra
directamente. Invariante D3 heredada: el lookup en sí sigue sin crear filas ni
eventos (segunda mitad del acceptance).

## Verificación

- Backend: `pytest` → **1711 passed** (+3 sobre v3.31.1, el nuevo
  `test_dictionary_bridge_v332.py`) + `ruff check .` limpio. El dossier usa el
  patrón de aceptación HTTP con `TestClient` (un único `with TestClient(app)`
  por test para no re-ejecutar el lifespan/`init_db()` —el backfill V3.19 de
  `chat_prod` re-etiquetaría filas modernas de speaking-only—) y el generador
  de contenido aislado con fetcher offline para degradar a
  `definition_source="none"` de forma determinista:
  - `test_lookup_new_word_read_only_and_practice_writes_identical_evidence`:
    A consulta una palabra nueva → `usage.tracked=false`, cero filas y cero
    eventos (mitad D3); A practica tras consultar y B practica la misma
    palabra directamente → filas IDÉNTICAS en las claves de evidencia
    (`speaking_prod=1`, `production_count=1`, `exposure_count=0`,
    `chat_prod=0`), un evento `produced` (channel=speaking, activity=drill) por
    práctica y un `learning_events` `drill:quokka:ok`; la práctica de A no
    crea filas extra en B.
  - `test_sentence_step_after_lookup_equivalent_evidence_and_d3_closure`: el
    paso frase tras consultar acredita la misma evidencia (contexto de plantilla,
    detalle `drill:quokka:sentence:ok`) y una segunda consulta YA ve la
    palabra trackeada pero no crea filas ni eventos adicionales (cierre D3 sin
    regresiones).
  - `test_lookup_and_practice_isolated_between_users`: lo que hace A no toca
    el léxico de B (ni la consulta ni la práctica) hasta que B practica por su
    cuenta, y entonces crea su propia fila idéntica a la de A.
- Frontend: `vitest` → **63 ficheros / 542 tests passed** (incluye los casos
  nuevos de `DictionaryLookup.test.tsx`: el botón se renderiza con `userId` y
  `entry`, al pulsarlo se monta la escalera con la palabra consultada y el
  paso frase del drill refresca la entrada del diccionario en silencio; sin
  `userId` no se muestra) + `tsc --noEmit` limpio.
- `python scripts/check_release_consistency.py` → **3.32.0** exit 0.

## Documentación

- `PLAN.md`: hito estable V3.32.0 al frente de «Estado actual» (primer eslabón
  del puente) y cierre en «Siguiente incremento»; los diferidos de V3.30
  (consumo de `word_breakdown_json`, palabras tocables) y los eslabones
  siguientes del puente quedan como candidatos hacia **V3.33**.
- `CHANGELOG.md` con la entrada `[3.32.0]`; nota de cierre en `docs/RELEVO.md`.
- `agentes/v332-dictionary-learning-bridge.md` actualizado: primer eslabón
  implementado en v3.32.0 y aceptación cerrada; eslabones futuros marcados
  como pendientes.
