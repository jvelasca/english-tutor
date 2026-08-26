# V1.21 (1/6) — P0-1: Corpus de audio humano 1.0 (esquema ampliado + scaffolding + tooling)

## Rol
Backend. Extiendes la infraestructura de la biblioteca de audio humano para poder albergar y validar grabaciones reales. **NO grabas audio, NO inventas metadatos, NO añades dependencias.**

## Contexto
La V1.20 dejó la biblioteca con infraestructura correcta pero **vacía**:

```json
{"version": "1.0.0", "entries": []}
```

Esto es lo que la auditoría externa llama el "cuello de botella": la arquitectura está al ~95% pero el contenido de audio real está al ~20%.

El auditor propone (puntos 24 y 25 de su informe) que cada grabación lleve metadatos ampliados y que el `file` pueda vivir bajo una jerarquía por nivel y hablante, de modo que el sistema pueda saber "este alumno ya ha escuchado demasiado a este hablante" y cambie de voz.

### Contratos exactos actuales (NO romper)
Archivo `backend/services/audio_library.py`:

```python
AUDIO_LIBRARY_VERSION = "1.0.0"

class AudioLibraryEntry(BaseModel):
    audio_id: str          # único
    file: str              # nombre del WAV dentro de AUDIO_LIBRARY_DIR (hoy: sin subcarpetas)
    speaker_id: str
    accent: str
    speaker_count: int
    noise_level: str
    duration: float        # segundos
    transcript: str

class AudioLibraryManifest(BaseModel):
    version: str
    entries: list[AudioLibraryEntry]
```

Funciones existentes que **deben seguir funcionando y pasar sus tests**:

- `library_dir()` → `Path` de `AUDIO_LIBRARY_DIR`.
- `manifest_path()` → `Path` del `manifest.json`.
- `load_manifest()` → `AudioLibraryManifest`.
- `entry_for(audio_id)` → `AudioLibraryEntry | None`.
- `resolve_file(entry, base=None)` → `Path | None`. **Ya soporta rutas anidadas** (usa `is_relative_to(base)` y rechaza `../`). Solo hay que actualizar el docstring/validación para permitir `file` con subcarpetas.
- `is_recorded(audio_id)` / `recorded_audio_path(audio_id)`.
- `library_summary()` → dict de estadísticas.
- `validate_manifest(manifest)` → lista de problemas (ids únicos, archivos únicos, ruta dentro de la biblioteca).

Nota: `resolve_file` hace `(base / entry.file).resolve()` y comprueba `is_relative_to(base)`. Eso ya deja pasar rutas anidadas como `A1/speaker_001/001_hello.wav` y rechaza escapes. No cambies esa lógica de seguridad.

## Objetivo
Ampliar el esquema de metadatos, permitir jerarquía de carpetas por nivel/hablante y dejar tooling de importación determinista (solo stdlib), sin ningún WAV real aún.

## Tareas

1. **Ampliar `AudioLibraryEntry`** con los campos que pide el auditor, todos con default sensato para no romper nada:
   - `gender: str = "unknown"` (valores sugeridos: `"female" | "male" | "unknown"`)
   - `age_band: str = "unknown"` (p. ej. `"child" | "teen" | "adult" | "senior" | "unknown"`)
   - `region: str = "unknown"` (región geográfica/dialecto)
   - `speech_rate: float | None = None` (WPM declarado, `None` = sin declarar)
   - `spontaneity: str = "scripted"` (`"scripted" | "semi_scripted" | "spontaneous"`)
   - `recording_environment: str = "studio"` (`"studio" | "quiet_room" | "noisy" | "field"`)
   - `overlap: bool = False` (¿hay solapamiento de voces?)
   - `connected_speech: bool = False` (¿presenta *connected speech*: elisiones, *linking*, reducciones?)
   - `prosody: str = "unknown"` (etiqueta libre de rasgos prosódicos, p. ej. `"neutral"`, `"expressive"`)
   - `task_type: str = "unknown"` (tipo de tarea de listening: `"monologue" | "dialogue" | "announcement" | "instruction" | ...`)
   - `cefr: str = "unknown"` (`"A1" | "A2" | "B1" | "B2" | "unknown"`)

