# Auditoría EXTERNA del producto — punto de entrada anclado a `v3.75.0`

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **el producto publicado
> en `v3.75.0`**, no un plan ni un incremento aislado. La revisión es **de solo
> lectura**: no se cambia código, datos, configuración ni etiquetas publicadas.
>
> **Por qué esta auditoría y por qué ahora.** Entre la última auditoría externa
> (la de cierre, anclada en `v3.73.6`) y `v3.75.0` han aterrizado **tres releases de
> producto** que cambian cosas que la auditoría anterior declaró abiertas: el
> **endurecimiento** derivado de su sección de seguridad (V3.73.7), la **frontera
> de red** —loopback por defecto y LAN opt-in— (V3.74.0) y la **identidad firmada
> por el servidor** —el P0 de identidad, Fase 2— junto con los **dos P3** que
> quedaban (`VG-N5`, `VG-N6`) (V3.75.0). El objeto de esta auditoría es **el
> producto entero tal y como está publicado**, con atención especial a esa
> secuencia: tres releases se autoproclaman correcciones de seguridad y **ninguna
> la ha revisado alguien de fuera**.
>
> **Aviso de encuadre (léelo antes de puntuar).** La línea V3.73 **no añade
> capacidad pedagógica**: es una *validation line* (V3.73.0 instrumentó los 7
> gates; V3.73.1 ordenó la GUI; V3.73.2–V3.73.6 corrigieron CI, kit, trazabilidad
> y cifras). V3.73.7 y V3.74.0 **reducen superficie**; V3.75.0 cambia **quién es
> la autoridad sobre la identidad**, no quién puede pedirla. Si el auditor busca
> «qué se ha mejorado para el alumno», la respuesta honesta es **nada** en V3.73.7,
> V3.74.0 y V3.75.0 (V3.73.1 sí ordenó la navegación, sin capacidad nueva). Si
> busca «qué se ha demostrado», el objeto de esta auditoría es exactamente
> **separar lo demostrado de lo declarado**.
>
> **Estado:** entregado 2026-09-18, **dentro del commit de release** de `v3.75.0`.
> **Informe esperado:** `docs/audit/AJ-AUDITORIA-TOTAL-V375.md`. Prefijo **`AJ`**
> porque `AA`–`AF` los ocupan los dossiers de V3.70, `AG` y `AH` están reservados
> por los puntos de entrada de V3.70 y V3.71 (entregados, **sin informe
> recibido**) y `AI` por el punto de entrada de cierre de V3.73 (entregado,
> **sin informe recibido**): `AJ` es el primer prefijo libre.

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

1. `docs/RELEVO.md` — **cabecera** (nota de la posición vigente: `v3.75.0`) y
   **§0 «START HERE»**.
2. `PLAN.md` — §«Estado actual» (registro release a release) y la tabla de
   trazabilidad de briefings y auditorías.
3. `docs/audit/PARKED.md` — lo **aparcado a propósito** por fase y los pendientes
   de acción humana. Su sección **`V3.75`** es la declaración honesta de lo que
   esta línea **no** cierra; léela antes de buscar «lo que falta».
4. **Este documento**, hasta el final.
5. `docs/audit/PLAN-P0-IDENTIDAD.md` — el plan por fases del P0 de identidad, con
   las mediciones, los acoplamientos descubiertos, las alternativas descartadas y
   (**§14**) el estado implementado de la Fase 2, incluidos los tres fallos de
   diseño que aparecieron **implementando**.
6. `docs/audit/VERIFICACION-SEGURIDAD-V373.md` — la **contra-verificación
   interna**, hallazgo a hallazgo, de la sección de seguridad del informe externo
   sobre `v3.73.6`: dónde se confirmó, dónde se matizó y dónde se **refutó**. Es
   el mapa de lo que esta línea dice haber cerrado; el auditor debe tratarlo como
   **una afirmación más**, no como evidencia.
7. Notas de las tres releases: `release-notes-v3.73.7.md`,
   `release-notes-v3.74.0.md`, `release-notes-v3.75.0.md`.
8. `docs/BETA_GATES.md`, `docs/audit/KIT-VALIDACION-GATES.md` y
   `docs/audit/VALIDATION-RELEASE-V373.md` — los 7 gates: **siguen en `pending`**;
   el kit es la planilla de campo, no una validación.
9. `docs/ARQUITECTURA.md` — incluida la sección **«Superficie sin sesión»**, que es
   la declaración que cierra `VG-N6`.
10. `docs/PREMISAS.md`, `docs/CONSTITUCION-PEDAGOGICA.md`, `CHANGELOG.md` y
    `docs/audit/TEMPLATE.md` (formato del informe que se entrega).

