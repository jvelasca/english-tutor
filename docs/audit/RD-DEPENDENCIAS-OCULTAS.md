# RD — Dependencias ocultas y degradación (TTS/offline) (V3.71)

> **Tipo:** dossier de evidencia **interno** (no es un informe de auditoría
> externa). Por eso **no lleva letra**: `Z` y `Z2` siguen reservadas a los
> informes externos pendientes de V3.69
> (`agentes/auditoria-externa-v369-seguimiento.md`).
> **Eje auditado:** **RD** («¿hay dependencia accidental de Internet y la
> degradación es explícita?») del briefing
> `agentes/v371-runtime-offline-instalacion.md` §D.
> **Cierra además:** **RA-01** y **RA-03** del eje RA
> (`docs/audit/RA-RUNTIME-OFFLINE.md`): la descarga en caliente y el cuelgue sin
> red dejan de tener la forma que los hacía hallazgos.
> **Punto de partida:** `v3.70.0` (`9ba9c49`) + eje RE (`2c07fe0`) + eje RA
> (`fdefb2c`).
> **Autor:** el propio proyecto.
> **Fecha:** 2026-09-16.

## Alcance

- **Se audita:** el camino de descarga de voces Piper, que es la única dependencia
  de Internet que el proyecto tiene **dentro de una ruta de producto**
  (`POST /api/tts`). En concreto: si su timeout existe de verdad, si el fallo
  sin red es rápido o un cuelgue, si la degradación a otra voz es explícita y si
  lo descargado se verifica.
- **Se cierra:** el **P1 de TTS/offline** que el proyecto venía **difiriendo desde
  V3.46** en cuatro sitios (`release-notes-v3.47.0.md:110-113`;
  `release-notes-v3.48.0.md:97`; `CHANGELOG.md:439`; `CHANGELOG.md:453`), y que
  nunca tuvo cierre explícito. Sus tres vectores declarados eran
  **«timeout, UI y degradación»**.
- **No se audita:** el resto de dependencias de red (eje RA, ya entregado), la
  instalación limpia (RB), el runtime de producto (RC) ni la síntesis (RF).

## Método

1. **Medir antes de tocar.** Cada afirmación se comprueba contra el código y
   contra el comportamiento observable, no contra lo que el proyecto declara.
2. **Endurecimiento mínimo.** Solo se cambia lo que cierra un vector medido, con
   **test que falla sin el cambio**. Nada de refactor.
3. **Re-declarar con fase lo que no se cierra**, en lugar de cerrarlo en falso.
4. **El instrumento del eje RA debe seguir cuadrando**: si el endurecimiento
   cambia el código, la declaración de red debe actualizarse (y el test de
   anti-deriva lo exige).

## Evidencia

### E1 — El timeout de la descarga era **código muerto** (vector «timeout»)

```python
# V3.70 y anteriores — backend/services/voice_downloads.py
def _download_file(url: str, dest, timeout: float = 300.0) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        urllib.request.urlretrieve(url, tmp)   # <-- timeout NUNCA se usa
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        ...
```

`urllib.request.urlretrieve(url, filename=None, reporthook=None, data=None)` **no
acepta** un parámetro `timeout`. El `timeout: float = 300.0` declarado se pasaba
como **argumento posicional a nada**: la función se llamaba sin él. Consecuencia
medida: la descarga usaba el **timeout global de socket**, que en Python es
**`None`** por defecto ⇒ **sin límite alguno**.

Por qué importa exactamente aquí: esta descarga se dispara **dentro de
`POST /api/tts`** (`routers/voz.py:54`, `await run_in_threadpool(...)`). Con la
red cortada y una voz ausente, la petición del alumno **se queda esperando sin
cota** — no 5 minutos: indefinidamente, hasta que el SO agote sus reintentos de
TCP. La promesa implícita del código («300 s») **no existía**.

**Sin cobertura:** ningún test llamaba a `_download_file`; los **9** sitios que
lo mencionan en `backend/tests/test_voices.py` lo **sustituyen** por un doble
(`monkeypatch.setattr(voice_downloads, "_download_file", ...)`). Por eso el
parámetro muerto sobrevivió desde V3.45 sin que nadie lo notara.

### E2 — La degradación era silenciosa (vector «degradación»)

Si no hay voz del idioma pedido, `resolve_voice` cae al **fallback global**
(`services/tts.py:132-154`): se lee **español con voz inglesa** — la degradación
que V3.45 quiso evitar, reintroducida por la puerta de atrás cuando la descarga
no es posible. Y no se enteraba **nadie**:

| Observador | Antes | Ahora |
|---|---|---|
| Log del backend | nada | `logger.warning("TTS en es servido con una voz de otro idioma (…): degradación")` |
| Cliente HTTP | nada: recibía audio y no podía saber con qué voz | `X-TTS-Voice` (voz real) y `X-TTS-Degraded` (`0`/`1`) |
| Navegador desde otro origen | — | expuestas por CORS (`expose_headers` en `main.py`) |

Nota de honestidad: **la UI todavía no lee esas cabeceras**. Eso es el vector
«UI» del P1 y se re-declara con fase en **RD-04** (V3.72, UX/product completion).
Lo que se cierra ahora es que **el hecho deje de ser indetectable**.

