<#
.SYNOPSIS
  Restaura una copia de seguridad de Automation Center.

.DESCRIPTION
  Por defecto restaura SOLO la base de datos del backend (automation_center),
  los ficheros locales (.env, config/, workflows/) y, si se pide, el volumen de
  n8n. NUNCA hace `DROP DATABASE`: `pg_restore --clean --if-exists` recrea los
  objetos dentro de la BD existente.

  La restauración de la BD de n8n (--RestoreN8nDb) es opcional y peligrosa:
  sustituye workflows/credenciales/ejecuciones de n8n por los del backup.

.PARAMETER Path            Carpeta del backup (la que contiene manifest.json).
.PARAMETER RestoreN8nData  Restaura también el volumen n8n_data.tgz.
.PARAMETER RestoreN8nDb    Restaura también la BD de n8n (n8n.dump). PELIGROSO.
.PARAMETER Yes             No pedir confirmación.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$Path,
  [switch]$RestoreN8nData,
  [switch]$RestoreN8nDb,
  [switch]$Yes
)

. (Join-Path $PSScriptRoot 'common.ps1')
$RepoRoot = Get-RepoRoot

if (-not (Test-Path (Join-Path $Path 'manifest.json'))) {
  Write-ApLog -Level ERROR -Message "No es un backup válido (falta manifest.json): $Path"; exit 2
}
$manifest = Get-Content (Join-Path $Path 'manifest.json') -Raw | ConvertFrom-Json
Write-ApStep "Restaurar backup v$($manifest.version) del $($manifest.createdAt)"

if (-not $Yes) {
  Write-Host 'Esto SOBRESCRIBE la configuración y la BD del backend con el contenido del backup.' -ForegroundColor Yellow
  if ($RestoreN8nDb) { Write-Host 'Y ADEMÁS sobrescribe la BD de n8n (workflows, credenciales, ejecuciones).' -ForegroundColor Red }
  if ((Read-Host 'Escribe "si" para continuar') -ne 'si') { Write-ApLog 'Cancelado.'; exit 0 }
}

$docker = Get-DockerInfo
if (-not $docker.found -or -not $docker.running) { Write-ApLog -Level ERROR -Message 'Docker Desktop no está en marcha.'; exit 2 }
$dq = '"' + $docker.path + '"'
$envMap = Read-ApEnvMap $RepoRoot
$pgUser = if ($envMap.ContainsKey('POSTGRES_USER')) { $envMap['POSTGRES_USER'] } else { 'assistant' }
$pgPass = if ($envMap.ContainsKey('POSTGRES_PASSWORD')) { $envMap['POSTGRES_PASSWORD'] } else { '' }
$n8nDb  = if ($envMap.ContainsKey('POSTGRES_DB')) { $envMap['POSTGRES_DB'] } else { 'assistant' }

# Backup de seguridad ANTES de tocar nada.
Write-ApLog '   Creando un backup de seguridad previo...'
& (Join-Path $PSScriptRoot 'backup.ps1') -Label 'pre-restore' | Out-Null

Write-ApStep 'Parando servicios de aplicación'
Invoke-ApNative "$dq compose stop backend frontend n8n" $RepoRoot | Out-Null
Invoke-ApNative "$dq compose up -d postgres" $RepoRoot | Out-Null
Wait-ContainerHealthy $docker.path 'pa-postgres' 120 | Out-Null

function Restore-Db([string]$Db, [string]$File) {
  if (-not (Test-Path $File)) { Write-ApWarn "No hay dump para $Db; se omite."; return }
  Confirm-AcDatabase -DockerExe $docker.path -Cwd $RepoRoot | Out-Null  # no-op si es n8nDb
  $tmp = "/tmp/ac-restore-$Db.dump"
  Invoke-ApNative "$dq compose cp ""$File"" postgres:$tmp" $RepoRoot | Out-Null
  $cmd = "$dq compose exec -T postgres sh -c ""PGPASSWORD='$pgPass' pg_restore --clean --if-exists --no-owner -U $pgUser -d $Db $tmp"""
  Invoke-ApNative $cmd $RepoRoot | Out-Null
  Invoke-ApNative "$dq compose exec -T postgres rm -f $tmp" $RepoRoot | Out-Null
  Write-ApOk "BD '$Db' restaurada"
}

Restore-Db 'automation_center' (Join-Path $Path 'automation_center.dump')
if ($RestoreN8nDb) { Restore-Db $n8nDb (Join-Path $Path 'n8n.dump') }

if ($RestoreN8nData -and (Test-Path (Join-Path $Path 'n8n_data.tgz'))) {
  Write-ApStep 'Restaurando volumen n8n_data'
  Invoke-ApNative "$dq compose stop n8n" $RepoRoot | Out-Null
  $q = "$dq run --rm --volumes-from pa-n8n -v ""$Path"":/backup alpine sh -c ""rm -rf /home/node/.n8n/* && tar xzf /backup/n8n_data.tgz -C /home/node/.n8n"""
  Invoke-ApNative $q $RepoRoot | Out-Null
  Write-ApOk 'n8n_data restaurado'
}

# Ficheros locales
if (Test-Path (Join-Path $Path 'env'))       { Copy-Item (Join-Path $Path 'env') (Join-Path $RepoRoot '.env') -Force; Write-ApOk '.env restaurado' }
if (Test-Path (Join-Path $Path 'config'))    { Copy-Item (Join-Path $Path 'config\*')    (Join-Path $RepoRoot 'config')    -Recurse -Force; Write-ApOk 'config/ restaurado' }
if (Test-Path (Join-Path $Path 'workflows')) { Copy-Item (Join-Path $Path 'workflows\*') (Join-Path $RepoRoot 'workflows') -Recurse -Force; Write-ApOk 'workflows/ restaurados' }

Write-ApStep 'Levantando servicios'
Invoke-ApNative "$dq compose up -d" $RepoRoot | Out-Null
foreach ($c in $script:AP_CONTAINERS) { Wait-ContainerHealthy $docker.path $c 200 | Out-Null }

$wf = Get-N8nWorkflowCount -DockerExe $docker.path -Cwd $RepoRoot
Write-Host ''
Write-ApLog -Level OK -Message "Restauración completa. workflow_entity = $wf"
exit 0
