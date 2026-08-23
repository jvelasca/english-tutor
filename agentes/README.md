# Cómo lanzar los subagentes (sin gastar tokens)

El gerente del proyecto (el asistente) **no ejecuta** estos subagentes. Tú los
lanzas desde tus propios agentes locales. Cada subagente es un archivo Markdown
**autocontenido**: incluye todo lo que el agente necesita para trabajar sin
pedir más contexto.

## Cómo usar un subagente

1. Abre el archivo `agentes/<nombre>.md`.
2. Copia su contenido completo y pégalo como prompt en tu agente local
   (o ábrelo como archivo de contexto/tarea en tu agente).
3. El agente local trabaja y devuelve el resultado.
4. Pega el resultado de vuelta aquí; el gerente revisa e integra o genera el siguiente paso.

## Orden de lanzamiento (ver `PLAN.md`)

1. `m0-esqueleto-modular.md` — primero (establece la estructura modular).
2. `m1-backend-streaming.md` + `m2-backend-voz.md` — en paralelo (definen la API).
3. `m1-frontend-streaming.md` + `m2-frontend-voz.md` — con la API ya clara.

> Antes de lanzar cualquier subagente, el gerente se apoya en `docs/ARQUITECTURA.md`
> y `docs/PREMISAS.md`. Cada subagente indica si debe leerlos.

## Plantilla estándar de un subagente

Cada archivo contendrá las siguientes secciones:

- **Rol:** qué papel juega (backend, frontend, voz, testing…).
- **Objetivo:** qué debe conseguir exactamente.
- **Contexto:** stack, rutas de archivos, dependencias, cómo arrancar.
- **Tarea detallada:** pasos concretos.
- **Criterios de aceptación:** cómo saber que está bien hecho.
- **Restricciones:** qué NO debe hacer (no salir del scope, no tocar otros archivos, mantener tipado fuerte, 100% local…).
- **Salida esperada:** qué debe devolver (diff, archivos, explicación).
