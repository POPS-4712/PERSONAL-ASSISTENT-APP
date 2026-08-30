<#
  setup.ps1 - alias histórico. El instalador vive ahora en installer/install.ps1.
  Se conserva para no romper enlaces/documentación antiguos.
#>
[CmdletBinding()]
param()
$installer = Join-Path (Split-Path -Parent $PSScriptRoot) 'installer\install.ps1'
Write-Host "scripts/setup.ps1 -> installer/install.ps1" -ForegroundColor DarkGray
& $installer @args
exit $LASTEXITCODE
