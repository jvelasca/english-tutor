# Abre el puerto de English Tutor (8000: API + interfaz) en el firewall de
# Windows para que la app sea accesible desde cualquier dispositivo de la red
# local (cableada y WiFi).
#
# V3.72 (RC-01): hasta V3.71 había dos puertos (5173 el dev server de Vite, 8000
# la API). Ahora el backend sirve también la interfaz compilada, así que el
# producto vive en un único origen HTTPS (:8000).
#
# V3.73.x: la app escucha SOLO en loopback salvo que el modo LAN esté declarado
# (`ENGLISH_TUTOR_LAN=1`). Esta regla de firewall, por sí sola, no da acceso a
# nadie: sin el modo activo el puerto no está escuchando en la interfaz de red.
# Los dos pasos van juntos (ver README → "Usar la app desde otro dispositivo").
#
# Requiere ejecutarse como administrador:
#   powershell -ExecutionPolicy Bypass -File launcher\allow-firewall.ps1
#
# Las reglas se crean en los perfiles "Privada" y "Pública" (la WiFi suele
# estar marcada como Pública, que es lo que bloquea las conexiones entrantes).

$ErrorActionPreference = "Stop"

$ports = @(8000)
$prefix = "English Tutor"
$lanEnv = "ENGLISH_TUTOR_LAN"

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
if ($env:ENGLISH_TUTOR_LAN -eq "1") {
    Write-Host "Listo. Abre la app y accede desde tus dispositivos usando la URL LAN" `
        -ForegroundColor Cyan
    Write-Host "que muestra la barra de estado inferior (o el launcher)." -ForegroundColor Cyan
} else {
    Write-Host "Regla creada, pero la app todavia NO escucha en la red local." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "El modo LAN es opt-in. Para activarlo, abre el launcher y pulsa" -ForegroundColor Yellow
    Write-Host "'Activar red local' en el panel 'Acceso a la app' (reinicia el servidor)." -ForegroundColor White
    Write-Host ""
    Write-Host "Alternativa sin launcher: arranca con la variable puesta" -ForegroundColor DarkGray
    Write-Host "    `$env:$lanEnv = `"1`"" -ForegroundColor White
    Write-Host "(vale tambien dejarlo fijo con: setx $lanEnv 1)" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "Sin ese paso, la app solo responde en este equipo (loopback) y las" -ForegroundColor DarkGray
    Write-Host "conexiones entrantes no encontraran nada escuchando en el puerto." -ForegroundColor DarkGray
}
