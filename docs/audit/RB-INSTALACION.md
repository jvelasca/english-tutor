# RB — Instalación limpia desde cero (V3.71)

> **Tipo:** dossier de evidencia **interno** (no es un informe de auditoría
> externa). Por eso **no lleva letra**: `Z` y `Z2` siguen reservadas a los
> informes externos pendientes de V3.69
> (`agentes/auditoria-externa-v369-seguimiento.md`).
> **Eje auditado:** **RB** («¿se instala en una máquina limpia sin pasos
> tácitos?») del briefing `agentes/v371-runtime-offline-instalacion.md` §B.
> **Cierra además:** **RA-04** (`docs/audit/RA-RUNTIME-OFFLINE.md`) y **RD-06**
> (`docs/audit/RD-DEPENDENCIAS-OCULTAS.md`), los dos hallazgos que los ejes RA y
> RD trasladaron aquí por decisión de alcance.
> **Punto de partida:** `v3.70.0` (`9ba9c49`) + ejes RE (`2c07fe0`), RA
> (`fdefb2c`), RD (`b8d2ac4`) y RC (`37725d5`).
> **Autor:** el propio proyecto.
> **Fecha:** 2026-09-16.

## Alcance

- **Se audita** el camino de instalación desde un **clon limpio**, que son tres
  preguntas separadas:
  1. qué artefactos **no** están en el repo y hay que descargar;
  2. si el bootstrap que los descarga es **seguro** (no se cuelga) y **completo**
     (no deja cabos sueltos según el idioma);
  3. si hay una **verificación previa** que diga qué falta **antes** de arrancar.
- **Se cierra:** RA-04 (sin verificación previa ni runbook) y RD-06 (`urlretrieve`
  sin timeout + la voz inglesa por defecto fuera del catálogo).
- **Se declara:** `ollama pull` como paso **manual y explícito** (decisión B del
  briefing), y la frontera de lo que este eje **no** puede demostrar.
- **No se audita:** el runtime de producto (RC, ya entregado), el offline con la
  red cortada (RA, pendiente de ejecución en vivo) ni la síntesis (RF).

## Método

1. **Medir antes de tocar.** Cada afirmación se comprueba contra el código y
   contra el comportamiento observable, no contra lo que el proyecto declara.
2. **Endurecimiento mínimo.** Solo se cambia lo que cierra un vector medido, con
   **test que falla sin el cambio**. Nada de refactor.
3. **Falsación.** Cuando el hallazgo es una asimetría de comportamiento (el
   español sí, el inglés no), se **reproduce** el estado previo para demostrar
   que el fallo era real y que el cambio lo cierra.
4. **El instrumento del eje RA debe seguir cuadrando**: cambiar el bootstrap
   cambia sus puntos de red declarados, así que el manifiesto se actualiza y su
   par generado se regenera.

## Evidencia

### RB-01 — La voz inglesa por defecto no podía auto-descargarse (P2, **cerrado**)

**El hallazgo, medido.** `config.PIPER_VOICE = "en_US-lessac-medium"` es la voz
con la que la app **da clase** (y el default de `DEFAULT_VOICES["en"]`), pero
**no estaba** en el catálogo curado `services/voice_downloads.CATALOG`. Y
`ensure_voice_for_language` (la vía de auto-descarga que usa `POST /api/tts`)
abandona en cuanto el default no está en el catálogo:

```python
target = default_voice_for(lang)
if voice_downloads.spec_for(target) is None:
    return False          # sale SIN intentar la descarga
```

**La asimetría que esto producía:** el español **sí** se auto-descargaba
(`es_ES-davefx-medium` está en el catálogo) y el inglés **no**. En una
instalación limpia, con `backend/models/` vacío, la app no podía hablar en el
idioma que enseña salvo que el usuario ejecutase `download_models.py` o colocase
los ficheros a mano. El bootstrap lo tapaba, así que el fallo solo aparecía en la
vía de producto.

**Falsación (reproducida).** Con la lista de voces instaladas vacía (clon limpio),
se ejecutó el camino real con el catálogo corregido y con el catálogo previo:

| Catálogo | `spec_for(PIPER_VOICE)` | `ensure_voice_for_language("en")` |
|---|---|---|
| **actual** (con la voz) | `PiperVoiceSpec(id='en_US-lessac-medium', …)` | **`True`** (descarga) |
| **pre-fix** (sin la voz) | `None` | **`False`** (sale sin descargar) |

**Modo de fallo:** silencioso y **selectivo por idioma**. No había error, ni log,
ni aviso: el TTS degradaba al fallback y el alumno oía una voz que no era la
declarada. Es el mismo patrón que el proyecto ya había cerrado en V3.45 para el
español, pero que quedó abierto en el otro lado.

