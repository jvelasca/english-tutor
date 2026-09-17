# Informe de contraste WCAG (cierre GUI pre-V4.0, V3.73.1)

> Generado por `node frontend/scripts/contrast_audit.mjs`.

- Pares que BLOQUEAN (tipografía base + texto de acento + guardas): **0 fallos** de 144.
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

## Guardas

| Guarda | Estado | Detalle |
| --- | --- | --- |
| acento-solido-no-es-texto | OK | ningún `color: var(--color-accent)` (el texto de acento usa --color-accent-soft) |
| accent-soft-derivado | OK | --color-accent-soft se deriva del acento con color-mix() |

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
