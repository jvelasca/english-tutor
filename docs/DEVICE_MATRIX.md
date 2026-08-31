# Matriz de validación de dispositivos (LAN / móvil)

Validación física de English Tutor en dispositivos reales sobre la red local
(HTTPS autofirmado). El código cubre la detección de capacidades y la
recuperación de permisos, pero el comportamiento real de micrófono y audio solo
se puede confirmar en hardware físico. Marca cada celda con:

- `✓` funciona
- `✗` no funciona (describe el problema)
- `—` no aplica
- `⬜` pendiente de probar

## Cómo probar

1. Arranca la app con el launcher y anota la URL LAN (`https://<ip>:5173`).
2. En el dispositivo, abre la URL. La primera vez: confía el certificado
   (Ayuda → Conectar un dispositivo).
3. Verifica en el estado del sistema (barra inferior → "Ready"):
   - **HTTPS**: la URL se abre con candado/aviso aceptado y la página carga.
   - **mDNS**: `https://<hostname>.local:5173` resuelve (solo si el SO difunde
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