**Cierre:** `en_US-lessac-medium` entra en `CATALOG` con su ruta real
(`en/en_US/lessac/medium`). Al estar en la lista, las dos vías (bootstrap y
descarga en caliente) usan **el mismo** catálogo y no pueden divergir.

### RB-02 — El bootstrap descargaba sin límite y con URLs propias (P3, **cerrado**)

`download_models.py` tenía su propia copia de la URL base de Hugging Face y
descargaba con `urllib.request.urlretrieve`, que **no acepta `timeout`**: si el
host no respondía, la instalación se quedaba colgada **sin decir nada** (RD-06).
Es la misma clase de defecto que el eje RD cerró en ruta de producto (un
parámetro de seguridad **inerte**), aquí en el instalador.

Además, al escribir a mano la ruta de la voz, el bootstrap **duplicaba** el dato
del catálogo: los dos podían desviarse (y de hecho ya lo estaban, por RB-01).

**Cierre:** `download_piper()` recorre `config.DEFAULT_VOICES` y delega en
`voice_downloads.download_voice`, heredando **timeout real** (15 s por operación
de socket), **descarga atómica** (`.part` → `replace`) y **verificación de
tamaño** contra `Content-Length`. El script ya no contiene ninguna primitiva de
red propia ni construye URLs.

**Efecto secundario verificado:** el manifiesto del eje RA declaraba
`urlretrieve` en `download_models.py`; al desaparecer, el instrumento **habría
derivado**. Se actualizó la declaración (la primitiva vive ahora en
`services/voice_downloads.py`) y se regeneró el par
`docs/audit/generated/runtime-audit.{md,json}`: el reparto por tipo sigue siendo
**6 puntos de internet**, sin cambio de censo.

### RB-03 — No había verificación previa (RA-04, **cerrado**)

En un clon limpio, `backend/models/` está **vacío** (`.gitignore`), así que hacen
falta **~1,1 GB** de descargas (Piper ×2 voces ~120 MB + Whisper `small`
927 MB) más el `ollama pull` del modelo por defecto. Hasta V3.71 **nada** lo
decía: ni el README listaba el paso de Ollama, ni había forma de saber qué faltaba
**antes** de arrancar.

**Cierre — `download_models.py --check` (solo lectura).** Informe que distingue
explícitamente **qué es descarga y qué es local**, en el sitio donde el README ya
manda al usuario:

```
  [   OK] Voz Piper (en): en_US-lessac-medium.onnx
          tipo: descarga · origen: huggingface.co (rhasspy/piper-voices) · 60.3 MB
  [   OK] Voz Piper (es): es_ES-davefx-medium.onnx
          tipo: descarga · origen: huggingface.co (rhasspy/piper-voices) · 60.3 MB
  [   OK] Whisper `small` (STT, caché en disco)
          tipo: descarga · origen: huggingface.co (vía faster-whisper) · 927.4 MB
  [   OK] Base de datos (usuarios, evidencia, léxico)
          tipo: local · origen: se crea sola al arrancar la app · 732 KB
  [   ??] Modelo de Ollama `llama3.1:8b` (chat y definiciones)
          tipo: descarga · origen: ollama pull (paso manual del runbook) · -
```

Decisiones de honestidad del informe:

- **`--check` no descarga nada** (hay test que lo fija con un doble que revienta
  si se intenta), y `--json` da la misma información legible por máquina.
- **`exists=None` para Ollama**, no `False`: este script **no puede** comprobar el
  modelo de Ollama (lo gestiona el servicio). Un `False` fingiría un artefacto de
  disco que falta. Por eso `missing_offline_artifacts()` **excluye** lo no
  comprobable, y el código de salida solo cuenta lo que sí se puede verificar.
- **La ruta de la BD no se escribe a mano**: se importa de `repositories.db`
  (`DB_PATH`), que es la fuente única. Escribirla aquí habría sido una deriva más.
- **Los artefactos se derivan de `config.DEFAULT_VOICES`**, así que una voz por
  defecto nueva entra sola en el informe (y hay test que lo exige).

### RB-04 — El runbook del README no era ejecutable sin ayuda (P2, **cerrado**)

El README mandaba a `download_models.py` pero **no** decía:

- que hace falta **`ollama pull llama3.1:8b`** (el modelo por defecto, que es un
  paso **manual** por diseño: lo gestiona el servicio de Ollama, no el proyecto);
- que `backend/models/` **no se versiona**, así que en un clon limpio hay que
  ejecutar ese paso sí o sí;
- cómo **comprobar** el estado antes de arrancar.

**Cierre:** el runbook de `README.md` gana la verificación previa (`--check`), el
paso explícito de Ollama con el comando exacto y el modelo real, y la nota de qué
es descarga / qué es local. Se añadió además que **Node y npm son requisito de
ejecución** (hallazgo RC-01), que la sección de requisitos tampoco declaraba.

