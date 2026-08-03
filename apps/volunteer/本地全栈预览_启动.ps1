$ErrorActionPreference = 'Stop'

$AppDir = $PSScriptRoot
$AppsDir = Split-Path -Parent $AppDir
$RepoDir = Split-Path -Parent $AppsDir
$ApiDir = Join-Path $RepoDir 'services\api'
$PidFile = Join-Path $AppDir '.fullstack-preview.pid'
$OutLog = Join-Path $AppDir '.fullstack-preview.out.log'
$ErrLog = Join-Path $AppDir '.fullstack-preview.err.log'

if (Test-Path -LiteralPath $PidFile) {
    $ExistingPid = [int](Get-Content -LiteralPath $PidFile -Encoding ASCII)
    if (Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue) {
        Write-Output 'VisionBridge preview is already running.'
        Write-Output 'Dashboard: http://127.0.0.1:8000/'
        Write-Output 'Volunteer: http://127.0.0.1:8000/volunteer/'
        exit 0
    }
}

$PortCheck = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($PortCheck) { throw 'Port 8000 is already in use.' }

$env:VISIONBRIDGE_DATA_DIR = Join-Path $ApiDir 'data-local-preview'
$env:VISIONBRIDGE_EMAIL_DEBUG = '1'
$env:VISIONBRIDGE_SERVE_STATIC = '1'
$env:VISIONBRIDGE_SEED_DEMO_DATA = '1'
$env:VISIONBRIDGE_AUTH_SECRET = [System.Guid]::NewGuid().ToString('N')
$env:VISIONBRIDGE_INGEST_TOKEN = [System.Guid]::NewGuid().ToString('N')

$Python = (Get-Command python.exe).Source
$Process = Start-Process -FilePath $Python -ArgumentList @('-m','uvicorn','services.api.app:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $RepoDir -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -WindowStyle Hidden -PassThru
Set-Content -LiteralPath $PidFile -Value $Process.Id -Encoding ASCII

Start-Sleep -Milliseconds 1200
$Health = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 5
if ($Health.StatusCode -ne 200) { throw 'VisionBridge local API did not become ready.' }

Write-Output 'VisionBridge full-stack preview started.'
Write-Output 'Dashboard: http://127.0.0.1:8000/'
Write-Output 'Volunteer: http://127.0.0.1:8000/volunteer/'
Write-Output 'Local email debug mode is enabled; the verification code is filled automatically.'
