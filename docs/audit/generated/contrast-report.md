# Informe de contraste WCAG — release 3.86.0 (cierre GUI pre-V4.0 · rampa de niveles V3.75.4 · dirección del diccionario V3.75.8)

> Generado por `node frontend/scripts/contrast_audit.mjs` para la release **3.86.0** (`audit: V3.86.0-contraste-wcag`).

- Pares que BLOQUEAN (tipografía base + texto de acento + rampa de niveles + dirección + guardas): **0 fallos** de 444.
- Pares de acento reportados (relleno + tinta y borde): **17 fallos** de 42.

## Tipografía base sobre superficies (bloqueante)

| Tema | Par | Razón | Mínimo | Estado |
| --- | --- | ---: | ---: | --- |
| dark | texto principal sobre el fondo (--color-text / --color-bg) | 15.82 | 4.5 | OK |
| dark | texto principal sobre tarjeta (--color-text / --color-surface) | 13.69 | 4.5 | OK |
| dark | texto secundario sobre el fondo (--color-text-dim / --color-bg) | 7.59 | 4.5 | OK |
| dark | texto secundario sobre tarjeta (--color-text-dim / --color-surface) | 6.57 | 4.5 | OK |
| dark | texto secundario sobre superficie suave (--color-text-dim / --color-bg-soft) | 6.93 | 4.5 | OK |
| dark | texto terciario sobre el fondo (--color-text-faint / --color-bg) | 6.18 | 4.5 | OK |
| dark | texto terciario sobre tarjeta (--color-text-faint / --color-surface) | 5.35 | 4.5 | OK |
| dark | texto terciario sobre superficie suave (--color-text-faint / --color-bg-soft) | 5.65 | 4.5 | OK |
| light | texto principal sobre el fondo (--color-text / --color-bg) | 14.64 | 4.5 | OK |
| light | texto principal sobre tarjeta (--color-text / --color-surface) | 15.56 | 4.5 | OK |
| light | texto secundario sobre el fondo (--color-text-dim / --color-bg) | 5.48 | 4.5 | OK |
| light | texto secundario sobre tarjeta (--color-text-dim / --color-surface) | 5.82 | 4.5 | OK |
| light | texto secundario sobre superficie suave (--color-text-dim / --color-bg-soft) | 5.14 | 4.5 | OK |
| light | texto terciario sobre el fondo (--color-text-faint / --color-bg) | 4.85 | 4.5 | OK |
| light | texto terciario sobre tarjeta (--color-text-faint / --color-surface) | 5.16 | 4.5 | OK |
| light | texto terciario sobre superficie suave (--color-text-faint / --color-bg-soft) | 4.55 | 4.5 | OK |

## Texto de acento derivado del acento elegido (bloqueante)

`--color-accent-soft` se mezcla desde el acento del usuario (`--accent-soft-share` hacia blanco en oscuro y hacia negro en claro). Se mide sobre las superficies y sobre los fondos compuestos donde vive ese texto.

