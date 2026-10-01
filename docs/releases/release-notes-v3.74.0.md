# Release notes — English Tutor v3.74.0

**Fecha:** 2026-09-18 · **Tipo:** release de **PRODUCTO (minor)** que cambia la
**frontera de red** del producto · **Versión de app:** `3.73.7 → 3.74.0`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el banco y SIN tocar el currículum.** Ninguna
capacidad pedagógica nueva. A diferencia de V3.73.2–V3.73.7, cuyo diff era
documentación o un lote de endurecimiento acotado, **aquí cambia cómo se expone el
producto en la red** y, con ello, el **contrato de `/api/network`**: un cliente que
hoy espera una `url` de LAN tiene que mirar `lan_mode`.

---

## Qué es esta release

Cierra la **mitigación `R1`** del P0 de identidad, que quedó declarada como no
resuelta en `release-notes-v3.73.7.md` y en `CHANGELOG.md`. Hasta V3.73.6 el backend
se enlazaba **siempre** a `0.0.0.0` y la regex de CORS aceptaba **cualquier** IP
privada: la app se exponía a la red local **por defecto**, sin que nadie lo hubiera
pedido y sin ninguna señal en la interfaz.

El plan por fases, con las mediciones y las alternativas descartadas, está en
`docs/audit/PLAN-P0-IDENTIDAD.md`.

**Fuera de alcance (declarado).** El **P0 de identidad** —el `user_id` lo elige el
cliente y los endpoints de perfil no exigen credencial— **sigue abierto**. Esta
release le quita el suelo que lo hacía alcanzable desde cualquier equipo de la red;
**no** es autenticación. La Fase 2 (identidad derivada de una sesión firmada y
retirada del `et_user_id`) es la que cambia el modelo.

---

## 1. El problema: la frontera de red no se elegía, se heredaba

Con `bind 0.0.0.0` y CORS de red privada, **cualquier equipo de la misma red**
alcanzaba la API desde su navegador. Y como los endpoints de perfil no piden
credencial, ese acceso era **lectura y escritura** de los datos del alumno:

```text
antes   uvicorn --host 0.0.0.0        + CORS: cualquier IP privada
        -> exponerse a la WiFi era el DEFECTO (nadie lo pidió)
ahora   uvicorn --host 127.0.0.1      + CORS: solo loopback
        -> exponerse exige DECLARARLO (ENGLISH_TUTOR_LAN=1)
```

Lo importante no es el valor por defecto, sino **quién decide**: antes lo decidía
el código por omisión; ahora lo decide quien arranca la app, y el arranque lo deja
escrito en el log (`Modo de red: LAN | solo loopback`), de modo que «no me entra
desde el móvil» tiene una causa escrita en lugar de una hipótesis.

---

## 2. La solución: una sola decisión, leída fail-closed

El modo vive en **una** variable (`ENGLISH_TUTOR_LAN`) y el launcher la **propaga**
en el entorno del backend (`launcher/core.py::backend_env`), así que la interfaz a
la que se enlaza uvicorn (`backend_host`) y la política de orígenes salen de la
**misma** fuente y **no pueden discrepar**. `lan_mode()` se lee **fail-closed**:

| `ENGLISH_TUTOR_LAN` | bind | orígenes de red privada |
|---|---|---|
| ausente | `127.0.0.1` | **rechazados** |
| `0`, `false`, `no`, `off`, texto raro | `127.0.0.1` | **rechazados** |
| `1`, `true`, `yes`, `on`, `si`, `sí` | `0.0.0.0` | aceptados |

Se activa de dos maneras, y las dos exigen un acto explícito:

- el botón **«Activar red local»** del panel de acceso del launcher, que declara el
  modo y **reinicia el servidor** para aplicarlo (la app se recarga), o
- arrancar con `ENGLISH_TUTOR_LAN=1`.

**El modo no se persiste**, y es deliberado: exponer los datos del alumno no debe
poder quedar guardado como estado por accidente. Hay que declararlo en cada
arrancar. (El plan, `docs/audit/PLAN-P0-IDENTIDAD.md` §5.8, lo explica como decisión
y no como limitación.)

---

## 3. La trampa del patrón vacío (corrección al plan)

La primera versión del plan decía que bastaba con **vaciar**
`ALLOWED_ORIGIN_REGEX` y que `security.py` no necesitaba cambios. **Era falso, y en
la dirección peligrosa:** `origin_allowed` comprobaba con `_ORIGIN_RE.match(...)`, y
un patrón **vacío** casa con **cualquier** cadena. Vaciar la regex habría **abierto**
CORS en lugar de cerrarlo — el 403 habría dejado pasar todo. Es el fallo clásico de
«desactivar una validación» dejándola vacía.

