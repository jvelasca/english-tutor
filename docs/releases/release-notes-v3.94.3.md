# v3.94.3 — La ruta de Listening se ve en Formación, y un acierto no pide un segundo toque

Release de **PRODUCTO (patch)** sobre `v3.94.2`. **CON backend y CON frontend**,
**SIN migración de BD**, **SIN endpoints nuevos** y **SIN cambio de contrato
incompatible**: `CourseMap` gana `listening_route` (nivel, estado, dominadas,
total, cobertura, puerta). El campo es aditivo.

`PROVEN_OTHER_OVERLAP` **sigue en 2**. `GENERATOR_VERSION` (`1.7.0`),
`DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`) y
`LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate**
—siguen los **ocho**, todos `pending`— y
`docs/audit/validation-evidence.json` **sigue sin existir**.

**No abre V3.95.** El ledger de producción sigue a 0 filas.

## Qué cierra

1. **Una ruta, dos puertas.** La sección de Listening de un nivel de Formación
   muestra el mismo `route_gate` que Aprender. Mostrarlo no mueve
   `academy_objective_mastery`, no desbloquea el nivel siguiente y no es un
   certificado CEFR. Elegir B2 en Aprender no abre ni certifica B2 en
   Formación. El diccionario sigue siendo léxico: esta release no lo proyecta
   sobre la sección de vocabulario del curso.
2. **El repaso y el botón coinciden.** Un acierto borra la frase de
   `listening_review_queue`, pero la pantalla solo refrescaba el aviso al
   fallar. «Repaso pendiente» se quedaba encendido con «Repasar pendientes»
   apagado. Ahora el contador se refresca en los dos casos, y el botón cuenta
   las frases que siguen falladas. Si no queda ninguna, el botón principal es
   practicar frases nuevas del nivel. Una entrada aplazada vuelve a `pending`
   cuando `next_review_at` ya pasó.
3. **Un acierto, un toque.** Tras responder bien, **Siguiente** cierra el ítem
   y salta el shadowing opcional. Repetir en voz alta es una oferta en la
   misma revisión, no otra pantalla con «Hecho — siguiente ejercicio». En el
   móvil el resultado y el botón van antes que la transcripción, a ancho
   completo. El shadowing que no se puede saltar conserva su propia pantalla.

## Qué no cierra

- El ledger de producción sigue sin volumen. La sonda
  `backend/tests/test_sense_telemetry_probe.py` reproduce el corpus en una BD
  temporal y no escribe en `tutor.db`.
- El frontend **sigue sin pintar** `new_sense_exposure`.
- No hay `sense_id` estable ni FSRS por acepción.
- Los **ocho gates humanos siguen `pending`**.

## Verificación local

- `ruff` limpio en los ficheros de backend tocados.
- `pytest` de `test_course.py`, `test_listening_review_queue_v389.py` y
  `test_sense_telemetry_probe.py`: **44/44**.
- `tsc --noEmit` limpio.
- `vitest` de `microFlow.test.ts`: **42/42**.

El resto (pytest completo, vitest completo, build, contraste) lo corre la CI.
El tag anotado `v3.94.3` espera a que esa CI esté verde y a la auditoría
externa. Hasta entonces la *Latest* sigue siendo `v3.94.2`.