### E3 — Lo descargado no se verificaba (vector «integridad»)

`spec.size_mb = 63` es una **pista de presentación**, no una verificación. El
único control era `dest.exists() and dest.stat().st_size > 0`: bastaba **1 byte**
para dar una voz por instalada y servible a Piper — incluyendo el caso realista de
un CDN devolviendo una página de error con `200`.

### E4 — El endurecimiento aplicado (`voice_downloads.py`, `routers/voz.py`, `main.py`)

| # | Cambio | Qué cierra |
|---|---|---|
| **RD-01** | `_download_file` usa `urlopen(Request, timeout=...)` en lugar de `urlretrieve`, y el timeout pasa a tener **valor real** (`VOICE_DOWNLOAD_TIMEOUT_SECONDS = 15.0`) | El vector «timeout»: E1. Sin red, el fallo es **acotado** en lugar de ilimitado |
| **RD-02** | Verificación de lo recibido contra el `Content-Length` declarado, y rechazo de descarga **vacía**; el `.part` se limpia siempre | E3 (integridad) |
| **RD-03** | `/api/tts` registra y **declara** `X-TTS-Voice` / `X-TTS-Degraded`, expuestas por CORS | El vector «degradación»: E2 |

**Por qué 15 s no rompe las descargas legítimas.** El timeout de `urlopen` se
aplica **por operación de socket** (la conexión y cada lectura), **no** al total.
Un `.onnx` de ~60 MB a 200 KB/s tarda 5 minutos y **completa sin problema**: solo
aborta si **ninguna** operación avanza en 15 s — es decir, si el host no responde.
Ese es exactamente el caso que hay que cortar.

**Coste de llamada: cero.** `download_voice(voice_id)` conserva su firma, así que
los tres llamadores (`services/tts.py:190`, `routers/voices.py:75`,
`download_models.py:40`) y los **9** dobles de test siguen funcionando **sin
tocarlos**. El cambio vive dentro de la función privada.

### E5 — El instrumento del eje RA sigue cuadrando

El endurecimiento cambió el código que el eje RA declara, así que la declaración
se actualizó (`services/voice_downloads.py`: `urllib.request.urlretrieve` →
`urllib.request.urlopen`) y el test de anti-deriva lo exige. Tras el cambio:

```
| `services/voice_downloads.py` | `urllib.request.urlopen` | internet | no | si | … usa urlopen con timeout REAL y verifica el Content-Length |
- Declaraciones que ya NO cuadran con el codigo: ninguna
- Dependencias de Internet NO declaradas (ocultas): 3
```

El par `docs/audit/generated/runtime-audit.{md,json}` se regenera **byte a byte**
(`Get-FileHash` idéntico). Es decir: **el instrumento detecta deriva de verdad**,
no solo en teoría.

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Estado |
|---|---|---|---|---|
| **RD-01** | **P1** | **El timeout de la descarga de voces era código muerto** (`urlretrieve` no acepta `timeout`), así que la descarga **no tenía límite** y `POST /api/tts` podía quedarse colgado **indefinidamente** sin red. Sin cobertura: 9 dobles, 0 tests de la función real | E1; `services/voice_downloads.py:112-124` (antes) | **cerrado** (RD-01) |
| **RD-02** | **P2** | **La degradación de voz era silenciosa**: español leído con voz inglesa sin log ni aviso al cliente | E2; `services/tts.py:122-155` | **cerrado** (RD-03) |
| **RD-03** | **P2** | **Lo descargado no se verificaba**: bastaba 1 byte, o una página de error con `200`, para dar una voz por instalada | E3 | **cerrado** (RD-02) |
| **RD-04** | **P2** | **La UI no avisa de la descarga ni la consiente.** El vector «UI» del P1: el alumno no sabe que se están bajando ~60 MB ni cuál es la voz que suena (pese a existir ya `X-TTS-Degraded`) | E2; `frontend/src/api/voz.ts` (sin timeout ni aviso) | **re-declarado con fase → V3.72** (UX/product completion) |
| **RD-05** | **P3 (deuda)** | **La caché negativa sigue siendo volátil** (`_VOICE_ENSURE_FAILED`, 300 s, en memoria): se pierde en cada reinicio del proceso. Persistirla exigiría almacenamiento y no entra en un endurecimiento mínimo | `services/tts.py:56-57,176-179` | **aceptado** (coste acotado por RD-01) |
| **RD-06** | **P3 (deuda)** | El **bootstrap** `download_models.py` sigue usando `urlretrieve` **sin timeout**: si Hugging Face no responde, la instalación se queda colgada sin decir nada. Además `PIPER_VOICE` (`en_US-lessac-medium`) **no está en el catálogo curado**, así que la voz inglesa por defecto solo se obtiene por este script o a mano | `download_models.py:24`; `services/voice_downloads.py:CATALOG` | **trasladado a RB** (instalación limpia) |
| **RD-07** | **P3 (positivo)** | El resto de vectores del P1 **no aplicaba**: la descarga **ya era atómica** (`.part` → `replace`), y el fallo de red **nunca** devolvía 500 (`ensure_voice_for_language` no lanza: degrada) | `services/voice_downloads.py:130-133`; `services/tts.py:169` | **verificado** |