**Punto de partida git:**

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor
git fetch --tags
git log --oneline -3 main
```

---

## 1. Punto de entrada verificado (contra GitHub, no contra un árbol local)

- Repositorio: `jvelasca/english-tutor` (**público**), rama por defecto `main`.
- **Release auditada: el tag anotado `v3.75.0`.** Los identificadores exactos se
  **resuelven con git** en vez de fijarse aquí a mano:

```bash
git fetch --tags
git rev-parse v3.75.0            # objeto del tag anotado
git rev-parse v3.75.0^{commit}   # commit de release (el SHA exacto que se audita)
git log -1 --format='%H %s' v3.75.0^{commit}
```

- **Por qué este documento NO fija el SHA ni el run a mano (desde V3.73.5).** Un
  commit **no puede contener** su propio SHA ni el id de la run de CI que dispara
  su push: son datos que solo existen **después** de publicar. Fijarlos obligaba a
  un commit de re-anclaje **posterior al tag**, que quedaba a su vez fuera del tag
  siguiente, y por eso `main` iba siempre por delante en documentación. Desde
  V3.73.5 el ancla es el **tag**, el estado de publicación se **verifica por
  comando** y este archivo es coherente **dentro de su propio tag**, de modo que el
  commit de release es **final**. Si un documento de este tipo vuelve a fijar un
  SHA o un run a mano, es una **regresión**.
- **Base de comparación sugerida:** `v3.74.0` (la release inmediatamente anterior)
  y, para el arco largo, `v3.73.6` (el árbol de la última auditoría externa). El
  código **sí** cambió en las tres releases posteriores; lo que **no** cambió es el
  banco de contenido ni el currículum.
- **Sin GitHub Release** para `v3.75.0`: es una decisión declarada del gerente
  (solo tag anotado, que es la convención real del repo desde `v3.34.0`). El último
  Release object publicado es `v3.33.0`.

**Invariante del código.** El auditor puede comprobar que el tag y `main` sirven
el mismo producto:

```bash
git diff --stat v3.75.0..main -- backend frontend launcher scripts
```

Debe salir **vacío** (mientras no aterrice trabajo nuevo). Es decir: da igual
clonar `main` o hacer `git checkout v3.75.0`; **el código de producto y el arnés
citados aquí son los mismos**. Si el auditor encuentra una diferencia en esas
cuatro rutas entre el tag y `main`, tiene un hallazgo **P0**.

**Estado de publicación (verificado por comando, no fijado a mano):**

```bash
git rev-parse v3.75.0^{commit}      # SHA exacto del commit del tag
gh run list --commit $(git rev-parse v3.75.0^{commit}) --limit 1
```

La run del commit del tag debe estar en **`success`** con los **12 jobs** en verde
(un nombre por línea, para que un `grep` literal funcione):

- `Backend (ruff + pytest)`
- `Frontend (tsc + vitest + build)`
- `Release consistency`
- `Validation gate (checks automáticos)`
- `Beta V3.0 gate`
- `Content validation`
- `Playwright E2E (visual)`
- `Launcher (ruff + pytest)`
- **`Dependency audit (pip-audit + npm audit)`** (**bloqueante**; nuevo en V3.75.0)
- `Product origin (UI served over HTTPS)`
- `Launcher (Windows, ruff + pytest)` (**bloqueante**)
- `Product origin (Windows, informativo)` (**informativo declarado**,
  `continue-on-error: true`)

- **Nota para el auditor:** el run se dispara con el **push de `main`**; el tag se
  publica en el mismo push y apunta al commit de release.

**Consistencia de versión:** `backend/config.py::VERSION` es la fuente única
(`scripts/check_release_consistency.py`) y `3.75.0` debe aparecer en **6 orígenes**:
`backend/config.py`, `frontend/package.json`, `frontend/package-lock.json`,
`README.md`, `CHANGELOG.md` y `PLAN.md`.

---

## 2. Qué ha cambiado desde la última auditoría externa (`v3.73.6`)

Tres releases, todas de **producto**. La tabla dice qué afirma cada una; el
auditor comprueba si lo demuestra.

### 2.1 V3.73.7 — endurecimiento derivado del triage de seguridad

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `backend/security.py` (`_PATH_LIMITS`) | Cupos corregidos: `/api/transcribe`, `/api/tts`, `/api/translate`, `/api/voices/download` tenían el cupo **general** porque la tabla declaraba una ruta que **no existe** (`/api/voz/transcribe`) | Que un límite declarado **se aplica** a la ruta real, y que el error era **silencioso** (el cupo general es permisivo) |
| `backend/tests/test_rate_limit_paths.py` | Candado que recorre la **tabla de rutas real** de la app (descendiendo por los `_IncludedRouter`) y falla si una clave de `_PATH_LIMITS` no casa con ninguna ruta montada | Que el bug original (clave huérfana) habría sido cazado |
| `backend/services/backup.py` | `certs/` **fuera** del ZIP y **conservado** al restaurar; cota de tamaño descomprimido (4 GiB), cota de entradas (50 000) y rechazo explícito de rutas inseguras | Que la clave privada TLS no viaja en claro en las 7 copias automáticas y que un ZIP «bomba» no llena el disco |
| `backend/middleware.py` (`SecurityHeadersMiddleware`) | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy` y **CSP parcial** (`frame-ancestors`, `object-src`, `base-uri`, `form-action`) | Que hay defensas en profundidad **declaradas**; la CSP **no** cierra `script-src` (el artefacto lleva un script inline de tema) |
| `backend/schemas/users.py` | `UserCreate.name` con `max_length=80` (solo `PATCH` lo tenía) | Que el endpoint **sin credencial** no acepta un nombre de tamaño arbitrario |
| `frontend/src/utils/adminPin.ts` + consumidores | El PIN de administración pasa de `localStorage` (en claro, permanente, compartido entre perfiles) a `sessionStorage`, borrando la copia heredada | Único cambio **visible para el usuario** de la línea: se teclea una vez por sesión de navegador |
| `backend/routers/profile.py` (cookie de perfil) | `Secure` cuando la página va por HTTPS | Que la cookie de perfil no viaja por HTTP en el uso real (V3.75 retira esa cookie, ver §2.3) |

### 2.2 V3.74.0 — la frontera de red pasa a ser una decisión

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `backend/config.py` (`lan_mode`, `backend_host`), `launcher/core.py` (`backend_env`, `set_lan_mode`) | Uvicorn se enlaza a `127.0.0.1` salvo que el modo esté **declarado** (`ENGLISH_TUTOR_LAN=1` o el botón del launcher, que lo declara y **reinicia** el servidor) | Que exponerse a la LAN exige un acto explícito y que el valor por defecto es **no** exponerse |
| `backend/security.py` | Dos patrones de origen (`LOCAL_ORIGIN_REGEX` siempre válido; `LAN_ORIGIN_REGEX` solo en modo LAN), comprobación con **`fullmatch`** y decisión consultada **por petición** | Que «desactivar» la regex de LAN **no** abre CORS: un patrón **vacío** con `match` casaba con cualquier cadena (la trampa que el plan declaró y evitó) |
| `backend/tests/test_cors.py` (`test_las_dos_mitades_de_la_politica_de_origen_coinciden`) | Compara el patrón compilado por `CORSMiddleware` (una vez, al importar) con `security.origin_allowed` (por petición) sobre la misma lista de orígenes | Que las dos mitades no pueden discrepar en silencio |
| `backend/routers/network.py`, `frontend/src/api/network.ts`, `ConnectDeviceCard.tsx` | `/api/network` informa `lan_mode`/`bind` y **no** anuncia URL cuando la LAN no responde; la tarjeta explica el paso que falta (`connect.lanOff`) | Que no hay enlaces muertos tras cerrar la frontera |
| `backend/tests/test_lan_mode.py`, `launcher/tests/test_lan_mode.py` | Fail-closed (`ausente`, `0`, `false`, `no`, `off`, texto raro ⇒ cerrado) y valores afirmativos | Que la lectura del modo es **fail-closed**, no optimista |
| `backend/tests/test_docs_drift*.py` | Candado de **deriva documental**: si la frontera desaparece de `README.md`, `PREMISAS.md` o `ARQUITECTURA.md`, la suite falla | Que la declaración no se puede quedar atrás |

