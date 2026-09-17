# Manifiesto de runtime y offline (eje RA de V3.71)

> Generado por `python -m scripts.audit_dossier runtime-audit`.
> Instrumento de SOLO LECTURA: no descarga ni escribe en `data/`.

## 1. Puntos de red del backend

| Fichero | needle | tipo | oculto | cuadra | nota |
|---|---|---|---|---|---|
| `services/llm.py` | `ollama.AsyncClient()` | loopback | no | si | Cliente Ollama SIN argumentos: el endpoint es el default de la libreria (127.0.0.1:11434), no una constante de config.py |
| `services/net_interfaces.py` | `socket.getaddrinfo` | lan | no | si | V3.73: descubrimiento de la IP de LAN enumerando las direcciones del propio equipo. SIN salida a Internet (antes: socket UDP perezoso a 8.8.8.8, retirado en V3.73) |
| `services/network.py` | `socket.getaddrinfo` | lan | no | si | Resolucion mDNS real de <host>.local; sin respondedor devuelve False y la UI cae a la URL por IP |
| `services/voice_downloads.py` | `urllib.request.urlopen` | internet | no | si | Descarga de voces Piper desde huggingface.co (rhasspy/piper-voices). V3.71 (eje RD): usa urlopen con timeout REAL y verifica el Content-Length |
| `services/tts.py` | `from services import voice_downloads` | internet | SI | si | DEPENDENCIA OCULTA: el TTS importa el descargador de voces en la descarga perezosa; el disparador real esta en routers/voz.py |
| `routers/voz.py` | `ensure_voice_for_language` | internet | SI | si | DEPENDENCIA OCULTA EN RUTA DE PRODUCTO: un POST /api/tts de un idioma sin voz instalada dispara una descarga en caliente |
| `services/stt.py` | `download_root=str(WHISPER_DIR)` | internet | SI | si | DEPENDENCIA OCULTA: si el modelo Whisper no esta en disco, faster_whisper lo descarga en la primera transcripcion |
| `download_models.py` | `from services.voice_downloads import download_voice, spec_for` | internet | no | si | Bootstrap EXPLICITO: voces Piper por defecto. V3.71 (eje RB): delega en el catalogo curado en vez de tener URL y urlretrieve propios; la primitiva de red vive en services/voice_downloads.py (timeout real) |
| `download_models.py` | `download_root=str(WHISPER_DIR)` | internet | no | si | Bootstrap EXPLICITO: modelo Whisper |

- Reparto por tipo: {'loopback': 1, 'lan': 2, 'internet': 6}
- Dependencias de Internet NO declaradas (ocultas): **3**
  - `services/tts.py:from services import voice_downloads`
  - `routers/voz.py:ensure_voice_for_language`
  - `services/stt.py:download_root=str(WHISPER_DIR)`
- Declaraciones que ya NO cuadran con el codigo: ninguna

## 2. Manifiesto de modelos (debe estar en disco sin Internet)

| id | artefacto | ruta | presente | MB |
|---|---|---|---|---|
| `piper:en_US-lessac-medium.onnx` | Piper · voz inglesa por defecto (.onnx) | `backend/models/piper/en_US-lessac-medium.onnx` | si | 60.3 |
| `piper:en_US-lessac-medium.onnx.json` | Piper · voz inglesa por defecto (.onnx.json) | `backend/models/piper/en_US-lessac-medium.onnx.json` | si | 0.0 |
| `piper:es_ES-davefx-medium.onnx` | Piper · voz espanola por defecto (.onnx) | `backend/models/piper/es_ES-davefx-medium.onnx` | si | 60.3 |
| `piper:es_ES-davefx-medium.onnx.json` | Piper · voz espanola por defecto (.onnx.json) | `backend/models/piper/es_ES-davefx-medium.onnx.json` | si | 0.0 |
| `whisper:small` | faster-whisper `small` (cache en disco) | `backend/models/whisper` | si | 927.4 |

- Ausentes: **0** (nada que descargar)

## 3. Ollama (loopback)

- Endpoint: `http://127.0.0.1:11434` (default de la libreria `ollama`, **no** declarado en `config.py`)
- Estado: **no sondeado** (medicion determinista). El sondeo en vivo es `runtime-audit --probe-ollama`.
