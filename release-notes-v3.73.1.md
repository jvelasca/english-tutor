# Release notes — English Tutor v3.73.1

**Fecha:** 2026-09-17 · **Tipo:** release de **PARCHE** (cierre GUI/UX pre-V4.0, sin
capacidad pedagógica nueva) · **Versión de app:** `3.73.0 → 3.73.1`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el banco, SIN tocar el currículum y SIN tocar
backend ni launcher.** Todo el cambio vive en el frontend, salvo el bump de versión
y el bookkeeping documental.

---

## Qué es esta release

V3.73.0 se publicó con un dictamen externo de cierre (**9.7/10**) que dejó seis
hallazgos GUI/UX como **P2/P3** antes de V4.0. V3.73.1 los cierra **sin abrir
arquitectura**: ordena el hub de APRENDER, hace explícitos Reading y Writing como
prácticas con el tutor (en vez de dejarlos como superficies huérfanas que caían en
el chat), jerarquiza la navegación móvil, respeta `prefers-reduced-motion` en las
animaciones JS y **mide** —con instrumento propio y guardas automatizables— el
contraste real de los 7 acentos.

**Lo que NO hace:** no toca el Adaptive Engine, ni el banco, ni el currículum, ni el
backend, ni el launcher; no añade la matriz completa de visual regression (declarada
para V4.0.x); y **no cierra los 7 gates físicos**, que siguen `pending` por diseño
(`status --strict` sigue **rojo**).

---

## 1 · APRENDER deja de ser confuso (GUI-01, GUI-02, GUI-04)

**Lo que había (medido):** las 4 actividades del hub se pintaban en un grid de **3
columnas** en desktop, así que la cuarta quedaba aislada en una fila propia; el
`aria-labelledby` de la sección del grid apuntaba a un `id` **que no existía**; y
**Reading** y **Writing** estaban "huérfanos": su tarjeta navegaba a `/chat` y el
efecto de la ruta `/chat` **forzaba `speaking`**, de modo que elegir Reading abría
Speaking. La superficie `ReadingPractice` era **inalcanzable** y `SectionNav` no se
importaba en ningún sitio.

**Lo que hay ahora (Opción A: explícitos vía tutor, sin motores nuevos):**

| Pieza | Qué hace |
|---|---|
| `router/chat.ts` (nuevo) | `ChatSkill` (`reading` \| `writing`), slug por destreza y `chatSkillPath` → `/chat/lectura`, `/chat/escritura`; `chatSkillFromPath` devuelve la destreza de una URL o `null`. |
| `router/routeMap.ts` | `case "chat"` acepta un segundo segmento **solo** si es `lectura`/`escritura` (cualquier otra subruta degrada a `home`, como antes). |
| `App.tsx` | El `useLayoutEffect` de `route === "chat"` selecciona la sección que trae la URL; sin destreza en la URL mantiene el comportamiento anterior (`speaking`). Las secciones de chat libres navegan a `chatSkillPath(...)`, así que también las **recomendaciones** (`NextBestActivity`, Home) abren el chat con su contexto. |
| `PracticeView.tsx` | `reading` entra en la rama de chat (`writing` ya estaba) con su `kicker.reading`; desaparece el bloque muerto de `ReadingPractice`. |
| `Workspace.tsx` | Con destreza en la URL no se resalta Speaking (`activeActivity` deja de mentir). |
| `LearnHub.tsx` | Grid a `xl:grid-cols-4` (una fila con las 4 actividades en desktop) y **bloque secundario «Practica con el tutor»** con Reading y Writing, que abren `/chat/lectura` y `/chat/escritura`. |

**Accesibilidad del hub (GUI-01):** `SectionHeading` acepta `id` y el
`aria-labelledby` del grid apunta a un nodo que existe; el bloque nuevo tiene su
propio `aria-labelledby` y su lista con `data-testid` para las guardas de teclado.

**Código muerto retirado:** `components/SectionNav.tsx` y
`features/reading/ReadingPractice.tsx` **borrados** (recuperables con `git` cuando
llegue la Opción B), junto con sus claves i18n huérfanas (`nav.skills`,
`group.primary`, `group.support` y toda la familia `reading.*`). El gate
`check_i18n_coverage.py --strict` sigue en **0 huérfanas / 0 duplicadas / 0 vacías**
(1477 cadenas definidas). Se conservan `ReadingIcon`/`WritingIcon` (los usa
`NextBestCard`) y `WritingPanel`/`WritingJourney` (viven en Progress > Recorridos).