| Tema | Acento | Fondo | Razón | Mínimo | Estado |
| --- | --- | --- | ---: | ---: | --- |
| dark | indigo | --color-bg | 7.7 | 4.5 | OK |
| dark | indigo | --color-surface | 6.66 | 4.5 | OK |
| dark | indigo | --color-bg-soft | 7.03 | 4.5 | OK |
| dark | indigo | anillo de acento sobre --color-bg | 5.61 | 4.5 | OK |
| dark | indigo | tinte de acento al 15 % sobre --color-bg | 6.64 | 4.5 | OK |
| dark | indigo | anillo de acento sobre --color-surface | 4.8 | 4.5 | OK |
| dark | indigo | tinte de acento al 15 % sobre --color-surface | 5.64 | 4.5 | OK |
| dark | indigo | anillo de acento sobre --color-bg-soft | 5.06 | 4.5 | OK |
| dark | indigo | tinte de acento al 15 % sobre --color-bg-soft | 5.99 | 4.5 | OK |
| dark | violet | --color-bg | 7.71 | 4.5 | OK |
| dark | violet | --color-surface | 6.68 | 4.5 | OK |
| dark | violet | --color-bg-soft | 7.04 | 4.5 | OK |
| dark | violet | anillo de acento sobre --color-bg | 5.75 | 4.5 | OK |
| dark | violet | tinte de acento al 15 % sobre --color-bg | 6.63 | 4.5 | OK |
| dark | violet | anillo de acento sobre --color-surface | 4.93 | 4.5 | OK |
| dark | violet | tinte de acento al 15 % sobre --color-surface | 5.64 | 4.5 | OK |
| dark | violet | anillo de acento sobre --color-bg-soft | 5.15 | 4.5 | OK |
| dark | violet | tinte de acento al 15 % sobre --color-bg-soft | 5.94 | 4.5 | OK |
| dark | blue | --color-bg | 8.41 | 4.5 | OK |
| dark | blue | --color-surface | 7.28 | 4.5 | OK |
| dark | blue | --color-bg-soft | 7.68 | 4.5 | OK |
| dark | blue | anillo de acento sobre --color-bg | 6.12 | 4.5 | OK |
| dark | blue | tinte de acento al 15 % sobre --color-bg | 7.09 | 4.5 | OK |
| dark | blue | anillo de acento sobre --color-surface | 5.17 | 4.5 | OK |
| dark | blue | tinte de acento al 15 % sobre --color-surface | 5.99 | 4.5 | OK |
| dark | blue | anillo de acento sobre --color-bg-soft | 5.46 | 4.5 | OK |
| dark | blue | tinte de acento al 15 % sobre --color-bg-soft | 6.38 | 4.5 | OK |
| dark | teal | --color-bg | 11.21 | 4.5 | OK |
| dark | teal | --color-surface | 9.7 | 4.5 | OK |
| dark | teal | --color-bg-soft | 10.23 | 4.5 | OK |
| dark | teal | anillo de acento sobre --color-bg | 7.28 | 4.5 | OK |
| dark | teal | tinte de acento al 15 % sobre --color-bg | 8.97 | 4.5 | OK |
| dark | teal | anillo de acento sobre --color-surface | 6.19 | 4.5 | OK |
| dark | teal | tinte de acento al 15 % sobre --color-surface | 7.53 | 4.5 | OK |
| dark | teal | anillo de acento sobre --color-bg-soft | 6.55 | 4.5 | OK |
| dark | teal | tinte de acento al 15 % sobre --color-bg-soft | 7.95 | 4.5 | OK |
| dark | emerald | --color-bg | 11.1 | 4.5 | OK |
| dark | emerald | --color-surface | 9.61 | 4.5 | OK |
| dark | emerald | --color-bg-soft | 10.13 | 4.5 | OK |
| dark | emerald | anillo de acento sobre --color-bg | 7.29 | 4.5 | OK |
| dark | emerald | tinte de acento al 15 % sobre --color-bg | 8.95 | 4.5 | OK |
| dark | emerald | anillo de acento sobre --color-surface | 6.21 | 4.5 | OK |
| dark | emerald | tinte de acento al 15 % sobre --color-surface | 7.52 | 4.5 | OK |
| dark | emerald | anillo de acento sobre --color-bg-soft | 6.5 | 4.5 | OK |
| dark | emerald | tinte de acento al 15 % sobre --color-bg-soft | 7.95 | 4.5 | OK |
| dark | rose | --color-bg | 7.88 | 4.5 | OK |
| dark | rose | --color-surface | 6.82 | 4.5 | OK |
| dark | rose | --color-bg-soft | 7.19 | 4.5 | OK |
| dark | rose | anillo de acento sobre --color-bg | 5.9 | 4.5 | OK |
| dark | rose | tinte de acento al 15 % sobre --color-bg | 6.82 | 4.5 | OK |
| dark | rose | anillo de acento sobre --color-surface | 5.12 | 4.5 | OK |
| dark | rose | tinte de acento al 15 % sobre --color-surface | 5.85 | 4.5 | OK |
| dark | rose | anillo de acento sobre --color-bg-soft | 5.38 | 4.5 | OK |
| dark | rose | tinte de acento al 15 % sobre --color-bg-soft | 6.22 | 4.5 | OK |
| dark | amber | --color-bg | 12.71 | 4.5 | OK |
| dark | amber | --color-surface | 11 | 4.5 | OK |
| dark | amber | --color-bg-soft | 11.6 | 4.5 | OK |
| dark | amber | anillo de acento sobre --color-bg | 7.4 | 4.5 | OK |
| dark | amber | tinte de acento al 15 % sobre --color-bg | 9.95 | 4.5 | OK |
| dark | amber | anillo de acento sobre --color-surface | 6.33 | 4.5 | OK |
| dark | amber | tinte de acento al 15 % sobre --color-surface | 8.37 | 4.5 | OK |
| dark | amber | anillo de acento sobre --color-bg-soft | 6.63 | 4.5 | OK |
| dark | amber | tinte de acento al 15 % sobre --color-bg-soft | 8.87 | 4.5 | OK |
| light | indigo | --color-bg | 10.2 | 4.5 | OK |
| light | indigo | --color-surface | 10.84 | 4.5 | OK |
| light | indigo | --color-bg-soft | 9.57 | 4.5 | OK |
| light | indigo | anillo de acento sobre --color-bg | 7.8 | 4.5 | OK |
| light | indigo | tinte de acento al 15 % sobre --color-bg | 8.15 | 4.5 | OK |
| light | indigo | anillo de acento sobre --color-surface | 8.24 | 4.5 | OK |
| light | indigo | tinte de acento al 15 % sobre --color-surface | 8.63 | 4.5 | OK |
| light | indigo | anillo de acento sobre --color-bg-soft | 7.34 | 4.5 | OK |
| light | indigo | tinte de acento al 15 % sobre --color-bg-soft | 7.68 | 4.5 | OK |
| light | violet | --color-bg | 6.98 | 4.5 | OK |
| light | violet | --color-surface | 7.42 | 4.5 | OK |
| light | violet | --color-bg-soft | 6.55 | 4.5 | OK |
| light | violet | anillo de acento sobre --color-bg | 5.14 | 4.5 | OK |
| light | violet | tinte de acento al 15 % sobre --color-bg | 5.86 | 4.5 | OK |
| light | violet | anillo de acento sobre --color-surface | 5.44 | 4.5 | OK |
| light | violet | tinte de acento al 15 % sobre --color-surface | 6.19 | 4.5 | OK |
| light | violet | anillo de acento sobre --color-bg-soft | 4.89 | 4.5 | OK |
| light | violet | tinte de acento al 15 % sobre --color-bg-soft | 5.52 | 4.5 | OK |
| light | blue | --color-bg | 6.84 | 4.5 | OK |
| light | blue | --color-surface | 7.27 | 4.5 | OK |
| light | blue | --color-bg-soft | 6.42 | 4.5 | OK |
| light | blue | anillo de acento sobre --color-bg | 5.18 | 4.5 | OK |
| light | blue | tinte de acento al 15 % sobre --color-bg | 5.78 | 4.5 | OK |
| light | blue | anillo de acento sobre --color-surface | 5.44 | 4.5 | OK |
| light | blue | tinte de acento al 15 % sobre --color-surface | 6.11 | 4.5 | OK |
| light | blue | anillo de acento sobre --color-bg-soft | 4.88 | 4.5 | OK |
| light | blue | tinte de acento al 15 % sobre --color-bg-soft | 5.45 | 4.5 | OK |
| light | teal | --color-bg | 6.35 | 4.5 | OK |
| light | teal | --color-surface | 6.75 | 4.5 | OK |
| light | teal | --color-bg-soft | 5.96 | 4.5 | OK |
| light | teal | anillo de acento sobre --color-bg | 5.1 | 4.5 | OK |
| light | teal | tinte de acento al 15 % sobre --color-bg | 5.55 | 4.5 | OK |
| light | teal | anillo de acento sobre --color-surface | 5.35 | 4.5 | OK |
| light | teal | tinte de acento al 15 % sobre --color-surface | 5.87 | 4.5 | OK |
| light | teal | anillo de acento sobre --color-bg-soft | 4.86 | 4.5 | OK |
| light | teal | tinte de acento al 15 % sobre --color-bg-soft | 5.24 | 4.5 | OK |
| light | emerald | --color-bg | 6.41 | 4.5 | OK |
| light | emerald | --color-surface | 6.81 | 4.5 | OK |
| light | emerald | --color-bg-soft | 6.01 | 4.5 | OK |
| light | emerald | anillo de acento sobre --color-bg | 5.1 | 4.5 | OK |
| light | emerald | tinte de acento al 15 % sobre --color-bg | 5.61 | 4.5 | OK |
| light | emerald | anillo de acento sobre --color-surface | 5.39 | 4.5 | OK |
| light | emerald | tinte de acento al 15 % sobre --color-surface | 5.93 | 4.5 | OK |
| light | emerald | anillo de acento sobre --color-bg-soft | 4.86 | 4.5 | OK |
| light | emerald | tinte de acento al 15 % sobre --color-bg-soft | 5.31 | 4.5 | OK |
| light | rose | --color-bg | 7.1 | 4.5 | OK |
| light | rose | --color-surface | 7.55 | 4.5 | OK |
| light | rose | --color-bg-soft | 6.66 | 4.5 | OK |
| light | rose | anillo de acento sobre --color-bg | 5.14 | 4.5 | OK |
| light | rose | tinte de acento al 15 % sobre --color-bg | 5.86 | 4.5 | OK |
| light | rose | anillo de acento sobre --color-surface | 5.41 | 4.5 | OK |
| light | rose | tinte de acento al 15 % sobre --color-surface | 6.19 | 4.5 | OK |
| light | rose | anillo de acento sobre --color-bg-soft | 4.89 | 4.5 | OK |
| light | rose | tinte de acento al 15 % sobre --color-bg-soft | 5.51 | 4.5 | OK |
| light | amber | --color-bg | 6.35 | 4.5 | OK |
| light | amber | --color-surface | 6.75 | 4.5 | OK |
| light | amber | --color-bg-soft | 5.96 | 4.5 | OK |
| light | amber | anillo de acento sobre --color-bg | 5.19 | 4.5 | OK |
| light | amber | tinte de acento al 15 % sobre --color-bg | 5.69 | 4.5 | OK |
| light | amber | anillo de acento sobre --color-surface | 5.45 | 4.5 | OK |
| light | amber | tinte de acento al 15 % sobre --color-surface | 6.01 | 4.5 | OK |
| light | amber | anillo de acento sobre --color-bg-soft | 4.94 | 4.5 | OK |
| light | amber | tinte de acento al 15 % sobre --color-bg-soft | 5.4 | 4.5 | OK |

