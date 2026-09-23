# Premisas del proyecto — English Tutor

> **Fuente de verdad.** Si algo entra en conflicto con este documento, manda este documento.
> Mantenido por el gerente del proyecto.

## 1. Visión
Profesor/asistente de inglés que conversa por voz y texto, **100% local**: sin coste, sin
cuentas **en la nube** y con todo el procesamiento en el equipo. Arranca con diálogo por texto, luego voz, y evoluciona hacia un tutor
completo.

## 2. Principio rector: 100% local
- Todo el procesamiento (LLM, voz→texto, texto→voz) corre en la máquina del usuario.
- En desarrollo se aprovecha todo (GPU, servicios locales, etc.).
- Excepciones admitidas, **declaradas y fail-closed**: (a) la descarga inicial de modelos y
  dependencias; y (b) el **correo saliente** de verificación de email (V3.81), que solo existe
  si el webmaster configura un SMTP —sin SMTP **no se abre ninguna conexión**— y que está
  declarado como salida a Internet en `backend/scripts/audit_dossier.py::RUNTIME_TOUCHPOINTS`
  (`kind: "internet"`). `backend/tests/test_mailer_v381.py` fija las dos mitades: que sin
  configurar no se toca `smtplib` y que un fallo de envío no tumba la acción que lo pedía.
- Prohibido depender de APIs en la nube (Google STT, Microsoft TTS, OpenAI, etc.).

## 3. Stack (fijado)
- **Backend:** Python + FastAPI + Pydantic (tipado fuerte).
- **Frontend:** Vite + React + TypeScript (modo estricto).
- **LLM:** Ollama (servicio local). Modelo por defecto: `llama3.1:8b` (`backend/config.py::DEFAULT_MODEL`); `qwen3.5:9b` está **vetado** en el código (`UNUSABLE_MODELS`).
- **Runtime de producto (V3.72, eje UA — cierre de RC-01):** el launcher arranca **un
  solo proceso**, `uvicorn` por **HTTPS** (`--ssl-certfile/--ssl-keyfile` con el
  certificado autofirmado que genera `backend/scripts/ensure_tls_cert.py`), y ese proceso
  sirve la **API** y la **UI compilada** (`frontend/dist`) en el **mismo origen**
  (`https://<host>:8000`). El `dist` **no se versiona**: lo compila el launcher
  (`npm run build`) la primera vez si falta. Consecuencia declarada: **Node + npm son
  requisito de COMPILACIÓN/instalación, no de EJECUCIÓN**. `npm run dev` (dev server de
  Vite en `:5173`) sigue existiendo como **modo de desarrollo** con HMR. HTTPS es
  requisito de producto, no cosmético: sin *secure context* el navegador no expone
  `navigator.mediaDevices` y se rompe el micrófono desde otro equipo de la LAN.
  Cierre y evidencia en `docs/audit/RC-RUNTIME-PRODUCTO.md` (RC-01); fijado por test en
  `backend/tests/test_docs_drift_v372.py`.
- **Fail-closed del runtime de producto (V3.73):** el launcher arranca el backend con
  `ENGLISH_TUTOR_REQUIRE_UI=1` y **no lo arranca** si falta `frontend/dist/index.html`.
  Con la variable activa, la ausencia del artefacto es un **error explícito** en el
  montaje de la UI, no una app que parece lista y se ve vacía. Un `uvicorn main:app`
  manual (sin la variable) sigue siendo **fail-open** a propósito: es el modo
  desarrollo, donde un clon limpio conserva la API. Fijado por test en
  `backend/tests/test_serve_frontend_v373.py` y `launcher/tests/test_preflight_v373.py`.
- **Descubrimiento de la IP de LAN sin referencias externas (V3.73):** la IP con la que
  se anuncia la app se obtiene enumerando las direcciones del propio equipo
  (`backend/services/net_interfaces.py`, algoritmo puro `select_lan_ipv4`), **sin
  consultar ninguna dirección pública** (hasta V3.72 se usaba un socket UDP «connect» a
  `8.8.8.8`, perezoso pero con una referencia externa dentro de una app 100 % local).
  Override declarado: `ENGLISH_TUTOR_LAN_IP`. Fijado por test en
  `backend/tests/test_net_interfaces_v373.py` y `launcher/tests/test_lan_ip_v373.py`.
