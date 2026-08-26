# Abre los puertos de English Tutor (5173 frontend, 8000 backend) en el
# firewall de Windows para que la app sea accesible desde cualquier dispositivo
# de la red local (cableada y WiFi).
#
# Requiere ejecutarse como administrador:
#   powershell -ExecutionPolicy Bypass -File launcher\allow-firewall.ps1
#
# Las reglas se crean en los perfiles "Privada" y "Pública" (la WiFi suele
# estar marcada como Pública, que es lo que bloquea las conexiones entrantes).

$ErrorActionPreference = "Stop"

$ports = @(5173, 8000)
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
