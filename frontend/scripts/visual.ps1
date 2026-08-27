# Test visual (Playwright): captura screenshots de las rutas principales en 3
# breakpoints (desktop/tablet/móvil) para revisión manual de responsive y layout.
#
# Requisitos previos:
#   - Backend FastAPI corriendo en http://127.0.0.1:8000 (opcional: la app
#     se renderiza igual con estados vacíos si no está).
#   - Frontend Vite (npm run dev). Playwright lo arranca o reutiliza uno ya activo.
#
# Salida: tests/visual/screenshots/<desktop|tablet|mobile>/<ruta>.png
$ErrorActionPreference = "Stop"

Write-Host "== Tests visuales (Playwright) =="
npm run test:visual
exit $LASTEXITCODE