- **La red local es opt-in (V3.73.x):** por defecto el backend escucha en **loopback**
  (`127.0.0.1`) y **no** acepta orígenes de red privada: exponerse a la LAN dejó de ser
  el comportamiento por defecto y pasa a ser una decisión declarada. Se activa con el
  botón **«Activar red local»** del panel de acceso del launcher (reinicia el servidor
  para aplicarlo) o arrancando con `ENGLISH_TUTOR_LAN=1`; en los dos casos el launcher
  propaga el modo en el entorno del backend, de modo que la interfaz a la que se enlaza
  uvicorn y la política de orígenes no pueden discrepar. El modo se lee **fail-closed**
  (ausente o no afirmativo ⇒ cerrado). Mientras no haya autenticación por perfil (P0,
  ver `docs/audit/PARKED.md`), quien alcanza el puerto ve y escribe los datos del
  alumno: por eso la frontera es explícita. Fijado por test en
  `backend/tests/test_lan_mode.py` y `launcher/tests/test_lan_mode.py`.

## 4. Voz local (fijado)
- **Oído (STT):** `faster-whisper`, modelo `small`, en CPU.
- **Boca (TTS):** `piper-tts`, voz `en_US-lessac-medium`, en CPU.
- Motivo CPU: la GPU (RTX 4060 Ti, 4 GB) ya la usa Ollama.

## 5. Proceso de trabajo: siempre con subagentes
- Todo el trabajo se descompone en **subagentes**: cada uno con una única responsabilidad
  y un briefing autocontenido en `agentes/<nombre>.md` (rol, objetivo, contexto, tarea,
  criterios de aceptación, restricciones, salida).
- Un subagente nunca depende del historial acumulado de otro: su briefing contiene todo lo
  que necesita para trabajar de forma independiente.
- El gerente redacta el briefing, lo ejecuta (o lo entrega para ejecución), revisa el
  resultado, integra y genera el siguiente paso.

## 6. Ritmo: poco a poco
- Avanzar hito a hito, en orden, un cambio a la vez.
- Evitar mezclar varias funcionalidades grandes en un solo paso.

## 7. Gestión del contexto (anti-alucinación)
- Vigilar la saturación del chat. Si el contexto se sobrecarga y hay riesgo de alucinación,
  se cambia a un agente/contexto nuevo.
- Cada subagente es autocontenido precisamente para no depender del contexto acumulado.

## 8. Vigilancia anti-saturación de agentes
- **Todos** los agentes (gerente y subagentes) se vigilan contra la saturación de contexto:
  cuando un agente acumula demasiada información y se vuelve propenso a alucinar, se detiene
  y se abre un agente/subagente nuevo con contexto limpio.
- Señales de saturación: respuestas incoherentes, "inventar" APIs o rutas inexistentes,
  contradecir la documentación, repetir decisiones ya tomadas como si fueran nuevas.
- Regla de oro: **antes de alucinar, reiniciar el contexto**. La documentación (`docs/`,
  `README.md`, `PLAN.md`) es el ancla para reanudar desde cero sin perder el hilo.
- Un cambio de contexto no es un fallo: es parte del proceso de calidad.

## 9. Documentación VITAL
- Cualquier programador debe poder seguir el proyecto **desde 0** en cualquier momento.
- Todo cambio relevante actualiza la documentación (`docs/`, `README.md`, `PLAN.md`).
- La documentación forma parte de la definición de "terminado", no es opcional.

## 10. Modularidad y estructura
- Súper modular, estructurado, con responsabilidades claras por capa.
- Mantenible y ampliable: añadir una feature no debe tocar código no relacionado.
- Estructura y responsabilidades definidas en `docs/ARQUITECTURA.md`.

## 11. GitHub
- Al alcanzar una **versión previa estable**, se sube a la cuenta GitHub del cliente.
- A partir de ahí, el seguimiento (issues, PR, releases, ramas) se hace desde GitHub.

## 12. Tests y scripts (obligatorio)
- **Toda la app debe tener tests** en sus carpetas correspondientes:
  - Backend: `backend/tests/` (pytest).
  - Frontend: `frontend/src/**/*.test.ts` (vitest).
- **Toda la app debe tener scripts** en sus carpetas correspondientes:
  - Backend: `backend/scripts/` (p. ej. smoke test).
  - Frontend: `frontend/scripts/`.
- Los tests son parte de la definición de "terminado": ninguna feature se da por acabada sin sus tests.
- Los tests deben ser **rápidos y deterministas** (sin depender de la red ni de modelos externos).

## 13. Multi-usuario con cuenta local (seguimiento independiente)
- La app admite **varios usuarios locales**, cada uno con su propio espacio: conversaciones,
  progreso, correcciones, puntuaciones de pronunciación y ajustes, **totalmente independientes**
  entre sí.
- **Desde V3.81 la identidad es una cuenta con credencial propia** (nombre + email + contraseña),
  no un nombre elegido de una lista: cualquiera puede **crearse una cuenta** desde la app
  (registro autoservicio, en loopback) y **darse de baja** por sí mismo. Entrar sin contraseña
  solo lo permite una cuenta **heredada** sin credencial (`password_hash == ''`): es una deuda
  declarada y el lanzador la enseña como tarea pendiente.
