# Matriz de validación de dispositivos (LAN / móvil)

Validación física de English Tutor en dispositivos reales sobre la red local
(HTTPS autofirmado). El código cubre la detección de capacidades y la
recuperación de permisos, pero el comportamiento real de micrófono y audio solo
se puede confirmar en hardware físico. Marca cada celda con:

- `✓` funciona
- `✗` no funciona (describe el problema)
- `—` no aplica
- `⬜` pendiente de probar

> **V3.73:** el producto sirve la UI y la API en **un solo origen HTTPS, el
> puerto `8000`** (`RC-01`, V3.72). El puerto `5173` es el **dev server de Vite**
> y no forma parte del runtime de producto: si aparece en una prueba, se está
> probando otro artefacto. Este gate es `G4 dispositivos` de
> `docs/audit/VALIDATION-RELEASE-V373.md`.

## Cómo probar

1. Arranca la app con el launcher y anota la URL LAN (`https://<ip>:8000`).
2. En el dispositivo, abre la URL. La primera vez: confía el certificado
   (Ayuda → Conectar un dispositivo).
3. Verifica en el estado del sistema (barra inferior → "Ready"):
   - **HTTPS**: la URL se abre con candado/aviso aceptado y la página carga.
     - **mDNS**: `https://<hostname>.local:8000` resuelve (solo si el SO difunde
     mDNS; en Windows sin Bonjour usa la IP).
   - **Micrófono**: `Test microphone` (habla y observa el nivel de entrada).
   - **Reproducción**: `Test playback`.
4. Completa una actividad real de Listening y una de Speaking.
5. **Recuperación**: deniega el micrófono, vuelve a la pestaña, concédelo en
   los ajustes del navegador y verifica que la UI se actualiza sin recargar.

## Matriz

| Dispositivo | Navegador | HTTPS | mDNS | Mic | Audio | Listening | Speaking | Recuperación | Notas |
|---|---|---|---|---|---|---|---|---|---|
| PC (Windows) | Chrome | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| PC (Windows) | Edge | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| PC (Windows) | Firefox | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| PC (macOS) | Safari | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| PC (macOS) | Chrome | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| Android | Chrome | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| Android | Edge | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| iPhone | Safari | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| iPhone | Chrome | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| iPad | Safari | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |

## Matriz de interacción (V3.73)

Las columnas de arriba miden capacidades de hardware. Estas miden la **capa de
interacción** en pantallas táctiles y ventanas pequeñas, que es donde una web de
escritorio suele romperse. Tampoco se puede certificar con capturas.

| Dispositivo | Touch / tap targets | Viewport y scroll | Teclado en pantalla | Orientación (vertical/horizontal) | Notas |
|---|---|---|---|---|---|
| Android | ⬜ | ⬜ | ⬜ | ⬜ | |
| iPhone | ⬜ | ⬜ | ⬜ | ⬜ | |
| iPad | ⬜ | ⬜ | ⬜ | ⬜ | |
| Windows (ventana estrecha) | — | ⬜ | — | — | |

Puntos concretos a comprobar en cada uno:

- **Touch**: los controles de las prácticas (opciones, botones de escucha y de
  grabación) responden al primer toque y no exigen hover.
- **Viewport**: no hay scroll horizontal; los paneles (`FSRS`,
  `EvidenceGraph`, `AssessmentLadder`) se leen sin recortes.
- **Teclado**: al enfocar un campo, el teclado no tapa el enunciado ni el botón
  de envío.
- **Orientación**: girar el dispositivo no pierde estado ni deja la actividad a
  medias.

## Checklist V3.0 Beta (pruebas reales)

Además de la matriz, en la fase post-freeze (`docs/BETA_V3.md` §4.4) conviene
ejercitar el stack pedagógico nuevo:

1. **Speaking Mission**: un intento débil → drills → retry → ver improvement %.
2. **Assessment 2.0**: formative de un objetivo + unit assessment.
3. **FSRS**: abrir Today → Spaced review → grade Again/Good y ver nuevo due.
4. **Evidence Graph**: Profile → can-do → comprobar limiting factor.
5. **Next-best**: Home debe mostrar viñetas **Because:**.

Marca la fila del dispositivo cuando esos cinco flujos pasen en LAN/HTTPS.

## Puntos de atención conocidos

- **iPhone/iPad + Safari**: el acceso al micrófono exige HTTPS y, en algunos
  casos, habilitar el micrófono en Ajustes → Safari → Avanzado. Si falla, revisa
  `mic.unavailable.not_secure_context`.
- **Android + Chrome**: un certificado autofirmado muestra
  "Tu conexión no es privada"; hay que pulsar Avanzado → Continuar. Tras ello,
  el micrófono debe funcionar si el permiso está concedido.
- **Recuperación de permiso**: deniega el micrófono, ve a ajustes, concédelo y
  vuelve a la pestaña. La UI debe actualizarse sin recargar (el aviso desaparece
  y el test de micrófono funciona).
- **mDNS**: la URL `.local` solo se ofrece si `local_url_available` es `true`.
  En Windows sin Bonjour/mDNS, usa la URL por IP (la vía fiable).
- **Modo LAN (V3.73.x)**: desde otro dispositivo, la app solo responde si el modo
  LAN está declarado (`ENGLISH_TUTOR_LAN=1`). Con el modo apagado el backend
  escucha en loopback y `/api/network` devuelve `lan_mode: false` y `url: ""`, así
  que la tarjeta de conexión no ofrece QR ni enlace. Si no hay QR, el primer paso
  no es el certificado: es arrancar en modo LAN y abrir el puerto.
