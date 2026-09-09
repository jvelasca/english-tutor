# Candidato V3.32 — Dictionary → Learning Bridge (primer eslabón implementado en v3.32.0)

> Rol: documento de diseño del candidato **V3.32**. El **primer eslabón**
> (puerta del diccionario → escalera de drill existente, «Practicar esta
> palabra») se implementó y publicó el 2026-09-09 en **v3.32.0**
> (`release-notes-v3.32.0.md`); los eslabones siguientes (escaleras por
> destreza, recall demorado, transferencia) y los diferidos de V3.30 quedan
> como candidatos abiertos para próximos incrementos. Antes de implementar un
> eslabón nuevo, revisar `docs/RELEVO.md` (nota superior), `PLAN.md` («Estado
> actual» y «Siguiente incremento») y el dossier
> `docs/DISENO-V330-DICCIONARIO-CONSULTA.md` (decisiones D1/D2/D3 de V3.30 que
> este candidato debe respetar).
> Borrador: 2026-09-09 · Primer eslabón cerrado: v3.32.0 (2026-09-09).

## Primer eslabón cerrado (v3.32.0)

- **Qué se implementó.** La tarjeta de `DictionaryLookup` gana «Practicar esta
  palabra» (`frontend/src/features/vocabulary/DictionaryLookup.tsx`), que monta
  in-line bajo la tarjeta la escalera de drill existente **Recall → Sentence**
  (`wordDrill.tsx`, extraída sin cambio funcional de `PersonalDictionary.tsx`).
  Al producir la palabra, la entrada se re-consulta en silencio para actualizar
  las marcas de uso. Cero backend nuevo: los endpoints de drill ya aceptan
  palabras arbitrarias (también `usage.tracked=false`).
- **Evidencia.** Un éxito de práctica crea exactamente la misma evidencia que
  esa práctica fuera del diccionario: `record_production_text(speaking,
  as_unit=True, activity="drill")` + `learning_events` `drill:<word>:ok` (o
  `:sentence:ok`), con fila de producción pura (`speaking_prod=1`,
  `production_count=1`, `exposure_count=0`). Sin etiquetas de origen en el
  Student Model. D3 intacto: el lookup sigue sin escribir nada.
- **Acceptance (`backend/tests/test_dictionary_bridge_v332.py`, +3).** Lookup
  read-only + práctica con evidencia idéntica entre usuarios A/B ·
  paso frase equivalente con cierre D3 (segunda consulta no crea filas ni
  eventos) · aislamiento entre usuarios.
- **Pendiente de este candidato (NO implementado en v3.32.0).** Los eslabones
  de las secciones «Escaleras por destreza» y «Frontend» abajo (reconocimiento
  MCQ sobre la definición, recall demorado con FSRS, transferencia por contexto
  de actividad V3.23 y la partición de componentes de la tarjeta cuando crezca).
  > **Cierre parcial (v3.33.0, 2026-09-09):** el eslabón **Recognition**
  > (peldaño `1 · Recognize` en la escalera compartida `wordDrill.tsx`, MCQ
  > definición ↔ palabra determinista con evidencia SOLO informativa
  > `drill:<word>:recognition:ok|ko`) se implementó y publicó en **v3.33.0**
  > (briefing `agentes/v333-dictionary-recognition-mcq.md`). Siguen pendientes:
  > recall demorado con FSRS, transferencia por contexto de actividad V3.23 y
  > la partición de componentes de la tarjeta cuando crezca.

## Objetivo

Convertir el diccionario de consulta (V3.30) en la **puerta natural de entrada
al aprendizaje adaptativo**, sin romper la decisión D3: «consultar» sigue
siendo solo lectura y **nunca** genera evidencia; «practicar» (una acción
explícita del alumno sobre una palabra consultada) crea una actividad real cuyo
éxito SÍ puede alimentar el Student Model.

                 DICTIONARY
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    Definition    Context      Usage
        │            │            │
        └────────────┼────────────┘
                     ▼
                PRACTICE
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
     Recognition   Recall   Production
          │          │          │
          └──────────┼──────────┘
                     ▼
                  Transfer
                     │
                     ▼
                 Retention
                     │
                     ▼
              Student Model

## Invariante fundamental (heredada de D3)

