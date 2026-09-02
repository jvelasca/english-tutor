# F — UX / Learning Journey (auditoría V3.0)

- **Fecha:** 2026-09-02
- **Alcance:** Home (`frontend/src/features/home/HomeScreen.tsx`), `NextBestCard`, `TriadCard`, cobertura i18n (`frontend/src/utils/i18n.ts` + usos en `frontend/src`), y revisión de carga cognitiva de las superficies profundas (Assessment ladder, FSRS, Evidence Graph). No se auditan aquí los flujos de dispositivos (auditoría G).
- **Relación con freeze:** UX (`BETA_V3.md` §4.3). Trabajo permitido: verificación de las 5 preguntas de Home, estados vacíos, i18n y carga cognitiva. Sin features nuevas.
- **Entregable:** este dossier + `scripts/check_i18n_coverage.py` (nuevo) + informe `docs/audit/generated/i18n-report.{json,md}`.

## Método

1. **5 preguntas de Home** — verificación formal contra el código real y los estados de API (`getNextBestActivity`, `dashboard`, props `profile`), no contra un mockup.
2. **Checker i18n automático (nuevo)** — `python scripts/check_i18n_coverage.py` parsea el objeto `STRINGS` y cruza con las claves referenciadas en `frontend/src` (directas `t("x")`, indirección `i18nKey:`/`titleKey:`, familias dinámicas `t(\`prefix.${...}\`)`). Detecta: usadas-sin-definir, duplicadas, traducciones vacías, y candidatas a limpieza.
3. **Estados vacíos/error** — revisión del render en ausencia de backend o sin usuario.
4. **Carga cognitiva** — lectura dirigida de `AssessmentLadder.tsx`, `FsrsReviewPanel.tsx` y `EvidenceGraphPanel.tsx`.
5. **Pulido aprobado en el momento del audit** — corrección del positivo falso «All done» (ver F1). Validado con `tsc --noEmit` y `vitest run` (245 tests, 31 ficheros) el 2026-09-02.

## Evidencia — las 5 preguntas de Home

Verificado en `HomeScreen.tsx`, `NextBestCard.tsx`, `TriadCard.tsx` y claves `home.*`/`readiness.*`/`reason.*` de `i18n.ts`.

| # | Pregunta | Dónde responde | Contenido real (API/código) | Veredicto |
|---|---|---|---|---|
| 1 | **Where am I** | `LevelBadge` + tarjeta progreso + tríada | nivel estimado (`estimated_level`) con `LevelBadge showLabel`, readiness% global hacia `target_level` con banda (`readiness.ready/approaching/developing`), y tríada Progress/Mastery/Readiness | **Sí, con matiz:** no hay ancla textual «estás aquí» ni posición en la ruta del curso; la clave `home.youAreHere` está definida pero sin usar (ver F4). |
| 2 | **How am I doing** | tarjeta progreso + `Stat` inferior + tríada | tendencia (chip Improving/Needs review/Stable), racha actual y mejor (`history.streak`), actividad reciente agregada, readiness% con barra animada | **Sí.** La sección está marcada `aria-label="home.yourProgress"`. |
| 3 | **What is weak** | `home.nextFocus` + `SkillBar` × 6 | `profile.readiness.blocking_skills[0]` (primer skill bloqueante) + etiquetas de dominio por skill (`mastery.strong/developing/needsPractice` por umbral 0.75/0.5) | **Parcial en Home:** da el skill débil y el color por skill, pero la sub-destreza concreta y el `because[]` están en el panel Evidence Graph (accesible), no en Home. Aceptable por jerarquía de información. |
| 4 | **What should I do now** | `NextBestCard` | única actividad de `GET /api/academy/next-best` con título, icono de skill, razón (`reason.*`), minutos y CTA «Continue»; si no hay nada → «All done for today» | **Sí**, acción dominante única (con matiz de estados: ver F1). |
| 5 | **Why** | `NextBestCard` | `reason`, frase `why`, lista `because[]` y `limiting_factor` (id + score % o `missing`) | **Sí**, con la jerarquía recomendada: por qué → porque → factor limitante. |

## Evidencia — checker i18n (2026-09-02, exit 0)

