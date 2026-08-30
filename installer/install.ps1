<#
.SYNOPSIS
  Instalador de Automation Platform para Windows (x64 / ARM64).

.DESCRIPTION
  DESCARGAR -> EJECUTAR -> INSTALACIÓN AUTOMÁTICA -> READY.
  Detecta la plataforma, comprueba Docker, genera .env, ajusta puertos,
  construye y levanta los servicios, importa los workflows, ejecuta health
  checks reales y registra el arranque automático.

  Idempotente (re-ejecutar no duplica nada) y reanudable (guarda el estado
  en %LOCALAPPDATA%\AutomationPlatform\state.json).

.PARAMETER Unattended
  No hace preguntas. Los secretos se toman de variables de entorno o de -ConfigFile.

.PARAMETER ConfigFile
  Ruta a un JSON con los secretos: { "GEMINI_API_KEY": "...", "TELEGRAM_CHAT_ID": "...", ... }

.PARAMETER Reconfigure
  Regenera .env aunque ya exista (conserva las claves internas si puede).

.PARAMETER Force
  Ignora el estado guardado y ejecuta todos los pasos desde el principio.

.PARAMETER SkipBrowser
  No abre el navegador al terminar.
#>
[CmdletBinding()]
param(
  [switch] $Unattended,
  [string] $ConfigFile,
  [switch] $Reconfigure,
  [switch] $Force,
  [switch] $SkipBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'lib.ps1')

$Version = (Get-Content (Join-Path $RepoRoot 'VERSION') -Raw).Trim()

# Secretos que consume el stack. internal=lo genera el instalador.
$SecretSpec = @(
  @{ key='POSTGRES_PASSWORD';      internal=$true  }
  @{ key='N8N_ENCRYPTION_KEY';     internal=$true  }
  @{ key='GEMINI_API_KEY';         internal=$false; hint='API key de Google AI Studio (https://aistudio.google.com/app/apikey)' }
  @{ key='TELEGRAM_CHAT_ID';       internal=$false; hint='Tu chat id de Telegram (bot <token>/getUpdates)' }
  @{ key='TELEGRAM_NOTICIAS_TOKEN';internal=$false; hint='Token del bot de Noticias (@BotFather)' }
  @{ key='TELEGRAM_TOKEN_MARCA';   internal=$false; hint='Token del bot de Marca Personal' }
  @{ key='TELEGRAM_TOKEN_LABORAL'; internal=$false; hint='Token del bot de Laboral' }
  @{ key='TELEGRAM_TOKEN_EMAIL';   internal=$false; hint='Token del bot de Email' }
)

function New-RandomSecret([int]$Len = 48) {
  -join ((48..57) + (65..90) + (97..122) | Get-Random -Count $Len | ForEach-Object { [char]$_ })
}