### RB-05 — Lo que este eje NO puede demostrar (P3, **deuda declarada**)

- **No se ejecutó el runbook en una máquina físicamente limpia.** La verificación
  aquí es **estática y de comportamiento** (catálogo, informe, rutas de código) más
  el manifiesto real de este equipo. Un clon limpio de verdad aportaría la prueba
  end-to-end, pero exige otra máquina o una VM: se declara como acción humana, no
  como trabajo pendiente del proyecto.
- **El informe no mide espacio en disco ni tiempo de descarga**; solo presencia.
- **`ollama pull` sigue siendo un paso que el proyecto no puede verificar** (por
  diseño). El runbook lo dice, pero nadie comprueba automáticamente que el modelo
  esté: la comprobación es `ollama list`, a mano.

## Veredicto

**Aprobado con una deuda declarada.** El eje cierra los dos hallazgos que los
ejes anteriores le trasladaron, y el central no es cosmético: **la voz con la que
la app da clase no se podía descargar por la vía de producto**, en silencio y solo
en inglés, mientras el español sí. Con el bootstrap delegado en el catálogo, el
instalador deja de poder colgarse y deja de tener datos duplicados.

No se ha añadido capacidad de producto: el diff es **endurecimiento,
consolidación y verificación**. Lo que no se demuestra (una máquina limpia real)
se declara con su acción humana.

| Área | Valoración |
|---|---|
| Completitud del bootstrap (todas las voces por defecto) | 10/10 (derivado de `config.DEFAULT_VOICES`, con test) |
| Robustez sin red del instalador | 9,5/10 (timeout real y descarga atómica, heredados del eje RD) |
| Verificación previa | 9/10 (dice qué falta y de qué tipo; no mide disco ni tiempo) |
| Prueba en máquina limpia **real** | **sin ejecutar** (RB-05, acción humana) |

**Hallazgos: P0 = 0 · P1 = 0 · P2 = 2 (ambos cerrados) · P3 = 3 (2 cerrados, 1 declarado como acción humana).**

## Regenerar / Verificar

```powershell
cd backend

# 1. La verificación previa (solo lectura: no descarga nada)
.venv\Scripts\python.exe download_models.py --check
.venv\Scripts\python.exe download_models.py --json

# 2. La voz inglesa por defecto es alcanzable (RB-01)
.venv\Scripts\python.exe -c "import config; from services import voice_downloads as v; print(v.spec_for(config.PIPER_VOICE))"
#   → PiperVoiceSpec(id='en_US-lessac-medium', ...)

# 3. El bootstrap ya no tiene primitivas de red ni URLs propias (RB-02)
Select-String -Path download_models.py -Pattern 'urlretrieve|urlopen|PIPER_BASE|https://'
#   no debe salir nada

# 4. Los tests del eje
.venv\Scripts\python.exe -m pytest tests/test_install_bootstrap_v371.py -q

# 5. El instrumento del eje RA sigue cuadrando (se regenera sin cambio de censo)
.venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit
#   → docs/audit/generated/runtime-audit.{md,json}

# 6. Suite completa y lint
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m ruff check .
```

## Tests que respaldan

`backend/tests/test_install_bootstrap_v371.py` (**13 tests**):

- **RB-01** — `test_la_voz_inglesa_por_defecto_esta_en_el_catalogo_curado`,
  `test_la_voz_inglesa_por_defecto_tiene_la_ruta_real_de_hugging_face` (un id o
  una ruta mal escritos darían **404** en la descarga),
  `test_el_ingles_por_defecto_se_puede_auto_descargar` (la consecuencia
  observable: se **decide** descargar, no si hay red).
- **RB-02** — `test_el_bootstrap_no_usa_urlretrieve_ni_construye_urls` (guarda
  sobre el **código**, no sobre la prosa: el docstring *sí* debe poder explicar el
  defecto histórico) y `test_el_bootstrap_instala_todas_las_voces_por_defecto`.
- **RB-03** — `test_el_informe_de_instalacion_cubre_todas_las_voces_por_defecto`,
  `test_el_informe_distingue_descarga_de_local`,
  `test_el_informe_declara_que_ollama_no_lo_comprueba_este_script`,
  `test_la_base_de_datos_es_un_dato_local_no_una_descarga`,
  `test_la_verificacion_previa_no_descarga_nada`,
  `test_el_modo_check_json_es_parseable`,
  `test_faltantes_solo_cuenta_lo_comprobable_en_disco`.
- **RB-04** — `test_el_runbook_del_readme_incluye_ollama_y_la_verificacion_previa`.

Todos **fallan** sin el cambio correspondiente.