**Deuda declarada:** el CSS legacy asociado a `ReadingPractice`
(`.reading-practice-*`, `.reading-academy-*`, `.reading-card-*`, `.reading-empty`)
**no se toca** en este parche: queda registrado para limpieza en V4.0.x, junto con
otros selectores legacy ya sin uso en TSX.

## 2 · Navegación móvil: el núcleo manda (GUI-03, GUI-08)

**Lo que había (medido):** la bottom-nav tiene 5 destinos y **dos son utilidades**
(Diccionario, Traductor) que competían visualmente con las tres áreas de aprendizaje
(Inicio, Formación, Aprender).

**Lo que hay ahora:** se mantienen **los 5 destinos** y los **touch targets**
(`min-h-14`, `flex-1`), pero la separación núcleo/auxiliar deja de ser un `border-l`
sutil: hay un **divisor real** antes del bloque auxiliar y los dos auxiliares bajan
de peso visual (icono y etiqueta atenuados, etiqueta más pequeña en anchos
estrechos). La regla queda escrita en el componente: **los 3 mundos dominan;
Diccionario y Traductor son utilidades**.

## 3 · `prefers-reduced-motion` de verdad (GUI-05)

**Lo que había (medido):** solo `legacy.css` respetaba la preferencia; las
animaciones de `motion/react` (stagger del hub, píldoras de la nav, transiciones) la
**ignoraban**.

**Lo que hay ahora:** la app se envuelve en `<MotionConfig reducedMotion="user">`,
así que **todas** las animaciones de `motion` respetan el sistema, y el bloque
`@media (prefers-reduced-motion: reduce)` de `legacy.css` sigue cubriendo las
animaciones CSS puras (los spinners funcionales no quedan inertes).

## 4 · Contraste: se mide, se arregla lo arreglable y se numera lo que no (GUI-06)

**Instrumento nuevo:** `frontend/scripts/contrast_audit.mjs` (+`npm run
audit:contrast`, en CI) lee **los tokens reales** de `legacy.css` e `index.css`,
calcula la razón WCAG de cada par y escribe
`docs/audit/generated/contrast-report.{json,md}`. **184 pares + 2 guardas**:

- **Bloqueante (sale 1 si baja de AA):** tipografía base sobre las superficies y
  **texto de acento** sobre superficies y fondos compuestos, en los 2 temas y los 7
  acentos. Hoy: **0 fallos**.
- **Reportado (no bloquea):** relleno de acento + tinta y acento como borde, con la
  **mejor tinta posible** y el **máximo alcanzable** de la rampa actual. Hoy: **17
  fallos** de 42 pares.

**Lo que se corrigió:**

- **Tipografía terciaria (`--color-text-faint`) en tema claro** pasa de `#6f7c90` a
  `#616e84`: el par más ajustado (sobre `--color-bg-soft`) sube a **4.55:1**.
  Los 16 pares de tipografía base cumplen AA en los dos temas.
- **El texto de acento deja de ser un hex fijo.** `--color-accent-soft` **se deriva
  del acento elegido** con
  `color-mix(in srgb, var(--color-accent) var(--accent-soft-share), var(--accent-soft-target))`:
  hacia blanco en tema oscuro (objetivo `#ffffff`) y hacia negro en claro
  (objetivo `#000000`), con el **mayor porcentaje de acento que mantiene AA con
  margen** para cada uno de los 7 acentos (64 % índigo, 67 % violeta, 65 % azul,
  56 % turquesa, 56 % esmeralda, 64 % rosa, 52 % ámbar). Antes el token era
  **único y no seguía al acento**: elegir turquesa pintaba el texto de acento en
  índigo, y con ámbar en tema claro el texto de acento se quedaba en **2.02:1**.
  Las ~20 reglas que usaban el acento **sólido como color de texto** pasan a usar
  este token; el acento sólido queda para relleno, borde y anillo de foco.
- **Guardas nuevas:** el CSS no puede volver a usar `color: var(--color-accent)`
  como color de texto, y `--color-accent-soft` tiene que seguir derivándose con
  `color-mix()` (si desaparece la derivación, las mediciones dejan de corresponderse
  con lo pintado). Además, `tests/visual/accentContrast.spec.ts` comprueba **en el
  navegador real** los 14 pares acento×tema: resuelve el color computado y exige
  ≥4.5:1 contra las tres superficies — es la única forma de detectar que un
  `var()` dentro del porcentaje de `color-mix()` dejase el token inválido.

