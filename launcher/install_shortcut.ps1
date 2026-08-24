# Crea un acceso directo del escritorio para el launcher (genera el icono si falta).
# Uso:  powershell -ExecutionPolicy Bypass -File install_shortcut.ps1
$ErrorActionPreference = "Stop"

$launcherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $launcherDir
$pythonw = Join-Path $repoRoot "backend\.venv\Scripts\pythonw.exe"
$script = Join-Path $launcherDir "launcher.py"
$iconPath = Join-Path $launcherDir "icon.ico"

if (-not (Test-Path $iconPath)) {
    & (Join-Path $launcherDir "make_icon.ps1")
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "English Tutor.lnk"
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($shortcutPath)
$sc.TargetPath = $pythonw
$sc.Arguments = "`"$script`""
$sc.WorkingDirectory = $launcherDir
$sc.IconLocation = "$iconPath,0"
$sc.Description = "Arranca/detiene English Tutor y muestra su estado"
$sc.Save()

Write-Host "Acceso directo creado: $shortcutPath"
