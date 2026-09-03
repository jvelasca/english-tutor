# UI V3.1 — Diseño de la reorganización de la navegación en 3 mundos

> Estado: **propuesta de diseño para estudio conjunto, con acta de decisiones incorporada**.
> Este documento NO cambia código.
> Fase actual: arquitectura de información (IA) + mapa maestro de pantallas (decisiones cerradas,
> sección 8); siguiente: wireframes visuales.
> Rama de trabajo: `ui-rethink-v3.1` (desde `main`, que permanece en V3.0.0 sin tocar).
> Fecha de creación: 2026-09-02 · Acta de decisiones: 2026-09-02.

---

## 1. Contexto y por qué paramos el desarrollo funcional

El stack pedagógico está **congelado en V3.0.0** (ver `docs/BETA_V3.md`: freeze declarado el
2026-09-02; gates pedagógicos G6–G9 10/10; versión única en `backend/config.py`). El backend
ya tiene maduros el curso CEFR con gating, el Adaptive Engine (`next-best` explicable), el
Evidence Graph, los motores de listening/speaking/writing/pronunciation, el repaso FSRS y los
assessments. Con los motores listos, la siguiente oportunidad de mejora real es la **experiencia
de usuario**: hoy la navegación mezcla demasiados conceptos pedagógicos que compiten entre sí y
el usuario no debería tener que conocer nuestra arquitectura interna para usar la app.

Esta fase produce **un único documento de diseño** (`docs/UI_V3.1.md`) que se eleva en la rama
`ui-rethink-v3.1` para auditoría externa. **No se toca una línea de código de la UI** hasta que el
mapa de navegación esté acordado.

### Decisiones ya confirmadas

1. **Elevación en GitHub**: crear la rama `ui-rethink-v3.1` desde `main`, redactar este documento,
   hacer commit + push para que el auditor revise un artefacto real. (La auditoría externa no pudo
   crear rama por un 403 de su integración; la rama sí existe ahora en `origin/ui-rethink-v3.1`.)
2. **MI PROGRESO va anidado** (no es una 4ª sección raíz): se abre desde INICIO y desde FORMACIÓN.
3. **Las preguntas abiertas del estudio conjunto están resueltas**: el acta de decisiones vive en
   la sección 8 y cada decisión está incorporada en el cuerpo del documento.

---

## 2. Estado actual: diagnóstico verificado

La app navega por **pestañas raíz sin URLs** (estado React, no hay react-router). El layout es:
Header sticky (píldoras de escritorio) -> contenido -> píldoras móviles (mismo listado, con scroll)
-> StatusBar. No existe sidebar de navegación global (el `Sidebar` que hay es el de conversaciones,
solo en chat).

### 2.1 Rutas y componentes actuales

Fuente: `frontend/src/app/routes.ts` y el mapa ruta->pantalla en `frontend/src/app/Workspace.tsx`.

| Ruta | Etiqueta (es/en) | Pantalla | Archivo actual |
|---|---|---|---|
| `home` | Inicio / Home | Dashboard diario | `frontend/src/features/home/HomeScreen.tsx` |
| `learn` | Aprender / Learn | Práctica por destreza (workspace 3 paneles) | `frontend/src/app/PracticeView.tsx` |
| `course` | Curso / Course | Currículum CEFR por niveles | `frontend/src/features/course/CourseScreen.tsx` |
| `progress` | Progreso / Progress | Desglose de progreso (acordeones) | `frontend/src/features/progress/ProgressScreen.tsx` |
| `journey` | Trayecto / Journey | Escalera CEFR Pre-A1 -> C2 | `frontend/src/features/journey/JourneyScreen.tsx` |
| `vocabulary` | Vocabulario / Vocabulary | Diccionario personal (léxico FSRS) | `frontend/src/features/vocabulary/PersonalDictionary.tsx` |
| `chat` | Chat / Chat | Misma `PracticeView`, fuerza Speaking + conversación + sidebar | `frontend/src/app/PracticeView.tsx` |
| `help` | (icono, no está en `ROUTES`) | "Conectar dispositivo LAN" | `frontend/src/features/help/ConnectHelp.tsx` |

