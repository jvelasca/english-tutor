# Abre el puerto de English Tutor (8000: API + interfaz) en el firewall de
# Windows para que la app sea accesible desde cualquier dispositivo de la red
# local (cableada y WiFi).
#
# V3.72 (RC-01): hasta V3.71 había dos puertos (5173 el dev server de Vite, 8000
# la API). Ahora el backend sirve también la interfaz compilada, así que el
# producto vive en un único origen HTTPS (:8000).
#
# Requiere ejecutarse como administrador:
#   powershell -ExecutionPolicy Bypass -File launcher\allow-firewall.ps1
#
# Las reglas se crean en los perfiles "Privada" y "Pública" (la WiFi suele
# estar marcada como Pública, que es lo que bloquea las conexiones entrantes).

$ErrorActionPreference = "Stop"

$ports = @(8000)
$prefix = "English Tutor"

foreach ($port in $ports) {
    $name = "$prefix ($port)"

    if (Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue) {
        Write-Host "La regla '$name' ya existe. Se omite." -ForegroundColor Yellow
        continue
    }

    New-NetFirewallRule `
        -DisplayName $name `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $port `
        -Profile Private, Public `
        -Description "Acceso en red local a English Tutor (puerto $port)." |
        Out-Null

    Write-Host "Regla '$name' creada (TCP $port, perfiles Privada y Publica)." -ForegroundColor Green
}

Write-Host ""
Write-Host "Listo. Abre la app y accede desde tus dispositivos usando la URL LAN" `
    -ForegroundColor Cyan
Write-Host "que muestra la barra de estado inferior (o el launcher)." -ForegroundColor Cyan
