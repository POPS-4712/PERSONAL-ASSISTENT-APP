<#
.SYNOPSIS
  Habilita WSL2 en Windows. REQUIERE ADMINISTRADOR.

.DESCRIPTION
  Idempotente. Si ya está todo, no hace nada. Si falta:
    1. Habilita 'Microsoft-Windows-Subsystem-Linux'
    2. Habilita 'VirtualMachinePlatform'
    3. wsl --set-default-version 2
    4. Instala una distribución (Ubuntu) si no hay ninguna
  Si Windows necesita reiniciar, sale con código 10 (el llamador registra la
  continuación tras el reinicio). NUNCA deja el proceso a medias sin avisar.

.PARAMETER Distro
  Distribución a instalar si no hay ninguna. Por defecto 'Ubuntu'.
#>
[CmdletBinding()]
param([string]$Distro = 'Ubuntu')

. (Join-Path $PSScriptRoot 'common.ps1')

if (-not (Test-IsAdmin)) {
  Write-ApLog -Level ERROR -Message 'install-wsl.ps1 necesita permisos de administrador.'
  exit 2
}

Write-ApStep 'Configurando WSL2'
$needReboot = $false
$wsl = Get-WslInfo
if ($wsl.ok) {
  Write-ApOk "WSL2 ya funcional (distros v2: $((@($wsl.distros | Where-Object {$_.version -eq 2} | ForEach-Object name)) -join ', '))"
  exit 0
}

# 1 + 2: features
foreach ($feat in @('Microsoft-Windows-Subsystem-Linux','VirtualMachinePlatform')) {
  $state = Get-WindowsFeatureState $feat
  if ($state -eq 'Enabled') { Write-ApOk "$feat ya habilitado"; continue }
  Write-ApLog "   Habilitando $feat ..."
  $r = Enable-WindowsOptionalFeature -Online -FeatureName $feat -NoRestart -ErrorAction Stop
  if ($r.RestartNeeded) { $needReboot = $true }
  Write-ApOk "$feat habilitado"
}

if ($needReboot -or (Test-PendingReboot)) {
  Write-ApWarn 'Windows necesita REINICIAR para activar la virtualización antes de continuar.'
  exit 10
}

# 3: kernel + versión por defecto
try {
  & wsl.exe --update 2>&1 | ForEach-Object { if ("$_".Trim()) { Write-ApLog "   $_" } }
} catch { Write-ApWarn "wsl --update no disponible (se instalará con la distro)." }
try {
  & wsl.exe --set-default-version 2 2>&1 | ForEach-Object { if ("$_".Trim()) { Write-ApLog "   $_" } }
  Write-ApOk 'WSL versión por defecto = 2'
} catch { Write-ApWarn "No se pudo fijar la versión por defecto de WSL: $_" }

# 4: distribución
$wsl = Get-WslInfo
$hasV2 = ($wsl.distros | Where-Object { $_.version -eq 2 }).Count -ge 1
if ($hasV2) {
  Write-ApOk "Distribución WSL2 ya presente: $(($wsl.distros | Where-Object {$_.version -eq 2} | ForEach-Object name) -join ', ')"
} else {
  Write-ApLog "   Instalando distribución '$Distro' (sin lanzar el primer arranque)..."
  # --no-launch evita el prompt de crear usuario; Docker Desktop no lo necesita.
  & wsl.exe --install -d $Distro --no-launch 2>&1 | ForEach-Object { if ("$_".Trim()) { Write-ApLog "   $_" } }
  Start-Sleep 3
  $wsl = Get-WslInfo
  if (($wsl.distros | Where-Object { $_.version -eq 2 }).Count -lt 1) {
    if (Test-PendingReboot) { Write-ApWarn 'La distribución terminará de instalarse tras un reinicio.'; exit 10 }
    Write-ApWarn "La distribución '$Distro' no aparece todavía como v2. Docker Desktop puede usar su propia distro (docker-desktop) igualmente."
  } else {
    Write-ApOk "Distribución '$Distro' instalada (WSL2)"
  }
}

Write-ApOk 'WSL2 listo'
exit 0
