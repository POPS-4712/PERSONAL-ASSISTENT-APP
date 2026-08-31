<#
.SYNOPSIS
  Instala / arranca Docker Desktop. La instalación REQUIERE ADMINISTRADOR.

.DESCRIPTION
  Idempotente y conservador:
    - Si Docker Desktop ya está: NO reinstala. Comprueba versión, lo arranca si
      hace falta y verifica `docker info` + `docker compose version`.
    - Si no está: lo instala. Preferencia por winget (si existe); si no,
      descarga el instalador oficial "Docker Desktop Installer.exe" y lo
      ejecuta en modo silencioso.
  NUNCA toca contenedores ni imágenes existentes del usuario.

.PARAMETER InstallerUrl
  URL del instalador oficial (fallback sin winget). El arch se resuelve solo.
#>
[CmdletBinding()]
param(
  [string]$InstallerUrl
)

. (Join-Path $PSScriptRoot 'common.ps1')

Write-ApStep 'Docker Desktop'

$info = Get-DockerInfo
if ($info.found) {
  Write-ApOk "Docker Desktop ya instalado ($($info.path))"
  if (-not $info.running) {
    Write-ApLog '   Arrancando Docker Desktop...'
    if (-not (Start-DockerDesktop)) {
      Write-ApLog -Level ERROR -Message 'BLOCKED BY: Docker Desktop está instalado pero el motor no arrancó. Ábrelo manualmente y reintenta.'
      exit 2
    }
    $info = Get-DockerInfo
  }
  if (-not $info.composeVersion) {
    Write-ApLog -Level ERROR -Message 'BLOCKED BY: falta Docker Compose v2 (`docker compose`). Actualiza Docker Desktop.'
    exit 2
  }
  Write-ApOk "Motor $($info.serverVersion) · Compose $($info.composeVersion) · reutilizado (contenedores intactos)"
  exit 0
}

# --- No está: instalar --------------------------------------------------
if (-not (Test-IsAdmin)) {
  Write-ApLog -Level ERROR -Message 'La instalación de Docker Desktop necesita permisos de administrador.'
  exit 2
}

$plat = Get-ApPlatform
if (-not $plat.online) {
  Write-ApLog -Level ERROR -Message 'BLOCKED BY: sin conexión a Internet para descargar Docker Desktop.'
  exit 2
}

$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) {
  Write-ApLog '   Instalando Docker Desktop con winget...'
  $p = Start-Process -FilePath 'winget' -Wait -PassThru -ArgumentList @(
    'install','--id','Docker.DockerDesktop','--exact','--silent',
    '--accept-package-agreements','--accept-source-agreements')
  if ($p.ExitCode -ne 0 -and $p.ExitCode -ne -1978335189) {
    Write-ApWarn "winget devolvió $($p.ExitCode); probando con el instalador oficial."
    $winget = $null
  }
}

if (-not $winget) {
  if (-not $InstallerUrl) {
    $InstallerUrl = if ($plat.arch -eq 'arm64') {
      'https://desktop.docker.com/win/main/arm64/Docker%20Desktop%20Installer.exe'
    } else {
      'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe'
    }
  }
  $dst = Join-Path $env:TEMP 'DockerDesktopInstaller.exe'
  Write-ApLog "   Descargando Docker Desktop ($($plat.arch))..."
  try {
    Invoke-WebRequest -Uri $InstallerUrl -OutFile $dst -UseBasicParsing
  } catch {
    Write-ApLog -Level ERROR -Message "BLOCKED BY: no se pudo descargar Docker Desktop desde $InstallerUrl"
    exit 2
  }
  Write-ApLog '   Ejecutando el instalador (silencioso)...'
  $p = Start-Process -FilePath $dst -Wait -PassThru -ArgumentList @('install','--quiet','--accept-license')
  Remove-Item $dst -Force -ErrorAction SilentlyContinue
  if ($p.ExitCode -ne 0) {
    Write-ApLog -Level ERROR -Message "BLOCKED BY: el instalador de Docker Desktop devolvió $($p.ExitCode)."
    exit 2
  }
}

Write-ApOk 'Docker Desktop instalado. Arrancando el motor...'
# Tras instalar, el usuario puede necesitar cerrar/abrir sesión para el grupo
# 'docker-users'. Intentamos arrancar de todos modos.
if (-not (Start-DockerDesktop)) {
  Write-ApWarn 'Docker Desktop instalado pero el motor no respondió aún.'
  Write-ApWarn 'BLOCKED BY: cierra sesión y vuelve a entrar (para aplicar el grupo docker-users), abre Docker Desktop y reinicia el instalador.'
  exit 11
}

$info = Get-DockerInfo
if (-not $info.running -or -not $info.composeVersion) {
  Write-ApLog -Level ERROR -Message 'BLOCKED BY: Docker no quedó operativo tras la instalación. Abre Docker Desktop manualmente y reintenta.'
  exit 2
}
Write-ApOk "Motor $($info.serverVersion) · Compose $($info.composeVersion)"
exit 0