Lo implementado:

- **dos** patrones separados (`LOCAL_ORIGIN_REGEX`, siempre válido; y
  `LAN_ORIGIN_REGEX`, solo en modo LAN),
- comprobación con **`fullmatch`** (anclada, no `match`), y
- la decisión de LAN se consulta **por petición** en `origin_allowed`, mientras que
  `CORSMiddleware` compila su patrón **una vez al importar** — motivo por el que el
  launcher declara el modo **antes** de arrancar el proceso.

Ese acoplamiento (dos mitades de la misma política, resueltas en momentos
distintos) es exactamente lo que un cambio futuro puede romper **en silencio**, así
que tiene candado propio:
`test_las_dos_mitades_de_la_politica_de_origen_coinciden` recorre una lista de
orígenes y **falla si el patrón del middleware y `origin_allowed` discrepan**.

---

## 4. Sin enlaces muertos, y el botón del panel (Fase 1b)

Con el bind en loopback, `https://<ip>:8000` **no responde**. Anunciarla igual
habría convertido el panel de conexión en un enlace muerto sin explicación:

- **`/api/network`** informa del modo (`lan_mode`, `bind`) y devuelve `url` **vacía**
  cuando la LAN no está activa.
- **El panel del launcher** muestra «desactivada (solo este equipo)» en esa fila y
  el pie dice el paso exacto que falta.
- **`ConnectDeviceCard`** explica el modo apagado (`connect.lanOff` /
  `connect.lanOffHow`) en lugar de pintar un QR que no llevaría a ninguna parte.

El botón **«Activar/Desactivar red local»** reutiliza el **«Reiniciar servidor»**
que ya existía. Su decisión vive en `core.set_lan_mode`, **no** en la GUI: `tkinter`
no se puede probar sin pantalla, y esta decisión cambia la frontera de red, así que
tiene test de ida y vuelta (declarar → `backend_host` → entorno del proceso). Con la
app parada, el botón solo deja el modo **declarado**, y lo dice.

---

## 5. Verificación

Medido en el **árbol de trabajo** (con `frontend/dist` construido y los modelos
instalados), sobre el árbol que contiene esta release y **no** la anterior: cada
lote se publicó desde su propio árbol, y las cifras de V3.73.7 (2817 / 717 / 113)
se reprodujeron **exactas** en el árbol del parche antes de publicarlo.

| Comprobación | Resultado |
|---|---|
| Backend `pytest tests/ -q` | **2840 passed** |
| Frontend `vitest run` | **719 passed** (86 ficheros) |
| Launcher `pytest tests/ -q` | **139 passed** |
| `ruff check .` / `npx tsc --noEmit` | limpios |
| i18n `check_i18n_coverage.py --strict` | 0 huérfanas / 0 duplicadas / 0 vacías |
| `validation_gate.py auto` | **10/10** |
| `check_release_consistency.py` | OK en los **6 orígenes** (`3.74.0`) |

Los recuentos suben **exactamente** por los tests nuevos: backend 2817 → 2840
(**+23**), frontend 717 → 719 (**+2**, 85 → 86 ficheros) y launcher 113 → 139
(**+26**).

---

## 6. Honestidad

1. **No es autenticación y el P0 sigue abierto.** En modo LAN, `/api/users` sigue
   enumerando y creando perfiles **sin credencial**, y el `user_id` lo sigue
   eligiendo el cliente. Esta release **reduce la superficie** (deja de estar
   expuesta por defecto); no cierra el riesgo. El `et_user_id` no desaparece hasta
   la **Fase 2**.
2. **El candado de coherencia cubre una lista de orígenes**, no demuestra que sea
   exhaustiva: fija que las dos mitades coincidan sobre lo que se le pasa.
3. **El modo no se persiste** (decisión), así que quien arranque el backend a mano
   sin la variable obtiene loopback aunque ayer usara la app desde el móvil.
4. **El botón reinicia el servidor**: no es un ajuste en caliente. Con la app parada
   solo declara el modo, y así se informa.
5. **Los 7 gates siguen en `pending`.** Esta release no mueve la validación física:
   la identidad sellada en `docs/audit/KIT-VALIDACION-GATES.md` (`3.73.6` →
   `13cc30b`) es el registro del **pre-vuelo** y **no se reescribe**.
