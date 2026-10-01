# v3.12.0 — Grammar por rutas CEFR

**Grammar por rutas CEFR: página única de checks MC del currículo.**

## Qué cambia

APRENDER → **Grammar** deja el chat del tutor (que sigue accesible en `/chat`) y pasa a una **página única con scroll** (espejo de Speaking/Listening/Pronunciation/Conversation/Vocabulary):

- **Arriba, el escenario de práctica**: un **check MC de grammar del currículo** del nivel recomendado. Eliges la opción correcta, con feedback inmediato y la respuesta correcta revelada si fallas.
- **Debajo, el mapa de rutas A1–C2** con anillos de cobertura y, al abrir un nivel, sus modos: **Practicar el nivel / Repetir fallidas / Repasar aprendidas**, más el bloque **«Demostrar el nivel»** que abre los instrumentos formales del curso (exámenes y escalera de evaluaciones).

## Contenido y evaluación

- El banco **no se inventa**: cada nivel reutiliza los **checks MC de la destreza grammar del currículo oficial** (`backend/curriculum/a1.json`…`c2.json`, 97 checks en total), sin contenido nuevo.
- Grammar monta sobre el **motor compartido de rutas quiz** (`backend/services/quiz_routes.py`, estrenado por Vocabulary) con su propia tabla (`grammar_route_attempts`), endpoints `/api/grammar/routes/*` y namespace de errores.
- Los **bancos cortos** (B2 = 8 y C2 = 4 checks) adaptan la puerta automáticamente (checkpoint proporcional) con la nota honesta en la UI.
- Cada intento es **determinista** y se persiste. La ruta es un **hito de práctica** (techo `functional`), **nunca certifica**: demostrar el nivel exige los exámenes y evaluaciones formales del curso.

## Unifica APRENDER

Con Grammar, **las 6 actividades de APRENDER comparten la misma página única de rutas CEFR** (Listening, Speaking, Pronunciation, Conversation, Vocabulary y Grammar) con su filosofía común: práctica con control total del alumno, y el nivel demostrado solo por evidencia formal.

## Técnica

- Backend: `grammar_routes` (schemas/repositories/domain/routers) + tabla `grammar_route_attempts` + endpoints `/api/grammar/routes/stats|question|items` y `POST /attempt` sobre el motor compartido `quiz_routes`.
- Frontend: página única `GrammarRoutesPractice` + `GrammarLevelPanel` + máquina de sesión + API client + tipos; Workspace monta `/#/aprender/gramatica` como página propia (fuera de PracticeView).
- Tests: 24 pytest nuevos (**1259** en total en verde), vitest (**379**), Playwright visual nuevo `grammarRoutesReview.spec.ts`.
