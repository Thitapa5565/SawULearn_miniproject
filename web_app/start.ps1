$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run setup.ps1 first.' }
Set-Location -LiteralPath $projectRoot
Write-Host 'SawULearn: http://127.0.0.1:8000/#practice (Ctrl+C to stop)'
& $pythonPath -m uvicorn web_app.backend.app:app --host 127.0.0.1 --port 8000
