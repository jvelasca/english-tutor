# Release notes — English Tutor v3.73.7

**Fecha:** 2026-09-18 · **Tipo:** release de **PARCHE** con **cambios de producto**
(corrige un límite de seguridad que no se aplicaba, saca la clave privada TLS del
backup y endurece cuatro superficies más; **sin** capacidad pedagógica nueva) ·
**Versión de app:** `3.73.6 → 3.73.7`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el banco y SIN tocar el currículum.** A
diferencia de V3.73.2–V3.73.6, cuyo diff era **documentación**, aquí sí cambia el
producto: backend, frontend y una pieza nueva de middleware. **El P0 de identidad
no se toca** (ver §Honestidad).

---

## Qué es esta release

Nace del **triage interno** de la sección de seguridad del informe externo sobre
`v3.73.6`: el documento `docs/audit/VERIFICACION-SEGURIDAD-V373.md` verificó hallazgo
a hallazgo qué estaba confirmado, qué matizado y qué refutado, y de ahí salió un lote
acotado de correcciones.

**Fuera de alcance (declarado).** El **P0 de identidad** —el `user_id` lo elige el
cliente y los endpoints de perfil no exigen credencial— **no se toca**: es una
migración del modelo de identidad que arrastra al frontend entero y a toda la suite de
aislamiento por propietario, y merece su propio plan. Esta release cierra el lote
barato y autocontenido, **no** el riesgo principal.

---

## 1. El bug: un límite declarado que no se aplicaba

`backend/security.py` declaraba el cupo reforzado de transcripción con la clave
**`/api/voz/transcribe`**, y esa ruta **no existe**: el router monta
**`/api/transcribe`**. Consecuencia medida: Whisper quedó con el cupo **general**
(**1200/min** por IP) en vez del **180/min** que el propio código declaraba, en un
endpoint que acepta subidas de audio.

```text
_PATH_LIMITS   declaraba: /api/voz/transcribe  -> 180/min   (nunca se aplicaba)
rutas reales   montaba:   /api/transcribe      -> 1200/min  (cupo general)
```

Y no era el único: `/api/tts`, `/api/translate` y `/api/voices/download` —las tres
sin credencial— caían también en el cupo general. Las cuatro pasan a tener cupo
propio:

| Ruta | Cupo | Por qué |
|---|---|---|
| `/api/transcribe` | **180/min** | CPU de Whisper y subida de audio |
| `/api/tts` | **240/min** | CPU de Piper por cada mensaje que se reproduce |
| `/api/translate` | **120/min** | CPU del modelo local |
| `/api/voices/download` | **10/min** | Disco y red (cada paquete son decenas de MB) |

### La causa raíz, no el síntoma

El motivo de fondo no era la errata: era que las claves de `_PATH_LIMITS` eran
**cadenas sueltas sin ningún candado**. Un cupo que no casa con ninguna ruta no falla,
simplemente no existe. Ahora hay tres tests:

- **`test_path_limits_match_real_routes`** — recorre la tabla de rutas **real** de la
  app y exige que **cada** clave de `_PATH_LIMITS` sea prefijo de una ruta montada.
  Este es el test que **habría cazado** el bug el día que se introdujo.
- **`test_costly_routes_have_own_rate_limit`** — las rutas de coste alto declaradas no
  pueden perder su cupo ni caer al general.
- **`test_transcribe_uses_its_own_limit`** — prueba de comportamiento: con el cupo
  general la segunda petición pasaría; con el suyo, la segunda es un 429.

**Detalle técnico que obligó a cambiar el enfoque.** La primera versión del candado
consultaba `app.routes` y **falló por otra razón**: FastAPI **no expande**
`include_router` en `app.routes` —deja un `_IncludedRouter` con el router original
dentro—, así que el inventario salía casi vacío. El recorrido ahora **desciende** por
esos routers y, además, un suelo (`MIN_APP_ROUTES = 100`) impide que el candado pase
«por vacío» si FastAPI vuelve a cambiar. Comprobado: el inventario ve **163 rutas**
reales y la clave vieja `/api/voz/transcribe` **no casa con ninguna**.

---

## 2. El backup sacaba la clave privada TLS del equipo

`_write_zip` recorría **todo** `DATA_DIR` y `certs/` vive ahí, de modo que
`data/certs/key.pem` —la **clave privada** con la que el producto sirve HTTPS en la
LAN— viajaba dentro de cada copia:

- **en claro** (el ZIP no se cifra), y
- **multiplicada**: el auto-backup diario conserva **7**, y `GET
  /api/system/backup/export` la sirve como descarga.

Arreglado con **una sola** constante, `_NON_PORTABLE_TOP_NAMES = {"backups", "certs"}`,
que gobierna **los dos lados**: `certs/` no viaja en el ZIP **y** se **conserva** al
restaurar. La segunda mitad importa tanto como la primera: sin ella, restaurar el
estado borraría el certificado del equipo y el producto se quedaría **sin HTTPS**.
Efecto secundario buscado: restaurar un backup viejo ya no revive el certificado.

---

## 3. Restaurar no tenía cota de expansión

El tope de **512 MB** de `POST /api/system/restore` es del ZIP **comprimido**. Sin
cota del expandido, un ZIP de pocos MB con ratio alto (unos megabytes de ceros
comprimen a unos kilobytes) llena el disco de `%TEMP%` durante la extracción.
`_validate_archive` rechaza antes de extraer:

