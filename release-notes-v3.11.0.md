# v3.11.0 — Vocabulary por rutas CEFR

**Vocabulary por rutas CEFR: página única de checks MC del currículo + diccionario a mano.**

## Qué cambia

APRENDER → **Vocabulary** deja de ser solo el diccionario personal y pasa a una **página única con scroll** (espejo de Speaking/Listening/Pronunciation/Conversation):

- **Arriba, el escenario de práctica**: un **check MC de vocabulary del currículo** del nivel recomendado. Eliges la palabra correcta, con feedback inmediato y la respuesta correcta revelada si fallas.
- **Debajo, el mapa de rutas A1–C2** con anillos de cobertura y, al abrir un nivel, sus modos: **Practicar el nivel / Repetir fallidas / Repasar aprendidas**, más el bloque **«Demostrar el nivel»** que abre los instrumentos formales del curso (exámenes y escalera de evaluaciones).

## Contenido y evaluación

- El banco **no se inventa**: cada nivel reutiliza los **checks MC de la destreza vocabulary del currículo oficial** (`backend/curriculum/a1.json`…`c2.json`), sin contenido nuevo.
- La lógica de rutas sobre checks MC vive en un **motor compartido** (`backend/services/quiz_routes.py`) con puerta de cobertura/precisión/checkpoint **adaptada a bancos cortos**; Grammar (v3.12) lo reutilizará.
- Cada intento es **determinista** y se persiste en `vocabulary_route_attempts`. La ruta es un **hito de práctica** (techo `functional`), **nunca certifica**: demostrar el nivel exige los exámenes y evaluaciones formales del curso.

## Diccionario personal

El **diccionario personal** se integra en la propia página (botón «Mi diccionario», también accesible desde la franja superior), conservando su función completa: añadir palabras durante las lecciones, FSRS y seguimiento por nivel CEFR.

## Técnica

- Backend: `quiz_routes` (motor MC compartido) + `vocabulary_routes` (services/schemas/repositories/domain/routers) + tabla `vocabulary_route_attempts` + endpoints `/api/vocabulary/routes/stats|question|items` y `POST /attempt`.
- Frontend: página única `VocabularyRoutesPractice` + `VocabularyLevelPanel` + máquina de sesión + API client; Workspace/learnHub montan `/#/aprender/vocabulario` y el diccionario queda dentro de la página.
- Tests: 22 pytest nuevos (**1235** en total en verde), vitest (**369**), Playwright visual nuevo `vocabularyRoutesReview.spec.ts`.
