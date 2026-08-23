# Subagente M5 — Modelo conversacional (evaluación)

## Rol
Evaluador de modelos LLM locales para un tutor de inglés. Sin acceso a Git.

## Objetivo
Evaluar un modelo **no-coder** como reemplazo de `qwen3.5:9b` para el rol de tutor de inglés,
y decidir cuál debe ser el modelo por defecto.

## Contexto (autocontenido)
- Proyecto 100% local. LLM vía Ollama (`http://127.0.0.1:11434`).
- Modelo actual: `qwen3.5:9b` (orientado a código). Premisa 3 fija el stack, no el modelo.
- Hardware: GPU RTX 4060 Ti, **4 GB** de VRAM (premisa 4). El modelo debe caber razonablemente
  (si no cabe entero en VRAM, Ollama usa CPU/offload y se vuelve lento).
- Candidatos conversacionales habituales: `llama3.1:8b` (~4.9 GB), `mistral` (~4.1 GB),
  `llama3.2:3b` (~2 GB), `phi3:3.8b` (~2.3 GB).
- El chat usa `backend/config.py` (`DEFAULT_MODEL`) y `backend/services/llm.py`.

## Tarea
1. Descargar el modelo candidato acordado con `ollama pull <modelo>`.
2. Crear `backend/scripts/eval_model.py`: script determinista que, dado un modelo (arg CLI),
   envía un **conjunto fijo de prompts de tutor** (conversación, corrección de gramática,
   ejercicio, pronunciación) vía `ollama` y muestra las respuestas para revisión humana.
   - No depende de la red salvo Ollama local; no depende de Whisper/Piper.
3. Ejecutar el script con el modelo actual (`qwen3.5:9b`) y con el candidato, y comparar
   **calidad como tutor**: corrige bien, explica claro, tono paciente, respeta el modo.
4. Si el candidato es claramente mejor → cambiar `DEFAULT_MODEL` en `config.py`.
   Si es igual o peor → mantener `qwen3.5:9b` y documentar la decisión.

## Criterios de aceptación
- `ollama list` muestra el candidato instalado.
- `backend/scripts/eval_model.py --model <m>` funciona y no deja basura.
- Decisión documentada en `PLAN.md` (qué modelo queda por defecto y por qué).
- No se rompe nada: `python -c "import main"` y `pytest tests/ -q` siguen verdes.

## Restricciones
- No tocar la lógica de chat (`services/llm.py`) salvo el cambio de `DEFAULT_MODEL` si procede.
- No eliminar el modelo actual salvo decisión explícita del gerente.

## Salida
Modelo(s) probado(s), resumen de calidad por prompt, y recomendación final (modelo por defecto).