- STRINGS definidas: **660** · claves referenciadas en código: 610 · prefijos dinámicos `t(\`prefix.${…}\`)`: 12.
- Usadas y NO definidas (rompería en runtime): **0**.
- Duplicadas en STRINGS: **0** · entradas con `en`/`es` vacío: **0**.
- Candidatas a limpieza (definidas y nunca referenciadas): **50** (informe completo en `docs/audit/generated/i18n-report.json`).

Las 50 huérfanas son coherentes con un historial de UI real: claves sustituidas por diseños posteriores (`home.start`, `home.today`, `home.review`, `home.reviewN/practiceN`, `kind.*`, `course.back/finalExam/…`, `listening.review/seen`, `progress.mainFocus/seeDetails/…`, `triad.readinessHint`, `home.youAreHere`, etc.). `common.back` y similares podrían estar accedidas vía un `back` genérico; se listan como candidatas, **no** como errores. No bloquean el freeze.

Nota de método: las claves usadas solo por indirección dinámica (p. ej. bandas de readiness devueltas por backend) quedan protegidas por el registro de prefijos dinámicos; el informe separa ambos casos.

## Evidencia — estados vacíos/error y pulido aplicado

Hallazgo F1 (positivo falso) → **fix aplicado** en `HomeScreen.tsx`:

- **Antes:** `getNextBestActivity` fallaba en silencio y `next` quedaba `null` → la tarjeta mostraba «All done for today. Great work!» (mensaje de éxito) aunque el backend estuviera caído o no hubiera usuario. El «all done» es el único estado correcto cuando la API responde y no hay nada pendiente.
- **Después:** estado `loading → error → done`. Con API caída se muestra una tarjeta neutra (`home.unavailable`) con CTA «Try again» (`home.retry`) si hay usuario; el éxito («All done») solo aparece tras una respuesta real sin pendientes. Nuevas claves `home.unavailable` y `home.retry` (en/es) en `i18n.ts`.

Validación: `npx tsc --noEmit` (exit 0) y `npx vitest run` (31 ficheros / 245 tests en verde).

## Evidencia — carga cognitiva de Assessment ladder + FSRS + Evidence Graph

- **FSRS (`FsrsReviewPanel.tsx`)** — panel que sigue el contrato What / Why / When / How strong / Last / Next: un único card, 6 micro-datos etiquetados y 4 botones de calificación (Again/Hard/Good/Easy). Carga baja y con vocabulario explicado por `explain.*`. **Aceptado.**
- **Assessment 2.0 (`AssessmentLadder.tsx`)** — flujo por pasos guiado (por parte de la ladder), con feedback de superación/umbral por tipo (`assessmentV2.*`). El contenido es denso (porque la ladder evalúa destrezas), pero la interacción es lineal y con CTA única. **Aceptado.**
- **Evidence Graph (`EvidenceGraphPanel.tsx`)** — resumen compacto (nivel, avg mastery, abiertos/dominados, top limiting factor) y hasta 12 chips seleccionables con drill-down por objetivo. **Aceptado.**

## Hallazgos

| # | Sev. | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| F1 | media | Home mostraba «All done for today» (éxito) cuando el backend no respondía o no había usuario: positivo falso en el estado vacío más visible de la app. | `HomeScreen.tsx` pre-fix | Diferenciar loading/error/done; error neutro + reintento, éxito solo con respuesta real. | **fix aplicado** (2026-09-02) |
| F2 | baja | Duplicidad de lectura de readiness en Home: `TriadCard` y la tarjeta inmediatamente inferior muestran el mismo readiness% casi yuxtapuestos. | `HomeScreen.tsx` (tríada + card) | Decidir consolidación: reservar la tríada para Progress y dejar en Home nivel + readiness hacia target, o unificar la fuente. No urgente (freeze). | abierto (decisión de diseño) |
| F3 | info | Q1 no tiene ancla textual «estás aquí» ni posición en la ruta; `home.youAreHere` está definido y sin uso. | `i18n.ts`, `HomeScreen.tsx` | Opcional: anclar `LevelBadge`/posición de nivel con la etiqueta existente en Home o Journey. | abierto (mejora) |
| F4 | info | Los paneles profundos (`FsrsReviewPanel`, `EvidenceGraphPanel`, `AssessmentLadder`) tragan errores de carga en silencio (catch vacío) y dejan la sección vacía sin explicación. | `FsrsReviewPanel.tsx`, `EvidenceGraphPanel.tsx` | Extender el patrón loading/error aplicado en Home (F1) a estos paneles. Fuera del alcance mínimo del freeze. | abierto (mejora) |
| F5 | info | 50 claves i18n huérfanas (historial de UI) sin duplicados ni roturas. | `i18n-report.json` | Depuración posterior como limpieza; no bloquea. | abierto |
| F6 | info | Carga cognitiva de ladder/FSRS/Evidence Graph controlada (paso a paso, CTA única, drill-down). | código + revisión F | Mantener; validar con el protocolo de usuario real. | aceptado |
| F7 | info | Checker i18n nuevo en `scripts/` (exit 0, informe reproducible). | `i18n-report.json` | Integrarlo en el gate de cierre junto a `check_beta_v3.py`. | aceptado |

