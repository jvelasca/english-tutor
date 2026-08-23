# Verificación del frontend: tipos + tests.
$ErrorActionPreference = "Stop"

Write-Host "== TypeScript (tsc --noEmit) =="
npx tsc --noEmit
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== Tests (vitest) =="
npm test
