param(
    [int]$Port = 4173
)

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StaticDir = Join-Path $ProjectDir 'static-deploy'
$PidFile = Join-Path $ProjectDir '.local-preview.pid'

if (-not (Test-Path -LiteralPath (Join-Path $StaticDir 'index.html'))) {
    throw "Static build not found: $StaticDir"
}

if (Test-Path -LiteralPath $PidFile) {
    $ExistingPid = [int](Get-Content -LiteralPath $PidFile -Raw)
    if (Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue) {
        Write-Host "VisionBridge local preview is already running: http://127.0.0.1:$Port/"
        exit 0
    }
}

$PythonExe = (Get-Command python -ErrorAction Stop).Source
$Process = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList @('-m', 'http.server', "$Port", '--bind', '127.0.0.1', '--directory', $StaticDir) `
    -WorkingDirectory $ProjectDir `
    -WindowStyle Hidden `
    -PassThru

Set-Content -LiteralPath $PidFile -Value $Process.Id -Encoding ASCII
Start-Sleep -Milliseconds 800

if (-not (Get-Process -Id $Process.Id -ErrorAction SilentlyContinue)) {
    throw 'Local preview process failed to start.'
}

Write-Host "VisionBridge local preview started: http://127.0.0.1:$Port/"
Write-Host 'The page falls back to demo data when the cloud API is unreachable.'