2. **Permitir `file` con subcarpetas**. Cambia el docstring de `AudioLibraryEntry.file` (y de `resolve_file`) para dejar claro que `file` es una ruta relativa dentro de `AUDIO_LIBRARY_DIR`, p. ej. `B1/speaker_003/dialogue_shop.wav`. `resolve_file` ya es correcto: NO lo toques salvo el docstring. Asegúrate de que `validate_manifest` no rechace rutas anidadas.

3. **Bump de versión de manifiesto**: `AUDIO_LIBRARY_VERSION = "1.1.0"` y actualiza `backend/audio_library/manifest.json` a `{"version": "1.1.0", "entries": []}` (sigue vacío).

4. **`validate_manifest`**: añade validación de los campos nuevos con `Literal` (usa el mismo patrón de checks limpios que ya existe). P. ej.: `cefr` debe estar en `{"A1","A2","B1","B2","unknown"}`, `gender` en `{"female","male","unknown"}`, `speech_rate` si no es `None` debe ser `> 0`, etc. No reescribas la función entera: añade checks.

5. **`library_summary()`**: añade desglose útil para el futuro selector de voz: recuento por `cefr`, por `speaker_id`, y por `accent`/`region`. Devuelve un dict que siga siendo compatible con lo que hoy consuma `library_summary` (añade claves nuevas, no quites las existentes).

6. **Tooling de importación determinista** — nuevo `backend/scripts/import_audio.py`:
   - Un helper puro y testeable: `wav_metadata(path: Path) -> dict` que lee un WAV **solo con `wave`** (stdlib) y devuelve `{"duration": float, "channels": int, "framerate": int, "sample_width": int}`. Maneja `wave.Error` devolviendo `{}` o lanzando un error claro si no es WAV válido.
   - Un CLI (`argparse`, stdlib) `import_audio.py --wav <ruta> --audio-id <id> --speaker-id <id> [--cefr B1] [--accent ...] ...` que: (a) calcula `duration` real desde el WAV, (b) compone un `AudioLibraryEntry` con el resto de campos pasados por flags, (c) valida con `validate_manifest`, (d) añade/actualiza la entrada en `manifest.json` y (e) copia el WAV a `library_dir()/file`. **No inventes valores**: los campos no pasados por flag toman su default.
   - Imprime el entry resultante en JSON para que sea inspeccionable.

7. **Tests** — amplía `backend/tests/test_audio_library.py` (o crea uno nuevo si no existe) para:
   - `AudioLibraryEntry` con los campos nuevos (validación de `Literal`).
   - `resolve_file` aceptando rutas anidadas y rechazando `../` (conserva el test de seguridad).
   - `validate_manifest` con un entry que viola `cefr`/`gender`.
   - `wav_metadata` con un WAV sintético generado en el test con `wave` (tempfile), y con un archivo no-WAV (debe fallar limpio).
   - `library_summary` incluye los desgloses nuevos.

## Restricciones
- **Cero dependencias nuevas.** `wave`, `argparse`, `pathlib`, `tempfile` son stdlib.
- **El `manifest.json` queda vacío** (`entries: []`). No fabriques grabaciones.
- No toques `resolve_file` salvo docstring: la comprobación de seguridad `is_relative_to(base)` es sagrada.
- No rompas los consumidores existentes de `AudioLibraryEntry` (p. ej. `listening.py` usa `is_recorded`/`entry_for`): los campos nuevos deben ser opcionales/con default.
- Pasa `pytest` y `ruff`. No toques frontend en este briefing.
- Crea un único commit `feat: corpus de audio humano 1.0 (esquema + scaffolding + import)` (no hagas push). Deja el briefing untracked.