### 2.3 V3.75.0 — la identidad la firma el servidor (Fase 2 del P0)

| Ruta | Qué es | Qué afirma |
|---|---|---|
| `backend/services/sessions.py` (nuevo) | Token `base64url(payload).base64url(hmac_sha256(secreto, payload))`, `payload = {iat, uid}` en JSON canónico; **stdlib**; comparación con **`hmac.compare_digest`**; `SESSION_TTL_SECONDS = 365 días`; margen de reloj de 60 s | Que la firma es correcta y que la comparación **no** filtra por temporización |
| `backend/routers/session.py` (nuevo) | `POST`/`GET`/`DELETE /api/session`; cookie `et_session` **`HttpOnly`**, `SameSite=Lax`, `Path=/`, `Secure` según el esquema; `POST` responde 404 si el perfil no existe | Que el cliente **no puede leer** la identidad y que la cookie no viaja en flujos de terceros ni por HTTP en el uso real |
| `backend/dependencies.py` | `current_user` verifica la cookie ⇒ **401 `SESSION_REQUIRED`**; `current_user_optional` ⇒ `None` | Que la identidad ya **no** la fija el cliente y que la ausencia de sesión se distingue de «vacío legítimo» |
| `backend/routers/users.py`, `routers/settings.py` | `PATCH /api/users/{id}` y `PUT /api/settings` exigen sesión **y** que el id sea el de la sesión (**403** si no) | Que el borde de **autorización** se cierra, no solo el de identidad |
| `backend/services/backup.py` (`_NON_PORTABLE_TOP_NAMES`) | `session.secret` fuera del ZIP y **conservado** al restaurar | Que el ZIP de otro equipo no permite **forjar sesiones** y que restaurar no invalida las sesiones locales |
| `backend/tests/conftest.py` (`_identidad_por_sesion`) | Adaptador que traduce el `?user_id=` de las **109** suites históricas a una **sesión firmada real**, delegando en `current_user` | Que se toca **una** pieza (el origen de la identidad en tests) en vez de 109 ficheros — y que el resto del camino se ejecuta de verdad |
| `backend/tests/test_identity_source.py` (marcado `identidad_cruda`) | Manda **sesión de A** y `?user_id=B` a la vez y exige los datos de **A** | Que el parámetro dejó de significar nada |
| `backend/tests/test_sessions.py`, `test_users_self_only.py`, `test_public_surface.py`, `test_supply_chain_v375.py` | Firma, caducidad, atributos de la cookie, 401; perfil propio sí / ajeno no; superficie sin sesión declarada y acotada; pines por SHA + auditoría de dependencias + Dependabot | Que cada afirmación de arriba tiene un candado que **falla** si se rompe |
| `frontend/src/api/session.ts`, `utils/session.ts` (`planSession`), `hooks/useChat.ts`, 17 módulos de `api/` | Al arrancar se pregunta `GET /api/session`; elegir o crear perfil **abre** sesión; las URLs **no** llevan identidad | Que un perfil «activo» sin sesión no puede quedar pintado sin que cada petición responda 401 |
| `frontend/src/utils/cookie.ts` (**borrado**) | Se retira `et_user_id`, la cookie que escribía JavaScript | Que la identidad ya no la escribe el cliente |
| `launcher/browser_cookies.py`, `launcher.py` | El panel informa «sesión abierta: sí/no» y **enmascara** el valor de `et_session` | Que el token firmado no se imprime en pantalla (Firefox guarda las cookies en claro) |
| `.github/workflows/ci.yml`, `.github/dependabot.yml` (nuevo) | Actions fijadas por **SHA de commit**, `permissions: contents: read`, job **bloqueante** `deps-audit`, Dependabot para `pip`, `npm` y `github-actions` | Que la cadena de suministro del CI no tiene referencias móviles y que una dependencia vulnerable **rompe el CI** |
| `backend/requirements.txt` | `fastapi` **0.141.1** (→ `starlette` **1.6.0**) | Que los 10 avisos conocidos de `starlette 0.50.0` desaparecen; **y** que se aceptó un salto de versión mayor de Starlette dentro de una release de seguridad |

### 2.4 Lo que la línea dice haber cerrado, y con qué palabras

- **P0 de identidad: parcialmente cerrado.** La **autoridad** sobre la identidad
  pasa del cliente al servidor; **no** hay autenticación (`POST /api/session` acepta
  cualquier `user_id` existente sin credencial). `docs/audit/PARKED.md` §V3.75 y
  `PLAN-P0-IDENTIDAD.md` §14.2 lo declaran con esas palabras, y la **Fase 3**
  (autenticación real) queda como **decisión de producto**, no como deuda técnica.
- **Los dos P3 que la auditoría anterior dejó abiertos** (`VG-N5` dependencias y
  cadena de suministro; `VG-N6` superficie sin credencial) se declaran cerrados:
  el primero con job bloqueante, pines por SHA y Dependabot; el segundo
  **declarando por escrito** qué responde sin sesión y acotándolo por test en las
  dos direcciones.
- **Sigue abierto y declarado:** los **7 gates** de validación física en `pending`
  (nada de esta línea los ejecuta), `RA-02`, `RA-07` y `RD-05` como deuda aceptada,
  la ausencia de audio humano y de evaluación acústica en listening, y la matriz de
  dispositivos (`docs/DEVICE_MATRIX.md`) íntegramente en ⬜.

---

## 3. Batería automática — reproducir, no creer

El auditor **debe** ejecutar esto y comparar con lo declarado. Cifras declaradas
por la release (medidas en el árbol de trabajo con `frontend/dist` construido y los
modelos presentes):

