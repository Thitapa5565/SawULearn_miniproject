param([switch]$WebOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 including the Python launcher, then run setup.ps1 again.' }
}
$requirementsFile = if ($WebOnly) { 'requirements.txt' } else { 'requirements-notebooks.txt' }
& ./.venv/Scripts/python.exe -m pip install -r $requirementsFile
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the pip output.' }
& ./.venv/Scripts/python.exe scripts/check_install.py
if ($LASTEXITCODE -ne 0) { throw 'Installation check failed.' }
Write-Host 'Ready. Start: powershell -ExecutionPolicy Bypass -File web_app/start.ps1'
