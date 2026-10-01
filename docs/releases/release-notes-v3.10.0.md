# v3.10.0 — Conversation por rutas CEFR

**Conversation por rutas CEFR: página única de mini-diálogos guiados multi-turno.**

## Qué cambia

APRENDER → **Conversation** deja de ser el chat libre y pasa a una **página única con scroll** (espejo de Speaking/Listening/Pronunciation):

- **Arriba, el escenario de práctica**: un **mini-diálogo guiado multi-turno** con el tutor —situación, rol del alumno y del tutor, metas comunicativas y línea de apertura—. Conversas por texto o con el micrófono hasta cumplir las metas y pulsas «Terminar y puntuar».
- **Debajo, el mapa de rutas A1–C2** con anillos de cobertura y, al abrir un nivel, sus modos: **Practicar el nivel / Repetir fallidos / Repasar aprendidos**, más el bloque **«Demostrar el nivel»** que abre el Speaking Assessment (instrumento formal oral).

## Contenido y evaluación

- Banco oficial versionado y auditable **`curriculum/conversation_corpus.json`** (v1.0.0): **11 mini-diálogos por nivel (A1–C2)**, alineados con el currículo CEFR, cada uno con contexto, roles, apertura y metas comunicativas.
- Al terminar una conversación se evalúa el **transcripto completo** con el pipeline LLM de evidencia existente (`extract_speaking_evidence`, `task_type: conversation`) fusionado con la **señal objetiva de interacción** y se persiste el intento por diálogo.
- La ruta es un **hito de práctica** (techo `functional`, puerta de cobertura/precisión/checkpoint), **nunca certifica**: demostrar el nivel exige el Speaking Assessment + evidencia + retención, con la nota honesta del nivel oral demostrado.

## Chat libre

El chat libre con el tutor se mantiene accesible y ahora tiene **ruta propia `/chat`** (el espacio conversacional clásico con historial). Desde la página de Conversation hay un acceso claro a «Conversación libre».

## Técnica

- Backend: `conversation_routes` (services/schemas/repositories/domain/routers) + tabla `conversation_route_attempts` + endpoints `/api/conversation/routes/stats|question|items` y `POST /attempt`.
- Frontend: página única `ConversationRoutesPractice` + panel de nivel + máquina de sesión + API client; routing reordenado (`/aprender/conversar` = rutas guiadas, `/chat` = chat libre).
- Tests: 18 pytest nuevos (1213 en total en verde), vitest (359), Playwright visual nuevo `conversationRoutesReview.spec.ts` y ajustes de los specs de rutas.