```text
App (estado route)
├── Header sticky
│     [EN] English Tutor | (píldoras: Home Learn Course Progress Journey Vocabulary Chat) |
│     HandsFree · Help · Ajustes(gear) · Usuario
├── Ruta (Workspace, con lazy+Suspense)
│     home        -> HomeScreen
│     learn       -> PracticeView   (destrezas: Listening Speaking Reading Writing | Grammar Pronunciation)
│     course      -> CourseScreen   (niveles A1-B2 · unidades · hitos/objetivos)
│     progress    -> ProgressScreen (acordeones por destreza)
│     journey     -> JourneyScreen  (escalera Pre-A1 -> C2)
│     vocabulary  -> PersonalDictionary
│     chat        -> PracticeView   (fuerza sección Speaking, modo conversación, sidebar)
│     help        -> ConnectHelp
├── Bottom-nav móvil (md:hidden): mismas píldoras con scroll horizontal
└── StatusBar "· Ready" -> popover Sistema
```

### 2.2 Duplicidades y problemas detectados (motivo del rediseño)

1. **Chat = Learn/Speaking.** `chat` y `learn` renderizan la misma `PracticeView`. La diferencia es
   que `chat` fuerza `section=speaking` + `mode=conversation` y muestra el sidebar de
   conversaciones. Dos entradas raíz para lo mismo.
2. **Curso ≈ Trayecto.** `CourseScreen` ("Your English journey", niveles A1-B2 con hitos) y
   `JourneyScreen` ("Learning Journey", Pre-A1->C2) muestran escaleras CEFR casi idénticas, y la
   tríada Progress/Mastery/Readiness se repite en Home, Course, Progress y Journey.
3. **"Next best" duplicado**: tarjeta grande en Home + `NextStep` compacto tras listening,
   pronunciation y speaking assessment.
4. **Contenido experto escondido**: FSRS, Evidence Graph, speaking/writing journeys, assessment 2.0,
   Today Plan y calidad del tutor viven dentro del panel `AnalysisPanel` (7 pestañas) acoplado al
   workspace de learn/chat, o en acordeones de Progreso. En móvil es un drawer; para un usuario
   nuevo es prácticamente invisible.
5. **Ayuda confusa**: la ruta `help` muestra `ConnectHelp` (conectar dispositivo a la red LAN), no
   una ayuda general. `HelpDialog` existe montado en `App` pero nunca se abre (código muerto).
6. **Sobrecarga de conceptos en la navegación**: Curso, Journey, Aprender, Vocabulario, Chat,
   Progreso... más modos (Listening/Speaking/Grammar/Writing). Demasiados "¿dónde voy?".
7. **Reading sin semántica clara**: al pulsar "empezar" un objetivo de lectura abre una conversación
   oral (App fuerza speaking/conversation). Confuso.
8. **Nada es un "lugar de aprendizaje claro"**: el usuario no distingue "estoy haciendo mi curso"
   de "estoy practicando libremente". Las actividades del curso y las libres comparten workspace.

---

## 3. Objetivo: reducir la app a 3 mundos

```text
             ENGLISH TUTOR
                  |
      +-----------+-----------+
      |           |           |
   INICIO      FORMACION    APRENDER
   (mando)    (curso CEFR)  (práctica libre)
      |           |           |
      +-----------+-----------+
                  |
             MI PROGRESO
                  |
             STUDENT MODEL
```

- **INICIO** — el centro de mando diario (no un tablero de estadísticas).
- **FORMACIÓN** — "Tengo que aprender esto": curso reglado CEFR tipo Oxford/Babbel/Busuu.
- **APRENDER** — "Quiero mejorar esto": práctica libre, adaptativa y conversacional.
- **MI PROGRESO** — representación del progreso (anidado, no sección raíz).
- **AJUSTES / AYUDA** — fuera de la navegación principal (iconos de cabecera).