```powershell
# Backend
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q          # 2882 casos (ver reparto abajo)
.venv\Scripts\python.exe -m ruff check .              # declarado: limpio

# Frontend
cd ..\frontend
npx tsc --noEmit                                      # declarado: limpio
npx vitest run                                        # declarado: 721 passed (87 ficheros)
npm run audit:contrast                                # declarado: 0 fallos bloqueantes
npm run build                                         # declarado: OK
npm audit --omit=dev --audit-level=high               # declarado: 0 vulnerabilidades

# Launcher
cd ..\launcher
..\backend\.venv\Scripts\python.exe -m pytest tests/ -q  # declarado: 142 passed
..\backend\.venv\Scripts\python.exe -m ruff check .      # declarado: limpio

# Auditoría de dependencias del árbol de producto (lo que hace el job de CI)
cd ..
backend\.venv\Scripts\python.exe -m pip install pip-audit
backend\.venv\Scripts\python.exe -m pip_audit -r backend\requirements.txt  # declarado: 0 vulnerabilidades

# Gates de release
backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist  # declarado: 10/10
backend\.venv\Scripts\python.exe scripts\validation_gate.py status               # declarado: 7 pending
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict      # declarado: exit 1
backend\.venv\Scripts\python.exe scripts\validation_gate.py status --strict --same-tree  # declarado: exit 1
backend\.venv\Scripts\python.exe scripts\check_i18n_coverage.py --strict         # declarado: 0 huérfanas
backend\.venv\Scripts\python.exe scripts\check_release_consistency.py            # declarado: 3.75.0, 6 orígenes
backend\.venv\Scripts\python.exe scripts\check_beta_v3.py                        # declarado: OK
cd backend
.venv\Scripts\python.exe scripts\content_validation.py                           # declarado: OK
.venv\Scripts\python.exe scripts\transfer_validation.py                          # declarado: OK (con avisos advisory)
```

**Recuento de la suite: el invariante y el reparto.** El **invariante es el número
de casos: 2882**. Lo que **no** es invariante es el reparto entre `passed` y
`skipped`, porque depende de artefactos **no versionados**:

| Entorno | `passed` | `skipped` | Qué falta |
|---|---|---|---|
| **Clon limpio de GitHub** (sin `npm run build`) | **2879** | **3** | `frontend/dist` (1) + modelo Whisper opt-in (2) |
| Ese mismo clon **tras `npm run build`** | **2880** | **2** | modelo Whisper opt-in (2) |
| Árbol con `dist`, modelos Whisper y BD local | **2882** | **0** | nada |

Los tres suman **2882 casos**. Los saltos son **condicionales de artefactos no
versionados** y están declarados en el propio código:

```text
SKIPPED tests/test_serve_frontend_v372.py:173   -> frontend/dist no construido en este entorno
SKIPPED tests/test_stt_asr_integration.py:24    -> Modelo Whisper no descargado: integración ASR opt-in (x2)
```

Si acabas de clonar y no has compilado, lo que verás es **2879 + 3**, y eso **no es
un hallazgo**: es el estado esperado de un clon limpio. Si el **total de casos** no
es 2882, o aparece un salto **no** listado arriba, sí lo es.

**Prerrequisito del informe determinista (importante).** La comprobación 9 de `auto`
(«el artefacto de la UI está construido») **exige `frontend/dist/index.html`**, que
**no se versiona**. En un clon limpio, `auto --require-dist` **falla** hasta que se
ejecute `npm run build`; sin `--require-dist`, esa comprobación sale **`skip`** y el
informe regenerado **no** será idéntico al commiteado. Compila antes de comprobar
determinismo:

```powershell
cd frontend; npm run build; cd ..
backend\.venv\Scripts\python.exe scripts\validation_gate.py auto --require-dist
git diff --stat -- docs/audit/generated/release-validation.md docs/audit/generated/release-validation.json
# debe salir VACÍO: el informe regenerado es idéntico al commiteado
```

Y el artefacto commiteado **no puede contener la ruta absoluta de ninguna máquina**:

```powershell
Select-String -Path docs/audit/generated/release-validation.md -Pattern 'E:\\|/home/|/Users/'
# debe salir VACÍO
```

---

## 4. Áreas auditadas y preguntas falsables

Cada pregunta está pensada para **refutarse desde el clon**, sin credenciales, sin
servicios y sin hardware. Se indica dónde mirar y **qué la falsaría**.

### A. Arquitectura y backend

1. **¿La arquitectura declarada coincide con los directorios reales?** Comparar
   `docs/ARQUITECTURA.md` con el árbol de `backend/`. **Falsable:** un módulo citado
   que no exista (o al revés), incluidos los **tres nuevos** de V3.75
   (`services/sessions.py`, `routers/session.py`, `utils/session.ts`).
2. **¿La máquina de estados tiene estados y transiciones cerrados?** **Falsable:**
   un `else` que degrade cualquier estado desconocido sin error.
3. **¿Hay concurrencia declarada sin resolver?** SQLite + FastAPI: buscar
   `check_same_thread`, `WAL`, `timeout`, `pool`, `asyncio.Lock`. **Falsable:** la
   afirmación «multiusuario» sin ninguna serialización declarada.
4. **¿La persistencia es migrable?** Buscar migraciones aditivas y su guard.
   **V3.73.7, V3.74.0 y V3.75.0 no migran**: confirmarlo (`VERSION` de BD sin
   cambio). **Falsable:** un `CREATE TABLE`/`ALTER` nuevo sin migración declarada.
5. **¿El tratamiento de errores es honesto?** Buscar `except Exception: pass` y
   `return None` silenciosos en `backend/services` y `backend/routers`. **Falsable:**
   un error que el cliente no pueda distinguir de «vacío legítimo». Caso nuevo y
   deliberado: `sessions.verify()` devuelve `None` para **todos** los motivos
   (ausente, mal formado, firma, caducidad) — ¿es defendible esa opacidad o tapa
   diagnósticos legítimos?
6. **¿La identidad es del servidor en todo el backend?** `rg "user_id=" backend/routers`
   y `rg "request.query_params" backend` — buscar cualquier lectura de identidad
   desde query/body en una ruta autenticada. **Falsable:** una ruta que siga
   leyendo el `user_id` del cliente sin contrastarlo con la sesión.
7. **¿Rendimiento: hay alguna métrica o solo promesas?** La línea **no** aporta
   benchmarks. Declarar **NO COMPROBABLE** lo que no tenga medición. `_secret()`
   lee 44 bytes **por petición** (decisión declarada): ¿el coste está justificado o
   es una caché que faltó?
