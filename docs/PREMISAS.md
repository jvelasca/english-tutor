# Premisas del proyecto — English Tutor

> **Fuente de verdad.** Si algo entra en conflicto con este documento, manda este documento.
> Mantenido por el gerente del proyecto.

## 1. Visión
Profesor/asistente de inglés que conversa por voz y texto, **100% local** (sin Internet,
sin cuentas, sin costes). Arranca con diálogo por texto, luego voz, y evoluciona hacia un tutor
completo.

## 2. Principio rector: 100% local
- Todo el procesamiento (LLM, voz→texto, texto→voz) corre en la máquina del usuario.
- En desarrollo se aprovecha todo (GPU, servicios locales, etc.).
- Única excepción admitida: la descarga inicial de modelos y dependencias.
- Prohibido depender de APIs en la nube (Google STT, Microsoft TTS, OpenAI, etc.).

## 3. Stack (fijado)
- **Backend:** Python + FastAPI + Pydantic (tipado fuerte).
- **Frontend:** Vite + React + TypeScript (modo estricto).
- **LLM:** Ollama (servicio local). Modelo inicial: `qwen3.5:9b`.

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

## 13. Multi-usuario (seguimiento independiente)
- La app admite **varios usuarios locales** (perfiles), cada uno con su propio espacio:
  conversaciones, progreso, correcciones, puntuaciones de pronunciación y ajustes,
  **totalmente independientes** entre sí.
- Sin cuentas en la nube (coherente con la premisa 2): los perfiles son locales y se
  seleccionan de forma simple al abrir la app.
- **Aislamiento total de datos entre usuarios**: nada de un usuario puede verse desde otro.
- El seguimiento de progreso (historial, estadísticas, logros) es **por usuario**.

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