function Read-EnvFile([string]$Path) {
  $h = @{}
  if (Test-Path $Path) {
    foreach ($l in Get-Content $Path) {
      if ($l -match '^\s*#') { continue }
      if ($l -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') { $h[$Matches[1]] = $Matches[2] }
    }
  }
  return $h
}

function Write-EnvFile([string]$Path, [hashtable]$Values) {
  $order = @(
    'POSTGRES_DB','POSTGRES_USER','POSTGRES_PASSWORD','POSTGRES_PORT','',
    'N8N_PORT','N8N_HOST','WEBHOOK_URL','N8N_LOG_LEVEL','N8N_ENCRYPTION_KEY','',
    'PROFILE_PORT','','TZ','',
    'GEMINI_API_KEY','GEMINI_MODEL','',
    'TELEGRAM_CHAT_ID','TELEGRAM_NOTICIAS_TOKEN','TELEGRAM_TOKEN_MARCA','TELEGRAM_TOKEN_LABORAL','TELEGRAM_TOKEN_EMAIL'
  )
  $lines = New-Object System.Collections.Generic.List[string]
  $lines.Add('# Generado por installer/install.ps1 - NO subir a git (.gitignore).')
  foreach ($k in $order) {
    if ($k -eq '') { $lines.Add(''); continue }
    if ($Values.ContainsKey($k)) { $lines.Add("$k=$($Values[$k])") }
  }
  foreach ($k in $Values.Keys) {
    if ($order -notcontains $k) { $lines.Add("$k=$($Values[$k])") }
  }
  Set-Content -Path $Path -Value ($lines -join "`n") -Encoding utf8 -NoNewline
}

# ==========================================================================
Write-Host ''
Write-ApLog -Level STEP -Message "Automation Platform installer v$Version"
Initialize-ApHome

$state = Get-ApState
$resume = ($state.step -and -not $Force)
if ($resume) { Write-ApWarn "Reanudando: último paso completado = '$($state.step)'" }

# --- 1. DETECTING -------------------------------------------------------
Set-ApState 'detecting'
Write-ApStep 'Detectando plataforma'
$plat = Get-ApPlatform
Write-ApLog "   OS=$($plat.os) $($plat.osVersion)  arch=$($plat.arch)  RAM=$($plat.ramGB)GB  discoLibre=$($plat.diskFreeGB)GB  admin=$($plat.admin)  online=$($plat.online)"
if (-not $plat.supported) { throw "Arquitectura no soportada: $($plat.arch). Solo x64 y ARM64." }
if ($plat.ramGB -lt 3)      { Write-ApWarn "RAM baja ($($plat.ramGB)GB). Recomendado >= 4GB." }
if ($plat.diskFreeGB -lt 5) { throw "Espacio insuficiente en disco ($($plat.diskFreeGB)GB). Se necesitan >= 5GB." }
if (-not $plat.online)      { Write-ApWarn 'Sin conectividad detectada: la primera build necesita descargar imágenes.' }
Write-ApOk 'Plataforma OK'

# --- 2. DEPENDENCIES --------------------------------------------------
Set-ApState 'dependencies'
Write-ApStep 'Comprobando Docker'
$docker = Get-DockerInfo
if (-not $docker.found) {
  Write-ApLog -Level ERROR -Message 'Docker no está instalado.'
  Write-ApLog -Level ERROR -Message 'BLOCKED BY: instala Docker Desktop desde https://www.docker.com/products/docker-desktop/ y vuelve a ejecutar este instalador.'
  exit 2
}
if (-not $docker.running) {
  if (-not (Start-DockerDesktop)) {
    Write-ApLog -Level ERROR -Message 'BLOCKED BY: Docker Desktop no arrancó. Ábrelo manualmente y reintenta.'
    exit 2
  }
  $docker = Get-DockerInfo
}
$DockerExe = $docker.path
Write-ApOk "Docker $($docker.serverVersion)  ·  Compose $($docker.composeVersion)"
if (-not $docker.composeVersion) { throw 'Docker Compose v2 no disponible (se necesita `docker compose`).' }

# --- 3. DIRECTORIES -------------------------------------------------
Set-ApState 'directories'
Write-ApStep 'Preparando directorios'
foreach ($d in @('config','output\marca-personal')) {
  $p = Join-Path $RepoRoot $d
  if (-not (Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null }
}
if (-not (Test-Path (Join-Path $RepoRoot 'config\user_profile.json'))) {
  Copy-Item (Join-Path $RepoRoot 'config\user_profile.example.json') (Join-Path $RepoRoot 'config\user_profile.json')
  Write-ApOk 'config/user_profile.json creado desde el ejemplo'
}
Write-ApOk 'Directorios OK'

# --- 4. CONFIGURING (.env) ----------------------------------------
Set-ApState 'configuring'
Write-ApStep 'Configurando .env'
$envPath = Join-Path $RepoRoot '.env'
$env = Read-EnvFile $envPath
$fromConfig = @{}
if ($ConfigFile) {
  if (-not (Test-Path $ConfigFile)) { throw "ConfigFile no encontrado: $ConfigFile" }
  (Get-Content $ConfigFile -Raw | ConvertFrom-Json).psobject.Properties | ForEach-Object { $fromConfig[$_.Name] = "$($_.Value)" }
}

$needEnv = ((-not (Test-Path $envPath)) -or $Reconfigure)
if ($needEnv) {
  # valores base
  if (-not $env.ContainsKey('POSTGRES_DB'))   { $env['POSTGRES_DB'] = 'assistant' }
  if (-not $env.ContainsKey('POSTGRES_USER')) { $env['POSTGRES_USER'] = 'assistant' }
  if (-not $env.ContainsKey('N8N_HOST'))      { $env['N8N_HOST'] = 'localhost' }
  if (-not $env.ContainsKey('N8N_LOG_LEVEL')) { $env['N8N_LOG_LEVEL'] = 'info' }
  if (-not $env.ContainsKey('GEMINI_MODEL'))  { $env['GEMINI_MODEL'] = 'gemini-3.6-flash' }
  if (-not $env.ContainsKey('TZ'))            { $env['TZ'] = 'Europe/Madrid' }

  $missing = @()
  foreach ($spec in $SecretSpec) {
    $k = $spec.key
    if ($env.ContainsKey($k) -and $env[$k] -and $env[$k] -notmatch 'CAMBIA|PEGA_AQUI|PLACEHOLDER') { continue }
    if ($spec.internal) { $env[$k] = New-RandomSecret; continue }
    $val = $null
    $fromEnvVar = [Environment]::GetEnvironmentVariable($k)
    if     ($fromConfig.ContainsKey($k)) { $val = $fromConfig[$k] }
    elseif ($fromEnvVar)                 { $val = $fromEnvVar }
    elseif (-not $Unattended) {
      Write-Host "   $k  —  $($spec.hint)" -ForegroundColor DarkGray
      $val = Read-Host "   $k (Enter para dejarlo pendiente)"
    }
    if ($val) { $env[$k] = $val } else { $env[$k] = ''; $missing += $k }
  }
  Write-EnvFile $envPath $env
  Write-ApOk '.env escrito'
  if ($missing.Count) {
    foreach ($m in $missing) { Write-ApLog -Level WARN -Message "BLOCKED BY: falta $m — el stack arrancará, pero el workflow que lo usa no funcionará hasta rellenarlo en .env (ver CREDENCIALES.md)." }
  }
} else {
  Write-ApOk '.env ya existe (usa -Reconfigure para regenerarlo)'
}

# --- 5. PORTS --------------------------------------------------------
Set-ApState 'ports'
Write-ApStep 'Comprobando puertos'
$env = Read-EnvFile $envPath
$n8nWant     = [int]($(if ($env.ContainsKey('N8N_PORT'))     { $env['N8N_PORT'] }     else { 5678 }))
$profileWant = [int]($(if ($env.ContainsKey('PROFILE_PORT')) { $env['PROFILE_PORT'] } else { 7777 }))
# ¿ya es nuestra instalación la que ocupa ese puerto?
$n8nRunningHere = Test-ApContainerRunning $DockerExe 'pa-n8n'
$n8nPort     = if ($n8nRunningHere) { $n8nWant } else { Get-FreePort $n8nWant }
$profilePort = if ($n8nRunningHere) { $profileWant } else { Get-FreePort $profileWant }
if ("$n8nPort" -ne "$($env['N8N_PORT'])" -or "$profilePort" -ne "$($env['PROFILE_PORT'])") {
  $env['N8N_PORT'] = "$n8nPort"; $env['PROFILE_PORT'] = "$profilePort"
  $env['WEBHOOK_URL'] = "http://localhost:$n8nPort/"
  Write-EnvFile $envPath $env
}
if ($n8nPort -ne $n8nWant)         { Write-ApWarn "Puerto $n8nWant ocupado -> n8n usará $n8nPort" }
if ($profilePort -ne $profileWant) { Write-ApWarn "Puerto $profileWant ocupado -> profile usará $profilePort" }
Write-ApOk "n8n:$n8nPort  profile:$profilePort"

$dq = '"' + $DockerExe + '"'

# --- 6. BUILDING ----------------------------------------------------
Set-ApState 'building'
Write-ApStep 'Construyendo imágenes (puede tardar la primera vez)'
if ((Invoke-ApNative "$dq compose build" $RepoRoot) -ne 0) { throw 'docker compose build falló' }
Write-ApOk 'Imágenes construidas'

# --- 7. STARTING SERVICES ----------------------------------------
Set-ApState 'starting-services'
Write-ApStep 'Levantando servicios'
if ((Invoke-ApNative "$dq compose up -d" $RepoRoot) -ne 0) { throw 'docker compose up falló' }
foreach ($c in @('pa-postgres','pa-playwright','pa-profile','pa-n8n')) {
  if (Wait-ContainerHealthy $DockerExe $c 200) { Write-ApOk "$c healthy" }
  else { throw "$c no llegó a healthy. Revisa: docker compose logs $c" }
}

# --- 8. IMPORTING WORKFLOWS -------------------------------------
Set-ApState 'importing-workflows'
Write-ApStep 'Importando workflows'
Invoke-ApNative "$dq compose exec -T n8n n8n import:workflow --separate --input=/files/workflows" $RepoRoot | Out-Null
Write-ApOk 'Workflows importados'

# --- 9. HEALTH CHECK ------------------------------------------------
Set-ApState 'health-check'
Write-ApStep 'Health checks'
$hc = Invoke-ApHealthChecks -DockerExe $DockerExe -N8nPort $n8nPort -ProfilePort $profilePort -Cwd $RepoRoot
$allOk = $true
foreach ($k in $hc.Keys) {
  $ok = $hc[$k]
  if ($ok) { Write-ApOk "$k = OK" } else { Write-ApLog -Level ERROR -Message "$k = FALLO"; $allOk = $false }
}

# --- Autostart: arranca el stack al iniciar sesión --------------
Write-ApStep 'Registrando arranque automático'
$taskName = 'AutomationPlatform'
$autostart = $false
try {
  $action   = New-ScheduledTaskAction -Execute $DockerExe -Argument 'compose up -d' -WorkingDirectory $RepoRoot
  $trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force -ErrorAction Stop | Out-Null
  $autostart = $true
} catch {
  # fallback: schtasks.exe (más permisivo con usuarios sin privilegios)
  try {
    $tr = '"' + $DockerExe + '" compose up -d'
    & schtasks.exe /Create /TN $taskName /TR "cmd /c cd /d `"$RepoRoot`" ^&^& $tr" /SC ONLOGON /RL LIMITED /F 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $autostart = $true }
  } catch { }
}
if ($autostart) { Write-ApOk "Arranque automático registrado (tarea '$taskName')" }
else {
  Write-ApWarn "No se pudo registrar el arranque automático (permisos). El stack seguirá vivo por 'restart: unless-stopped' de Docker mientras Docker Desktop arranque solo."
}

# --- 10. READY ----------------------------------------------------
if (-not $allOk) {
  Set-ApState 'health-check'
  Write-ApLog -Level ERROR -Message 'FINAL STATUS: BLOCKED — algún health check falló. Revisa install.log y `docker compose logs`.'
  exit 1
}
Set-ApState 'ready'
Write-Host ''
Write-ApLog -Level OK -Message '================  READY  ================'
Write-ApLog -Level OK -Message "n8n (workflows):   http://localhost:$n8nPort"
Write-ApLog -Level OK -Message "Editor de perfil:  http://localhost:$profilePort"
Write-ApLog -Level OK -Message "Log:               $script:AP_LOG"
Write-Host ''
Write-ApLog "Siguiente: abre n8n, crea la cuenta de propietario (local) y prueba cada workflow."
if (-not $SkipBrowser) {
  Start-Process "http://localhost:$n8nPort"
  Start-Process "http://localhost:$profilePort"
}
exit 0
