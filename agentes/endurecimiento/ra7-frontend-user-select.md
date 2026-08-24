# RA7 — Frontend: no auto-seleccionar el primer usuario cuando hay varios

## Objetivo
Al iniciar, si existen varios perfiles la app auto-selecciona `existing[0]`. Para multiusuario
local es preferible: si hay exactamente uno → seleccionarlo; si hay varios → mostrar el selector
("Selecciona perfil").

## Cambios
- `frontend/src/utils/users.ts`: añadir `resolveInitialUserId(users): string | null`
  (un usuario → su id; cero o varios → `null`).
- `frontend/src/hooks/useChat.ts`: usar `resolveInitialUserId` en la carga inicial en vez de
  `existing[0].id`.
- `frontend/src/components/UserSelect.tsx`: opción por defecto "Selecciona perfil" cuando
  `currentUserId` es `null`.

## Tests
- `frontend/src/utils/users.test.ts`: casos `resolveInitialUserId` (1 usuario, varios, 0).

## Verificación
- `cd frontend && npx tsc --noEmit` y `npm test`.
