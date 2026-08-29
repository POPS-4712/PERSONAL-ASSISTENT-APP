<#
  setup.ps1 - Arranca la fase 1 del asistente (Windows).

  Qué hace:
    1. Localiza Docker Desktop y comprueba que el motor responde.
    2. Crea .env a partir de .env.example si no existe.
    3. Crea config/user_profile.json a partir del ejemplo si no existe.
    4. Levanta postgres + n8n.
    5. Espera a que n8n esté "healthy".
    6. Importa (o actualiza) el workflow de Noticias.

  Es idempotente: puedes ejecutarlo las veces que quieras.
#>

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# --- 1. Docker ---------------------------------------------------------------
$dockerCandidates = @(
  "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin",
  "$env:ProgramFiles\Docker\Docker\resources\bin"
)
foreach ($p in $dockerCandidates) {
  if (Test-Path (Join-Path $p 'docker.exe')) { $env:Path = "$p;$env:Path"; break }
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "No encuentro docker.exe. Abre Docker Desktop una vez y vuelve a ejecutar este script."
}

Write-Host "==> Comprobando el motor de Docker..." -ForegroundColor Cyan
docker info --format '{{.ServerVersion}}' *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host "   El motor no responde. Abriendo Docker Desktop..." -ForegroundColor Yellow
  $dd = Get-ChildItem $dockerCandidates -Filter 'Docker Desktop.exe' -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1
  if (-not $dd) { $dd = Get-Item "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe" -ErrorAction SilentlyContinue }
  if ($dd) { Start-Process $dd.FullName }
  for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep 5
    docker info --format '{{.ServerVersion}}' *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Write-Host "   ...esperando al motor ($($i*5)s)"
  }
  if ($LASTEXITCODE -ne 0) { throw "Docker no arrancó. Ábrelo manualmente y reintenta." }
}
Write-Host "   Motor OK." -ForegroundColor Green

# --- 2/3. Ficheros de configuración ----------------------------------------
if (-not (Test-Path '.env')) {
  Copy-Item '.env.example' '.env'
  Write-Host "==> Creado .env desde .env.example. EDITA .env y pon tus claves reales:" -ForegroundColor Yellow
  Write-Host "      GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID" -ForegroundColor Yellow
  Write-Host "      (POSTGRES_PASSWORD y N8N_ENCRYPTION_KEY: pon cualquier cadena larga aleatoria)" -ForegroundColor Yellow
}
if (-not (Test-Path 'config/user_profile.json')) {
  Copy-Item 'config/user_profile.example.json' 'config/user_profile.json'
  Write-Host "==> Creado config/user_profile.json desde el ejemplo." -ForegroundColor Green
}

# --- 4. Levantar servicios -------------------------------------------------
Write-Host "==> Construyendo imágenes y levantando servicios (postgres, n8n, playwright, profile)..." -ForegroundColor Cyan
docker compose up -d --build

# --- 5. Esperar a n8n ----------------------------------------------------
Write-Host "==> Esperando a que n8n esté listo..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 36; $i++) {
  Start-Sleep 5
  $h = docker inspect --format '{{.State.Health.Status}}' pa-n8n 2>$null
  if ($h -eq 'healthy') { $ok = $true; break }
  Write-Host "   ...n8n: $h ($($i*5)s)"
}
if (-not $ok) { throw "n8n no llegó a 'healthy'. Revisa: docker compose logs n8n" }
Write-Host "   n8n OK." -ForegroundColor Green

# --- 6. Importar workflows ----------------------------------------------
Write-Host "==> Importando workflows..." -ForegroundColor Cyan
docker compose exec -T n8n n8n import:workflow --separate --input=/files/workflows |
  Select-String -NotMatch 'Permissions 0644|Error tracking disabled|too wide|Could not (find|remove)|ActiveWorkflowManager|processTicksAndRejections|at (Import|Command|/usr)'

Write-Host ""
Write-Host "================ LISTO ================" -ForegroundColor Green
Write-Host "n8n (workflows):     http://localhost:5678"
Write-Host "Editor de perfil:    http://localhost:7777"
Write-Host ""
Write-Host "1. Abre n8n y crea la cuenta de propietario (local, no requiere internet)."
Write-Host "2. Rellena tus claves en .env (ver CREDENCIALES.md) y ejecuta: docker compose up -d"
Write-Host "3. Ajusta tu perfil en http://localhost:7777"
Write-Host "4. Prueba cada workflow con 'Execute workflow' y actívalo cuando funcione."