## Rampa de niveles por esquema y tema (bloqueante)

Cada paso (Pre-A1 → C2, más el cajón «sin dato») declara su tinta y el relleno se DERIVA de ella al 15 %; se mide la tinta sobre ese relleno compuesto sobre las dos superficies donde viven insignias, bandas y chips. «Monocromo» sale del acento del usuario, así que se mide en los 7. El relleno es translúcido: sobre otro fondo (p. ej. `--color-surface-2`, más cercano a la tinta) el margen se estrecha, y por eso las tintas de la rampa se eligen con holgura y no al filo del 4.5:1.

| Esquema | Tema | Acento | Fondo | Pre-A1 | A1 | A2 | B1 | B2 | C1 | C2 | s/d |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Semáforo | Oscuro | — | --color-bg | 6.16 | 6.9 | 8.42 | 7.24 | 5.61 | 7.51 | 6.55 | 6.02 |
| Semáforo | Oscuro | — | --color-surface | 5.25 | 5.8 | 7.03 | 6.04 | 4.71 | 6.27 | 5.5 | 5.04 |
| Semáforo | Claro | — | --color-bg | 5.42 | 5.28 | 5.15 | 5.82 | 5.24 | 5.67 | 5.34 | 5.7 |
| Semáforo | Claro | — | --color-surface | 5.74 | 5.59 | 5.46 | 6.16 | 5.54 | 5.99 | 5.66 | 6.04 |
| Espectro | Oscuro | — | --color-bg | 7.92 | 7.73 | 8.1 | 9.04 | 6.61 | 5.76 | 5.61 | 6.02 |
| Espectro | Oscuro | — | --color-surface | 6.59 | 6.44 | 6.75 | 7.51 | 5.56 | 4.91 | 4.71 | 5.04 |
| Espectro | Claro | — | --color-bg | 5.45 | 5.67 | 5.34 | 5.15 | 5.42 | 5.7 | 5.24 | 5.7 |
| Espectro | Claro | — | --color-surface | 5.77 | 5.99 | 5.66 | 5.46 | 5.74 | 6.03 | 5.54 | 6.04 |
| Monocromo | Oscuro | indigo | --color-bg | 5.98 | 5.97 | 5.98 | 6.04 | 6.05 | 6.07 | 6.08 | 6.01 |
| Monocromo | Oscuro | indigo | --color-surface | 5.01 | 5 | 5.05 | 5.06 | 5.07 | 5.08 | 5.09 | 5.04 |
| Monocromo | Oscuro | violet | --color-bg | 6.01 | 5.97 | 5.94 | 5.99 | 6.01 | 6.04 | 6.1 | 5.93 |
| Monocromo | Oscuro | violet | --color-surface | 5.02 | 5 | 5.03 | 5.02 | 5.08 | 5.06 | 5.15 | 5.02 |
| Monocromo | Oscuro | blue | --color-bg | 6.08 | 6.13 | 6.2 | 6.27 | 6.35 | 6.49 | 6.52 | 6.08 |
| Monocromo | Oscuro | blue | --color-surface | 5.14 | 5.19 | 5.18 | 5.24 | 5.31 | 5.43 | 5.5 | 5.08 |
| Monocromo | Oscuro | teal | --color-bg | 6.39 | 6.62 | 6.93 | 7.21 | 7.54 | 7.89 | 8.26 | 6.35 |
| Monocromo | Oscuro | teal | --color-surface | 5.4 | 5.58 | 5.84 | 6.06 | 6.34 | 6.63 | 6.92 | 5.31 |
| Monocromo | Oscuro | emerald | --color-bg | 6.35 | 6.59 | 6.88 | 7.2 | 7.52 | 7.86 | 8.21 | 6.33 |
| Monocromo | Oscuro | emerald | --color-surface | 5.37 | 5.55 | 5.8 | 6.07 | 6.25 | 6.54 | 6.83 | 5.3 |
| Monocromo | Oscuro | rose | --color-bg | 5.94 | 5.87 | 5.94 | 6.02 | 6.02 | 6.16 | 6.28 | 5.98 |
| Monocromo | Oscuro | rose | --color-surface | 4.98 | 4.98 | 4.97 | 5.05 | 5.11 | 5.18 | 5.29 | 5.01 |
| Monocromo | Oscuro | amber | --color-bg | 6.57 | 6.92 | 7.29 | 7.69 | 8.15 | 8.69 | 9.2 | 6.41 |
| Monocromo | Oscuro | amber | --color-surface | 5.49 | 5.77 | 6.06 | 6.45 | 6.84 | 7.21 | 7.62 | 5.36 |
| Monocromo | Claro | indigo | --color-bg | 5.05 | 5.44 | 5.94 | 6.36 | 6.87 | 7.38 | 7.85 | 4.97 |
| Monocromo | Claro | indigo | --color-surface | 5.35 | 5.75 | 6.29 | 6.74 | 7.28 | 7.81 | 8.3 | 5.25 |
| Monocromo | Claro | violet | --color-bg | 4.78 | 4.94 | 5.1 | 5.23 | 5.34 | 5.46 | 5.52 | 4.72 |
| Monocromo | Claro | violet | --color-surface | 5.06 | 5.21 | 5.4 | 5.54 | 5.66 | 5.78 | 5.85 | 5 |
| Monocromo | Claro | blue | --color-bg | 4.7 | 4.81 | 4.99 | 5.12 | 5.2 | 5.38 | 5.47 | 4.68 |
| Monocromo | Claro | blue | --color-surface | 4.97 | 5.09 | 5.28 | 5.42 | 5.5 | 5.69 | 5.78 | 4.96 |
| Monocromo | Claro | teal | --color-bg | 4.68 | 4.79 | 4.88 | 4.91 | 4.98 | 5.03 | 5.07 | 4.64 |
| Monocromo | Claro | teal | --color-surface | 4.95 | 5.06 | 5.17 | 5.19 | 5.27 | 5.32 | 5.36 | 4.9 |
| Monocromo | Claro | emerald | --color-bg | 4.71 | 4.77 | 4.88 | 4.97 | 5.06 | 5.05 | 5.09 | 4.65 |
| Monocromo | Claro | emerald | --color-surface | 4.98 | 5.04 | 5.16 | 5.27 | 5.36 | 5.35 | 5.39 | 4.92 |
| Monocromo | Claro | rose | --color-bg | 4.91 | 5.19 | 5.4 | 5.57 | 5.63 | 5.62 | 5.55 | 4.83 |
| Monocromo | Claro | rose | --color-surface | 5.2 | 5.48 | 5.72 | 5.9 | 5.95 | 5.95 | 5.88 | 5.11 |
| Monocromo | Claro | amber | --color-bg | 4.69 | 4.77 | 4.9 | 5 | 5.02 | 5.08 | 5.09 | 4.65 |
| Monocromo | Claro | amber | --color-surface | 4.95 | 5.05 | 5.19 | 5.29 | 5.31 | 5.38 | 5.39 | 4.92 |