- **tamaño descomprimido** acumulado por encima de **4 GiB** (holgura sobre el caso
  legítimo —SQLite más los WAV de la biblioteca, que comprimen ~2x—, no sobre un
  abuso),
- más de **50 000** entradas, y
- rutas **inseguras** de forma **explícita** (`..`, absolutas, con unidad `C:`).

Sobre lo último: `extractall` de Python ya **sanea** los nombres (descarta `..` y
rutas absolutas), así que **no** había Zip Slip. La comprobación explícita se añade
para fallar con un mensaje claro y **no depender de ese detalle del intérprete**.

---

## 4. Cuatro endurecimientos menores

| | Qué cambia | Dónde |
|---|---|---|
| **D1** | `UserCreate.name` pasa a `max_length=80`. Solo `PATCH` lo tenía, y `POST /api/users` **no exige credencial**: era una vía trivial de crecimiento de la BD | `backend/schemas/users.py` |
| **D2** | La cookie de perfil lleva **`Secure`** cuando la página ya se sirve por HTTPS (el runtime de producto); en el modo dev por HTTP no se marca, porque el navegador la descartaría | `frontend/src/utils/cookie.ts` |
| **D3** | Middleware nuevo `SecurityHeadersMiddleware`: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy` (`microphone=(self)`, cámara y geolocalización cerradas) y **CSP acotada** | `backend/security_headers.py` |
| **D4** | El PIN de administración deja `localStorage` y pasa a `sessionStorage`, con **borrado de la copia heredada** | `frontend/src/api/audioLibrary.ts` |

**CSP parcial, a propósito.** La CSP cubre `frame-ancestors 'none'`, `object-src
'none'`, `base-uri 'self'` y `form-action 'self'` — lo que **no** puede romper la
carga de recursos. **No** fija `script-src`: `frontend/dist/index.html` trae un script
**inline** de tema (el bootstrap de `data-theme`), así que cerrarlo exige un hash y su
propio candado. Preferimos una CSP honesta y parcial a una completa que rompa la UI sin
que ningún test lo note.

**Sin HSTS, a propósito.** El producto sirve HTTPS con un certificado **autofirmado**
(`backend/data/certs/`): un `Strict-Transport-Security` sobre un certificado que ningún
navegador acepta como de confianza dejaría el origen inutilizable hasta que el usuario
limpiara el estado del navegador.

**D4 es el único cambio visible para el usuario.** El PIN se teclea **una vez por
sesión de navegador** en lugar de una vez para siempre. Es la postura correcta para una
credencial (antes quedaba en claro, de forma permanente y compartido por todos los
perfiles del navegador), y es reversible si molesta.

---

## 5. Verificación

Medido en el **árbol de trabajo** (con `frontend/dist` construido y los modelos
instalados). **No** se declara el reparto de un clon limpio: no se ha medido en esta
pasada, y declarar un reparto no medido fue exactamente el error que corrigió V3.73.6.

| Comprobación | Resultado |
|---|---|
| Backend `pytest tests/ -q` | **2817 passed** (0 skipped) |
| Frontend `vitest run` | **717 passed** (85 ficheros) |
| Launcher `pytest tests/ -q` | **113 passed** |
| `ruff check .` / `npx tsc --noEmit` | limpios |
| i18n `check_i18n_coverage.py --strict` | 0 huérfanas / 0 duplicadas / 0 vacías |
| `validation_gate.py auto` | **10/10** |
| `check_release_consistency.py` | OK en los **6 orígenes** (`3.73.7`) |

Los recuentos suben **exactamente** por los tests nuevos: backend 2798 → 2817
(**+19**), frontend 712 → 717 (**+5**).

### Los tests muerden

No basta con que pasen. Para el bloque del backup se dejó el fuente original en un
`git stash` temporal y se corrió la suite: **7 de los 8 tests nuevos fallan**. El
octavo (`test_restore_preserves_local_certs`) **pasó**, y se investigó por qué: con el
código viejo los certificados **sí** viajaban en el ZIP, así que se restauraban solos.
Ese test es el guardián del **acoplamiento** entre las dos mitades del arreglo, y se
verificó aislando el lado de la restauración (quitar solo el `keep_top`) → el
certificado desaparece.

---

## 6. Honestidad

1. **El P0 de identidad sigue abierto.** El `user_id` lo sigue eligiendo el cliente y
   `POST/PATCH/DELETE /api/users` siguen sin credencial. Esta release cierra el lote
   barato y acotado; **no** cierra el riesgo principal del producto.
2. **La CSP es parcial** por la razón declarada arriba, y **no** se envía HSTS.
3. **No es un pentest.** Son correcciones con el test que falla sin el cambio,
   verificadas con lectura de fuente y suites automáticas. La barrera de red (bind a
   `0.0.0.0`, CORS de redes privadas) y el modelo de identidad quedan **como estaban**.
4. **Los cupos son juicio de ingeniería, no carga medida.** Los valores nuevos
   (tts 240, translate 120, voices 10) están elegidos sobre uso humano esperado; no se
   han probado bajo carga ni con varios clientes simultáneos.
5. **Los 7 gates siguen en `pending`.** La identidad sellada en
   `docs/audit/KIT-VALIDACION-GATES.md` (`3.73.6` · `13cc30b`) es el registro del
   **pre-vuelo** de la campaña y **no se reescribe**. Si la campaña física se ejecuta
   después de este commit, sus `record` sellarán el SHA nuevo — y eso es correcto.