8. **¿Offline: qué toca Internet de verdad?** Ejecutar el instrumento y compararlo
   con el código:

   ```powershell
   cd backend
   .venv\Scripts\python.exe -m scripts.audit_dossier runtime-audit
   ```

   Buscar primitivas de red (`urlopen`, `urlretrieve`, `requests.`, `httpx.`,
   `socket.`, `aiohttp`) y comparar con `RUNTIME_TOUCHPOINTS`.
   **Falsable:** una primitiva sin declarar (nuevo en V3.75: `pip-audit` **no**
   entra en ruta de producto, solo en CI).

### B. Adaptive Engine, evidencia y procedencia

9. **¿El motor adaptativo decide con evidencia rastreable?** Cada decisión lleva su
   `why`/`because` y el cliente **no** recalcula señales (premisa 21). **Falsable:**
   una decisión pintada en la UI sin `why` del backend.
10. **¿La evidencia es procedural (con origen) o solo un número?** **Falsable:** un
    score sin procedencia declarada.
11. **¿Los umbrales de banda están en un solo sitio?** Deben estar unificados en
    `backend/services/cefr.py`. **Falsable:** un segundo corte de banda duplicado.
12. **¿La divulgación del placement es cierta?** El proyecto declara que el
    placement mide **reconocimiento/meta-lenguaje, no producción**, y que **no hay
    pantalla de nivelación**. Comprobar las dos mitades. **Falsable:** un componente
    que consuma el placement sin divulgación.

### C. Pedagogía, contenido y claims de nivel

13. **¿«Tener un nivel» está definido o es retórica?** Leer
    `docs/CONSTITUCION-PEDAGOGICA.md` y comprobar que el código la implementa.
    **Falsable:** un camino que conceda nivel sin la evidencia exigida.
14. **¿La acreditación se distingue de la práctica?** **Falsable:** un badge de
    nivel alcanzable solo con práctica.
15. **¿La cobertura aguanta la afirmación CEFR A1–C2?** Ejecutar la validación de
    contenido y leer `docs/audit/AB-PED-COBERTURA.md`; el proyecto **declara huecos**
    (niveles altos por debajo del objetivo) y **0 audio humano**. Comprobar que
    **no** se cuentan como cubiertos.
16. **¿La transferencia se mide como se declara?** El proyecto declara que mide
    **escrito, no oral**: verificar en `backend/scripts/transfer_validation.py`.
17. **¿El feedback textual existe en todas las destrezas?** El proyecto declara que
    **listening solo puntúa, sin mensaje correctivo**. **Falsable:** que haya dejado
    de ser cierto sin decirlo (o al revés).
18. **¿Los claims de nivel están acotados?** **Falsable:** una promesa del tipo
    «alcanzarás B2» sin la evidencia que la constitución exige.

### D. Listening (área bajo escrutinio especial)

19. **¿Qué fases existen de verdad?** El proyecto declara **`pre`, `while1`,
    `while2`, `post`, `shadowing`** (`backend/services/listening_flow.py`) y que
    **la UI se salta `pre`** (`microFlow.ts::SKIPPED_STAGES`). **Falsable:** que la
    UI ejecute `pre`, o que una fase declarada no se sirva.
20. **¿Pasiva y activa se distinguen?** **Falsable:** que sean la misma pantalla
    con distinto título.
21. **¿Dictado y cloze están en el contenido o se derivan?** El proyecto declara
    que **no hay cloze ni dictado parcial ni segmentación en el currículum JSON**:
    se derivan en runtime. **Falsable:** un `"skill": "cloze"` en el corpus.
22. **¿El connected speech está realizado o solo etiquetado?** **Falsable:** que el
    audio de un ítem `connected_speech` no contenga la reducción declarada.
23. **¿El shadowing se puntúa de verdad?** El proyecto declara **dos** cosas
    distintas (puntúa sobre texto ASR; y en el paso `shadowing` del micro-flujo
    receptivo la grabación es **libre y no puntuada**). Comprobar ambas y que no se
    presente como evaluación acústica.
24. **¿La velocidad es continua o una escalera fija?** Declara **3 variantes
    fijas** (`slow`/`normal`/`fast` → 0.75/1.0/1.25) **globales, no por nivel CEFR**.
    **Falsable:** afirmar calibración por banda.
25. **¿El transcript se revela con política o siempre?** Debe haber política por
    nivel CEFR y la UI debe respetarla.
26. **¿La dificultad del listening es adaptativa?** Declara dificultad **fija por
    ítem** y adaptación **por sub-destreza débil y capa cognitiva**, sin IRT.
    **Falsable:** la palabra «adaptativo» aplicada a la dificultad sin motor que la
    recalibre.
27. **¿El audio es humano o TTS?** Declara **todo Piper** y biblioteca humana
    **vacía**: comprobar `backend/audio_library/manifest.json`. **Falsable:** un
    ítem con audio humano.

### E. GUI y navegación

28. **¿La estructura real coincide con la declarada?**

    ```text
    INICIO
      ├── FORMACIÓN REGLADA → Curso / progreso
      └── APRENDER → Listening, Vocabulary, Reading, Grammar, Speaking, Chat
    ```

    Lo que el código dice es **distinto**, y el auditor debe dictaminarlo: la
    navegación raíz son **3 mundos hermanos** (Inicio, Formación, Aprender) más
    **2 auxiliares** (Diccionario, Traductor) — **5 destinos**
    (`frontend/src/app/routes.ts`, `Navigation.tsx`); el hub de **Aprender tiene 4
    tarjetas** primarias (`xl:grid-cols-4`), **no 6**, más un bloque **secundario**
    con Reading y Writing que abre `/chat/lectura` y `/chat/escritura`
    (`frontend/src/features/learn/LearnHub.tsx`, `router/chat.ts`); **Reading no
    tiene directorio de feature versionado** mientras Writing sí; la navegación es
    un **hash router propio**, no `react-router`; `JourneyScreen.tsx` **no se
    importa** (código muerto). **Pregunta falsable:** ¿sigue habiendo confusión
    entre Curso / Aprender / Trayecto / Vocabulary / Chat, y es un problema de
    producto o una decisión declarada?
29. **¿Los estados loading/error/empty/success son consistentes?** El proyecto
    declara un patrón mínimo compartido (`PanelState.tsx`) y reconoce que **no hay**
    componentes compartidos de vacío/carga/error. **Falsable:** una pantalla que
    muestre «vacío» cuando en realidad hay error.
