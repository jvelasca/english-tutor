# V3.33.1 — Hardening de Recognition (auditoría V3.33.0)

> Rol: documento de diseño e instrucciones del parche **V3.33.1**, que endurece el
> eslabón **Recognition** publicado en V3.33.0 a partir de la auditoría externa.
> Corrige dos P1 sin cambiar la arquitectura de evidencia (sigue SOLO
> informativa) ni la seguridad del scoring (el GET nunca expone la correcta).
> Publicado como **v3.33.1**.
>
> Normas que este parche DEBE respetar:
> - **Premisa 21**: la UI nunca declara acierto; el servidor puntúa recomponiendo
>   la pregunta. Se mantiene, ahora con un seed de intento.
> - **Sin estado servidor**: el seed (`question_id`) es un nonce que viaja en la
>   respuesta y vuelve en el intento, no se guarda sesión. Sin firmar: el seed
>   solo ordena y la correcta nunca viaja, así que manipularlo no revela ni
>   acredita nada.
> - **D3 / V3.13**: el acierto de Recognition sigue sin escribir en `vocabulary`,
>   sin mover FSRS/mastery/usage y sin sacar la palabra de candidatas; único
>   rastro, el evento `drill:<word>:recognition:ok|ko`.
>
> Borrador: 2026-09-10.

## Hallazgos de la auditoría que cierra

- **P1-01 — posición de la correcta fija por palabra.** El barajado se derivaba
  solo de `target_word`, así que repetir `cat` devolvía siempre la correcta en el
  mismo índice: se podía memorizar el patrón. No era un agujero de seguridad (el
  GET nunca expone `correct_index`), pero sí un problema pedagógico.
- **P2 — `_stable_int` colisionaba.** La suma ponderada por posición
  (`sum((i+1)*ord(ch))`) no dispersa bien y puede asignar el mismo índice a
  palabras distintas.
- **P1-02 — el drill arrancaba en Recall.** El componente declaraba
  `Recognition → Recall → Sentence`, pero `step` inicializaba en `"recall"`: el
  primer peldaño existía solo como paso manual.

## Qué implementa V3.33.1

1. **Seed de intento (P1-01)** — `services/dictionary_mcq.py`:
   `recognition_options_for(word, entries, seed="")` deriva la permutación de
   `palabra + seed`. La selección de distractores no cambia (determinista por
   palabra); el seed solo rebaraja.
2. **Hash estable (P2)** — `_stable_int` usa `SHA-256(text)` (primeros 8 bytes).
   Solo afecta al MCQ de diccionario; `listening_bottom_up` conserva su hash.
3. **Contrato aditivo** — `RecognitionQuestionOut.question_id` (nonce por
   intento, `""` si no disponible) y `RecognitionAttemptIn.question_id`
   (opcional). El GET lo emite (`secrets.token_urlsafe(8)`); el POST lo reenvía y
   el dominio recomputa con el mismo seed.
4. **Arranque en Recognize (P1-02)** — `wordDrill.tsx` abre en
   `step="recognition"`, carga la pregunta sola y degrada a Recall si
   `available=false` (sin pisar una elección manual de otro paso). Cada entrada
   en Recognize pide un `question_id` nuevo.

## Acceptance

- `test_dictionary_recognition_v333.py`: permutación estable por seed y variable
  entre seeds; determinismo/aislamiento sobre `question_id`; acierto/fallo solo
  informativos; sin contenido → `available=false`/409 sin evento.
- Frontend: arranque directo en Recognize; reentrar pide pregunta nueva;
  `available=false` degrada a Recall sin romper la escalera.
- Gates: pytest, ruff, vitest, `tsc --noEmit` y
  `check_release_consistency` 3.33.1 exit 0.