- **La baja autoservicio no borra nada**: la cuenta deja de operar y sus sesiones se cierran,
  pero la evidencia se conserva. Borrar de verdad (purgar) es una acción **administrativa**, con
  copia previa, confirmación por nombre y registro en el historial.
- **Sin cuentas en la nube** (coherente con la premisa 2): las cuentas, los hashes y los datos
  viven en la BD local. El **email** es PII nueva y es una **señal**, no un muro: si no hay SMTP
  configurado, el webmaster sella la verificación a mano desde el lanzador.
- La contraseña se guarda **hasheada** (PBKDF2-HMAC-SHA256 con sal por usuario, iteraciones
  declaradas en el propio valor) y tanto el cambio de contraseña como una baja forzada
  **tumban las sesiones abiertas** al instante (época de autenticación), no al caducar la cookie.
- **Aislamiento total de datos entre usuarios**: nada de un usuario puede verse desde otro.
- El seguimiento de progreso (historial, estadísticas, logros) es **por usuario**.
- El **lanzador** («Gestión de la APP») tiene el control y la prioridad: resuelve la cola de
  solicitudes, crea cuentas, asigna o restablece credenciales, verifica emails a mano,
  desactiva, reactiva, **fuerza la baja con motivo**, edita datos, enseña el historial, purga y
  configura el correo. Es el único sitio desde el que se borra a una persona.

## 14. Diseño y UX nivel "top del mercado"
- La interfaz aspira al nivel de las mejores apps del mercado (p. ej. ChatGPT, Duolingo,
  Grammarly): moderna, pulida, atractiva y con las mejores prácticas de UX.
- **Responsive total:** toda la UI debe adaptarse perfectamente a **móviles y tablets**
  (además de escritorio), accesible (a11y), con estados vacíos, de carga y de error cuidados.
- Sistema de diseño con **tokens** (colores, tipografía, espaciado, radios) para consistencia,
  y soporte de **tema claro/oscuro**.
- Micro-interacciones y feedback visual (transiciones, animaciones sutiles, indicadores al
  hablar/escuchar).
- El diseño forma parte de la definición de "terminado": ninguna feature se da por acabada
  si queda "fea" o inconsistente con el resto.

## 15. 100% libre (sin pago, por ahora)
- Todas las opciones de la app están disponibles para **todos los usuarios**, sin
  suscripción, paywall ni limitaciones por nivel de cuenta.
- No hay muro de pago: la Academy (currículum CEFR, mastery, evaluaciones, Study Plan y
  AI Teacher por lección) es accesible para cualquier perfil local.
- La capa comercial (`subscriptions`/`entitlements`) queda **diferida** hasta que exista
  contenido que la justifique, y no se referencia en la UI.
- Coherente con la premisa 2 (100% local, sin costes y sin cuentas **en la nube**).

## 16. Nivel "mejor de cada plataforma profesional"
- La UI toma como referencia lo mejor de las apps profesionales del sector
  (Duolingo, Busuu, Babbel, British Council, etc.), adaptándolo —no copiando— a una app
  100% local y de uso personal.
- Se elige lo mejor de cada plataforma: claridad de progreso (árbol de niveles y
  seguimiento por objetivo), indicadores visuales por estado (acertado / fallado / a
  repasar), y navegación por pestañas con indicador de nivel CEFR.
- El resultado debe sentirse "PRO" sin sacrificar las premisas de localidad, privacidad y
  ausencia de cuentas **en la nube** —la cuenta es local y, desde V3.81, con contraseña propia—.

## 17. Documentación accesible y Ayuda para no ingenieros
- La documentación de `docs/` es la fuente de verdad técnica. La **Ayuda** de la app
  enlaza a `docs/` en lugar de copiar su contenido: **no se duplica información**.
- La Ayuda está pensada para un usuario **no ingeniero**: lenguaje claro, pasos concretos
  y sin jerga. Si un término técnico es imprescindible, se explica brevemente.
- Cualquier usuario debe poder entender qué hace la app, cómo arrancarla y cómo resolver
  problemas frecuentes **sin conocimientos de programación**.
- **Autor del proyecto:** José Alberto Velasco — <josealberto.vel@gmail.com>.

## 18. Docstrings y documentación autogenerada (obligatorio)
- **Todo el código lleva docstrings/docblocks**: en Python, docstrings de módulo, clase y
  función (qué hace, parámetros, retorno, excepciones relevantes); en TypeScript/React,
  comentarios JSDoc/TSDoc equivalentes. No hay fichero "sin explicar".
