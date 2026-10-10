param(
    [Parameter(Mandatory=$true)][string]$HostIP,
    [int]$HttpsPort=8443,
    [int]$SetupPort=8002
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$pythonPath=Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run setup.ps1 first.' }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'dist\index.html'))) { throw 'Build the frontend first.' }
Set-Location -LiteralPath $projectRoot
& $pythonPath -m web_app.backend.local_https --host $HostIP --https-port $HttpsPort --setup-port $SetupPort