## Estado de los checkboxes §4.3 (`docs/BETA_V3.md`)

| Checkbox | Estado | Cómo se cubre |
|---|---|---|
| «Home: Where am I / How am I doing / What is weak / What should I do / Why» | ✅ (cerrado el 2026-09-02) | Verificación formal de la tabla anterior; responde las 5 con evidencia de API/código. |
| «Vaciar estados vacíos restantes; i18n de strings nuevas V2.9–V2.12» | ✅ (cerrado el 2026-09-02) | Fix F1 (Home) + checker i18n (0 roturas, informe reproducido) + claves nuevas en/es. |
| «Revisar carga cognitiva de Assessment ladder + FSRS + Evidence Graph» | ✅ (cerrado el 2026-09-02) | Revisión F6; superficies por pasos y CTA única; recomendaciones abiertas anotadas. |

## Veredicto

**Home responde formalmente a las 5 preguntas del aprendizaje** y su estado vacío más visible ya no puede mentir: el «All done» solo aparece con respuesta real. El checker i18n confirma 0 roturas (0 usadas-sin-definir, 0 duplicadas, 0 vacías); las 50 huérfanas son limpieza no bloqueante. La carga cognitiva de las superficies profundas está controlada. La fase de observación con usuario real queda como protocolo abierto (requiere persona externa y backend con datos).

## Protocolo — usuario real (a ejecutar fuera de la máquina)

Contexto: persona ajena al proyecto (sin conocimiento de CEFR ni del motor interno), sesión guiada de ~25 min con la app en PC/Chrome y perfil con datos de al menos una semana.

**Tarea:** «Estudia 20 minutos de inglés como lo harías tú.»

**Observación guiada (anotar en vivo):**

1. **Where am I** — sin preguntar, ¿el participante verbaliza dónde está en su aprendizaje (nivel, progreso) mirando Home? ¿Duda entre la tríada y la tarjeta de readiness?
2. **What should I do** — ¿encuentra la siguiente acción en <10 s y la inicia sin ayuda? ¿Ignora «Continue» por no entender a qué lleva?
3. **Why / improvement** — al completar una actividad y volver a Home, ¿busca y entiende el «why/because» del siguiente paso? ¿Consulta el panel Evidence Graph?
4. **Error de flujo natural** — si se cae el backend (matarlo a mitad de sesión), ¿qué mensaje ve? (regresión de F1).

**Criterios de fallo (si se cumple ≥1 → abrir incidencia de UX):**

- No encuentra la acción siguiente en 30 s con Home cargado y API OK.
- No comprende qué significa el % de readiness ni qué hacer con él tras una pista.
- Confunde «All done» con un error o viceversa.
- Abandona la sesión antes de 20 min por frustración de navegación (no por dificultad del idioma).

**Criterios de éxito:** completa la tarea autónomamente, hace ≥2 actividades, explica con sus palabras «por qué me sugiere esto» (puede ser impreciso pero debe apuntar a debilidad/repaso/orden).

## Regenerar / Verificar

```powershell
# Checker i18n + informe
python scripts/check_i18n_coverage.py

# Pulido Home (F1)
cd frontend
npx tsc --noEmit
npx vitest run
```

## Tests que respaldan

- `npx vitest run` — 245 tests (31 ficheros) en verde tras el fix F1 (2026-09-02).
- El checker i18n es reproducible vía `python scripts/check_i18n_coverage.py`; salida en `docs/audit/generated/i18n-report.json`.