- La documentación técnica se **genera automáticamente desde los docstrings** con una
  herramienta estándar (p. ej. **mkdocstrings** + MkDocs o Sphinx/autodoc en backend;
  **TypeDoc** o VitePress en frontend), enlazada desde `docs/`. Nunca se redacta a mano lo
  que el código ya declara: la referencia de API sale de los docstrings.
- `docs/` mantiene lo que **no** puede derivarse del código (visión, decisiones,
  arquitectura, guías de uso, planes), sin duplicar la referencia autogenerada.
- **Estándar estricto:** al crear código nuevo o al **refactorizar** código existente, se
  añaden/actualizan los docstrings y se regenera la referencia. Es parte de la definición
  de "terminado" (como los tests de la premisa 12).

## 19. Panel de análisis: pestañas, no acordeones apilados
- El panel **ANALYSIS** del chat (y cualquier panel lateral denso) usa **navegación por
  pestañas**: una sección a la vez, agrupando paneles afines (p. ej. Speaking = diagnóstico +
  panel + recorrido). Se prohíbe apilar acordeones colapsables como único medio de organización.
- El contenido **nunca se corta**: cada sección tiene su propio scroll vertical; no se usa
  `text-overflow: ellipsis` ni `overflow: hidden` para truncar títulos o cuerpos dentro del panel.

## 20. Responsive 100% verificado y tests visuales
- **Responsive total verificable**: toda la UI debe adaptarse a **móvil, tablet y escritorio**
  sin overflow horizontal, con tap targets adecuados y drawers a pantalla completa en móvil.
  La verificación en los 3 breakpoints forma parte de la Definition of Done.
- **Tests visuales obligatorios**: al tocar UI (rediseños, layout, responsive) se capturan
  screenshots reproducibles con **Playwright** en al menos 3 viewports (escritorio/tablet/móvil)
  de las rutas principales, revisados antes de dar la tarea por terminada. El tooling y el script
  viven en `frontend/` (p. ej. `playwright.config.ts` + `npm run test:visual`).

## 21. La IA produce evidencia; el Mastery Engine determinista decide
- La IA (AI Teacher) **interactúa** y **da feedback**, pero **nunca decide** si un objetivo
  está dominado: esa decisión la toma el **Mastery Engine determinista** (recencia EMA,
  racha y confianza), igual que el resto de la lógica de la Academy.
- El **frontend tampoco declara** "acertado" por sí mismo: envía respuestas (nunca
  puntuaciones) y el backend las puntúa y convierte en evidencia.
- Terminar una lección (`lesson_completed`) **no** es evidencia de dominio; la evidencia
  proviene de evaluaciones deterministas (grammar, vocabulary, reading, listening) y del
  examen de nivel. Speaking/writing/pronunciation (con IA) quedan diferidos y, cuando
  lleguen, alimentarán el mismo motor determinista.
- El dominio puede **bajar** (decay): un objetivo dominado puede volver a "a repasar" si la
  evidencia reciente empeora. Se descarta el patrón `score = MAX(score, new)`.
- El **mastery es por objetivo** (`user + level + objective + skill`), no por destreza global
  del nivel: dominar `grammar` en el objetivo 1 **no** contagia el dominio a los objetivos 2..N
  que comparten destreza. El progreso del árbol (objetivo → módulo → nivel), el gating y el
  estado "dominado" se calculan desde `academy_objective_mastery`. La tabla
  `academy_skill_mastery` queda **solo** como evidencia de certificación del examen de nivel.
- Declarar un objetivo como dominado exige **consistencia**: además de alcanzar el umbral por
  destreza, se requiere un mínimo de intentos (`minimum_attempts`). Un único acierto no domina.
- El **gating curricular** se valida también en los endpoints de evaluación: solo se pueden
  evaluar, intentar o completar objetivos en estado `available` o `review` (nunca `locked`).

## 22. Paneles del chat redimensionables y persistentes
- En CHAT los tres paneles (conversaciones, zona central y Análisis) son **redimensionables** por
  el usuario con asas verticales visibles (grip) y accesibles (teclado, `aria-valuenow/min/max`).
- El ancho elegido se **persiste por usuario** (`settings.layout`), con persistencia eficiente:
  se guarda una sola vez al terminar de arrastrar (debounce), nunca en cada `pointermove`.
- En móvil/tablet los paneles son drawers y las asas se ocultan; el redimensionado solo aplica en
  desktop (≥1024px).
- Los límites de ancho están acotados (`SIDEBAR_MIN/MAX`, `RIGHT_MIN/MAX`) para no dejar un panel
  inservible; los valores persistidos se validan/recortan al cargar.