30. **¿Hay errores silenciados, y cuáles importan?** Buscar `catch {}` y
    `.catch(() => {})` en `frontend/src`. **Nuevo en V3.75:** elegir perfil y crear
    perfil tragan el fallo de `openSession` («backend no disponible: el selector no
    cambia de perfil»). Dictaminar si ese silencio es **aceptable** (la petición
    siguiente fallará con 401 de forma visible) o deja la UI en un estado mentiroso.
31. **¿Accesibilidad: hay evidencia o solo intención?** Declara skip link,
    `aria-current`, `role="tablist"/"tab"/"tabpanel"`, `role="status"`/`aria-live`,
    `role="alert"`, `sr-only`; y declara que **no hay tests de a11y automatizados**
    (ni `axe-core`). Hay **cuatro** contratos de UI en Playwright (contraste de los
    7 acentos, teclado, `prefers-reduced-motion`, zoom 200 %/reflow).
    **Falsable:** una dependencia de a11y, o que el proyecto afirme cobertura.
    **Aviso (2026-09-18, corrección antes de publicar el tag):** el arnés visual
    corre **sin backend** y, desde `frontend/tests/visual/gateHelper.ts::mockIdentitySession`,
    mockea `/api/session` igual que ya mockeaba `/api/users`. Por tanto un verde de
    `Playwright E2E (visual)` **no** es evidencia de que el servidor emita, firme y
    verifique la sesión: eso vive en `backend/tests/test_sessions.py`,
    `test_identity_source.py`, `test_users_self_only.py`, `test_public_surface.py`,
    `frontend/src/utils/session.test.ts` y el humo de `product-origin`. La razón y
    el detalle están en `release-notes-v3.75.0.md` §7.1 (la primera run real de CI
    sobre el commit de release salió **11/12** justo por esto).
32. **¿Responsive/touch/teclado: hay verificación?** Declara 3 viewports en
    Playwright (1280×800, 768×1024, 390×844) **sin** aserciones de tamaño táctil ni
    de layout numérico. **Falsable:** declarar verificada la matriz de dispositivos:
    `docs/DEVICE_MATRIX.md` está **en ⬜** (todo `?`).
33. **¿La puerta de perfil sigue funcionando sin sesión?** `ProfileGate` debe poder
    listar y crear perfiles **antes** de que exista sesión (si no, nadie podría
    entrar). **Falsable:** que el flujo de primer arranque exija una sesión previa;
    o que cree el perfil y **no** abra sesión (se vería «activo» con 401 en todo).

### F. Seguridad, identidad y cadena de suministro

34. **¿La cookie de sesión es realmente `HttpOnly` y de dónde sale su `Secure`?**
    Leer `routers/session.py::_set_session_cookie` y
    `frontend/src/utils/cookie.ts` (**no debe existir**). **Falsable:** encontrar JS
    que escriba o lea la identidad, o una cookie sin `HttpOnly`.
35. **¿El token resiste manipulación?** Ejecutar los tests de `test_sessions.py` y,
    mejor, comprobarlo a mano: cambiar un byte del payload, del `uid`, la firma, u
    omitir el `iat`; y emitir con `now` del futuro. **Falsable:** cualquier
    manipulación que devuelva un `user_id`.
36. **¿La comparación de firmas es en tiempo constante?** `hmac.compare_digest`.
    **Falsable:** un `==` sobre la firma (filtra por temporización).
37. **¿La identidad es inmune al parámetro?** Con sesión de A, pedir
    `GET /api/profile?user_id=<B>` (y `PATCH`/`PUT`) debe devolver datos de **A** o
    **403** — nunca de B. **Falsable:** cualquier respuesta con datos de B.
    Recordatorio: los tests que fijan esto van marcados `identidad_cruda` porque el
    adaptador de `conftest` los falsearía.
38. **¿El secreto de firma puede salir del equipo?** `_NON_PORTABLE_TOP_NAMES` en
    `services/backup.py`: el ZIP **no** debe contener `session.secret` (ni
    `certs/`), y restaurar un ZIP ajeno **no** debe borrar el secreto local.
    **Falsable:** el fichero dentro de un ZIP generado.
39. **¿La caducidad se aplica?** `SESSION_TTL_SECONDS = 365 días` y margen de reloj
    de 60 s. **Falsable:** que un token viejo siga valiendo, o que un token «del
    futuro» se acepte sin límite.
40. **¿La superficie sin sesión está declarada y acotada?** Leer
    `docs/ARQUITECTURA.md` §«Superficie sin sesión» y
    `backend/tests/test_public_surface.py`: las **9** rutas declaradas sin sesión
    (`/api`, `/api/health`, `/api/health/live`, `/api/health/ready` —200 **o**
    503—, `/api/health/dependencies`, `/api/users`, `/api/models` —200 o 502 si
    Ollama no responde—, `/api/network` y `/api/system/status`) **deben** responder
    como se declara; las **8** declaradas con sesión (`/api/settings`,
    `/api/profile`, `/api/progress`, `/api/conversations`, `/api/vocabulary`,
    `/api/grammar/errors`, `/api/academy/levels`, `/api/listening/stats`) **deben**
    dar **401** `SESSION_REQUIRED` incluso mandando `?user_id=`. **Falsable:** un
    endpoint de datos del alumno en la lista pública; o que borrar la sección del
    documento **no** haga fallar el test.
41. **¿Los límites de tasa se aplican a las rutas reales?** `backend/security.py`
    (`_PATH_LIMITS`) contra la tabla de rutas montada. **Falsable:** una clave que
    no corresponda a ninguna ruta (el bug de V3.73.7) o una ruta cara sin cupo
    propio.
42. **¿La frontera de red es fail-closed y coherente?** `lan_mode()` con la
    variable ausente/`0`/`false`/texto raro ⇒ loopback; `backend_host` y la política
    de CORS salen de la **misma** decisión. **Falsable:** que `ENGLISH_TUTOR_LAN=0`
    abra el bind, o que el middleware y `origin_allowed` discrepen.
