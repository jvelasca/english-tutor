# Guía de desarrollo — English Tutor

> Cómo trabajar en este proyecto desde 0 y cómo operan el gerente y los subagentes.

## 1. Puesta en marcha desde 0

### Requisitos
- Ollama corriendo en `http://127.0.0.1:11434`.
- Python 3.11+ y Node.js 18+.

### Con F5 (recomendado)
Pulsa **F5** en Cursor y elige la configuración **"English Tutor (F5)"** la primera vez.
Arranca backend + frontend en dos terminales y abre el navegador. Configuración en
`.vscode/launch.json` (compuesto con `stopAll`, así que al parar se cierran ambos).

### Manual

### Backend
```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe download_models.py   # descarga Whisper + voz Piper (solo la 1ª vez)
.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

### Frontend
```powershell
cd frontend
npm install
npm run dev
```

Abrir **http://localhost:5173**.

## 2. Flujo de trabajo (gerente + subagentes)

1. El **gerente** mantiene `PLAN.md` (backlog) y `docs/` (premisas y arquitectura).
2. Para cada tarea, el gerente escribe un **briefing autocontenido** en `agentes/<nombre>.md`.
   El briefing incluye: rol, objetivo, contexto, tarea, criterios de aceptación, restricciones y salida.
3. El briefing se **ejecuta** (el gerente directamente, o el cliente desde su agente local).
4. El **gerente** revisa, integra, actualiza la documentación y genera el siguiente paso.

## 3. Regla de contexto (anti-alucinación)

- Si un agente (gerente o subagente) se satura y hay riesgo de alucinación, se abre un
  **agente/contexto nuevo** con contexto limpio (premisa 12).
- Los subagentes son autocontenidos a propósito: no dependen del historial acumulado.
- **Antes de alucinar, reiniciar el contexto.** La documentación (`docs/`) es el ancla
  para reanudar desde cero sin perder el hilo.

## 4. Estándares de documentación (VITAL)

- Cada feature nueva actualiza: `README.md` (si cambia el arranque), `docs/ARQUITECTURA.md`
  (si cambia la estructura), `PLAN.md` (estado de hitos).
- Los endpoints de la API se documentan en una tabla de `docs/` o `README.md`.
- Un programador nuevo debe poder arrancar y entender el proyecto **solo leyendo `docs/`**.

## 5. Git / GitHub

- Repositorio remoto: **https://github.com/jvelasca/english-tutor** (privado).
- Durante el desarrollo: commits locales con mensajes claros (formato `tipo: descripción`).
- Cada hito estable se etiqueta (`git tag vX.Y.Z`) y se publica como **release** en GitHub.
- Desde GitHub: seguimiento con **issues** (backlog), **PR** (cambios revisables) y **releases**.
- Flujo típico por hito:
  1. Rama `feature/<hito>` → commits pequeños.
  2. PR a `main` con descripción y checklist de la Definition of Done.
  3. Merge, tag `vX.Y.Z` y release en GitHub.

```powershell
git checkout -b feature/<hito>
# ... commits ...
git push -u origin feature/<hito>
gh pr create --title "<hito>" --body "..."
```

## 6. Definición de "terminado" (Definition of Done)

Una tarea está terminada cuando:
1. Cumple los criterios de aceptación del briefing.
2. Pasa el chequeo de tipos (frontend: `npx tsc --noEmit`; backend: sin errores de import).
3. Se verifica en ejecución (endpoint/UI probados).
4. La documentación relevante está actualizada.
5. Tiene sus tests (y pasan).

## 7. Tests y scripts

### Tests
- **Backend** (`backend/tests/`, pytest):
  ```powershell
  cd backend
  .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
  .venv\Scripts\python.exe -m pytest tests/ -q
  ```
- **Frontend** (`frontend/src/**/*.test.ts`, vitest):
  ```powershell
  cd frontend
  npm install
  npm test          # vitest run
  ```

### Scripts
- **Backend** (`backend/scripts/`): scripts de utilidad (p. ej. `smoke_test.py` contra el
  servidor en ejecución).
- **Frontend** (`frontend/scripts/`): scripts de verificación (p. ej. `check.ps1` → tsc + tests).

> Los tests deben ser rápidos y deterministas: no dependen de la red ni de modelos externos.
> Para probar integración real (Ollama, Whisper, Piper) se usan los scripts de `scripts/`.