> Regla de oro de esta reorganización: el usuario nunca debe preguntarse "¿dónde tengo que ir?".
> Cada pantalla pertenece a un único mundo y una pantalla se alcanza por un único camino.

### 3.1 Principios de IA tomados de las mejores apps

| Referencia | Qué tomamos | Cómo lo aplicamos |
|---|---|---|
| Duolingo | Simplicidad y acción inmediata | Home con un único CTA primario; navegación de 3 iconos en móvil |
| Babbel / Busuu | Estructura pedagógica CEFR y árbol de niveles | Formación: escalera A1->C2, progreso por unidad con gating visible |
| Busuu | Progresión por nivel CEFR | Indicador de nivel CEFR siempre visible (premisa #16) |
| ELSA | Speaking/pronunciación con feedback inmediato | Pronunciation como práctica libre dentro de Aprender |
| Anki | Repaso espaciado | Cola FSRS como tarjeta "Repaso" en INICIO (decisión D2) |
| LingQ | Aprendizaje libre por contenido | "Práctica libre" que no bloquea ni califica |
| ChatGPT | Conversación fluida | Conversar es un modo dentro de Aprender (y el vehículo de las lecciones del curso) |

Alineado con `docs/PREMISAS.md` #16 (lo mejor de cada plataforma, adaptado a una app 100% local).

---

## 4. Mapa maestro de pantallas (IA objetivo)

Convenciones de este mapa:

- **[C]** = componente que ya existe y se reutiliza. **[M]** = requiere mover/fusionar. **[N]** = nuevo.
- Los "->" describen qué ocurre al pulsar cada elemento.
- Cada pantalla cita el endpoint del backend que la sirve (referencia, no contrato de esta fase).

### 4.1 INICIO (dashboard diario)

```text
INICIO
│
├── Cabecera de bienvenida: "Buenos días, Alberto"  [N] sobre HomeScreen actual
│     - Nivel CEFR + progreso compacto  (GET /api/academy/student-model)
│
├── TU OBJETIVO DE HOY            (GET /api/academy/today + goal)
│     Actividad propuesta (duración + porqué) -> [EMPEZAR] lanza la actividad
│
├── TU FORMACIÓN
│     "B1 · Unidad 4 · 78%"  -> CONTINUAR abre FORMACIÓN en el punto exacto
│     (siguiente: Speaking — Expressing opinions)   (GET /api/academy/course/{level_id})
│
├── RECOMENDADO PARA TI
│     Tarjeta NextBest (motivo + factor limitante)   (GET /api/academy/next-best)
│     -> abre la actividad sugerida
│
├── REPASO  ("8 elementos pendientes")   [REPASAR]  (GET /api/academy/fsrs/due)
│
└── TU PROGRESO  (mini-barras de habilidades)
      -> abre MI PROGRESO
```

Reglas de INICIO:

- Máximo **una acción primaria visible** a la vez en móvil.
- Es un panel de mando, no un tablero de estadísticas: cada tarjeta tiene una única llamada a la acción.
- No duplica la escalera CEFR ni la tríada completa: eso vive en Formación / Mi Progreso.

Reutilización: se construye reorganizando `HomeScreen` + `NextBestCard` + `ProgressRing` + nueva
tarjeta FSRS (ya existe `FsrsReviewPanel`/`TodayPlan` que hoy están ocultos en Analysis).

### 4.2 FORMACIÓN (curso reglado CEFR)

```text
FORMACIÓN
│
├── Mi nivel / escalera CEFR
│     A1 dominado | A2 dominado | B1 actual | B2 bloqueado | C1 bloqueado | C2 bloqueado
│     (estado por nivel: dominado / actual / bloqueado)
│     -> pulsar nivel actual abre el curso; pulsar nivel bloqueado muestra requisitos
│
├── Curso actual (p. ej. B1)
│     B1 · Intermediate      ████████░░ 78%
│     Siguiente: Unidad 4 · Speaking "Expressing opinions"
│     [CONTINUAR CURSO] -> retoma la unidad/objetivo siguiente
│
├── Lista de unidades del nivel (gating visible)
│     Unidad 1 dominada | Unidad 2 dominada | Unidad 3 dominada | Unidad 4 (actual) | Unidad 5 pendiente ...
│     -> cada unidad abre su detalle
│
└── Evaluaciones  (bloque siempre visible, con estados: pendiente / disponible / bloqueado - D5)
      - Test de nivel (placement): paso ineludible al empezar si aún no hay nivel asignado
      - Assessment de unidad / progreso / nivel (assessment/v2): su estado se muestra siempre en
        cada nivel/unidad aunque todavía no toque realizarlo
      - Examen final de nivel: bloqueado hasta completar el nivel (gating del backend)
```

Detalle de una unidad (B1 · Unidad 4):

```text
B1 · Unidad 4
████████░░ 78%

Objetivos / actividades con estado:
   Vocabulary  dominado
   Grammar     dominado
   Listening   dominado
   Speaking    disponible (el siguiente)
   Interaction pendiente
   Assessment  bloqueado (gate)
```

Reglas de FORMACIÓN:

- **El curso manda sobre el workspace** (decisión D3): al lanzar una lección desde Formación se abre
  la práctica en el mismo workspace con envoltura de contexto —cabecera "B1 · Unidad 4 · Speaking —
  Expressing opinions", progreso del objetivo y vuelta al árbol del curso al terminar—.
- Solo aquí existe gating, exámenes, dominios por objetivo y certificación interna.
- Reutilización: `CourseScreen`, `JourneyNode`, `Milestone`, `AssessmentLadder`, endpoints
  `GET /api/academy/levels`, `/course/{level_id}`, `/cefr-ladder`, `/assessment/v2/ladder`.
- `JourneyScreen` (Pre-A1->C2) se **funde** aquí como la escalera de niveles. Ruta `journey` se
  elimina de la navegación raíz.

### 4.3 APRENDER (práctica libre y adaptativa)

```text
APRENDER
│
├── "¿Qué quieres practicar hoy?"  (hub de tarjetas grandes)   [C]
│     6 tarjetas: 3x2 en escritorio, lista vertical en móvil.
│       - Listening       - Speaking        - Pronunciación
│       - Conversar       - Vocabulario     - Gramática
│     (Repaso y Reading NO viven aquí: decisiones D2 y D4)
│
├── RECOMENDADO PARA TI   (Adaptive Engine)
│     (GET /api/academy/next-best) -> lanza práctica sugerida
│
└── Al entrar en una tarjeta: la práctica se abre SIN cabecera de curso,
      con su propio recorrido (historial, retos, sesiones guardadas).
```

Qué vive en cada tarjeta (todo reutiliza componentes existentes):

| Tarjeta | Qué hace | Componente/API actual |
|---|---|---|
| Listening | Ejercicio por habilidad, sin anclar el curso | `ListeningPractice` + `/api/listening/*` |
| Speaking | Práctica oral libre (misiones, escenarios, diagnóstico) | `SpeakingScenarios`/`SpeakingMission` + `/api/academy/speaking/*` |
| Pronunciación | Drill guiado de pronunciación con feedback (estilo ELSA) | `PronunciationPractice` + `/api/pronunciation` |
| Conversar | Chat con el tutor (modo conversación) | `PracticeView` + `/api/chat`, `/api/conversations` |
| Vocabulario | Diccionario personal y práctica léxica | `PersonalDictionary` + `/api/vocabulary/*` |
| Gramática | Análisis y errores recurrentes | `/api/grammar/*`, modo grammar de la conversación |

Reglas de APRENDER:

- **Aquí no existe gating**: nada se bloquea, todo es explorable. Nada puntúa dominio de curso.
- La **práctica libre genera evidencia** (envía respuestas/eventos) pero no avanza unidades del
  curso; solo alimenta el modelo del alumno (repaso, recomendación, diagnóstico).
- El CHAT deja de ser una sección raíz: "Conversar" vive aquí. Cuando la conversación es una lección
  del curso (lanzada desde Formación) la cabecera muestra el contexto del curso; cuando se entra
  desde Aprender es práctica libre. Es el **mismo workspace con distinta envoltura**, nunca dos
  rutas.
- Reading / Pronunciation: Reading queda **aparcado en esta fase** (decisión D4): no aparece en
  APRENDER ni como destreza navegable, hasta que exista contenido real de lectura. Pronunciación es
  tarjeta propia del hub (motor dedicado, decisión D6).
- El Repaso (FSRS) NO vive aquí: es la tarjeta diaria de INICIO (decisión D2).

### 4.4 MI PROGRESO (anidado)

Se abre desde INICIO (tarjeta "Tu progreso") y desde FORMACIÓN ("Mi nivel"). No aparece en la
navegación raíz. En el modelo de URLs (decisión D7) tiene su propia ruta `#/progreso`.

```text
MI PROGRESO
│
├── Curso          B1 · 78% · unidades dominadas y actual (GET /course/{level_id})
│
├── Habilidades    barras por destreza (8 skills) + subdestreza limitante
│                  (GET /api/academy/student-model + evidence-graph)
│
├── Trayectoria    A1 dominado | A2 dominado | B1 actual | B2 pendiente | C1 pendiente | C2 pendiente
│                  (GET /api/academy/cefr-ladder)
│
└── Recorridos     Pestañas, no acordeones (premisa #19):
      - Listening (diagnóstico/resiliencia)   - Speaking (journey/misiones)
      - Writing (journey/diagnóstico)         - Assessment (ladder)
```

Reglas de MI PROGRESO:

- Fusiona `ProgressScreen`, `JourneyScreen` (escalera) y los paneles expertos que hoy viven ocultos
  en `AnalysisPanel` (FSRS/Evidence Graph/Today/Assessment) con el patrón **pestañas** de premisa #19.
- "Trayecto"/Journey como **concepto** no desaparece: es una pestaña de Mi Progreso.
- El panel `Analysis` del workspace se replantea (ver 4.5).

### 4.5 Destino del panel "Analysis" actual

Hoy es la "tumba de features": FSRS, Evidence Graph, speaking/writing journeys, assessment y
calidad del tutor solo son alcanzables abriendo el panel derecho del workspace. Propuesta:

- Lo que es **perfil/progreso** (Progreso, Plan de hoy, Perfil, Speaking journey, Writing journey,
  Assessment ladder) migra a MI PROGRESO por pestañas.
- Lo que es **contexto de la conversación en curso** (calidad del tutor, diagnóstico de la sesión)
  se mantiene accesible durante la práctica, pero en versión ligera y bajo demanda.
- `ProgressDashboard`, `LearningProfile`, `SpeakingPanel`, `WritingPanel`, `TutorQualityPanel`,
  `EvidenceGraphPanel`, `TodayPlan` y `AssessmentLadder` se reubican, no se borran.

---

## 5. Navegación desktop y móvil

### 5.1 Escritorio (>=1024 px)

Decisión D1: **píldoras en cabecera reducidas a 3 destinos** (Inicio · Formación · Aprender), el
mismo patrón de `Header` + `Navigation` actual con solo 3 píldoras. La barra lateral izquierda se
evaluó en el estudio conjunto y se descartó.

```text
Escritorio (>=1024 px) -- esquema estructural, no a escala
------------------------------------------------------------
Cabecera: [EN] English Tutor | Inicio · Formación · Aprender |
          · nivel CEFR · voz · ayuda · ajustes · usuario
------------------------------------------------------------
CONTENIDO
  Contenedor adaptativo por tipo de pantalla (sin max-w-3xl
  apretado en monitores grandes, salvo pantallas de lectura)
------------------------------------------------------------
```

Reglas desktop:

- Máximo 3 destinos raíz; nada más compite por la atención.
- Las pantallas de contenido dejan de forzarse a `max-w-3xl` cuando eso desperdicia zona útil en
  pantallas grandes; se usa un contenedor adaptable con ancho máximo cómodo de lectura por tipo de
  pantalla.
- Paneles redimensionables solo en desktop (premisa #22).

### 5.2 Móvil (<768 px)

```text
Movil (<768 px)  -- esquema estructural, no a escala
----------------------------------------------------
  Cabecera: English Tutor | nivel CEFR · voz · ajustes
----------------------------------------------------
  CONTENIDO (una cosa a la vez, scroll vertical natural)
  ...
  [   CTA primaria grande, justo sobre la barra   ]
----------------------------------------------------
  [INICIO]   [FORMACION]   [APRENDER]
  bottom-nav fija de 3 iconos (accesible con el pulgar)
```

Reglas móvil:

- **Bottom-nav fija de 3 iconos** (Inicio / Formación / Aprender), siempre visible y accesible con
  el pulgar. Se elimina la fila de píldoras scrolleables actual.
- **Una acción primaria visible** por pantalla, grande y clara.
- **Menos información simultánea**: tarjetas grandes, sin tablas, sin píldoras infinitas.
- **Drawers a pantalla completa** para cualquier panel secundario (premisa #20).
- **Micrófono/audio siempre accesibles**: el botón de voz (hands-free/PTT) permanece en cabecera y/o
  como acción flotante sobre el contenido cuando la pantalla lo usa.
- La navegación interna de cada mundo usa sub-páginas apilables (con botón atrás), nunca pestañas
  horizontales inaccesibles.

### 5.3 Tablet (768–1023 px)

- Tablet (>=768 px) usa las mismas píldoras de cabecera que escritorio; la bottom-nav de 3 iconos
  se reserva para móvil (<768 px).
- Contenido en 1–2 columnas según el tipo de pantalla; sin overflow horizontal.

---

## 6. Reglas de zona útil y responsive (para la fase de implementación)

Estas reglas se aplicarán al implementar y son **Definition of Done** (premisas #14 y #20):

1. Tres breakpoints consistentes (móvil/tablet/escritorio) con tokens ya existentes; cero overflow
   horizontal en ninguno.
2. Cada pantalla declara **una acción primaria**; las secundarias se ordenan por importancia y se
   ocultan en móvil si no caben.
3. Contenedor de contenido adaptativo: ancho cómodo de lectura en desktop, ancho completo útil en
   móvil; nada de "comprimir el desktop".
4. Los drawer del workspace móvil pasan a pantalla completa; los paneles fijos solo en desktop
   (premisa #22).
5. Tests visuales Playwright en >=3 viewports (escritorio/tablet/móvil) de las rutas principales
   antes de dar por terminado cualquier cambio de layout (`npm run test:visual`).
6. Tap targets >=44 px; estados vacíos/de carga/de error cuidados en cada pantalla reubicada.
7. El frontend sigue sin decidir dominio (premisa #21): al mover pantallas no cambia el contrato de
   datos, solo la envoltura y la navegación.

---

## 7. Mapa de migración actual -> nuevo

| Elemento actual | Destino en V3.1 | Acción |
|---|---|---|
| Ruta `home` | INICIO | Rediseñar el contenido (dashboard de acción) |
| Ruta `course` | FORMACIÓN | Mantener + envolver con escalera A1->C2 y contexto claro |
| Ruta `journey` | FORMACIÓN (escalera) + MI PROGRESO (trayectoria) | Fusionar; eliminar de la navegación raíz |
| Ruta `learn` | APRENDER | Mantener como hub de práctica libre |
| Ruta `chat` | APRENDER -> Conversar | Fusionar con learn/Speaking; eliminar entrada raíz |
| Ruta `vocabulary` | APRENDER -> Vocabulario | Reubicar; eliminar entrada raíz |
| Ruta `progress` | MI PROGRESO (anidado) | Consolidar por pestañas |
| Ruta `help` | AYUDA real (docs, premisa #17) + apartado "Conectar dispositivo" | Separar conceptos |
| `PracticeView` (workspace) | Shared engine para Formación (lecciones) y Aprender (libre) | Envolver según contexto del mundo |
| `AnalysisPanel` (7 pestañas) | MI PROGRESO + versión ligera contextual en práctica | Reubicar contenido por tab |
| `PersonalDictionary` | APRENDER -> Vocabulario | Mover |
| `ListeningPractice` | APRENDER -> Listening y lecciones del curso | Reutilizar igual |
| `PronunciationPractice` | APRENDER -> Pronunciación (tarjeta propia del hub, D6) | Reubicar |
| `ReadingPractice` | Aparcado en esta fase (D4); sin tarjeta en APRENDER | Ocultar / archivar |
| `HomeScreen`/`NextBestCard` | INICIO | Reorganizar |
| `FsrsReviewPanel`, `TodayPlan`, `EvidenceGraphPanel` | INICIO (Repaso/Plan) y MI PROGRESO | Sacar de Analysis |
| `JourneyNode`, `Milestone`, `ProgressRing` | FORMACIÓN y INICIO | Reutilizar |
| `ConnectHelp`, `HelpDialog` | AYUDA (separar ayuda general de conectar dispositivo) | Arreglar (hoy HelpDialog es código muerto) |
| Audio Library / Backup / System / MicrophoneTest | AJUSTES / popover Sistema (admin) | Sin cambio de IA |

Cambios estructurales de navegación:

- `frontend/src/app/routes.ts`: migrar a **URLs reales con HashRouter** (decisión D7): tres mundos
  raíz (`#/inicio`, `#/formacion`, `#/aprender`) + sub-rutas por mundo (p. ej.
  `#/formacion/b1/unidad-4`, `#/aprender/listening`) + `#/progreso` (anidado). HashRouter para que
  las rutas profundas funcionen en local/LAN sin configuración de servidor.
- `frontend/src/app/AppShell.tsx` + `Navigation.tsx`: bottom-nav móvil de 3 iconos (<768 px) y
  píldoras de 3 destinos en cabecera (>=768 px, decisión D1); el estado `route` y los efectos
  laterales de `navigate` (App.tsx) se simplifican al eliminar las duplicaciones chat/learn.
- `frontend/src/utils/i18n.ts` (claves `nav.*`): renombrar a `nav.home/formation/learn` y limpiar
  las ~50 claves huérfanas detectadas en la auditoría F.

---

## 8. Acta de decisiones (estudio conjunto, 2026-09-02)

Resolución de las preguntas abiertas de esta fase por el propietario del proyecto. Cada decisión
está incorporada en el cuerpo del documento.

| # | Punto decidido | Acuerdo |
|---|---|---|
| D1 | Navegación de escritorio | Píldoras en cabecera reducidas a 3 destinos (Inicio · Formación · Aprender). Se descarta la barra lateral. Tablet >=768 px usa el mismo patrón; bottom-nav de 3 iconos solo en móvil (<768 px). |
| D2 | Repaso (FSRS) | Vive solo en INICIO como tarjeta diaria con contador de pendientes. No se duplica en APRENDER. |
| D3 | Lección del curso vs Conversar libre | Workspace único con envoltura de contexto: lección = cabecera del curso + vuelta al árbol; Conversar = historial y sin contexto de curso. Panel Analysis ligero bajo demanda en ambos. |
| D4 | Reading | Aparcado en esta fase: sin tarjeta en APRENDER ni destreza navegable, hasta que exista contenido real de lectura. |
| D5 | Evaluaciones en FORMACIÓN | Bloque siempre visible con estados (pendiente / disponible / bloqueado). Placement inicial ineludible si no hay nivel asignado. |
| D6 | Pronunciación en APRENDER | Tarjeta propia del hub (motor dedicado). El hub queda con 6 tarjetas: Listening, Speaking, Pronunciación, Conversar, Vocabulario y Gramática (3x2 en escritorio). |
| D7 | URLs reales | Sí, con HashRouter (`#/inicio`, `#/formacion/...`, `#/aprender/...`, `#/progreso`): funciona en local/LAN sin configuración de servidor; botón atrás y deep links. |
| D8 | Ayuda y "Conectar dispositivo" | Separar conceptos: la ayuda general enlaza a `docs/` (premisa #17); "Conectar dispositivo" pasa a Ajustes/Sistema. Limpiar `HelpDialog` (código muerto). |

Los detalles de disposición que no fija esta acta (densidad visual de las tarjetas del hub,
jerarquía de cada tarjeta de INICIO, etc.) se resuelven en la fase de wireframes.

---

## 9. Fases siguientes (a ejecutar tras la pausa)

1. **Auditoría externa**: este documento (con el acta de la sección 8) se envía a auditoría externa.
2. **Wireframes visuales** por breakpoint (PC/tablet/móvil) de las pantallas maestras; aquí se
   resuelven los detalles de disposición que no fija el acta.
3. **Implementación** (ramas cortas, subagentes autocontenidos según `docs/PREMISAS.md` #5):
   URLs/rutas y Workspace, shell responsive, i18n, reubicación de pantallas, limpieza de código
   muerto.
4. **Tests visuales Playwright** en 3 viewports (premisa #20) y **pruebas reales** en dispositivos
   (`docs/DEVICE_MATRIX.md`).
5. **Bump de versión a V3.1.0** validado con `backend/scripts/check_release_consistency.py` (solo en
   la fase de implementación).

Fuera de alcance de esta fase: cambios de código de UI, cambios de versión, wireframes, tests.

---

## Anexo: inventario técnico previsto (sin ejecutar, fase 2)

Lista orientativa de toques para cuando se apruebe la implementación (no es un compromiso cerrado):

- `frontend/src/app/routes.ts`: migrar a URLs HashRouter de 3 mundos + sub-rutas (D7);
  `Workspace.tsx`: nuevo mapa de vistas.
- `frontend/src/app/AppShell.tsx` y `app/Navigation.tsx`: bottom-nav 3 iconos (<768 px) / píldoras
  de 3 destinos en cabecera (>=768 px, D1).
- `frontend/src/App.tsx`: simplificar `navigate`/`handleStartLesson`/`handleSelectSection`; quitar
  duplicación chat/learn; limpiar `helpOpen`/`HelpDialog` muerto (D8).
- `frontend/src/app/Header.tsx`: cabecera por mundo (nivel CEFR visible, micrófono, usuario).
- `frontend/src/features/`: `home` (rediseño), `course` (envoltura), `journey` (fusión), `progress`
  (consolidación por pestañas), `learn` (hub de tarjetas), `vocabulary` (reubicación),
  `reading` (ocultar/archivar, D4), `help` (división: docs/ vs Conectar dispositivo).
- `frontend/src/components/PracticeView.tsx`: envoltura de contexto "lección del curso" vs "práctica
  libre"; análisis del panel Analysis en MI PROGRESO.
- `frontend/src/utils/i18n.ts`: claves `nav.*` nuevas y limpieza de huérfanas.
- Backend: **sin cambios** salvo los que surjan del cierre de preguntas (por ejemplo, si hace falta
  algún endpoint para "colgar" el curso o el contexto). El contrato de datos actual es suficiente.