## Dirección de la consulta del diccionario (bloqueante)

El sentido de la consulta se ve por su color —azul EN→ES, fucsia ES→EN— y ese color se mide igual que la rampa: cada dirección declara su tinta y el relleno se DERIVA de ella al 15 %. La pareja no sigue al acento del usuario (es una convención del diccionario, no del perfil), así que se mide con un solo acento y en los dos temas.

| Tema | Dirección | Fondo | Razón | Mínimo | Estado |
| --- | --- | --- | ---: | ---: | --- |
| dark | EN→ES | --color-bg | 7.83 | 4.5 | OK |
| dark | EN→ES | --color-surface | 6.51 | 4.5 | OK |
| dark | ES→EN | --color-bg | 8.02 | 4.5 | OK |
| dark | ES→EN | --color-surface | 6.69 | 4.5 | OK |
| light | EN→ES | --color-bg | 6.37 | 4.5 | OK |
| light | EN→ES | --color-surface | 6.75 | 4.5 | OK |
| light | ES→EN | --color-bg | 5.99 | 4.5 | OK |
| light | ES→EN | --color-surface | 6.35 | 4.5 | OK |

## Guardas

| Guarda | Estado | Detalle |
| --- | --- | --- |
| acento-solido-no-es-texto | OK | ningún `color: var(--color-accent)` (el texto de acento usa --color-accent-soft) |
| accent-soft-derivado | OK | --color-accent-soft se deriva del acento con color-mix() |
| rampa-niveles-completa | OK | los 7 pasos (+ sin dato) declaran su tinta en los 3 esquemas y los 2 temas |
| rampa-clases-y-derivados | OK | cada paso tiene relleno y borde derivados y su clase .lv-*, más los modificadores .lv-outline/.lv-ink/.lv-quiet |
| direccion-completa | OK | las dos direcciones (EN→ES, ES→EN) declaran su tinta en los 2 temas |
| direccion-clases-y-derivados | OK | cada dirección tiene relleno (15 %) y borde derivados, su clase .dir-*, los modificadores .dir-chip/.dir-ink/.dir-line/.dir-wash/.dir-bar y el marco .dir-field |