43. **¿La CSP y las cabeceras defensivas hacen lo que dicen?**
    `SecurityHeadersMiddleware`: comprobar `nosniff`, `X-Frame-Options`,
    `Referrer-Policy`, `Permissions-Policy` y **qué** cubre la CSP (declara ser
    **parcial**: no cierra `script-src`). **Falsable:** que el proyecto la presente
    como CSP completa.
44. **¿El PIN de administración sigue en `localStorage`?** Debe estar en
    `sessionStorage` y la copia heredada borrada. **Falsable:** `localStorage` en
    `adminPin.ts` o en `App.tsx`.
45. **¿Las Actions van fijadas por SHA?** Ningún `uses:` con `@vN`, `@main` o
    etiqueta móvil en `.github/workflows/`. **Falsable:** un `@v4` reintroducido
    (el job `deps-audit` y el test `test_todas_las_actions_van_fijadas_por_sha`
    deben cazarlo).
46. **¿La auditoría de dependencias es real y bloqueante?** El job `deps-audit`
    ejecuta `pip-audit -r requirements.txt` **del árbol de producto** y
    `npm audit --omit=dev --audit-level=high`, y **no** tiene
    `continue-on-error: true`. **Falsable:** que sea informativo, o que audite el
    árbol de desarrollo en vez del de producto.
47. **¿El árbol publicado está limpio de vulnerabilidades conocidas?** Ejecutar
    `pip-audit -r backend/requirements.txt` y `npm audit --omit=dev`. **Falsable:**
    cualquier aviso. **Nota:** la versión anterior de esta batería declaraba 10
    avisos en `starlette 0.50.0`; se cerraron subiendo `fastapi` a `0.141.1`
    (`starlette 1.6.0`). Dictaminar si un **salto de versión mayor** de Starlette
    dentro de una release de seguridad es proporcionado.
48. **¿Dependabot cubre los tres ecosistemas?** `.github/dependabot.yml` con `pip`
    (`/backend`), `npm` (`/frontend`) y `github-actions`. **Falsable:** falta de
    `github-actions` (sin él los pines por SHA se quedan viejos para siempre).
49. **¿El diagnóstico del launcher filtra el token?** `browser_cookies._mask_value`
    debe enmascarar `et_session` (Firefox guarda las cookies **en claro**) y el
    panel mostrar presencia, no identidad. **Falsable:** el valor del token
    impreso, o una máscara que pise la descripción `(cifrado · N bytes)` de una
    cookie de Chromium.
50. **¿HTTPS y micrófono?** El producto sirve por HTTPS en `:8000` con certificado
    autofirmado (obligatorio para `navigator.mediaDevices`). Comprobar los SANs y
    que la generación es determinista e idempotente. **Falsable:** servir producto
    por HTTP y declararlo equivalente; o una cookie sin `Secure` por HTTPS.
51. **¿Los `PATCH`/`PUT` de perfil son del propio perfil?** `test_users_self_only.py`
    y el código: 403 cuando el id no es el de la sesión. **Falsable:** un `PATCH`
    aplicado a otro perfil (o a un id inexistente con efecto lateral).

### G. Runtime, instalación y entorno

52. **¿El fail-closed es real y está en los dos lados?** Quitar/renombrar
    `frontend/dist/index.html` y comprobar que el **runtime de producto** eleva un
    error accionable, **y** que un `uvicorn main:app` manual sigue siendo fail-open
    (modo desarrollo declarado). **Falsable:** que el producto arranque sin UI.
53. **¿TTS/STT/Ollama: qué es local y qué necesita Internet?** La voz se descarga
    **una vez** (~60 MB, con consentimiento); el modelo LLM por defecto es
    `llama3.1:8b` vía Ollama. Comparar `backend/config.py` con `README.md`.
    **Falsable:** una discrepancia entre lo declarado y el código.
54. **¿La instalación limpia está documentada o ejecutada?** El proyecto declara que
    **no** se ha probado en una máquina físicamente limpia (`RB-05`) y que
    `backend/models/` (~1,1 GB) no se versiona. **Falsable:** declararla verificada.
55. **¿El launcher es Windows-only?** Debe declararse, y el job de CI en Windows
    **no** sustituye a la prueba humana (gate G3). **Falsable:** presentar
    `launcher-windows` verde como certificación de Windows.

### H. CI/CD y release

56. **¿Cuántos jobs hay y cuáles son bloqueantes?** Deben ser **12** (los 11
    anteriores + `deps-audit`), con `launcher-windows` **bloqueante** y
    `product-origin-windows` **informativo declarado** (`continue-on-error: true`)
    con criterio de promoción escrito. **Falsable:** que el informativo pase por
    bloqueante en la práctica, o que el proyecto lo cuente como certificación.
57. **¿Los permisos del workflow son mínimos?** `permissions: contents: read`.
    **Falsable:** `write` o permisos implícitos ampliados.
58. **¿`--strict` se exige en CI?** **No** puede estar (los gates son acción
    humana: un CI que los exigiera sería rojo permanentemente). Hay un test que lo
    fija. **Falsable:** `validation_gate.py status --strict` en el workflow.
59. **¿La reproducibilidad aguanta?** Regenerar el informe y el par de auditoría de
    red y comprobar **diff vacío** e **idempotencia** (compila antes: ver §3).
    **Falsable:** cualquier diff, o una ruta absoluta filtrada.
60. **¿La documentación declara lo que el código hace?** Buscar **drift** en
    `README.md`, `docs/PREMISAS.md`, `docs/ARQUITECTURA.md`, `docs/DEVICE_MATRIX.md`
    (debe apuntar a `:8000`, no a `:5173`), los tres protocolos de los gates y
    `docs/RELEVO.md`. **Falsable:** una frontera nueva (LAN, sesión) ausente de
    esos documentos: desde V3.74 hay un guard de deriva que debería cazarlo.

---

## 5. Matriz de cierre (la rellena el auditor)

Cada fila debe sostenerse en **evidencia de código o de test** del árbol publicado.
Si un área no se puede comprobar sin hardware o sin persona, se marca **NO
COMPROBABLE** con el motivo; **no** se puntúa por lo que la documentación promete.

