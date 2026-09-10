# v3.40.0 — Traductor de viaje bidireccional ES↔EN (5.º destino)

**Fase 2 del plan maestro V3.39+ (diccionario reversible → Traductor → motor de
tarea óptima → transferencia real). Release ADITIVA que añade una utilidad
AUXILIAR de traducción en ambos sentidos por voz o texto: se habla o escribe en
un idioma y se lee/escucha la traducción en el otro, con voces Piper en español
descargables. No toca el núcleo de aprendizaje, no registra evidencia, funciona
sin perfil y todo el contrato HTTP es aditivo y retrocompatible (`direction` y
`language` con sus valores históricos por defecto).**

Versión de app `3.39.0 → 3.40.0`. Backend (`services/translate.py`,
`schemas/translate.py`, `routers/translate.py`, `schemas/voz.py`,
`routers/voz.py`, `services/tts.py`, `services/voice_downloads.py`) + frontend
(`features/translator/TranslatorScreen.tsx`, `api/translate.ts`, `api/voz.ts`,
`components/ListenButton.tsx` y `MicButton.tsx`, `app/routes.ts`,
`router/paths.ts`, `router/routeMap.ts`, `app/Workspace.tsx`,
`app/Navigation.tsx`, i18n) + tests y docs.

## Contexto

La app tenía un diccionario reversible (V3.39) pero ninguna forma de traducir
**frases** para un uso de viaje: hablar en español y que la app lo escriba y lo
lea en inglés, y al revés. La traducción de apoyo existente (`/api/translate`)
era unidireccional EN→ES, pensada para pantallas de práctica, y el TTS resolvía
una única voz (inglesa).

La decisión de diseño fue **no tocar el núcleo**: el Traductor es una utilidad
independiente con su propia ruta (`/traductor`), su propio estado y su propio
historial, y **no registra evidencia** (ni `vocabulary`, ni eventos, ni puertas
de dominio). La voz se resuelve por **idioma**, de modo que el mismo endpoint
`/api/tts` sirve voz inglesa o española según lo pida el cliente.

```text
ES → APP   MicButton(language="es") → /api/transcribe(language=es)
           → /api/translate(direction="es-en") → texto EN + /api/tts(language=en)
APP → ES   MicButton(language="en") → /api/transcribe(language=en)
           → /api/translate(direction="en-es") → texto ES + /api/tts(language=es)
```

## Qué cambia

### 1. Traducción bidireccional (`services/translate.py`)

- `translate_text(text, model=None, direction="en-es")`: prompt por dirección
  (`_SYSTEM_PROMPT_EN_ES`, el histórico, y `_SYSTEM_PROMPT_ES_EN`, nuevo) y
  **caché por `(direction, text)`** — la misma cadena en sentidos distintos no
  colisiona.
- Una dirección desconocida cae a `"en-es"` (defensa en profundidad); el
  esquema Pydantic la restringe a `Literal["en-es","es-en"]` (422 si no).
- `/api/translate` sigue siendo best-effort: 502 si el modelo local no está, y
  **no registra nada**.

### 2. Voz por idioma (`/api/tts`, `services/tts.py`)

- `TTSRequest.language` (defecto `"en"`) y `transcribe(blob, language)` en el
  cliente: el STT de faster-whisper ya aceptaba `language`, solo había que
  pasarlo desde el Traductor (`"es"`).
- `voice_language(id)` (puro) extrae el idioma del locale (`en_US-lessac-medium`
  → `en`, `es_MX-ald-medium` → `es`).
- `resolve_voice(prefs, language="en")` (puro) elige, en este orden: voz
  preferida del usuario si está instalada **y** es del idioma → voz por defecto
  del sistema si es del idioma → primera voz instalada del idioma → fallback
  global (degradación documentada antes que quedarse sin audio).
- El catálogo curado de Piper deja de ser solo-inglés: **tres voces `es_*`
  medium** descargables desde Ajustes → Voces (`es_ES-davefx-medium`,
  `es_ES-sharvard-medium`, `es_MX-ald-medium`), con etiquetas en `VOICE_LABELS`.
  Se mantiene la política de no ofrecer calidades `high`/`low`.