- **Consultar ≠ aprender.** Un lookup no crea filas en `vocabulary`, no registra
  eventos ni mueve mastery (ya blindado por tests en V3.30 y V3.30.1).
- **Practicar ≠ consultar.** El botón «Practicar» en la tarjeta del diccionario
  abre una actividad real; solo el resultado de ESA actividad (y no el mero
  lookup) puede escribir en el Student Model a través de los puntos de volcado
  existentes (`record_production`, `record_exposure`, retrievals, FSRS…).

## Arquitectura propuesta

1. **Semilla mínima (primer eslabón — IMPLEMENTADO en v3.32.0).** Acción
   «Practicar esta palabra» en la tarjeta del diccionario que reutiliza el
   micro-drill existente (V3.19–V3.21) con la escalera **Recall (decir la
   palabra) → Sentence (frase en contexto)** decidida con el usuario; NO se
   añadió paso nuevo de MCQ de reconocimiento. Se puede practicar cualquier
   palabra consultada, también `usage.tracked=false`: el intento con éxito
   crea su fila como producción pura. El volcado de producción sigue usando
   los canales/actividades actuales (`as_unit=True`, `activity="drill"`), de
   modo que la evidencia es idéntica a la de cualquier otra práctica y NO
   distingue su origen.
2. **Sin etiquetas de origen en el Student Model.** No se persiste «vino del
   diccionario» como campo de evidencia (evitaría contaminar la semántica de
   canal/actividad); si hiciera falta telemetría de producto, usar un evento de
   `learning_events` informativo sin peso de mastery.
3. **Escaleras por destreza (después del primer eslabón).** Reconocimiento
   (MCQ definición ↔ palabra), recall demorado (reutilizar el scheduler FSRS),
   producción en contexto y transferencia por contexto de actividad (V3.23).
   El peldaño **Reconocimiento** se implementó en v3.33.0 con evidencia solo
   informativa (`drill:<word>:recognition:ok|ko`); recall demorado y
   transferencia siguen pendientes.
4. **Frontend.** La tarjeta de `DictionaryLookup` crece; si el candidato añade
   varios bloques, dividir el componente (DictionarySearch / DictionaryEntryCard /
   DictionaryDefinition / DictionaryExample / DictionaryUsage /
   DictionaryUnitUsage) **antes** de acumular más secciones.

## Deuda estructural declarada (pendiente, no implementada)

- Polisemia por senses (una entrada ≠ inventario de sentidos; relevante en B2+).
- Definición adaptada al CEFR del alumno (hoy el prompt pide «simple English»
  sin `learner_level`).
- Diccionario contexto-aware (headword + sentence + nivel) para transcriptos de
  listening con palabras tocables.

## Criterios de aceptación

Estado: los tres criterios del primer eslabón quedaron **cerrados en v3.32.0**
por `backend/tests/test_dictionary_bridge_v332.py` (+3 tests, pytest 1711).

- ✅ Test e2e: lookup no crea evidencia; lookup + «Practicar» + éxito de
  práctica SÍ crea la misma evidencia que esa práctica fuera del diccionario
  (`test_lookup_new_word_read_only_and_practice_writes_identical_evidence`).
- ✅ Test de aislamiento entre usuarios del contenido y de la práctica
  (`test_lookup_and_practice_isolated_between_users`).
- ✅ Sin regresiones en V3.30/V3.30.1/V3.31.1 (single-flight,
  `generator_version`, `UNUSABLE_MODELS`, negative cache): suite completa
  pytest **1711 passed** + ruff limpio + vitest + `tsc --noEmit` +
  `check_release_consistency` 3.32.0 exit 0.
- ⏳ Criterios de eslabones futuros (cuando se implementen): recall demorado
  FSRS y transferencia por contexto; manteniendo la regla de «evidencia
  idéntica, sin etiquetas de origen».
- ✅ **Recognition (v3.33.0).** Peldaño `1 · Recognize` en la escalera
  compartida con MCQ definición ↔ palabra determinista servido y puntuado por
  el backend (premisa 21), evidencia SOLO informativa `drill:<word>:
  recognition:ok|ko` (cerrado por `backend/tests/test_dictionary_recognition_v333.py`).
