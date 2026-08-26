# V1.21 (2/6) — P0-2: Validación determinista audio↔metadata (declarado vs real)

## Rol
Backend. Añades una capa de validación **determinista** que contrasta los metadatos declarados de cada grabación con lo que se puede medir del archivo WAV real. **Sin ML, sin dependencias nuevas, y sin pretender medir lo que no se puede medir.**

## Contexto
La auditoría externa pide (P0-2): comprobar automáticamente `declared speaker_count` vs real, `accent`, `duration`, `noise`, `speed`. El punto clave es la honestidad: algunas de esas señales **no se pueden verificar de forma determinista** sin análisis acústico, y hay que declararlo explícitamente en vez de fingir.

`audio_library.py` ya tiene `validate_manifest(manifest)` que valida la **estructura** (ids únicos, archivos únicos, rutas dentro de la biblioteca). Lo que falta es validar el **contenido** del archivo contra el metadata.

### Contratos exactos actuales (NO romper)
- `AudioLibraryEntry` tiene `duration: float` (segundos), `speaker_count: int`, `noise_level: str`, `accent: str`, `speech_rate: float | None` (este último lo añade el briefing P0-1/p18, junto con `recording_environment`, `overlap`, etc.).
- `resolve_file(entry, base=None) -> Path | None` devuelve la ruta del WAV (o `None` si escapa de la biblioteca). Úsala para localizar el archivo.
- `validate_manifest(manifest) -> list[str]` devuelve problemas como strings.

## Objetivo
Añadir `validate_audio_entry(entry, base=None) -> list[AudioValidationIssue]` que, de forma puramente determinista y con stdlib, compare lo declarado contra lo medible, e integrarla en el flujo de validación.

## Tareas

1. **Helper `wav_probe(path)`** en `audio_library.py` (o un módulo nuevo `audio_probe.py` si prefieres aislarlo):
   - Lee el WAV **solo con `wave`** (stdlib) y devuelve `{"duration": float, "channels": int, "framerate": int, "sample_width": int}`.
   - `duration = nframes / framerate` (con `framerate > 0`); si el archivo no abre como WAV, lanza/indica un error claro y no devuelves duración.

2. **Modelo de issue** — define `AudioValidationIssue` (Pydantic, igual que el resto del módulo):
   ```python
   class AudioValidationIssue(BaseModel):
       field: str          # "duration" | "speaker_count" | "noise_level" | "speech_rate" | "accent" | ...
       severity: str       # "error" | "warning" | "info"
       declared: str | None
       measured: str | None
       message: str
   ```

3. **`validate_audio_entry(entry, base=None) -> list[AudioValidationIssue]`** con estas reglas exactas:
   - **`duration`** — medible y verificable:
     - `resolve_file(entry, base)` → si `None`, issue `error` de ruta inválida (fuera de la biblioteca).
     - Si el archivo no existe o no es WAV válido → issue `error`.
     - Si `abs(declared - measured) > tolerance` (tol = max(0.5 s, 5% de declared)) → issue `error`/`warning` con ambos valores.
   - **`speaker_count`** — verificable **solo parcialmente y como proxy**:
     - `channels == 1` ⇒ como máximo 1 hablante. Si `declared speaker_count > 1` → issue `warning` ("mono sugiere un único canal; speaker_count>1 no verificable por canales").
     - `channels == 2` ⇒ estéreo, no prueba N hablantes. Si `declared > 2` → issue `info` ("el nº de hablantes no es verificable desde canales").
     - **Nunca** emitas un `error` por speaker_count: los canales no determinan hablantes. Sé honesto en el `message`.
   - **`speech_rate`** — **no verificable** sin transcripción forzada:
     - Si `declared speech_rate is not None` → issue `info` explicando que el WPM declarado no se valida automáticamente (requiere alineación fonética/ASR).
   - **`noise_level`**, **`accent`**, **`recording_environment`**, **`prosody`** — **no verificables de forma determinista**:
     - Emite issues `info` únicos por cada campo declarado, dejando claro que quedan sin validación automática (pendiente de análisis acústico). No te inventes una SNR.

4. **Integración**:
   - Añade `validate_audio_entries(manifest, base=None) -> dict[str, list[AudioValidationIssue]]` que mapea `audio_id -> issues` para todas las entradas.
   - Mantén `validate_manifest` intacta (estructura) y deja claro en docstrings que `validate_audio_entry(s)` valida **contenido** (requiere WAV real). No hagas que `validate_manifest` dependa de archivos, para no romper el test que valida un manifest sin WAV.
   - Expón `validate_audio_entry`/`validate_audio_entries` como importables públicos del módulo.

5. **CLI de auditoría** — amplía `backend/scripts/import_audio.py` (del briefing P0-1) con un subcomando o flag `--validate-all` que: carga el manifest, resuelve cada WAV y vuelca por `audio_id` los issues en JSON. Si el manifest está vacío, imprime que no hay entradas.

6. **Tests** — en `backend/tests/test_audio_library.py`:
   - Genera un WAV sintético con `wave` (tempfile) de duración conocida; comprueba que `validate_audio_entry` da `0` issues de duración.
   - Cambia el `duration` declarado y comprueba que aparece un issue de duración con `declared`/`measured` correctos.
   - WAV mono con `speaker_count=3` → issue `warning` (no `error`).
   - `speech_rate`/`noise_level`/`accent` declarados → issues `info` (no `error`).
   - Archivo no-WAV → issue `error`.

## Restricciones
- **Cero dependencias nuevas** (`wave` es stdlib).
- `resolve_file` y la comprobación `is_relative_to(base)` no se tocan.
- No inventes una métrica de ruido/acento. Los `info` de "no verificable" son un requisito, no un atajo.
- Pasa `pytest` y `ruff`. No toques frontend.
- Crea un único commit `feat: validación determinista audio↔metadata` (no hagas push). Deja el briefing untracked.
