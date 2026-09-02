# G — LAN + Real Devices (auditoría V3.0)

- **Fecha:** 2026-09-02
- **Alcance:** validación física en LAN/HTTPS autofirmado del stack V2.7–V2.12 sobre dispositivos reales: PC Windows (Chrome/Edge), Android (Chrome), iPhone (Safari) e iPad (Safari). No se audita contenido ni calibración (A–E) ni UX de Home (F).
- **Relación con freeze:** pruebas reales (`BETA_V3.md` §4.4 y `docs/DEVICE_MATRIX.md`).
- **Naturaleza:** runbook ejecutable. La ejecución física requiere hardware humano; este dossier deja los pasos exactos por dispositivo y el registro donde anotar resultados. **Estado: protocolo listo, ejecución pendiente.**

## Preparación (una vez)

1. Arranca la app con el launcher (`launcher/launcher.py`) y anota la URL LAN que muestra (`https://<ip>:5173`).
2. Comprueba en la barra inferior de estado: **HTTPS** ok (candado aceptado), **mDNS** disponible si `local_url_available` es `true`, micrófono «Test microphone» con nivel de entrada y «Test playback» con audio audible.
3. Para móviles, coloca el dispositivo en la misma red Wi-Fi que el PC y apunta el navegador a la URL LAN. En Android/iOS Chrome el autofirmado exige *Avanzado → Continuar* la primera vez.

## Runbook — por dispositivo

Cada fila = un dispositivo nuevo. Para cada uno repite el checklist funcional y anota en la tabla de Registro.

### A. PC Windows — Chrome y Edge

1. Abrir la URL LAN en el navegador; aceptar el certificado autofirmado.
2. Estado del sistema: HTTPS `✓`, mDNS (por IP si no hay Bonjour), Test microphone (nivel audible), Test playback.
3. **Checklist V3.0** completo (abajo).
4. Ventana de 1280×800 y de 360 px de ancho (DevTools): comprobar que Home no rompe el layout (menu móvil).

### B. Android — Chrome (y Edge si está instalado)

1. Mismo Wi-Fi; abrir URL LAN. Aviso «Tu conexión no es privada» → Avanzado → Continuar.
2. HTTPS `✓`. En Chrome Android el micrófono requiere permiso por web (botón de permiso al usar por primera vez); conceder.
3. Test microphone y Test playback; después **Checklist V3.0**.
4. Rotación vertical/horizontal durante una actividad: la UI debe conservar el estado (no reiniciar la actividad).
5. **Recuperación de permiso**: denegar micrófono en la UI → conceder en Ajustes del navegador → volver a la pestaña → el aviso debe desaparecer **sin recargar**.

### C. iPhone — Safari (y Chrome)

1. Mismo Wi-Fi. **Safari exige HTTPS** y micrófono habilitado: Ajustes → Safari → *Avanzado* (y, si aplica, Ajustes del sitio). Si el micrófono falla, ver `mic.unavailable.not_secure_context`.
2. Test microphone + playback; **Checklist V3.0**.
3. Recuperación de permiso como en B5.
4. Comprobar que el scroll de la tríada/Home es fluido y que los botones grandes son alcanzables con pulgar (sin hover).

### D. iPad — Safari

1. Igual que C (HTTPS + micrófono). Pantalla grande: comprobar que no se ve el layout de teléfono estirado (usa ≥2 columnas donde esté previsto).
2. **Checklist V3.0** completo. Es la única tablet del plan: presta atención a la ladder de Assessment con split view de Safari (si se abre, que no pierda la sesión).

## Checklist V3.0 Beta (por dispositivo)

1. **Speaking Mission**: un intento débil → aparecen drills → completar un drill → retry → se ve el % de mejora (improvement).
2. **Assessment 2.0**: formative de un objetivo + unit assessment, hasta el resultado con umbrales.
3. **FSRS**: Today → Spaced review → calificar una carta (p. ej. Good) → nuevo `due` coherente (ver `fsrs.lastEvidence`).
4. **Evidence Graph**: abrir el panel → elegir un can-do → comprobar *limiting factor* y `because[]`.
5. **Next-best en Home**: con una semana de uso, Home muestra una tarjeta con viñetas **Because:** y CTA.

## Registro

Marca `✓ / ✗ / — / ⬜` igual que `docs/DEVICE_MATRIX.md`. Copiar resultados aquí y a la matriz.

| Dispositivo | Navegador | HTTPS | mDNS | Mic | Audio | Listening | Speaking | Recuperación | Checklist V3.0 | Notas |
|---|---|---|---|---|---|---|---|---|---|---|
| PC (Windows) | Chrome | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| PC (Windows) | Edge | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| Android | Chrome | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| iPhone | Safari | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| iPhone | Chrome | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |
| iPad | Safari | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | |

## Criterios de fallo

- El micrófono no captura tras conceder el permiso (nivel plano en Test microphone) → abrir incidencia `mic.*`.
- Listening/Speaking se cortan a mitad por red/certificado (no por contenido) → revisar LAN + servidor.
- La recuperación de permiso no refleja el cambio sin recargar → incidencia de estado de permisos.
- En móvil, una actividad pierde estado al rotar o al salir/volver → incidencia de ciclo de vida.

## Hallazgos

| # | Sev. | Hallazgo | Evidencia | Recomendación | Estado |
|---|---|---|---|---|---|
| G1 | — | Ejecución física no realizada por el agente (requiere hardware). Runbook y registro listos. | este dossier | Ejecutar el runbook por dispositivo y volcar resultados a `DEVICE_MATRIX.md`. | abierto (acción humana) |
| G2 | info | Los flujos frágiles que se detecten en E2E durante la ejecución se corrigen como regresión (estilo commit `edb2208`), no como features. | plan V3.0 | Registrar el SHA y el fix junto a la celda correspondiente. | — |

## Regenerar / Verificar

```powershell
# Reproducir la preparación
cd launcher
python launcher.py            # o el acceso directo instalado

# Puntos de atención (no bloqueantes de la matriz)
# - Windows sin Bonjour: usar URL por IP
# - iPhone/iPad Safari: micrófono en Ajustes -> Safari -> Avanzado
```

## Tests que respaldan

- `launcher/tests/*` — proceso/estado/UI del launcher (regresión del arranque LAN).
- El Checklist V3.0 de este dossier ejercita, en físico, lo que los golden A–F ya cubren en lógica (`test_golden_*.py`, checker i18n).
