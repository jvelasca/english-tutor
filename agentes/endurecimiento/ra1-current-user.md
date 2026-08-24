# RA1 — Unificar `current_user` en todos los endpoints sensibles

## Objetivo
Eliminar la inconsistencia de identidad señalada por la auditoría externa: algunos endpoints
resuelven el perfil con `Depends(current_user)` y otros confían en un `user_id` enviado por el
cliente. Todos los endpoints que consultan o modifican datos pedagógicos deben usar `current_user`.

## Alcance
- `backend/dependencies.py`: conservar `current_user` y añadir `current_user_optional`
  (`user_id: str | None = Query(None)`) para el chat sin perfil.
- `backend/routers/chat.py`: `chat` y `chat_stream_endpoint` usan `Depends(current_user_optional)`;
  `_system_prompt` y `_record_activity` reciben `user_id` resuelto (puede ser `None`).
- `backend/routers/conversations.py`: `create` y `list_all` usan `Depends(current_user)` y
  eliminan `user_id` como parámetro explícito.
- `backend/routers/pronunciation.py`: usa `Depends(current_user)` (o optional) y elimina `user_id`
  del form/body.
- `backend/routers/vocabulary.py`, `grammar.py`, `learning.py`: unificar con `current_user` si
  aún confiaban en `user_id` del cliente.
- `backend/schemas/chat.py`: quitar `user_id` de `ChatRequest`.

## Frontend
- `frontend/src/api/chat.ts` (`sendChat`, `streamChat`) y `pronunciation.ts` (`checkPronunciation`):
  enviar `user_id` como query param (no en el body).
- `frontend/src/api/vocabulary.ts` / `grammar.ts` / `learning.ts` si aplica.

## Tests a actualizar
- `backend/tests/test_chat_profile.py`, `test_activity.py`, `test_api_security.py`,
  `test_fluency.py` y los que referencien `user_id` en body → query param.

## Verificación
- `cd backend && .venv\Scripts\python.exe -m pytest tests/ -q` (verde)
- `cd backend && .venv\Scripts\python.exe -m ruff check .` (limpio)
- `cd frontend && npx tsc --noEmit` y `npm test` (verde)