| Área | 🟢/🟡/🔴 | Evidencia (archivo:línea, test o comando) | DEMOSTRADO / DECLARADO / NO COMPROBABLE |
|---|---|---|---|
| Arquitectura | | | |
| Backend | | | |
| Adaptive Engine | | | |
| Pedagogía | | | |
| Contenido | | | |
| GUI | | | |
| Responsive | | | |
| Listening | | | |
| Speaking | | | |
| TTS/STT | | | |
| Offline | | | |
| Instalación | | | |
| **Identidad y sesión** | | | |
| **Superficie sin sesión** | | | |
| **Cadena de suministro** | | | |
| Seguridad | | | |
| CI | | | |
| Documentación | | | |

**Criterio de veredicto:** `APROBADO` / `APROBADO CON OBSERVACIONES` / `NO APROBADO`
para **el modelo de identidad publicado en V3.75.0**, con la lista de lo que debe
cerrarse. Recordatorio: la puerta declarada de V4.0 sigue siendo
`validation_gate.py status --strict` saliendo **0**, y **no** depende de esta
release.

---

## 6. Reglas duras para el auditor

1. **Solo lectura.** No se modifica nada; no se abren PRs correctivos.
2. **Separar lo verificado de lo declarado.** Toda afirmación que no se pueda
   reproducir desde el clon se marca como **DECLARACIÓN**, no como hecho.
3. **Severidad `P0`–`P3`** (`P0` rompe una garantía central, `P3` es documental), y
   **una afirmación por hallazgo**, con `archivo:línea` del árbol publicado y
   comando de reproducción.
4. **Falsabilidad primero:** un hallazgo que no se pueda refutar con un comando no es
   un hallazgo. **Nada de «podría», «convendría» ni «en el futuro»** sin dato.
5. **Lo que no se pueda comprobar se declara NO COMPROBABLE**, con el motivo.
6. **Sin cortesía:** si el producto no demuestra lo que dice, decirlo; si lo
   demuestra, decirlo también.
7. **No confundir el instrumento con la validación.** Que exista un gate, un
   candado, un kit o un informe **no** es evidencia de que el hecho esté verificado.
8. **Regla nueva (V3.75): no confundir «firmado» con «autenticado».** Una cookie
   firmada por el servidor prueba **quién emitió** la identidad, no **quién tiene
   derecho** a ella. Cualquier hallazgo que trate la sesión como autenticación debe
   declarar esa distinción.

---

## 7. Honestidad esperada del informe

El auditor debe pronunciarse **explícitamente** sobre estas declaraciones del propio
proyecto, que acotan lo que puede leerse como demostrado:

- **Esto no es autenticación y la Fase 3 no está decidida.** `POST /api/session`
  acepta cualquier `user_id` **existente** sin credencial y `GET/POST /api/users`
  siguen abiertos: en modo LAN, quien alcance la API puede **abrir sesión para
  cualquier perfil**. Lo que V3.75.0 cierra es la **autoridad** sobre la identidad
  (no se forja desde fuera, no se elige por petición). Cerrarlo exige credencial y
  contradice «sin cuentas, sin contraseñas» de `docs/PREMISAS.md`: es una decisión
  de producto, no un pendiente técnico. **Comprobación:** `PARKED.md` §V3.75.
- **Los 7 gates están en `pending`.** Nadie ha hecho el corte de red real
  (`RA-05`), ni una instalación en máquina limpia (`RB-05`), ni pruebas en móvil
  real, ni pruebas con audio real. El código marca los **7** gates como
  `human: bool = True`; la cifra vigente es **7 de 7**.
- **El kit es una planilla, no una validación.** `KIT-VALIDACION-GATES.md` ordena y
  registra la ejecución humana; **no** mueve ningún gate a `pass`.
- **`product-origin-windows` es informativo**, no bloqueante, y así se declara.
- **El fail-closed cubre el arranque, no la ejecución degradada.**
- **Las cookies migradas:** la de perfil (V3.73.7) y la de identidad (V3.75.0)
  llevan `Secure` **según el esquema de la petición**. En el uso real (HTTPS) va
  puesta; servido por HTTP plano, no. Dictaminar si eso es aceptable o si debería
  ser incondicional.
- **El adaptador de `conftest` reduce lo que prueban 109 suites.** Ya no prueban
  «la identidad viene de la cookie»; eso lo cubren los tests nuevos, marcados
  `identidad_cruda` para poder saltarse el adaptador. Si el auditor cree que el
  marcador puede usarse para esconder una regresión, es un hallazgo.
- **El candado de `VG-N6` fija una lista, no demuestra que sea completa.** La
  completitud de una superficie de API se revisa, no se prueba.
- **`starlette 1.6.0` es un salto de versión mayor** dentro de una release de
  seguridad. La evidencia declarada es la suite completa en verde (2882 casos), no
  la lectura de un changelog ajeno.
- **El listening no tiene audio humano, ni evaluación acústica, ni feedback textual
  correctivo**, y su dificultad **no** es adaptativa.
- **La accesibilidad y la matriz de dispositivos no tienen evidencia ejecutada:**
  `docs/DEVICE_MATRIX.md` está **en ⬜** (todo `?`) y no hay motor de accesibilidad
  (`axe`). Lo que hay son **cuatro contratos de UI** en Playwright: acotado, no es
  una auditoría.
- **Sigue abierto y aceptado:** `RA-02` (endpoint de Ollama sin declarar en
  `config.py`), `RA-07`, `RD-05`.

---

## 8. Cierre

**Estado del punto de entrada: entregado (2026-09-18), dentro del commit de release
de `v3.75.0`.** Verificado por comando contra GitHub, no contra el árbol local:

- **Release auditada:** el tag anotado **`v3.75.0`**; el commit y el objeto del tag
  se resuelven con `git rev-parse` (§1), **no** se fijan a mano.
- **`main`:** el tag se publica sobre el mismo commit que `main`; desde V3.73.5
  **no hay commit documental posterior al tag** (el punto de entrada viaja dentro).
- **CI:** `success` con los **12 jobs** en verde en la run del commit del tag
  (`gh run list --commit $(git rev-parse v3.75.0^{commit}) --limit 1`).
- **Invariante del código:** `git diff --stat v3.75.0..main -- backend frontend
  launcher scripts` sale **vacío**.
- **Consistencia de versión:** `3.75.0` en los **6 orígenes**
  (`scripts/check_release_consistency.py`).
- **Invariante de la suite:** **2882 casos**; reparto de `passed`/`skipped` según
  artefactos (§3).

**Informe esperado:** `docs/audit/AJ-AUDITORIA-TOTAL-V375.md`.
