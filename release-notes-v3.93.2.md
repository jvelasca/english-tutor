# Release notes — English Tutor v3.93.2

**Fecha:** 2026-09-30 · **Tipo:** release de **ROBUSTEZ** (patch) · **Versión de app:**
`3.93.1 → 3.93.2`

**Con backend y frontend**, **SIN migración de BD** (reutiliza la columna `attempt_id` de
`listening_attempts` y su índice único **parcial**, creados en V3.93.1), **SIN endpoints
nuevos** y **SIN cambio de contrato incompatible**: `attempt_id` es un campo **aditivo** de
`POST /api/listening/dictation` y `POST /api/listening/shadowing`.
`GENERATOR_VERSION` (`1.7.0`), `DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue
`1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se retira gate**
—siguen los **ocho**, todos en `pending`— y `docs/audit/validation-evidence.json` **sigue
sin existir**.

**En una frase.** El P0-B de V3.93.1 cerró la idempotencia del intento **solo** en la ruta
receptiva; esta entrega cierra la **otra puerta** (dictado y shadowing), que seguía
insertando sin dedup, reutilizando la misma unidad atómica y **sin** alterar un ápice el
comportamiento de la cola de repaso.

---

## 1. Por qué este patch, y no V3.94

V3.93.1 endureció el flujo del intento receptivo (`record_answer_event`) y el de la
evidencia (`claim_evidence_and_write_card`). Al revisar el resultado quedó a la vista que
**la ruta de producción no pasaba por ninguna de las dos**: `submit_production` seguía
llamando a `listening_repo.record_attempt` directo. Es **la misma clase de defecto** que
V3.93.1 declaró cerrada, así que corresponde cerrarla antes de abrir la fase semántica
(`ENFORCE`, V3.94), no después.

## 2. El defecto, reproducido

`POST /api/listening/dictation` (o `/shadowing`) no llevaba `attempt_id`: repetir el envío
del **mismo** intento —doble toque, reintento de red del cliente— insertaba **2 filas** en
`listening_attempts`. Todo lo que se deriva de los intentos quedaba inflado:
`GET /api/listening/diagnostic`, el perfil auditivo (`auditory_profile`) y las métricas del
día.

No era tan grave como el P0-A/P0-B original —**no** toca `fsrs_cards` ni
`listening_review_queue`— pero es la misma puerta sin cerrar.

## 3. El arreglo

**(A) Producción pasa por la unidad atómica.** `submit_production` llama ahora a
`listening_repo.record_answer_event(..., attempt_id=attempt_id, sync_queue=False)`. La
deduplicación por `attempt_id` (`ON CONFLICT(user_id, attempt_id) DO NOTHING`, dentro de un
`BEGIN IMMEDIATE`) ya existía desde V3.93.1: aquí solo se **reutiliza**.

**(B) `sync_queue`, para no cambiar nada más.** `record_answer_event` gana
`sync_queue: bool = True`. La ruta receptiva no cambia (default `True`); la de producción
llama con `False`, de modo que **no lee, no inserta ni borra** `listening_review_queue`
—esa cola es de **frases receptivas falladas** (V3.89)—. Consecuencias verificadas por
test: un dictado **fallado** sigue sin encolarse, y un dictado **acertado** no resuelve una
frase receptiva encolada (la cola es por `(user_id, question_id)` y las `qid` no colisionan).

**(C) Identidad propia en el cliente.** El `attempt_id` receptivo cuelga del micro-flujo
(`pregunta:attemptCount`), que en dictado/shadowing **no existe**. `ListeningPractice.tsx`
usa un `productionAttemptIdRef` independiente: reutiliza el UUID mientras la pregunta no
cambie y lo regenera al cargar otra. `submitProduction` lo propaga solo cuando existe
(cliente legacy ⇒ sin `attempt_id` ⇒ semántica anterior).

## 4. Superficie del cambio

| Capa | Fichero | Cambio |
|---|---|---|
| Repo | `repositories/listening.py` | `record_answer_event(..., sync_queue=True)`; con `False` no toca la cola y `fail_count` = 0 |
| Dominio | `domain/listening.py` | `submit_production(..., attempt_id="")` usa `record_answer_event` en vez de `record_attempt` |
| Esquema | `schemas/listening.py` | `ListeningProductionRequest.attempt_id: str = ""` |
| Router | `routers/listening.py` | Reenvía `body.attempt_id` en `/dictation` y `/shadowing` |
| API | `api/listening.ts` | `submitProduction` envía `attempt_id` si existe |
| UI | `ListeningPractice.tsx` | `productionAttemptIdRef` + `productionAttemptId()`; reset en `load()` |

## 5. Verificación

| Comprobación | Resultado |
|---|---|
| `ruff` (backend) | limpio |
| `pytest` backend | **3465/3465** (3459 + 6 nuevos) |
| `vitest` frontend | **1108/1108** (1106 + 2 nuevos, 112 ficheros) |
| `tsc --noEmit` + `vite build` | limpios |
| `check_release_consistency` | OK en los **6 orígenes** (`3.93.2`) |
| `frontend/dist/index.html` | 2012 B, 0 bytes a cero (sano) |

Tests nuevos (`backend/tests/test_listening_event_atomicity_v3931.py` y
`frontend/src/api/listening.test.ts`):

- `test_production_double_submit_same_attempt_id_is_idempotent`
- `test_production_shadowing_double_submit_is_idempotent`
- `test_production_distinct_attempt_ids_create_two_attempts`
- `test_production_legacy_empty_attempt_id_keeps_old_behaviour`
- `test_production_never_enqueues_failed_task`
- `test_production_submit_does_not_disturb_existing_queue_entry`
- `submitListeningDictation propaga attemptId cuando existe`
- `submitListeningShadowing propaga attemptId junto a las señales`

## 6. Honestidad y límites

1. Es una **puerta secundaria**: no toca FSRS ni la cola de repaso, así que su impacto es
   menor que el del P0-A/P0-B original. Se cierra por **coherencia** (misma clase de
   defecto), no porque fuera urgente.
2. Un `attempt_id` **vacío** (cliente legacy / tests) conserva la semántica anterior:
   inserta siempre. Igual que en la ruta receptiva.
3. **Sigue sin haber migración** que hacer: la columna y el índice parcial son de
   V3.93.1.
4. El ledger de evidencia **sigue creciendo** y no se poda; `mismatch` sigue sin poder
   dispararse; `sense_id` estable sigue pendiente.
5. Los **ocho gates humanos siguen `pending`**.

## 7. Qué queda para V3.94+

- `ENFORCE`: decidir `declared:none` con datos reales y aplicar `allows_difficulty_evidence`.
- Cablear las **alternativas** del diccionario para que `mismatch` sea alcanzable
  (`new_sense_exposure`).
- `MAX_MATCHES` por relevancia en vez de por orden de aparición.
- Persistir `sense_key`/`sense_id` estables en el alta.