## Acento como relleno y como borde (reportado; decisión para V4.0.x)

Con la mejor tinta posible, el máximo alcanzable sobre el relleno se queda por debajo de AA: cumplirlo exige re-rampar los acentos (relleno más oscuro en tema claro). La última columna da el techo real de la rampa actual.

| Tema | Acento | Par | Razón | Mínimo | Mejor tinta | Máx. alcanzable | Estado |
| --- | --- | --- | ---: | ---: | --- | ---: | --- |
| dark | indigo | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 4.47 | 4.5 | #0b1220 | 4.19 | FALLA |
| dark | indigo | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 3.37 | 4.5 | #0b1220 | 4.19 | FALLA |
| dark | indigo | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 3.67 | 3 | #0b1220 | 4.19 | OK |
| dark | violet | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 3.96 | 4.5 | #ffffff | 3.96 | FALLA |
| dark | violet | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 5.38 | 4.5 | #ffffff | 3.96 | OK |
| dark | violet | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 4.14 | 3 | #ffffff | 3.96 | OK |
| dark | blue | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 3.68 | 4.5 | #ffffff | 3.68 | FALLA |
| dark | blue | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 6.7 | 4.5 | #ffffff | 3.68 | OK |
| dark | blue | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 4.45 | 3 | #ffffff | 3.68 | OK |
| dark | teal | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 2.49 | 4.5 | #0b1220 | 3.42 | FALLA |
| dark | teal | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 5.47 | 4.5 | #0b1220 | 3.42 | OK |
| dark | teal | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 6.58 | 3 | #0b1220 | 3.42 | OK |
| dark | emerald | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 2.54 | 4.5 | #0b1220 | 3.41 | FALLA |
| dark | emerald | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 5.48 | 4.5 | #0b1220 | 3.41 | OK |
| dark | emerald | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 6.45 | 3 | #0b1220 | 3.41 | OK |
| dark | rose | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 3.67 | 4.5 | #ffffff | 3.67 | FALLA |
| dark | rose | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 6.29 | 4.5 | #ffffff | 3.67 | OK |
| dark | rose | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 4.46 | 3 | #ffffff | 3.67 | OK |
| dark | amber | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 6.83 | 4.5 | #0b1220 | 3.73 | OK |
| dark | amber | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 2.92 | 4.5 | #0b1220 | 3.73 | FALLA |
| dark | amber | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 7.62 | 3 | #0b1220 | 3.73 | OK |
| light | indigo | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 6.29 | 4.5 | #ffffff | 6.29 | OK |
| light | indigo | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 7.9 | 4.5 | #ffffff | 6.29 | OK |
| light | indigo | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 6.29 | 3 | #ffffff | 6.29 | OK |
| light | violet | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 3.96 | 4.5 | #ffffff | 3.96 | FALLA |
| light | violet | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 5.38 | 4.5 | #ffffff | 3.96 | OK |
| light | violet | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 3.96 | 3 | #ffffff | 3.96 | OK |
| light | blue | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 3.68 | 4.5 | #ffffff | 3.68 | FALLA |
| light | blue | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 6.7 | 4.5 | #ffffff | 3.68 | OK |
| light | blue | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 3.68 | 3 | #ffffff | 3.68 | OK |
| light | teal | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 2.49 | 4.5 | #0b1220 | 3.42 | FALLA |
| light | teal | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 5.47 | 4.5 | #0b1220 | 3.42 | OK |
| light | teal | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 2.49 | 3 | #0b1220 | 3.42 | FALLA |
| light | emerald | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 2.54 | 4.5 | #0b1220 | 3.41 | FALLA |
| light | emerald | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 5.48 | 4.5 | #0b1220 | 3.41 | OK |
| light | emerald | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 2.54 | 3 | #0b1220 | 3.41 | FALLA |
| light | rose | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 3.67 | 4.5 | #ffffff | 3.67 | FALLA |
| light | rose | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 6.29 | 4.5 | #ffffff | 3.67 | OK |
| light | rose | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 3.67 | 3 | #ffffff | 3.67 | OK |
| light | amber | relleno + tinta (botones, píldora activa) (--color-on-accent / --color-accent) | 6.83 | 4.5 | #0b1220 | 3.73 | OK |
| light | amber | relleno en hover + tinta (--color-on-accent / --color-accent-hover) | 2.92 | 4.5 | #0b1220 | 3.73 | FALLA |
| light | amber | acento como BORDE/UI sobre tarjeta (--color-accent / --color-surface) | 2.15 | 3 | #0b1220 | 3.73 | FALLA |