### 3. Quinto destino de navegación (`/traductor`)

- `Route` gana `"translator"`; `TRANSLATOR_PATH = "/traductor"`; `routeMap`
  reversible (10 valores de `Route`, `pathToRoute("#/traductor")` → `translator`)
  y `ROUTES` lo registra tras el diccionario, en el MISMO bloque auxiliar tras el
  separador.
- `Navigation` usa el icono `Languages` y la bottom-nav pasa a `grid-cols-5`
  (cabecera sin cambios de corte: píldoras desde `xl` con `overflow-x-auto`).
- `Workspace` renderiza `TranslatorScreen` en modo perezoso y le pasa el perfil
  activo (opcional).

### 4. Pantalla `TranslatorScreen.tsx` (`features/translator/`)

- Conmutador ES→EN / EN→ES con **ES→EN por defecto** (el caso del viajero) y
  botón ⇄ que intercambia sentido y textos.
- Entrada por **voz** (`MicButton`, ahora con `language` y auto-stop a los 120 s)
  o por **texto**; el dictado traduce en cuanto llega la transcripción.
- Panel de resultado con la traducción y `ListenButton` para escuchar origen y
  destino en su idioma.
- **Historial reciente** (8 frases) en `localStorage`
  (`english-tutor.translator-history`) con reutilización de una consulta y
  borrado.
- Aviso «Herramienta de apoyo»: usar el traductor no cambia el progreso. Sin
  perfil el traductor es plenamente funcional.

## Compatibilidad

| Elemento | Antes | Ahora |
| --- | --- | --- |
| `POST /api/translate` | `{text, model?}` | `{text, model?, direction?}` (defecto `"en-es"`) |
| `POST /api/tts` | `{text}` | `{text, language?}` (defecto `"en"`) |
| `POST /api/transcribe` | `language` (form) | Igual (el cliente ahora lo usa) |
| `resolve_voice(prefs)` | Voz preferida o default | `resolve_voice(prefs, language="en")` (comportamiento histórico intacto) |
| Catálogo Piper | Solo `en_*` | `en_*` + `es_*` (medium) |
| Rutas | 9 destinos resueltos | + `/traductor` |

Ningún campo existente cambia de semántica y ninguna llamada existente necesita
tocar su payload.

## Tests

- **Backend pytest 1924 passed** (+14). `test_translate.py`: prompt inverso,
  prompt histórico por defecto, caché por dirección, dirección desconocida →
  `en-es`, endpoint ES→EN y 422 de dirección inválida. `test_voices.py`:
  `voice_language`, cinco casos de `resolve_voice` por idioma, catálogo
  inglés+español medium y tres casos de `/api/tts` con `language` (voz del idioma
  con y sin perfil, y defecto inglés retrocompatible).
- **Frontend vitest 70 ficheros/597 tests** (+2 ficheros/+19).
  `features/translator/TranslatorScreen.test.tsx` (dirección por defecto, texto,
  ⇄, inversión que limpia el resultado, error del modelo, dictado con idioma y
  auto-traducido, historial persistido/reutilizado/borrado y uso sin perfil),
  `api/voz.test.ts` (idioma en `transcribe` y `speak`, contrato por defecto),
  dirección en `api/translate.test.ts`, `/traductor` en `routeMap.test.ts` y los
  5 destinos en `Navigation.test.tsx`.
- `ruff check backend/` limpio, `tsc --noEmit` limpio y
  `python scripts/check_release_consistency.py` → **3.40.0** exit 0.

## Fuera de alcance (fases siguientes)

- **Fase 3** — motor de tarea óptima por skill
  (`skill_priority`/`limiting_skill`/`select_task`), actividad de escritura que
  registra `written_production`, y robustez de señales (recencia de errores,
  distribución de latencia, `automatic` derivado, orden cronológico del ledger y
  batching de cues).
- **Fase 4** — transferencia contextual real, actividad `spontaneous_use`,
  agregación por `lexical_unit` y descomposición de `wordDrill.tsx`.