## Cierre del P1 de TTS/offline

El P1 declaró **tres** vectores: *timeout*, *UI* y *degradación*.

| Vector | Estado tras V3.71 |
|---|---|
| **timeout** | ✅ **cerrado** — el timeout es real y acotado (RD-01) |
| **degradación** | ✅ **cerrado** — declarada en log y cabeceras (RD-03) |
| **UI** | ⬜ **re-declarado con fase: V3.72** — aviso de descarga/progreso/consentimiento y consumo de `X-TTS-Degraded`) |

Es decir: **2 de 3 vectores cerrados; el tercero tiene fase asignada y ya no puede
quedar en el olvido**, porque el backend expone el dato que la UI necesita. La
deuda deja de ser un P1 abierto y pasa a ser trabajo de UX fechado.

## Veredicto

**Aprobado con alcance acotado.** El eje encuentra y cierra un **P1 real y
verificado** que había sobrevivido **cuatro declaraciones de diferimiento**: un
parámetro de seguridad **inerte** que dejaba la única dependencia de Internet en
ruta de producto **sin límite de tiempo**, en una petición que ejecuta el alumno.
Con ello caen **RA-01** (la descarga en caliente ya no es silenciosa) y **RA-03**
(el cuelgue pasa de ilimitado a acotado).

Lo que **no** se cierra se declara con fase (UI, V3.72) o se traslada (bootstrap,
RB). No se ha añadido ninguna capacidad de producto: el diff es **endurecimiento
y verificación**.

| Área | Valoración |
|---|---|
| Timeout y robustez sin red | 9,5/10 (timeout real y acotado, con verificación de integridad) |
| Honestidad de la degradación | 9/10 (log + cabeceras + CORS; falta que la UI lo lea) |
| Cobertura de la descarga real | 9/10 (era 0: ningún test tocaba `_download_file`) |
| Bootstrap de instalación | **sin evaluar** (RD-06, es RB) |

**Hallazgos: P0 = 0 · P1 = 1 (cerrado) · P2 = 3 (2 cerrados, 1 re-declarado con fase) · P3 = 3 (1 aceptado, 1 trasladado, 1 positivo).**

## Regenerar / Verificar

```powershell
cd backend

# 1. El P1 original: el timeout ya no es código muerto
Select-String -Path services\voice_downloads.py -Pattern 'urlretrieve'   # no debe salir nada
Select-String -Path services\voice_downloads.py -Pattern 'urlopen|VOICE_DOWNLOAD_TIMEOUT'

# 2. Los tests del endurecimiento
.venv\Scripts\python.exe -m pytest tests/test_voices.py -q           # incluye RD-01/02/03
.venv\Scripts\python.exe -m pytest tests/test_runtime_audit_v371.py -q

# 3. La degradación es observable
.venv\Scripts\python.exe -m pytest tests/test_voices.py -q -k degradacion

# 4. El instrumento sigue cuadrando (sin deriva) y es determinista
.venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit

# 5. Suite completa y lint
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m ruff check .
```

## Tests que respaldan

En `backend/tests/test_voices.py` (sección «V3.71 (eje RD)», **6 tests nuevos**):

- `test_download_file_pasa_el_timeout_real_a_urlopen` — **RD-01**. Monta un
  `urlopen` falso y exige que reciba
  `VOICE_DOWNLOAD_TIMEOUT_SECONDS`. **Falla con el código anterior**, porque
  `urlretrieve` no pasaba ningún timeout.
- `test_el_timeout_de_descarga_es_acotado` — RD-01. Un `None` o un valor enorme
  volverían a permitir el cuelgue.
- `test_download_file_rechaza_descarga_truncada` — **RD-02**. `Content-Length`
  mayor que lo recibido ⇒ `RuntimeError` y **sin restos** `.part`.
- `test_download_file_rechaza_descarga_vacia` — RD-02.
- `test_tts_declara_la_voz_usada_y_si_hubo_degradacion` — **RD-03**. Sin voz del
  idioma: `X-TTS-Voice` = voz real y `X-TTS-Degraded` = `1`. **Falla con el código
  anterior**, que no devolvía cabeceras.
- `test_tts_no_declara_degradacion_cuando_la_voz_es_del_idioma` — RD-03, el caso
  contrario (sin falso positivo de degradación).
- `_FakeResponse` — doble mínimo de `urlopen` para poder testear la **función
  real** (el hueco que dejó pasar el P1: los 9 dobles anteriores sustituían
  `_download_file` entero).

Y en `backend/tests/test_runtime_audit_v371.py` (eje RA, **11 tests**):
`test_las_descargas_ocultas_conocidas_siguen_declaradas` fija que sigan
declaradas las 3 dependencias ocultas, y
`test_todo_punto_de_red_declarado_sigue_en_el_codigo` es lo que forzó a actualizar
la declaración de `services/voice_downloads.py` al cambiar `urlretrieve` por
`urlopen` (E5).