**Lo que NO se puede cerrar sin rediseño (y por eso se declara, con números):** el
**relleno de acento con su tinta encima** (botones primarios, píldora activa de la
nav) y el **acento como borde** en tema claro. Con la **mejor tinta posible** el
máximo alcanzable sobre el relleno se queda en **4.19:1** (índigo oscuro), **3.96**
(violeta), **3.73** (ámbar), **3.68** (azul), **3.67** (rosa), **3.42** (turquesa) y
**3.41** (esmeralda); el mínimo de AA es 4.5:1. No es un token mal elegido: es que un
**solo** color de relleno no puede ser a la vez fondo con tinta legible y borde con
3:1, y en tema claro los acentos al 500 no llegan a 3:1 como borde (turquesa
**2.49**, esmeralda **2.54**, ámbar **2.15**). Cumplirlo exige **re-rampar los 7
acentos** (p. ej. 600/700 como relleno en claro y 400/500 en oscuro), una decisión de
identidad visual que corresponde a **V4.0.x** y que ahora puede tomarse con la tabla
delante. **No se declara WCAG 2.2 AA certificado: se declara lo que se midió.**

## 5 · Teclado, zoom 200 % y foco

- `tests/visual/keyboard.spec.ts`: el primer `Tab` revela el **skip link** y enfoca
  `#main-content`; las tarjetas del hub (incluidas las **nuevas** entradas del tutor)
  se activan **solo con teclado** y con `focus-visible`.
- `tests/visual/reducedMotionAndZoom.spec.ts`: con `reducedMotion: "reduce"` el hub
  no deja contenido a medio aparecer (opacidad final 1 en las 6 tarjetas) y las
  rutas principales **no desbordan horizontalmente** (≤1 px) a 200 % de zoom con
  fuente grande.

---

## Verificación (lo que se ejecutó en este árbol)

```powershell
# Frontend
cd frontend
npx tsc --noEmit                                  # limpio
npx vitest run                                    # 712 passed (85 ficheros)
npm run audit:contrast                            # 0 fallos bloqueantes + 2 guardas OK
npx playwright test --workers=4                   # 38 passed · 28 skipped · 0 failed (13 specs × 3 breakpoints)
npm run build                                     # OK

# Gates del repo (raíz)
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py      # 6 orígenes (3.73.1)
backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py --strict   # 0 huérfanas / 0 duplicadas / 0 vacías
backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist  # 10/10
backend\.venv\Scripts\python.exe scripts\validation_gate.py status         # 7 pending
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict # exit 1 (correcto: puerta de V4.0)
```

Backend y launcher **no se tocan**: se corren igualmente por higiene de release
(`ruff` + `pytest`), sin cambios en sus cifras.

**Nota de instrumentación:** el primer `npx playwright test` a **16 workers** dio 13
fallos **solo en desktop** por contención del dev server (timeouts de 30 s con la
caché fría de Vite) y los 13 pasan al repetirlos; la corrida de referencia se hace a
**4 workers**, que es la que se publica. No es un fallo del producto: es el coste de
arrancar 63 casos en frío contra un servidor de desarrollo.

---

## Honestidad

- **Los 7 gates siguen en `pending`.** Este parche **no** hace la validación física:
  `status --strict` sigue saliendo **1** y esa sigue siendo la puerta real de V4.0.
- **El contraste de los acentos no está cerrado.** Está **medido**, con la parte
  arreglable arreglada (texto de acento) y la que exige re-rampar la paleta
  **cuantificada** (relleno + tinta y borde). Decir «GUI accesible» sin ese matiz
  sería falso, así que el informe va con los números.
- **La matriz de visual regression sigue sin existir** (screenshot baseline + pixel
  diff × breakpoint × tema): se aplaza a V4.0.x por decisión de alcance, no por
  olvido. Las capturas de `smoke.spec.ts` se generan, pero **no** se comparan contra
  una línea base.
- **El CSS legacy sin uso no se limpia aquí** (más allá de lo que arrastraban
  `SectionNav`/`ReadingPractice`): se registra para V4.0.x.
- **Terminología, densidad visual, textos de ayuda, progreso de descarga en MB,
  estados vacíos, orden de foco completo y zoom** siguen siendo P3 declarados para
  V4.0.x, como en el dictamen.

## Criterio de V4.0 (sin cambios)

V4.0 se declara cuando `validation_gate.py status --strict` salga **0**: los 7 gates
en `pass`. V3.73.1 **congela el código** y deja el siguiente hito donde siempre
estuvo: **ejecutar físicamente G1–G7**.
